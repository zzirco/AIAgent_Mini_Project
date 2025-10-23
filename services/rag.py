# services/rag.py
"""
간단한 RAG 유틸(임베딩 없이도 동작하는 키워드 매칭 폴백 포함).
- 외부 라이브러리 없이도 최소 검색/스코어링이 가능하도록 설계
- 실제 임베딩/VectorDB 연결 시: 인덱스/쿼리 함수만 교체

핵심 제공 함수
- build_index(raw_docs) -> index(dict)
- query(index, query_text, filters=..., top_k=6) -> List[passages]
- make_evidence_map(passages) -> List[dict]
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import re


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9가-힣]+", text.lower())


def build_index(raw_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    매우 단순한 인메모리 인덱스: {doc_id: {"meta":..., "tokens": [...], "text":...}}
    실제 구현 시: 임베딩 + VectorDB로 교체
    """
    index = {"docs": {}}
    for i, d in enumerate(raw_docs):
        doc_id = d.get("id") or f"doc-{i}"
        text = d.get("text") or (d.get("title", "") + " " + d.get("url", ""))
        tokens = _tokenize(text)[:5000]
        meta = {
            "title": d.get("title"),
            "url": d.get("url"),
            "date": d.get("date"),
            "kind": d.get("kind"),
            "region": d.get("region"),
            "company": d.get("company"),
            "issue_tags": d.get("issue_tags"),
        }
        index["docs"][doc_id] = {"meta": meta, "tokens": tokens, "text": text}
    return index


def _score(tokens_q: List[str], tokens_d: List[str]) -> float:
    """
    아주 단순한 토큰 교집합 스코어
    """
    if not tokens_q or not tokens_d:
        return 0.0
    set_q = set(tokens_q)
    set_d = set(tokens_d)
    inter = len(set_q & set_d)
    return inter / max(1, len(set_q))


def query(
    index: Dict[str, Any],
    query_text: str,
    *,
    filters: Dict[str, Any] | None = None,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """
    인덱스에서 간단 키워드 스코어링으로 top_k passage 반환.
    filters: {"region": [...], "company": [...], "issue_tags": [...], "date_range": (start, end)}
    """
    tokens_q = _tokenize(query_text)
    hits: List[Tuple[str, float]] = []

    def _filter(meta: Dict[str, Any]) -> bool:
        if not filters:
            return True
        # region
        if "region" in filters and filters["region"]:
            if meta.get("region") not in filters["region"] and meta.get("region") != "global":
                return False
        # company
        if "company" in filters and filters["company"]:
            if meta.get("company") not in filters["company"]:
                return False
        # issue tags
        if "issue_tags" in filters and filters["issue_tags"]:
            tags = meta.get("issue_tags") or []
            if not any(t in tags for t in filters["issue_tags"]):
                return False
        # date range (문자열 비교, 간단 처리)
        if "date_range" in filters and filters["date_range"]:
            start, end = filters["date_range"]
            d = meta.get("date")
            if d and (d < start or d > end):
                return False
        return True

    for doc_id, rec in index.get("docs", {}).items():
        if not _filter(rec["meta"]):
            continue
        s = _score(tokens_q, rec["tokens"])
        if s > 0:
            hits.append((doc_id, s))

    hits.sort(key=lambda x: x[1], reverse=True)
    out = []
    for doc_id, s in hits[:top_k]:
        meta = index["docs"][doc_id]["meta"]
        text = index["docs"][doc_id]["text"]
        snippet = text[:500] + ("..." if len(text) > 500 else "")
        out.append({
            "doc_id": doc_id,
            "score": round(float(s), 4),
            "title": meta.get("title"),
            "url": meta.get("url"),
            "date": meta.get("date"),
            "snippet": snippet,
            "meta": meta,
        })
    return out


def make_evidence_map(passages: List[Dict[str, Any]], start_n: int = 1) -> List[Dict[str, Any]]:
    """
    쿼리 결과를 리포트 각주에 쓸 수 있는 evidence 엔트리로 변환
    """
    evidence = []
    n = start_n
    for p in passages:
        evidence.append({
            "n": n,
            "title": p.get("title") or "(untitled)",
            "url": p.get("url") or "",
            "date": p.get("date") or "",
        })
        n += 1
    return evidence
