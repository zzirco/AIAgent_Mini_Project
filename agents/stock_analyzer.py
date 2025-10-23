# agents/stock_analyzer.py
"""
Stock_Analyzer Agent
LangGraph 노드 함수들로 구성
"""
from typing import Dict, Any
from state import AgentState
from services.finance import (
    fetch_price_series,
    compute_return_and_vol,
    fetch_fundamentals,
    ensure_currency,
)


def fetch_prices_financials(state: AgentState) -> Dict[str, Any]:
    """
    각 ticker별 가격 시계열 + 기초 재무를 services.finance에서 취득하는 노드
    """
    print(f"[Stock_Analyzer] fetch_prices_financials - benchmarks: {state.get('benchmarks', [])}")

    tickers = state.get("benchmarks", []) or []
    series_cache = {}
    fund_cache = {}

    for tk in tickers:
        series_cache[tk] = fetch_price_series(tk, state.get("period", "last_90d"))
        fund_cache[tk] = fetch_fundamentals(tk)

    return {
        "_series": series_cache,
        "_funds": fund_cache
    }


def compute_snapshots(state: AgentState) -> Dict[str, Any]:
    """
    시계열로 기간 수익률/변동성 계산하는 노드
    fundamentals 함께 포함해 multiples 필드 구성
    """
    print(f"[Stock_Analyzer] compute_snapshots")

    snapshots = []
    base_ccy = state.get("financials", {}).get("base_currency", "USD")

    for tk, series in (state.get("_series") or {}).items():
        pct_return, vol = compute_return_and_vol(series)
        funds = (state.get("_funds") or {}).get(tk, {})
        per = funds.get("per")
        eps = funds.get("eps_ttm")

        snapshots.append({
            "ticker": tk,
            "period_return_pct": round(pct_return, 2),
            "volatility": round(vol, 2),
            "multiples": {"PER": per, "EPS_TTM": eps, "CCY": base_ccy},
            "events": ["earnings_in_2w"],  # TODO: services.finance에 이벤트 소스 붙이면 교체
        })

    return {"stock_snapshots": snapshots}


def validate_financial_consistency(state: AgentState) -> Dict[str, Any]:
    """
    compute_snapshots에서 계산된 period_return_pct가,
    원시 시계열로 재계산한 값과 ±0.1% 이내인지 확인하는 노드
    """
    print(f"[Stock_Analyzer] validate_financial_consistency")

    ok = True
    for s in state.get("stock_snapshots", []):
        tk = s["ticker"]
        series = (state.get("_series") or {}).get(tk)
        if not series:
            continue
        calc_ret, _ = compute_return_and_vol(series)
        if abs(round(calc_ret, 2) - s["period_return_pct"]) > 0.1:
            ok = False

    # 개별 필드로 저장 (qa_metrics는 나중에 merge)
    return {"_qa_number_consistency": ok}
