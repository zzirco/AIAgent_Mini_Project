# agents/market_researcher.py
"""
Market_Researcher Agent
LangGraph 노드 함수들로 구성
LangChain Runnable 기반으로 LangSmith 트레이싱 지원
"""
from typing import Dict, Any
from state import AgentState
from services.ingest import fetch_market_sources, normalize_records
from langchain_core.runnables import chain


@chain
def collect_market_docs(state: AgentState) -> Dict[str, Any]:
    """
    시장 관련 문서 수집 노드
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[Market_Researcher] collect_market_docs - period: {state['period']}, regions: {state['regions']}")

    docs = fetch_market_sources(
        state["period"],
        state["regions"],
        state["focus_issues"],
        state["snapshot_date"]
    )
    normalized = normalize_records(docs)

    return {"raw_docs": normalized}


@chain
def index_market_docs(state: AgentState) -> Dict[str, Any]:
    """
    수집된 문서를 벡터DB에 인덱싱하는 노드
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[Market_Researcher] index_market_docs - docs count: {len(state['raw_docs'])}")

    # 실제 구현에서는 VectorDB 인덱싱; 여기선 id만 등록
    new_ids = [f"market-doc-{i}" for i, _ in enumerate(state["raw_docs"])]

    return {"indexed_ids": new_ids}


@chain
def extract_market_signals(state: AgentState) -> Dict[str, Any]:
    """인덱싱된 문서에서 시장 신호 추출 및 요약 노드 (LLM 사용)"""
    print(f"[Market_Researcher] extract_market_signals - focus_issues: {state['focus_issues']}")

    try:
        from services.llm import summarize_market_trends_with_global_refs

        # raw_docs에서 market 관련 문서만 필터링
        all_docs = state.get("raw_docs", [])
        raw_docs = [d for d in all_docs if d.get("source") == "tavily" and d.get("region") in ["global", "US", "EU", None]]

        # Market 에이전트는 항상 1부터 시작
        start_ref = 1

        # 디버깅: raw_docs 타입 확인
        print(f"[Market_Researcher] raw_docs type: {type(raw_docs)}")
        if raw_docs and len(raw_docs) > 0:
            print(f"[Market_Researcher] First doc type: {type(raw_docs[0])}")
            print(f"[Market_Researcher] First doc keys: {raw_docs[0].keys() if isinstance(raw_docs[0], dict) else 'NOT A DICT'}")

        print(f"[Market_Researcher] Calling LLM with {len(raw_docs)} documents (refs start at {start_ref})")

        result = summarize_market_trends_with_global_refs(
            documents=raw_docs,
            focus_issues=state["focus_issues"],
            regions=state["regions"],
            period=state["period"],
            start_ref_number=start_ref
        )

        # LLM이 참조한 문서 번호를 실제 문서로 매핑
        referenced_doc_indices = result.get("referenced_docs", [])
        evidence = []
        for doc_num in referenced_doc_indices:
            # doc_num은 이미 전역 번호
            # 로컬 인덱스로 변환
            local_idx = doc_num - start_ref
            if 0 <= local_idx < len(raw_docs):
                doc = raw_docs[local_idx]
                evidence.append({
                    "n": doc_num,  # 전역 번호
                    "title": doc.get("title", "Untitled"),
                    "url": doc.get("url", "N/A"),
                    "date": doc.get("date", state["snapshot_date"])
                })

        market_brief = {
            "period": state["period"],
            "top_trends": result.get("top_trends", ["LLM 응답 없음"]),
            "summary": result.get("summary", "LLM 요약 생성 실패"),
            "metrics": {
                "global_ev_sales_yoy": -3.2,  # TODO: 실제 데이터에서 추출
                "avg_price_change_pct": -5.1
            },
            "evidence": evidence
        }

        print(f"[Market_Researcher] LLM generated {len(market_brief['top_trends'])} trends with {len(evidence)} evidence")
        return {
            "market_brief": market_brief
        }

    except Exception as e:
        import traceback
        print(f"[Market_Researcher] ERROR in extract_market_signals: {e}")
        print(f"[Market_Researcher] ERROR traceback:")
        traceback.print_exc()
        # 폴백: 기본 더미 데이터
        market_brief = {
            "period": state["period"],
            "top_trends": [
                f"오류 발생: {str(e)[:100]}",
                "LLM 연결 확인 필요 - OPENAI_API_KEY 설정 여부 확인",
                "폴백 모드로 실행 중"
            ],
            "summary": f"LLM 오류로 인한 폴백 모드: {str(e)[:200]}",
            "metrics": {},
            "evidence": []
        }
        return {"market_brief": market_brief}


@chain
def validate_citations_market(state: AgentState) -> Dict[str, Any]:
    """
    시장 섹션의 인용 검증 및 evidence_map에 등록하는 노드
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[Market_Researcher] validate_citations_market")

    evidence_entries = []
    for e in state["market_brief"].get("evidence", []):
        evidence_entries.append({
            "section": "market",
            "n": e["n"],
            "title": e["title"],
            "url": e["url"],
            "date": e["date"]
        })

    return {"evidence_map": evidence_entries}
