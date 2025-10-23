# agents/company_analyzer.py
"""
Company_Analyzer Agent
LangGraph 노드 함수들로 구성
"""
from typing import Dict, Any
from state import AgentState
from services.ingest import fetch_company_sources, normalize_records
from services import rag


def collect_company_docs(state: AgentState) -> Dict[str, Any]:
    """
    벤치마크 기업에 대한 IR/공시/보도자료 수집 노드
    """
    print(f"[Company_Analyzer] collect_company_docs - benchmarks: {state.get('benchmarks', [])}")

    docs = normalize_records(
        fetch_company_sources(
            state.get("benchmarks", []),
            state.get("period", "last_90d"),
            state.get("regions", []),
            state.get("snapshot_date"),
        )
    )

    return {"raw_docs": docs}


def index_company_docs(state: AgentState) -> Dict[str, Any]:
    """
    회사 관련 raw_docs를 인메모리 RAG 인덱스로 구축하는 노드
    """
    print(f"[Company_Analyzer] index_company_docs - docs count: {len(state.get('raw_docs', []))}")

    # 간단히 전체 raw_docs를 한 인덱스로 구축(실전에서는 회사별 분리 가능)
    company_index = rag.build_index(state.get("raw_docs", []))

    # 기존 호환용 id 등록
    new_ids = [f"ir-{i}" for i, _ in enumerate(state.get("raw_docs", []))]

    return {
        "_company_index": company_index,
        "indexed_ids": new_ids
    }


def compose_company_dossiers(state: AgentState) -> Dict[str, Any]:
    """
    LLM으로 기업 정보 요약 및 도시에 작성
    """
    print(f"[Company_Analyzer] compose_company_dossiers")

    from services.llm import summarize_company_info

    idx = state.get("_company_index")
    dossiers = []
    start_n = state.get("_global_ref_counter", 10)  # 전역 카운터 사용

    for tk in state.get("benchmarks", []):
        # 회사별 쿼리(간단 키워드 기반)
        biz_passages = rag.query(
            idx,
            f"{tk} business strategy pricing margin",
            filters={"company": [tk]},
            top_k=4
        )
        risk_passages = rag.query(
            idx,
            f"{tk} risk regulation subsidy supply chain",
            filters={"company": [tk]},
            top_k=4
        )
        roadmap_passages = rag.query(
            idx,
            f"{tk} roadmap model pipeline capacity expansion",
            filters={"company": [tk]},
            top_k=4
        )

        # LLM으로 실제 요약 (referenced_docs 포함)
        business_result = summarize_company_info(tk, biz_passages, "business")
        risks_result = summarize_company_info(tk, risk_passages, "risk")
        roadmap_result = summarize_company_info(tk, roadmap_passages, "roadmap")

        # LLM 응답에서 points와 referenced_docs 추출
        business_points = business_result.get("points", []) if isinstance(business_result, dict) else business_result
        business_refs = business_result.get("referenced_docs", []) if isinstance(business_result, dict) else []

        risks_points = risks_result.get("points", []) if isinstance(risks_result, dict) else risks_result
        risks_refs = risks_result.get("referenced_docs", []) if isinstance(risks_result, dict) else []

        roadmap_points = roadmap_result.get("points", []) if isinstance(roadmap_result, dict) else roadmap_result
        roadmap_refs = roadmap_result.get("referenced_docs", []) if isinstance(roadmap_result, dict) else []

        # evidence 맵 생성: LLM이 참조한 문서만 포함
        ev = []

        # business 섹션의 참조 문서
        for doc_num in business_refs:
            doc_idx = doc_num - 1
            if 0 <= doc_idx < len(biz_passages):
                doc = biz_passages[doc_idx]
                ev.append({
                    "n": start_n + len(ev),
                    "title": doc.get("title", "Untitled"),
                    "url": doc.get("url", "N/A"),
                    "date": doc.get("date", state.get("snapshot_date", "N/A"))
                })

        # risk 섹션의 참조 문서
        for doc_num in risks_refs:
            doc_idx = doc_num - 1
            if 0 <= doc_idx < len(risk_passages):
                doc = risk_passages[doc_idx]
                ev.append({
                    "n": start_n + len(ev),
                    "title": doc.get("title", "Untitled"),
                    "url": doc.get("url", "N/A"),
                    "date": doc.get("date", state.get("snapshot_date", "N/A"))
                })

        # roadmap 섹션의 참조 문서
        for doc_num in roadmap_refs:
            doc_idx = doc_num - 1
            if 0 <= doc_idx < len(roadmap_passages):
                doc = roadmap_passages[doc_idx]
                ev.append({
                    "n": start_n + len(ev),
                    "title": doc.get("title", "Untitled"),
                    "url": doc.get("url", "N/A"),
                    "date": doc.get("date", state.get("snapshot_date", "N/A"))
                })

        dossiers.append({
            "ticker": tk,
            "name": tk,
            "business_highlights": business_points,
            "risk_factors": risks_points,
            "roadmap": roadmap_points,
            "evidence": ev,
        })

        # 다음 회사를 위해 start_n 업데이트
        start_n += len(ev)

    # 전역 카운터 업데이트
    return {
        "company_dossiers": dossiers,
        "_global_ref_counter": start_n
    }


def validate_citations_company(state: AgentState) -> Dict[str, Any]:
    """
    company_dossiers[].evidence를 evidence_map으로 병합하는 노드
    """
    print(f"[Company_Analyzer] validate_citations_company")

    evidence_entries = []
    for d in state.get("company_dossiers", []):
        for e in d.get("evidence", []):
            evidence_entries.append({
                "section": "company",
                "n": e["n"],
                "title": e["title"],
                "url": e["url"],
                "date": e["date"],
                "ticker": d["ticker"],
            })

    return {"evidence_map": evidence_entries}
