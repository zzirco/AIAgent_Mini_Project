# agents/chart_generator.py
"""
Chart_Generator Agent
LangGraph 노드 함수들로 구성
"""
from typing import Dict, Any
from pathlib import Path
from state import AgentState


def select_chart_specs(state: AgentState) -> Dict[str, Any]:
    """차트 사양을 선택하는 노드"""
    print(f"[Chart_Generator] select_chart_specs")

    charts = [{"id": "ch-returns", "kind": "line", "title": "Returns by Ticker"}]

    return {"_chart_specs": charts}


def render_charts(state: AgentState) -> Dict[str, Any]:
    """차트를 렌더링하는 노드"""
    print(f"[Chart_Generator] render_charts")

    # 실제 구현에서는 matplotlib/plotly 사용
    # TODO: 실제 차트 생성 로직 구현
    out = Path("outputs/charts/returns.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"")  # 자리표시자

    chart_entry = {
        "id": "ch-returns",
        "kind": "line",
        "path": str(out),
        "alt": "returns by ticker"
    }

    return {"charts": [chart_entry]}


def register_chart_assets(state: AgentState) -> Dict[str, Any]:
    """차트 자산을 evidence_map에 등록하는 노드"""
    print(f"[Chart_Generator] register_chart_assets")

    evidence_entry = {
        "section": "chart",
        "n": 99,
        "title": "Internal chart",
        "url": "outputs/charts/returns.png",
        "date": state["snapshot_date"]
    }

    return {"evidence_map": [evidence_entry]}
