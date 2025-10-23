# services/llm.py
"""
LLM 호출 유틸리티
OpenAI GPT-4o-mini를 사용하여 텍스트 생성
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
import re


def clean_citations(text: str) -> str:
    """
    중복된 인용 번호를 제거합니다.
    예: '[1][1]' -> '[1]', '[2][3][2]' -> '[2][3]'
    """
    if not text:
        return text

    # 연속된 인용 패턴 찾기
    def deduplicate_citations(match):
        citations = re.findall(r'\[(\d+)\]', match.group(0))
        # 중복 제거하되 순서 유지
        seen = set()
        unique_citations = []
        for c in citations:
            if c not in seen:
                seen.add(c)
                unique_citations.append(c)
        return ''.join([f'[{c}]' for c in unique_citations])

    # 연속된 [n][n]... 패턴을 찾아서 중복 제거
    cleaned = re.sub(r'(?:\[\d+\])+', deduplicate_citations, text)
    return cleaned


def get_llm():
    """
    LLM 인스턴스를 가져옵니다.
    환경 변수 OPENAI_API_KEY가 필요합니다.
    """
    try:
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[LLM] WARNING: OPENAI_API_KEY not found. Using fallback mode.")
            return None

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=api_key
        )
        return llm
    except ImportError:
        print("[LLM] WARNING: langchain-openai not installed. Using fallback mode.")
        return None


def load_prompt_template(prompt_file: str) -> str:
    """
    프롬프트 템플릿 파일을 로드합니다.
    """
    prompt_path = Path("prompts") / prompt_file
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""


def summarize_market_trends_with_global_refs(
    documents: List[Dict[str, Any]],
    focus_issues: List[str],
    regions: List[str],
    period: str,
    start_ref_number: int = 1
) -> Dict[str, Any]:
    """
    수집된 문서들을 LLM으로 요약하여 시장 트렌드를 추출합니다.
    전역 참조 번호를 사용합니다.

    Args:
        start_ref_number: 이 문서 세트의 시작 참조 번호 (전역 번호)

    Returns:
        {
            "top_trends": [...],
            "summary": "...",
            "referenced_docs": [1, 3, 5]  # 전역 참조 번호
        }
    """
    llm = get_llm()

    # LLM이 없으면 기존 더미 데이터 반환
    if not llm:
        return {
            "top_trends": [
                "글로벌 EV 판매 성장률 둔화 (LLM 미사용)",
                "보조금·관세 정책 변화가 수요를 변동 (LLM 미사용)",
                "LFP/LMFP 채택 확대, 원가 하락 압력 지속 (LLM 미사용)"
            ],
            "summary": "LLM이 설정되지 않아 더미 데이터를 사용합니다.",
            "referenced_docs": []
        }

    # 문서 컨텍스트 구성 (전역 번호 사용)
    context = "\n\n".join([
        f"[문서 {start_ref_number + i}] {doc.get('title', 'Untitled')}\n"
        f"Date: {doc.get('date', 'N/A')}\n"
        f"Source: {doc.get('url', 'N/A')}\n"
        f"Content: {doc.get('text', 'No content')[:1000]}"
        for i, doc in enumerate(documents[:10])  # 최대 10개 문서
    ])

    # 프롬프트 구성
    prompt_template = load_prompt_template("market_prompt.md")
    if not prompt_template:
        prompt_template = """다음 EV 시장 관련 문서들을 분석하여:
1. 주요 트렌드 3-5개 (각 한 줄로 요약)
2. 전체 요약 (2-3문장)

**인용 규칙 (매우 중요)**:
- 각 문장에서 실제로 해당 정보가 포함된 문서 번호만 인용하세요
- 같은 번호를 연속으로 반복하지 마세요 (예: [1][1] 금지)
- 가능한 한 다양한 문서를 인용하세요 (모든 트렌드에 [1]만 사용하지 마세요)
- 확실하지 않으면 인용 번호를 생략하는 것이 낫습니다
- 예시: "글로벌 EV 판매 성장률 둔화[2], 특히 유럽 시장의 보조금 축소가 영향[5]"

문서들:
{context}

분석 기간: {period}
관심 이슈: {focus_issues}
지역: {regions}

JSON 형식으로 응답:
{{
  "top_trends": ["트렌드1[n]", "트렌드2[n]", ...],
  "summary": "전체 요약문[n]",
  "referenced_docs": [n1, n2, n3]
}}

referenced_docs에는 실제로 인용한 문서 번호만 포함하세요."""

    prompt = prompt_template.format(
        context=context,
        period=period,
        focus_issues=", ".join(focus_issues),
        regions=", ".join(regions)
    )

    try:
        from langchain_core.messages import HumanMessage
        import json
        import re

        response = llm.invoke([HumanMessage(content=prompt)])
        result = json.loads(response.content)

        # 중복 인용 제거
        if "top_trends" in result:
            result["top_trends"] = [clean_citations(t) for t in result["top_trends"]]
        if "summary" in result:
            result["summary"] = clean_citations(result["summary"])

        # LLM이 referenced_docs를 반환하지 않은 경우, 텍스트에서 [n] 추출
        if "referenced_docs" not in result:
            # top_trends와 summary에서 [n] 패턴 추출
            text = " ".join(result.get("top_trends", [])) + " " + result.get("summary", "")
            citations = re.findall(r'\[(\d+)\]', text)
            result["referenced_docs"] = sorted(list(set(int(c) for c in citations)))

        return result
    except Exception as e:
        print(f"[LLM] Error during summarization: {e}")
        return {
            "top_trends": ["LLM 호출 오류 발생"],
            "summary": f"오류: {str(e)}",
            "referenced_docs": []
        }


def summarize_market_trends(
    documents: List[Dict[str, Any]],
    focus_issues: List[str],
    regions: List[str],
    period: str
) -> Dict[str, Any]:
    """
    호환성을 위한 래퍼 함수. summarize_market_trends_with_global_refs를 호출합니다.
    """
    return summarize_market_trends_with_global_refs(documents, focus_issues, regions, period, start_ref_number=1)


def summarize_company_info(
    ticker: str,
    documents: List[Dict[str, Any]],
    aspect: str  # "business" | "risk" | "roadmap"
) -> Dict[str, Any]:
    """
    기업 관련 문서를 LLM으로 요약합니다.

    Returns:
        {
            "points": ["포인트1[n]", ...],
            "referenced_docs": [1, 2]
        }
    """
    llm = get_llm()

    if not llm:
        return {
            "points": [f"{ticker} {aspect} - LLM 미사용 더미 데이터"],
            "referenced_docs": []
        }

    context = "\n\n".join([
        f"[문서 {i+1}] {doc.get('title', 'Untitled')}\n{doc.get('snippet', '')}"
        for i, doc in enumerate(documents[:5])
    ])

    aspect_map = {
        "business": "사업 전략, 가격 정책, 마진 관련",
        "risk": "리스크 요인, 규제, 공급망 이슈",
        "roadmap": "로드맵, 신모델, 생산 계획"
    }

    prompt = f"""기업 {ticker}의 {aspect_map.get(aspect, aspect)} 관련 정보를 분석하여
3-5개의 핵심 포인트를 추출하세요. 각 포인트는 한 문장으로 작성하세요.

**인용 규칙 (매우 중요)**:
- 각 포인트에서 실제로 해당 정보가 포함된 문서 번호만 인용하세요
- 같은 번호를 연속으로 반복하지 마세요 (예: [1][1] 금지)
- 가능한 한 다양한 문서를 인용하세요
- 확실하지 않으면 인용 번호를 생략하는 것이 낫습니다
- 예시: "Tesla는 Q3 7% 가격 인하로 판매량 15% 증가[2]; 배터리 수직 통합 전략 추진[3]"

문서:
{context}

JSON 형식으로 응답:
{{
  "points": ["포인트1[n]", "포인트2[n]", "포인트3[n]"],
  "referenced_docs": [1, 2, 3]
}}"""

    try:
        from langchain_core.messages import HumanMessage
        import json
        import re

        response = llm.invoke([HumanMessage(content=prompt)])
        result = json.loads(response.content)

        # 이전 버전 호환성: 리스트로 반환된 경우 Dict로 변환
        if isinstance(result, list):
            # 중복 인용 제거
            cleaned_points = [clean_citations(p) for p in result]
            text = " ".join(cleaned_points)
            citations = re.findall(r'\[(\d+)\]', text)
            return {
                "points": cleaned_points,
                "referenced_docs": sorted(list(set(int(c) for c in citations)))
            }

        # 중복 인용 제거
        if "points" in result:
            result["points"] = [clean_citations(p) for p in result["points"]]

        # referenced_docs가 없으면 텍스트에서 추출
        if "referenced_docs" not in result:
            text = " ".join(result.get("points", []))
            citations = re.findall(r'\[(\d+)\]', text)
            result["referenced_docs"] = sorted(list(set(int(c) for c in citations)))

        return result
    except Exception as e:
        print(f"[LLM] Error during company summarization: {e}")
        return {
            "points": [f"오류: {str(e)}"],
            "referenced_docs": []
        }


def generate_section_content(
    section_name: str,
    context: Dict[str, Any]
) -> str:
    """
    리포트 섹션 콘텐츠를 LLM으로 생성합니다.
    """
    llm = get_llm()

    if not llm:
        return f"<p>{section_name} - LLM이 설정되지 않아 콘텐츠를 생성할 수 없습니다.</p>"

    section_prompts = {
        "demand_pricing": """수요 & 가격 전략 섹션을 작성하세요:
- 세그먼트별 수요 동향
- ASP(평균 판매가) 변화
- 가격 인하 전략 영향
- 마진 압력 요인

**인용 규칙 (매우 중요)**:
- 컨텍스트의 top_trends, company_dossiers 등에 이미 [n] 형식의 인용이 포함되어 있습니다
- 이 인용들을 그대로 유지하세요
- 같은 번호를 연속으로 반복하지 마세요 (예: [1][1] 금지)
- 새로운 정보를 추가할 때만 추가 인용을 사용하세요

컨텍스트:
{context}

HTML 형식으로 작성 (제목 제외, 본문만). 인용 번호 [n]을 포함하되 중복 없이:""",

        "policy": """정책·규제 섹션을 작성하세요:
- 국가별 보조금 변화
- 관세/무역 정책 영향
- 탄소 규제 동향
- 정책 이벤트 타임라인

**인용 규칙 (매우 중요)**:
- 컨텍스트의 top_trends, company_dossiers 등에 이미 [n] 형식의 인용이 포함되어 있습니다
- 이 인용들을 그대로 유지하세요
- 같은 번호를 연속으로 반복하지 마세요 (예: [1][1] 금지)
- 새로운 정보를 추가할 때만 추가 인용을 사용하세요

컨텍스트:
{context}

HTML 형식으로 작성 (제목 제외, 본문만). 인용 번호 [n]을 포함하되 중복 없이:""",

        "battery_supply": """배터리 기술 & 공급망 섹션을 작성하세요:
- 배터리 화학 (LFP/LMFP/NMC) 동향
- kWh당 원가 변화
- 주요 벤더 생산 능력
- 수직 통합 전략

**인용 규칙 (매우 중요)**:
- 컨텍스트의 top_trends, company_dossiers 등에 이미 [n] 형식의 인용이 포함되어 있습니다
- 이 인용들을 그대로 유지하세요
- 같은 번호를 연속으로 반복하지 마세요 (예: [1][1] 금지)
- 새로운 정보를 추가할 때만 추가 인용을 사용하세요

컨텍스트:
{context}

HTML 형식으로 작성 (제목 제외, 본문만). 인용 번호 [n]을 포함하되 중복 없이:""",
    }

    prompt = section_prompts.get(section_name, "")
    if not prompt:
        return f"<p>{section_name} 섹션 프롬프트가 정의되지 않았습니다.</p>"

    try:
        from langchain_core.messages import HumanMessage
        import json

        prompt_filled = prompt.format(context=json.dumps(context, ensure_ascii=False, indent=2))
        response = llm.invoke([HumanMessage(content=prompt_filled)])
        # 중복 인용 제거
        return clean_citations(response.content)
    except Exception as e:
        print(f"[LLM] Error during section generation: {e}")
        return f"<p>오류: {str(e)}</p>"
