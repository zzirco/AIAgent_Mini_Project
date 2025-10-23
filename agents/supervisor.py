# agents/supervisor.py
"""
Supervisor Agent
LangGraph 노드 및 조건부 라우팅 함수들로 구성
LangChain Runnable 기반으로 LangSmith 트레이싱 지원
"""
from typing import Dict, Any, Literal
from state import AgentState
from langchain_core.runnables import chain


@chain
def parse_request(state: AgentState) -> Dict[str, Any]:
    """
    사용자 입력 파싱 및 초기화 노드
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[Supervisor] parse_request - run_id: {state['run_id']}")

    # QA metrics 초기화
    qa_metrics = {
        "citation_coverage": 0.0,
        "number_consistency": True,
        "document_ok": False
    }

    return {
        "qa_metrics": qa_metrics
    }


@chain
def merge_artifacts(state: AgentState) -> Dict[str, Any]:
    """
    각 에이전트의 결과물을 병합하는 노드
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[Supervisor] merge_artifacts")

    mb = state.get("market_brief", {})
    cds = state.get("company_dossiers", [])
    ss = state.get("stock_snapshots", [])

    draft = [
        "# SUMMARY\n",
        mb.get("summary", "(요약 준비중)"),
        "\n\n# 시장 개요\n",
        "\n".join(mb.get("top_trends", [])),
        "\n\n# 기업 하이라이트\n",
        "\n".join([c.get("name", "?") + ": " + "; ".join(c.get("business_highlights", [])) for c in cds]),
        "\n\n# 주식/재무 스냅샷\n",
        "\n".join([f"{s['ticker']}: return={s['period_return_pct']}%, vol={s['volatility']}" for s in ss]),
    ]

    return {"draft_report_md": "\n".join(draft)}


@chain
def qa_gate(state: AgentState) -> Dict[str, Any]:
    """
    품질 검증 게이트 노드 - 모든 QA 정보를 통합
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[Supervisor] qa_gate")

    ev_n = max(1, len(state.get("evidence_map", [])))
    # SUMMARY·시장·기업·주가 최소 합산 근거 6개 권장
    cov = min(1.0, ev_n / max(6, ev_n))

    # 개별 필드에서 수집한 QA 정보를 통합
    qa_metrics = {
        "citation_coverage": cov,
        "number_consistency": state.get("_qa_number_consistency", True),
        "document_ok": state.get("_qa_document_ok", False)
    }

    return {"qa_metrics": qa_metrics}


def should_continue(state: AgentState) -> Literal["continue", "end"]:
    """
    워크플로우 계속 여부를 결정하는 조건부 엣지 함수
    """
    # 간단한 조건: report_path가 있으면 종료
    if state.get("report_path"):
        return "end"
    return "continue"
