# services/ingest.py
"""
문헌 수집/정규화 유틸리티.
- Tavily API를 사용한 실시간 웹 검색 및 크롤링
- 외부 네트워크 미사용 환경에서도 더미 데이터를 반환하는 안전한 폴백 제공
- 실제 사용 시: fetch_* 계열만 교체하면 상위 에이전트 코드 수정 최소화

핵심 제공 함수
- fetch_market_sources(period, regions, focus_issues, snapshot_date)
- fetch_company_sources(benchmarks, period, regions, snapshot_date)
- normalize_records(records)
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
import os


@dataclass
class SourceDoc:
    """수집한 원문 문서의 최소 메타 스키마"""
    title: str
    url: str
    date: str              # ISO (YYYY-MM-DD)
    kind: str              # news | policy | ir | report | blog | pdf
    lang: str = "ko"
    text: Optional[str] = None
    source: str = "dummy"  # origin label
    region: Optional[str] = None
    company: Optional[str] = None
    issue_tags: Optional[List[str]] = None


def _today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _get_tavily_client():
    """
    Tavily 클라이언트를 가져옵니다.
    환경 변수 TAVILY_API_KEY가 필요합니다.
    """
    try:
        from tavily import TavilyClient
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            print("[Ingest] WARNING: TAVILY_API_KEY not found. Using fallback mode.")
            return None
        return TavilyClient(api_key=api_key)
    except ImportError:
        print("[Ingest] WARNING: tavily-python not installed. Using fallback mode.")
        return None
    except Exception as e:
        print(f"[Ingest] WARNING: Failed to initialize Tavily: {e}")
        return None


def _search_with_tavily(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Tavily API를 사용하여 웹 검색을 수행합니다.

    Returns:
        List of documents with 'title', 'url', 'content', 'published_date'
    """
    client = _get_tavily_client()
    if not client:
        return []

    try:
        print(f"[Ingest] Tavily search: '{query}' (max_results={max_results})")
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",  # 더 깊은 검색
            include_raw_content=True  # 전체 콘텐츠 포함
        )

        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", "Untitled"),
                "url": item.get("url", ""),
                "content": item.get("content", "") or item.get("raw_content", ""),
                "published_date": item.get("published_date", None),
                "score": item.get("score", 0.0)
            })

        print(f"[Ingest] Tavily returned {len(results)} results")
        return results

    except Exception as e:
        print(f"[Ingest] ERROR during Tavily search: {e}")
        return []


# =============== 시장/정책/뉴스 수집 ===============

def fetch_market_sources(
    period: str,
    regions: List[str],
    focus_issues: List[str],
    snapshot_date: str,
    *,
    offline_ok: bool = True,
) -> List[Dict[str, Any]]:
    """
    시장·정책·뉴스 원문 수집.
    - Tavily API를 사용하여 실시간 웹 검색 수행
    - 네트워크 실패 시 더미 데이터 반환
    """
    docs: List[SourceDoc] = []

    # Tavily로 실제 검색 수행
    try:
        # 검색 쿼리 구성
        regions_str = ", ".join(regions) if regions else "global"
        issues_str = ", ".join(focus_issues) if focus_issues else "EV market trends"

        queries = [
            f"electric vehicle EV market trends {regions_str} {period}",
            f"EV sales statistics {regions_str} 2024 2025",
            f"{issues_str} electric vehicle policy {regions_str}",
        ]

        for query in queries:
            results = _search_with_tavily(query, max_results=3)

            for result in results:
                # Tavily 결과를 SourceDoc으로 변환
                doc = SourceDoc(
                    title=result["title"],
                    url=result["url"],
                    date=result.get("published_date") or snapshot_date or _today_iso(),
                    kind="news",
                    lang="en",
                    source="tavily",
                    region=regions[0] if regions else "global",
                    issue_tags=focus_issues if focus_issues else [],
                    text=result["content"][:5000]  # 처음 5000자만 사용
                )
                docs.append(doc)

        if docs:
            print(f"[Ingest] Fetched {len(docs)} real documents from Tavily")
            return [asdict(d) for d in docs]

    except Exception as e:
        print(f"[Ingest] ERROR during market source fetch: {e}")

    # 폴백: 더미 데이터
    if offline_ok:
        print("[Ingest] Using fallback dummy data for market sources")
        docs = [
            SourceDoc(
                title="Global EV Sales Update",
                url="https://example.com/ev",
                date=snapshot_date or _today_iso(),
                kind="news",
                lang="en",
                source="example",
                region="global",
                issue_tags=["demand_softness"],
                text="Global EV sales growth slowed in the last quarter...",
            ),
            SourceDoc(
                title="EU Subsidy Change",
                url="https://example.com/eu",
                date=snapshot_date or _today_iso(),
                kind="policy",
                lang="en",
                source="example",
                region="EU",
                issue_tags=["subsidy_policy"],
                text="EU adjusted EV subsidy eligibility rules affecting OEM lineups...",
            ),
        ]
        return [asdict(d) for d in docs]

    return []


# =============== 기업(IR/공시) 수집 ===============

def fetch_company_sources(
    benchmarks: List[str],
    period: str,
    regions: List[str],
    snapshot_date: str,
    *,
    offline_ok: bool = True,
) -> List[Dict[str, Any]]:
    """
    기업별 IR/공시/보도자료 수집.
    - Tavily API를 사용하여 각 기업별 최신 정보 검색
    - 네트워크 실패 시 더미 IR 한 건씩 생성
    """
    docs: List[SourceDoc] = []

    # Tavily로 실제 검색 수행
    try:
        for tk in benchmarks or []:
            # 기업별 검색 쿼리
            queries = [
                f"{tk} electric vehicle business strategy pricing {period}",
                f"{tk} EV battery technology supply chain news",
                f"{tk} quarterly earnings revenue forecast {period}",
            ]

            for query in queries[:2]:  # 각 기업당 2개 쿼리만 실행
                results = _search_with_tavily(query, max_results=2)

                for result in results:
                    doc = SourceDoc(
                        title=result["title"],
                        url=result["url"],
                        date=result.get("published_date") or snapshot_date or _today_iso(),
                        kind="ir",
                        lang="en",
                        source="tavily",
                        region=None,
                        company=tk,
                        issue_tags=["pricing", "battery", "strategy"],
                        text=result["content"][:5000]  # 처음 5000자만 사용
                    )
                    docs.append(doc)

        if docs:
            print(f"[Ingest] Fetched {len(docs)} real company documents from Tavily")
            return [asdict(d) for d in docs]

    except Exception as e:
        print(f"[Ingest] ERROR during company source fetch: {e}")

    # 폴백: 더미 데이터
    if offline_ok:
        print("[Ingest] Using fallback dummy data for company sources")
        for tk in benchmarks or []:
            docs.append(
                SourceDoc(
                    title=f"{tk} IR Deck",
                    url=f"https://example.com/{tk}",
                    date=snapshot_date or _today_iso(),
                    kind="ir",
                    lang="en",
                    source="example",
                    region=None,
                    company=tk,
                    issue_tags=["pricing", "battery_vertical_integration"],
                    text=f"{tk} discusses pricing strategy, margin pressure, and battery integration.",
                )
            )
        return [asdict(d) for d in docs]

    return []


# =============== 정규화/후처리 ===============

def normalize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    수집 레코드 정규화:
    - date 포맷 보정
    - 필수 필드 누락 보강
    - 텍스트 길이 제한(너무 긴 경우 앞부분만 저장)
    """
    out = []
    for r in records:
        # SourceDoc 객체일 경우 딕셔너리로 변환
        if hasattr(r, '__dataclass_fields__'):
            r = asdict(r)
        else:
            r = dict(r)
        # 날짜 보정
        date = r.get("date") or _today_iso()
        try:
            _ = datetime.fromisoformat(date)
        except Exception:
            date = _today_iso()
        r["date"] = date

        # 필수 기본값
        r.setdefault("kind", "news")
        r.setdefault("lang", "en")
        r.setdefault("source", "unknown")
        r.setdefault("title", "(untitled)")
        r.setdefault("url", "")
        r.setdefault("text", None)

        # 텍스트 길이 제한
        if isinstance(r.get("text"), str) and len(r["text"]) > 8000:
            r["text"] = r["text"][:8000] + "\n...[truncated]"

        out.append(r)
    return out
