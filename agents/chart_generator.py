# agents/chart_generator.py
"""
Chart_Generator Agent
LangGraph 노드 함수들로 구성
"""
from typing import Dict, Any, List
from pathlib import Path
from state import AgentState
import matplotlib
matplotlib.use('Agg')  # GUI 없이 백그라운드에서 실행
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


def _setup_korean_font():
    """한글 폰트 설정"""
    try:
        # 한글 폰트 경로 시도
        font_paths = [
            "assets/fonts/NotoSansKR-Regular.ttf",
            "C:/Windows/Fonts/malgun.ttf",  # Windows
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
        ]

        for font_path in font_paths:
            if Path(font_path).exists():
                font_prop = fm.FontProperties(fname=font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
                print(f"[Chart_Generator] Korean font loaded: {font_path}")
                break
        else:
            print("[Chart_Generator] Korean font not found, using default")
    except Exception as e:
        print(f"[Chart_Generator] Font setup failed: {e}")


def select_chart_specs(state: AgentState) -> Dict[str, Any]:
    """차트 사양을 선택하는 노드"""
    print(f"[Chart_Generator] select_chart_specs")

    # 수집된 데이터를 기반으로 차트 스펙 결정
    chart_specs = []

    # 1. 주가 수익률 차트 (Stock_Analyzer 데이터 사용)
    if state.get("stock_snapshots"):
        chart_specs.append({
            "id": "ch-stock-returns",
            "kind": "bar",
            "title": "Stock Returns by Ticker",
            "section": "stock"
        })

    # 2. 시장 트렌드 차트 (Market_Researcher 데이터 사용)
    if state.get("market_brief", {}).get("top_trends"):
        chart_specs.append({
            "id": "ch-market-trends",
            "kind": "horizontal_bar",
            "title": "Key Market Trends",
            "section": "market"
        })

    # 3. 기업별 비즈니스 하이라이트 수 차트
    if state.get("company_dossiers"):
        chart_specs.append({
            "id": "ch-company-highlights",
            "kind": "bar",
            "title": "Company Business Highlights Count",
            "section": "company"
        })

    print(f"[Chart_Generator] Generated {len(chart_specs)} chart specs")
    return {"_chart_specs": chart_specs}


def render_charts(state: AgentState) -> Dict[str, Any]:
    """차트를 렌더링하는 노드"""
    print(f"[Chart_Generator] render_charts")

    _setup_korean_font()

    chart_specs = state.get("_chart_specs", [])
    chart_entries = []
    out_dir = Path("outputs/charts")
    out_dir.mkdir(parents=True, exist_ok=True)

    for spec in chart_specs:
        chart_id = spec["id"]
        kind = spec["kind"]
        title = spec["title"]
        section = spec["section"]

        try:
            if section == "stock":
                chart_path = _render_stock_returns_chart(state, out_dir, chart_id, title)
            elif section == "market":
                chart_path = _render_market_trends_chart(state, out_dir, chart_id, title)
            elif section == "company":
                chart_path = _render_company_highlights_chart(state, out_dir, chart_id, title)
            else:
                print(f"[Chart_Generator] Unknown section: {section}")
                continue

            if chart_path:
                chart_entries.append({
                    "id": chart_id,
                    "kind": kind,
                    "path": str(chart_path),
                    "alt": title,
                    "section": section
                })
                print(f"[Chart_Generator] Created chart: {chart_path}")
        except Exception as e:
            print(f"[Chart_Generator] Error rendering {chart_id}: {e}")

    return {"charts": chart_entries}


def _render_stock_returns_chart(state: AgentState, out_dir: Path, chart_id: str, title: str) -> Path:
    """주가 수익률 차트 생성"""
    snapshots = state.get("stock_snapshots", [])
    if not snapshots:
        return None

    tickers = [s.get("ticker", "N/A") for s in snapshots]
    returns = [s.get("period_return_pct", 0.0) for s in snapshots]

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['green' if r >= 0 else 'red' for r in returns]
    ax.bar(tickers, returns, color=colors, alpha=0.7)
    ax.set_xlabel('Ticker', fontsize=12)
    ax.set_ylabel('Return (%)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax.grid(axis='y', alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    chart_path = out_dir / f"{chart_id}.png"
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return chart_path


def _render_market_trends_chart(state: AgentState, out_dir: Path, chart_id: str, title: str) -> Path:
    """시장 트렌드 차트 생성"""
    market_brief = state.get("market_brief", {})
    trends = market_brief.get("top_trends", [])

    if not trends:
        return None

    # 트렌드 텍스트를 짧게 자르기 (인용 번호 제거)
    import re
    trend_labels = []
    for t in trends[:5]:  # 최대 5개만
        # 인용 번호 제거
        clean_text = re.sub(r'\[\d+\]', '', t)
        # 50자로 제한
        if len(clean_text) > 50:
            clean_text = clean_text[:47] + "..."
        trend_labels.append(clean_text)

    fig, ax = plt.subplots(figsize=(10, 6))
    y_pos = range(len(trend_labels))
    values = [len(trend_labels) - i for i in range(len(trend_labels))]  # 중요도를 숫자로 표현

    ax.barh(y_pos, values, color='steelblue', alpha=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(trend_labels, fontsize=9)
    ax.set_xlabel('Importance Ranking', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()

    chart_path = out_dir / f"{chart_id}.png"
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return chart_path


def _render_company_highlights_chart(state: AgentState, out_dir: Path, chart_id: str, title: str) -> Path:
    """기업 하이라이트 차트 생성"""
    dossiers = state.get("company_dossiers", [])
    if not dossiers:
        return None

    tickers = []
    highlight_counts = []

    for d in dossiers:
        ticker = d.get("ticker", "N/A")
        highlights = d.get("business_highlights", [])
        tickers.append(ticker)
        highlight_counts.append(len(highlights))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(tickers, highlight_counts, color='coral', alpha=0.7)
    ax.set_xlabel('Company', fontsize=12)
    ax.set_ylabel('Number of Highlights', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    chart_path = out_dir / f"{chart_id}.png"
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return chart_path


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
