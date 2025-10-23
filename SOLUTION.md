# "데이터 준비중" 문제 해결 가이드

## 📋 문제 원인

PDF 리포트에 "데이터 준비중"이 표시되는 이유는 **LLM이 실제로 호출되지 않기 때문**입니다.

### 현재 구조의 문제점

1. **데이터 수집**: ✅ services/ingest.py가 더미 데이터 제공
2. **RAG 검색**: ✅ services/rag.py가 키워드 매칭 수행
3. **LLM 요약/생성**: ❌ **실제 LLM 호출 없음**
4. **리포트 작성**: ❌ **하드코딩된 "데이터 준비중" 텍스트**

### 구체적 문제 파일

#### 1. [agents/market_researcher.py:36-70](agents/market_researcher.py)
```python
def extract_market_signals(state: AgentState) -> Dict[str, Any]:
    # TODO: 실제로는 RAG + LLM을 사용하여 트렌드 추출
    # 현재는 더미 데이터로 구성  ← 문제!
    market_brief = {
        "top_trends": ["하드코딩된 텍스트"]  # LLM 호출 없음
    }
```

#### 2. [agents/company_analyzer.py:48-100](agents/company_analyzer.py)
```python
def compose_company_dossiers(state: AgentState) -> Dict[str, Any]:
    # 간단 요약(더미): passage title을 불릿으로 사용 (실전: LLM 요약 결과 사용)
    business = [p.get("title") or "Business highlight" for p in biz_passages]  # LLM 없음
```

#### 3. [compiler/report_compiler.py:51-76](compiler/report_compiler.py)
```python
body_parts.append("<h2>수요 & 가격 전략(마진 압력)</h2>"
                  "<p>세그먼트 수요/점유율, ASP vs 판매량, 가격 인하 타임라인 — 데이터 준비중</p>")
# ← 하드코딩된 "데이터 준비중" 텍스트!
```

#### 4. prompts/ 폴더의 파일들이 사용되지 않음
- `market_prompt.md`
- `company_prompt.md`
- `summary_prompt.md`

**→ 코드에서 로드하거나 사용하지 않음**

---

## 🔧 해결 방법

### 방법 1: LLM 통합 (권장)

실제 OpenAI GPT-4o-mini를 사용하여 콘텐츠 생성

#### Step 1: 환경 변수 설정

`.env` 파일 생성:
```bash
OPENAI_API_KEY=your-api-key-here
```

#### Step 2: 의존성 설치 확인

```bash
pip install langchain-openai python-dotenv
```

#### Step 3: LLM 서비스 파일 생성

이미 생성된 `services/llm.py`를 확인하세요.

#### Step 4: 각 에이전트에 LLM 통합

**A) market_researcher.py 수정**

```python
def extract_market_signals(state: AgentState) -> Dict[str, Any]:
    """LLM을 사용하여 실제 트렌드 추출"""
    from services.llm import summarize_market_trends

    raw_docs = state.get("raw_docs", [])
    result = summarize_market_trends(
        documents=raw_docs,
        focus_issues=state["focus_issues"],
        regions=state["regions"],
        period=state["period"]
    )

    market_brief = {
        "period": state["period"],
        "top_trends": result.get("top_trends", []),
        "summary": result.get("summary", ""),
        # ...
    }
    return {"market_brief": market_brief}
```

**B) company_analyzer.py 수정**

```python
def compose_company_dossiers(state: AgentState) -> Dict[str, Any]:
    """LLM으로 기업 정보 요약"""
    from services.llm import summarize_company_info

    for tk in state.get("benchmarks", []):
        biz_passages = rag.query(idx, f"{tk} business strategy", ...)

        # LLM으로 실제 요약
        business = summarize_company_info(tk, biz_passages, "business")
        risks = summarize_company_info(tk, risk_passages, "risk")
        roadmap = summarize_company_info(tk, roadmap_passages, "roadmap")

        dossiers.append({
            "ticker": tk,
            "business_highlights": business,
            "risk_factors": risks,
            "roadmap": roadmap,
        })
```

**C) report_compiler.py 수정**

```python
def compose_sections(state: AgentState) -> Dict[str, Any]:
    """LLM으로 섹션 콘텐츠 생성"""
    from services.llm import generate_section_content

    # 기존 하드코딩 대신 LLM 사용
    context = {
        "market_brief": state.get("market_brief"),
        "company_dossiers": state.get("company_dossiers"),
        "stock_snapshots": state.get("stock_snapshots"),
    }

    # 각 섹션별로 LLM 호출
    demand_pricing_content = generate_section_content("demand_pricing", context)
    policy_content = generate_section_content("policy", context)
    battery_content = generate_section_content("battery_supply", context)

    body_parts.append(f"<h2>수요 & 가격 전략(마진 압력)</h2>{demand_pricing_content}")
    body_parts.append(f"<h2>정책·규제 Watch</h2>{policy_content}")
    body_parts.append(f"<h2>배터리 기술 & 공급망 코어</h2>{battery_content}")
```

---

### 방법 2: 수동 콘텐츠 작성 (임시)

LLM 없이 더 나은 콘텐츠를 하드코딩하여 제공

#### report_compiler.py 개선

```python
def compose_sections(state: AgentState) -> Dict[str, Any]:
    mb = state.get("market_brief", {})
    cds = state.get("company_dossiers", [])
    ss = state.get("stock_snapshots", [])

    # 실제 데이터를 사용하여 콘텐츠 구성
    body_parts.append(f"<h2>수요 & 가격 전략(마진 압력)</h2>")

    # 세그먼트 정보
    segments = state.get("segments", [])
    if segments:
        body_parts.append(f"<p>분석 세그먼트: {', '.join(segments)}</p>")

    # 가격 변화
    metrics = mb.get("metrics", {})
    if metrics:
        price_change = metrics.get("avg_price_change_pct", 0)
        body_parts.append(f"<p>평균 판매가 변화율: {price_change}%</p>")

    # 회사별 가격 전략
    if cds:
        body_parts.append("<ul>")
        for c in cds:
            highlights = c.get("business_highlights", [])
            if highlights:
                body_parts.append(f"<li><strong>{c['ticker']}</strong>: {highlights[0]}</li>")
        body_parts.append("</ul>")
    else:
        body_parts.append("<p>기업 데이터가 수집되지 않았습니다.</p>")
```

---

## 🎯 권장 솔루션

### 단계별 구현

#### Phase 1: 즉시 개선 (1-2시간)
1. ✅ `services/llm.py` 이미 생성됨
2. `market_researcher.py`에 LLM 통합
3. 환경 변수 설정 및 테스트

#### Phase 2: 완전한 통합 (2-4시간)
1. `company_analyzer.py`에 LLM 통합
2. `report_compiler.py`에 섹션별 LLM 통합
3. 프롬프트 템플릿 활용

#### Phase 3: 고급 기능 (4-8시간)
1. RAG 검색 개선 (벡터 임베딩)
2. 실제 뉴스/IR 데이터 수집 (크롤링/API)
3. 차트 생성 로직 구현
4. 멀티모달 분석 (이미지/테이블)

---

## 🧪 테스트 방법

### 1. LLM 연결 테스트

```python
# test_llm.py
from services.llm import get_llm, summarize_market_trends

llm = get_llm()
if llm:
    print("✅ LLM 연결 성공")

    result = summarize_market_trends(
        documents=[{"text": "EV sales grew 20% in Q1..."}],
        focus_issues=["demand"],
        regions=["global"],
        period="last_90d"
    )
    print(f"✅ 트렌드 생성: {result}")
else:
    print("❌ LLM 연결 실패 - OPENAI_API_KEY 확인 필요")
```

### 2. 전체 워크플로우 테스트

```bash
python app.py
```

생성된 PDF를 확인하여 "데이터 준비중" 대신 실제 콘텐츠가 있는지 확인

---

## 🐛 트러블슈팅

### LLM 호출 실패

**증상**: "LLM 미사용 더미 데이터" 메시지
**원인**: OPENAI_API_KEY 미설정
**해결**: `.env` 파일에 API 키 추가

```bash
# .env
OPENAI_API_KEY=sk-proj-...
```

### JSON 파싱 오류

**증상**: `json.loads() failed`
**원인**: LLM 응답이 JSON 형식이 아님
**해결**: 프롬프트에 "JSON 형식으로만 응답" 명시

### 토큰 제한 초과

**증상**: `RateLimitError` 또는 `TokenLimitExceeded`
**원인**: 문서가 너무 많거나 김
**해결**: 문서 수 제한 (예: 최대 10개)

```python
documents=raw_docs[:10]  # 상위 10개만 사용
```

---

## 📊 기대 효과

### Before (현재)
```
수요 & 가격 전략(마진 압력)
세그먼트 수요/점유율, ASP vs 판매량, 가격 인하 타임라인 — 데이터 준비중
```

### After (LLM 통합 후)
```
수요 & 가격 전략(마진 압력)

분석 기간(2025-07-22 ~ 2025-10-22) 동안 EV 시장은 다음과 같은 특징을 보였습니다:

1. 세그먼트별 수요: Passenger 차량은 전년 대비 12% 성장한 반면, SUV 세그먼트는
   8% 감소하여 소비자 선호도 변화가 관찰됨

2. 평균 판매가(ASP): 전 세그먼트 평균 5.1% 하락, 특히 Tesla와 BYD의
   공격적 가격 인하 정책이 시장 전반에 압력으로 작용

3. 가격 인하 전략:
   - TSLA: 2025년 Q3 평균 7% 가격 인하, 판매량 15% 증가
   - BYDDF: 신모델 출시와 함께 entry-level 가격대 공략
   - VWAGY: 배터리 원가 절감을 통한 마진 방어 전략

4. 마진 압력 요인:
   - 배터리 원자재 가격 변동성
   - 중국 제조사의 공격적 가격 경쟁
   - 정부 보조금 축소로 인한 실효 가격 상승
```

---

## 📚 다음 단계

1. ✅ LLM 서비스 구현 완료
2. ⬜ 각 에이전트에 LLM 통합
3. ⬜ 프롬프트 템플릿 최적화
4. ⬜ 실제 데이터 소스 연결
5. ⬜ 차트 생성 로직 구현
6. ⬜ 고급 RAG (벡터 임베딩) 적용

---

## 💡 팁

- **개발 중**: `depth: "quick"` 설정으로 빠른 테스트
- **프로덕션**: `depth: "standard"` 또는 `"deep"`으로 품질 향상
- **비용 절감**: GPT-4o-mini 대신 GPT-3.5-turbo 사용 가능
- **오프라인 테스트**: LLM 없이도 기본 동작하도록 폴백 로직 유지
