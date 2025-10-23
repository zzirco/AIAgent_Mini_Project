# state.py
from typing import TypedDict, List, Dict, Any, Annotated
from operator import add


class AgentState(TypedDict):
    """
    EV Market Trend Analysis Agent의 공통 State 스키마
    LangGraph의 TypedDict 기반 State 정의
    """
    # ===== A) 구성/제어 State (Supervisor가 생성 → 각 에이전트가 참조) =====
    run_id: str
    period: str
    regions: List[str]
    focus_issues: List[str]
    segments: List[str]
    depth: str
    snapshot_date: str
    output: Dict[str, Any]
    constraints: Dict[str, Any]
    benchmarks: List[str]
    policies: List[str]
    financials: Dict[str, Any]
    data_prefs: Dict[str, Any]
    risk_lens: Dict[str, float]
    cadence: Dict[str, str]
    persona: str

    # ===== B) 콘텐츠/산출물 State =====
    # Annotated를 사용하여 리스트 병합 연산자 지정
    raw_docs: Annotated[List[Dict[str, Any]], add]
    indexed_ids: Annotated[List[str], add]
    market_brief: Dict[str, Any]
    company_dossiers: List[Dict[str, Any]]
    stock_snapshots: List[Dict[str, Any]]
    charts: Annotated[List[Dict[str, Any]], add]
    evidence_map: Annotated[List[Dict[str, Any]], add]
    draft_report_md: str
    report_path: str

    # ===== C) 품질/메타/오류 State =====
    qa_metrics: Dict[str, Any]
    errors: Annotated[List[Dict[str, Any]], add]

    # QA 관련 개별 필드 (병합 방지)
    _qa_citation_coverage: float
    _qa_number_consistency: bool
    _qa_document_ok: bool

    # ===== 내부 캐시 (에이전트 간 전달용) =====
    _chart_specs: List[Dict[str, Any]]
    _outline: List[str]
    _company_index: Any
    _series: Dict[str, Any]
    _funds: Dict[str, Any]
    _global_ref_counter: int  # 전역 참조 번호 카운터 (각 에이전트가 증가시킴)
