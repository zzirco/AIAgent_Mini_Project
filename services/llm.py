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
    LangSmith 트레이싱을 지원합니다.
    """
    try:
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[LLM] WARNING: OPENAI_API_KEY not found. Using fallback mode.")
            return None

        # LangSmith 트레이싱 정보 로그
        langchain_tracing = os.getenv("LANGCHAIN_TRACING_V2", "false")
        langchain_project = os.getenv("LANGCHAIN_PROJECT", "default")
        print(f"[LLM] Creating ChatOpenAI instance - Tracing: {langchain_tracing}, Project: {langchain_project}")

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=api_key,
            model_kwargs={
                "response_format": {"type": "json_object"}  # JSON 모드 강제
            },
            # LangSmith 메타데이터 추가
            metadata={
                "project": langchain_project,
                "agent_type": "market_analyzer"
            }
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

    # 프롬프트 구성 - 항상 하드코딩된 프롬프트 사용 (JSON 키워드 보장)
    focus_issues_str = ", ".join(focus_issues)
    regions_str = ", ".join(regions)

    prompt = f"""You are analyzing EV market documents. Respond with a JSON object in KOREAN language.

**IMPORTANT: Write all content in KOREAN (한글). Only technical terms, company names, and URLs can be in English.**

다음 EV 시장 관련 문서들을 분석하여:
1. 주요 트렌드 3-5개 (각 한 줄로 요약)
2. 전체 요약 (2-3문장)

**작성 언어**: 반드시 한글로 작성하세요. 기업명, 기술 용어(EV, LFP, LMFP 등)는 영어 가능.

**인용 규칙 (매우 중요)**:
- 각 문장에서 실제로 해당 정보가 포함된 문서 번호만 인용하세요
- 같은 번호를 연속으로 반복하지 마세요 (예: [1][1] 금지)
- 가능한 한 다양한 문서를 인용하세요 (모든 트렌드에 [1]만 사용하지 마세요)
- 확실하지 않으면 인용 번호를 생략하는 것이 낫습니다
- 예시: "글로벌 EV 판매 성장률 둔화[2], 특히 유럽 시장의 보조금 축소가 영향[5]"

문서들:
{context}

분석 기간: {period}
관심 이슈: {focus_issues_str}
지역: {regions_str}

Please respond with a JSON object in this format (content must be in KOREAN):
{{
  "top_trends": ["트렌드1[n]", "트렌드2[n]", "트렌드3[n]"],
  "summary": "전체 요약문[n]",
  "referenced_docs": [n1, n2, n3]
}}"""

    try:
        from langchain_core.messages import HumanMessage
        import json
        import re

        # 디버깅: 프롬프트에 'json' 키워드가 포함되어 있는지 확인
        if 'json' not in prompt.lower():
            print(f"[LLM] WARNING: Prompt does not contain 'json' keyword!")
            print(f"[LLM] Prompt preview: {prompt[:200]}")
        else:
            print(f"[LLM] Prompt contains 'json' keyword - OK")

        response = llm.invoke([HumanMessage(content=prompt)])
        print(f"[LLM] Raw response type: {type(response.content)}")
        print(f"[LLM] Raw response (first 500 chars): {response.content[:500]}")

        # JSON 파싱 시도
        response_text = response.content.strip()

        # 마크다운 코드 블록으로 감싸진 경우 제거
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # ```json 제거
        if response_text.startswith("```"):
            response_text = response_text[3:]  # ``` 제거
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # ``` 제거
        response_text = response_text.strip()

        result = json.loads(response_text)

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

        print(f"[LLM] Successfully parsed JSON response with {len(result.get('top_trends', []))} trends")
        return result
    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parsing error: {e}")
        print(f"[LLM] Raw response content: {response.content}")
        return {
            "top_trends": [
                "글로벌 EV 판매 성장률 둔화 (JSON 파싱 오류로 더미 데이터 사용)",
                "보조금·관세 정책 변화가 수요에 영향",
                "LFP/LMFP 채택 확대 및 원가 하락 압력 지속"
            ],
            "summary": f"JSON 파싱 오류: {str(e)}. LLM 응답 형식을 확인하세요.",
            "referenced_docs": []
        }
    except Exception as e:
        print(f"[LLM] Error during summarization: {e}")
        import traceback
        traceback.print_exc()
        return {
            "top_trends": [
                "글로벌 EV 판매 성장률 둔화 (오류로 더미 데이터 사용)",
                "보조금·관세 정책 변화가 수요에 영향",
                "LFP/LMFP 채택 확대 및 원가 하락 압력 지속"
            ],
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

    prompt = f"""Analyze the company information and respond with a JSON object in KOREAN language.

**IMPORTANT: Write all content in KOREAN (한글). Only company names and technical terms can be in English.**

기업 {ticker}의 {aspect_map.get(aspect, aspect)} 관련 정보를 분석하여
3-5개의 핵심 포인트를 추출하세요. 각 포인트는 한 문장으로 작성하세요.

**작성 언어**: 반드시 한글로 작성하세요. 기업명, 기술 용어는 영어 가능.

**인용 규칙 (매우 중요)**:
- 각 포인트에서 실제로 해당 정보가 포함된 문서 번호만 인용하세요
- 같은 번호를 연속으로 반복하지 마세요 (예: [1][1] 금지)
- 가능한 한 다양한 문서를 인용하세요
- 확실하지 않으면 인용 번호를 생략하는 것이 낫습니다
- 예시: "Tesla는 Q3 7% 가격 인하로 판매량 15% 증가[2]; 배터리 수직 통합 전략 추진[3]"

문서:
{context}

Please respond with a JSON object in this format (content must be in KOREAN):
{{
  "points": ["포인트1[n]", "포인트2[n]", "포인트3[n]"],
  "referenced_docs": [1, 2, 3]
}}"""

    try:
        from langchain_core.messages import HumanMessage
        import json
        import re

        response = llm.invoke([HumanMessage(content=prompt)])

        # JSON 파싱 시도
        response_text = response.content.strip()

        # 마크다운 코드 블록으로 감싸진 경우 제거
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        result = json.loads(response_text)

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
    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parsing error in company summarization: {e}")
        print(f"[LLM] Raw response: {response.content}")
        return {
            "points": [f"{ticker} 정보 수집 중 (JSON 파싱 오류)"],
            "referenced_docs": []
        }
    except Exception as e:
        print(f"[LLM] Error during company summarization: {e}")
        import traceback
        traceback.print_exc()
        return {
            "points": [f"오류: {str(e)}"],
            "referenced_docs": []
        }


def get_llm_for_text():
    """
    텍스트 생성용 LLM (JSON 모드 없음)
    LangSmith 트레이싱을 지원합니다.
    """
    try:
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[LLM] WARNING: OPENAI_API_KEY not found. Using fallback mode.")
            return None

        # LangSmith 트레이싱 정보 로그
        langchain_tracing = os.getenv("LANGCHAIN_TRACING_V2", "false")
        langchain_project = os.getenv("LANGCHAIN_PROJECT", "default")
        print(f"[LLM] Creating ChatOpenAI (text mode) - Tracing: {langchain_tracing}, Project: {langchain_project}")

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=api_key,
            # JSON 모드 없음 - 일반 텍스트 생성
            metadata={
                "project": langchain_project,
                "agent_type": "section_generator"
            }
        )
        return llm
    except ImportError:
        print("[LLM] WARNING: langchain-openai not installed. Using fallback mode.")
        return None


def generate_section_content(
    section_name: str,
    context: Dict[str, Any]
) -> str:
    """
    리포트 섹션 콘텐츠를 LLM으로 생성합니다.
    """
    llm = get_llm_for_text()  # JSON 모드 없는 LLM 사용

    if not llm:
        return f"<p>{section_name} - LLM이 설정되지 않아 콘텐츠를 생성할 수 없습니다.</p>"

    section_prompts = {
        "demand_pricing": """Write a section about EV demand and pricing strategy in KOREAN language. Use HTML format.

**IMPORTANT: Write all content in KOREAN (한글). Only technical terms, company names can be in English.**

다음 주제를 다루세요:
- 세그먼트별 수요 동향
- ASP(평균 판매가) 변화
- 가격 인하 전략 영향
- 마진 압력 요인

**작성 언어**: 반드시 한글로 작성하세요. 기업명, 기술 용어는 영어 가능.

컨텍스트에서 관련 정보를 추출하여 작성하세요.

컨텍스트:
{context}

HTML로 작성 (제목 h2/h3는 제외, 본문 p/ul/li만 사용, 반드시 한글로):
<p>수요 동향...</p>
<ul><li>포인트1</li><li>포인트2</li></ul>""",

        "policy": """Write a section about EV policy and regulations in KOREAN language. Use HTML format.

**IMPORTANT: Write all content in KOREAN (한글). Only policy names, country names can be in English.**

다음 주제를 다루세요:
- 국가별 보조금 변화
- 관세/무역 정책 영향
- 탄소 규제 동향
- 정책 이벤트 타임라인

**작성 언어**: 반드시 한글로 작성하세요. 정책명, 국가명은 영어 가능.

컨텍스트에서 관련 정보를 추출하여 작성하세요.

컨텍스트:
{context}

HTML로 작성 (제목 h2/h3는 제외, 본문 p/ul/li만 사용, 반드시 한글로):
<p>정책 동향...</p>
<ul><li>포인트1</li><li>포인트2</li></ul>""",

        "battery_supply": """Write a section about battery technology and supply chain in KOREAN language. Use HTML format.

**IMPORTANT: Write all content in KOREAN (한글). Only technical terms, company names can be in English.**

다음 주제를 다루세요:
- 배터리 화학 (LFP/LMFP/NMC) 동향
- kWh당 원가 변화
- 주요 벤더 생산 능력
- 수직 통합 전략

**작성 언어**: 반드시 한글로 작성하세요. 기업명, 기술 용어(LFP, LMFP, NMC 등)는 영어 가능.

컨텍스트에서 관련 정보를 추출하여 작성하세요.

컨텍스트:
{context}

HTML로 작성 (제목 h2/h3는 제외, 본문 p/ul/li만 사용, 반드시 한글로):
<p>배터리 기술 동향...</p>
<ul><li>포인트1</li><li>포인트2</li></ul>""",
    }

    prompt = section_prompts.get(section_name, "")
    if not prompt:
        return f"<p>{section_name} 섹션 프롬프트가 정의되지 않았습니다.</p>"

    try:
        from langchain_core.messages import HumanMessage
        import json

        # .format() 대신 .replace()로 중괄호 에러 방지
        context_json = json.dumps(context, ensure_ascii=False, indent=2)
        prompt_filled = prompt.replace("{context}", context_json)

        response = llm.invoke([HumanMessage(content=prompt_filled)])

        # 응답에서 불필요한 마크다운 코드 블록 제거
        content = response.content.strip()
        if content.startswith("```html"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 중복 인용 제거
        return clean_citations(content)
    except Exception as e:
        print(f"[LLM] Error during section generation: {e}")
        import traceback
        traceback.print_exc()
        return f"<p>오류: {str(e)}</p>"
