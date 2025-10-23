# services/finance.py
"""
가격/재무 데이터 래퍼.
- yfinance 등 외부 의존성이 없어도 안전하게 동작하는 폴백 제공
- 실제 연결 시: fetch_price_series / fetch_fundamentals 내부만 교체하면 상위 코드는 동일

핵심 제공 함수
- fetch_price_series(ticker, period) -> dict
- compute_return_and_vol(series) -> (pct_return, volatility)
- fetch_fundamentals(ticker) -> dict
- ensure_currency(value, from_ccy, to_ccy, fx=...) -> float
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import math
import random


# =============== 가격 시계열 ===============

def fetch_price_series(ticker: str, period: str = "last_90d") -> Dict[str, Any]:
    """
    티커 가격 시계열을 반환.
    - 오프라인 폴백: 단조 증가하는 더미 가격 시계열 생성
    반환 예:
    {
      "ticker": "TSLA",
      "ccy": "USD",
      "close": [234.1, 235.2, ...],
      "dates": ["2025-07-01", ...]
    }
    """
    # 실제 구현 시: yfinance.download(..., period=...) 사용
    n = 60 if "90" in period else 20
    base = 100 + random.uniform(-5, 5)
    series = [round(base + i * random.uniform(0.05, 0.8), 2) for i in range(n)]
    dates = [f"2025-07-{(i % 28)+1:02d}" for i in range(n)]
    return {"ticker": ticker, "ccy": "USD", "close": series, "dates": dates}


def compute_return_and_vol(series: Dict[str, Any]) -> Tuple[float, float]:
    """
    가격 시계열로부터 기간 수익률(%)과 단순 일간 수익률 표준편차(변동성, %)를 계산.
    """
    closes = series.get("close", [])
    if len(closes) < 2:
        return 0.0, 0.0
    ret = (closes[-1] - closes[0]) / max(1e-9, closes[0]) * 100.0
    # 일간 로그수익률 표준편차 (간단 계산)
    rets = []
    for i in range(1, len(closes)):
        if closes[i-1] <= 0 or closes[i] <= 0:
            continue
        rets.append(math.log(closes[i] / closes[i-1]) * 100.0)
    if len(rets) == 0:
        vol = 0.0
    else:
        mean = sum(rets) / len(rets)
        var = sum((x - mean) ** 2 for x in rets) / max(1, len(rets) - 1)
        vol = math.sqrt(var)
    return round(ret, 2), round(vol, 2)


# =============== 재무 지표 (멀티플 등) ===============

def fetch_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    기본 재무 지표 폴백.
    실제 연결 시: 재무 API에서 EPS/시총/멀티플 등 조회
    """
    # 폴백: 임의 값
    eps_ttm = round(random.uniform(1.0, 6.0), 2)
    price = 120.0
    per = round(price / eps_ttm, 2) if eps_ttm else None
    return {
        "ticker": ticker,
        "eps_ttm": eps_ttm,
        "per": per,
        "currency": "USD",
    }


# =============== 통화 변환 ===============

def ensure_currency(value: float, from_ccy: str, to_ccy: str, fx: float | None = None) -> float:
    """
    통화 변환. fx가 없으면 간단 폴백 환율 사용.
    """
    if from_ccy == to_ccy:
        return value
    # 폴백 환율 (예시): 1 USD = 1300 KRW
    if fx is None:
        if from_ccy == "USD" and to_ccy == "KRW":
            fx = 1300.0
        elif from_ccy == "KRW" and to_ccy == "USD":
            fx = 1 / 1300.0
        else:
            fx = 1.0  # 미지정 통화쌍은 변환 안 함
    return value * fx
