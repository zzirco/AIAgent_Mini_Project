# workflow.py
"""
LangGraph 기반 EV Market Trend Analysis Workflow
병렬 실행을 지원하는 Multi-Agent 워크플로우
"""
from langgraph.graph import StateGraph, END
from state import AgentState

# Import all agent nodes
from agents import supervisor
from agents import market_researcher
from agents import company_analyzer
from agents import stock_analyzer
from agents import chart_generator
from compiler import report_compiler


def create_workflow() -> StateGraph:
    """
    LangGraph StateGraph를 생성하고 노드/엣지를 구성합니다.

    아키텍처:
    1. parse_request (Supervisor)
    2. 병렬 실행:
       - Market_Researcher: collect → index → extract → validate
       - Company_Analyzer: collect → index → compose → validate
       - Stock_Analyzer: fetch → compute → validate
    3. merge_artifacts (Supervisor)
    4. Chart_Generator: select → render → register
    5. Report_Compiler: assemble → compose
    6. qa_gate (Supervisor)
    7. Report_Compiler: export → post_qc
    """

    # StateGraph 생성
    workflow = StateGraph(AgentState)

    # ===== 1. Supervisor: 요청 파싱 =====
    workflow.add_node("parse_request", supervisor.parse_request)

    # ===== 2. Market_Researcher 노드들 =====
    workflow.add_node("collect_market_docs", market_researcher.collect_market_docs)
    workflow.add_node("index_market_docs", market_researcher.index_market_docs)
    workflow.add_node("extract_market_signals", market_researcher.extract_market_signals)
    workflow.add_node("validate_citations_market", market_researcher.validate_citations_market)

    # ===== 3. Company_Analyzer 노드들 =====
    workflow.add_node("collect_company_docs", company_analyzer.collect_company_docs)
    workflow.add_node("index_company_docs", company_analyzer.index_company_docs)
    workflow.add_node("compose_company_dossiers", company_analyzer.compose_company_dossiers)
    workflow.add_node("validate_citations_company", company_analyzer.validate_citations_company)

    # ===== 4. Stock_Analyzer 노드들 =====
    workflow.add_node("fetch_prices_financials", stock_analyzer.fetch_prices_financials)
    workflow.add_node("compute_snapshots", stock_analyzer.compute_snapshots)
    workflow.add_node("validate_financial_consistency", stock_analyzer.validate_financial_consistency)

    # ===== 5. Supervisor: 병합 =====
    workflow.add_node("merge_artifacts", supervisor.merge_artifacts)

    # ===== 6. Chart_Generator 노드들 =====
    workflow.add_node("select_chart_specs", chart_generator.select_chart_specs)
    workflow.add_node("render_charts", chart_generator.render_charts)
    workflow.add_node("register_chart_assets", chart_generator.register_chart_assets)

    # ===== 7. Report_Compiler 노드들 =====
    workflow.add_node("assemble_outline", report_compiler.assemble_outline)
    workflow.add_node("compose_sections", report_compiler.compose_sections)

    # ===== 8. Supervisor: QA Gate =====
    workflow.add_node("qa_gate", supervisor.qa_gate)

    # ===== 9. Report_Compiler: 최종 =====
    workflow.add_node("export_pdf", report_compiler.export_pdf)
    workflow.add_node("post_export_qc", report_compiler.post_export_qc)


    # ===== 엣지 구성 =====

    # 시작점 설정
    workflow.set_entry_point("parse_request")

    # parse_request → 3개 병렬 브랜치의 시작점
    workflow.add_edge("parse_request", "collect_market_docs")
    workflow.add_edge("parse_request", "collect_company_docs")
    workflow.add_edge("parse_request", "fetch_prices_financials")

    # Market_Researcher 체인
    workflow.add_edge("collect_market_docs", "index_market_docs")
    workflow.add_edge("index_market_docs", "extract_market_signals")
    workflow.add_edge("extract_market_signals", "validate_citations_market")
    workflow.add_edge("validate_citations_market", "merge_artifacts")

    # Company_Analyzer 체인
    workflow.add_edge("collect_company_docs", "index_company_docs")
    workflow.add_edge("index_company_docs", "compose_company_dossiers")
    workflow.add_edge("compose_company_dossiers", "validate_citations_company")
    workflow.add_edge("validate_citations_company", "merge_artifacts")

    # Stock_Analyzer 체인
    workflow.add_edge("fetch_prices_financials", "compute_snapshots")
    workflow.add_edge("compute_snapshots", "validate_financial_consistency")
    workflow.add_edge("validate_financial_consistency", "merge_artifacts")

    # merge_artifacts → Chart_Generator
    workflow.add_edge("merge_artifacts", "select_chart_specs")
    workflow.add_edge("select_chart_specs", "render_charts")
    workflow.add_edge("render_charts", "register_chart_assets")

    # register_chart_assets → Report_Compiler
    workflow.add_edge("register_chart_assets", "assemble_outline")
    workflow.add_edge("assemble_outline", "compose_sections")

    # compose_sections → QA Gate
    workflow.add_edge("compose_sections", "qa_gate")

    # qa_gate → 최종 PDF 생성
    workflow.add_edge("qa_gate", "export_pdf")
    workflow.add_edge("export_pdf", "post_export_qc")

    # post_export_qc → 종료
    workflow.add_edge("post_export_qc", END)

    return workflow


def compile_workflow() -> StateGraph:
    """
    워크플로우를 컴파일하여 실행 가능한 상태로 만듭니다.
    """
    workflow = create_workflow()
    compiled = workflow.compile()
    return compiled
