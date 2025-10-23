# compiler/report_compiler.py
"""
Report_Compiler Agent
LangGraph 노드 함수들로 구성
LangChain Runnable 기반으로 LangSmith 트레이싱 지원
"""
from typing import Dict, Any
from pathlib import Path
from state import AgentState
from langchain_core.runnables import chain


def _log(msg: str):
    print(f"[ReportCompiler] {msg}")


def _generate_appendix_content(state: AgentState) -> str:
    """Appendix 섹션 상세 내용 생성"""
    from datetime import datetime

    snapshot_date = state.get("snapshot_date", datetime.now().strftime("%Y-%m-%d"))

    company_count = len(state.get('company_dossiers', []))
    stock_count = len(state.get('stock_snapshots', []))
    reference_count = len(state.get('evidence_map', []))

    appendix_html = f"""
    <div class="appendix-section">
        <h3>데이터 개요</h3>
        <ul>
            <li><strong>분석 기준일:</strong> {snapshot_date}</li>
            <li><strong>수집 기업 수:</strong> {company_count}개 기업 프로필</li>
            <li><strong>주가·재무 샘플:</strong> {stock_count}개 티커 (Tavily 웹 검색 기반, 실패 시 내부 폴백 사용)</li>
            <li><strong>참고 문헌:</strong> {reference_count}개 문서 (Tavily 실시간 검색 결과 위주)</li>
        </ul>

        <h3>사용한 산식</h3>
        <ul>
            <li><strong>기간 수익률:</strong> ((마지막 종가 − 시작 종가) ÷ 시작 종가) × 100</li>
            <li><strong>일간 변동성:</strong> 일별 로그수익률의 표준편차 × 100</li>
            <li><strong>환율 보정:</strong> 통화가 다를 경우 USD↔KRW 1,300 기준 단순 환산</li>
        </ul>

        <h3>검증 및 평가 절차</h3>
        <ul>
            <li><strong>수치 일관성 검사:</strong> 리포트에 표기한 period_return_pct와 원시 시계열을 재계산했을 때 오차 ±0.1% 이내인지 확인</li>
            <li><strong>문서 인용 관리:</strong> LLM 요약에서 실제로 활용한 Tavily 문서만 evidence_map에 기록</li>
            <li><strong>데이터 폴백:</strong> 네트워크 미가용 시 준비된 예시 데이터로 보고서 생성을 지속</li>
        </ul>

        <h3>생성 파이프라인 메모</h3>
        <ul>
            <li><strong>LLM:</strong> OpenAI gpt-4o-mini (temperature 0.3, JSON 응답 모드)</li>
            <li><strong>워크플로우:</strong> LangGraph 기반 멀티 에이전트가 시장 요약·기업 분석·보고서 통합 순으로 실행</li>
        </ul>
    </div>
    """

    return appendix_html


@chain
def assemble_outline(state: AgentState) -> Dict[str, Any]:
    """아웃라인 결정을 위한 사전 단계 노드"""
    print(f"[ReportCompiler] assemble_outline")

    outline = state["output"].get("sections", [])

    return {"_outline": outline}


@chain
def compose_sections(state: AgentState) -> Dict[str, Any]:
    """
    HTML 문서 생성 노드 (UTF-8, 한글 폰트 임베딩)
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[ReportCompiler] compose_sections")

    mb = state.get("market_brief", {}) or {}
    cds = state.get("company_dossiers", []) or []
    ss = state.get("stock_snapshots", []) or []

    # 로컬 폰트 파일 → file:// URI (wkhtmltopdf가 접근 가능해야 함)
    font_regular_path = Path("assets/fonts/NotoSansKR-Regular.ttf")
    font_bold_path = Path("assets/fonts/NotoSansKR-Bold.ttf")

    font_regular_uri = font_regular_path.resolve().as_uri() if font_regular_path.exists() else ""
    font_bold_uri = font_bold_path.resolve().as_uri() if font_bold_path.exists() else font_regular_uri

    if not font_regular_uri:
        _log("WARN: assets/fonts/NotoSansKR-Regular.ttf not found. PDF 엔진에 따라 한글이 깨질 수 있습니다.")

    # LLM을 사용하여 섹션 콘텐츠 생성
    from services.llm import generate_section_content

    # 컨텍스트 구성
    context = {
        "market_brief": mb,
        "company_dossiers": cds,
        "stock_snapshots": ss,
        "segments": state.get("segments", []),
        "regions": state.get("regions", []),
        "period": state.get("period", ""),
    }

    # 표지 페이지 - 개선된 디자인
    from datetime import datetime
    report_number = f"EV-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    snapshot_date = state.get('snapshot_date', datetime.now().strftime('%Y-%m-%d'))

    cover_page = f"""
    <div class="cover-page">
        <div class="cover-header">
            <div class="cover-logo">
                <div class="logo-icon">⚡</div>
                <div class="logo-text">AI Market Intelligence</div>
            </div>
        </div>

        <div class="cover-main">
            <div class="cover-title">
                <h1>EV Market Trend Analysis Report</h1>
                <h2>전기차 시장 동향 분석 보고서</h2>
            </div>

            <div class="cover-subtitle">
                <p>AI-Driven Multi-Agent Analysis System</p>
            </div>
        </div>

        <div class="cover-info-box">
            <table class="cover-info-table">
                <tr>
                    <td class="info-label">보고서 번호</td>
                    <td class="info-value">{report_number}</td>
                </tr>
                <tr>
                    <td class="info-label">작성 일시</td>
                    <td class="info-value">{snapshot_date}</td>
                </tr>
                <tr>
                    <td class="info-label">분석 기간</td>
                    <td class="info-value">{state.get('period', 'N/A')}</td>
                </tr>
                <tr>
                    <td class="info-label">분석 대상 지역</td>
                    <td class="info-value">{', '.join(state.get('regions', ['Global']))}</td>
                </tr>
                <tr>
                    <td class="info-label">분석 세그먼트</td>
                    <td class="info-value">{', '.join(state.get('segments', ['All Segments']))}</td>
                </tr>
                <tr>
                    <td class="info-label">분석 시스템</td>
                    <td class="info-value">LangGraph Multi-Agent System</td>
                </tr>
                <tr>
                    <td class="info-label">AI 모델</td>
                    <td class="info-value">gpt-4o-mini</td>
                </tr>
            </table>
        </div>

        <div class="cover-footer">
            <p class="cover-disclaimer">본 보고서는 AI 시스템에 의해 생성된 분석 자료로, 투자 판단의 참고 자료일 뿐 투자 권유가 아닙니다.</p>
            <p class="cover-confidential">CONFIDENTIAL - 본 보고서의 무단 복제 및 배포를 금지합니다.</p>
        </div>
    </div>
    <div class="page-break"></div>
    """

    # 목차 생성
    toc = """
    <div class="toc-page">
        <h1>목차 (Table of Contents)</h1>
        <ul class="toc-list">
            <li><a href="#section-summary">1. SUMMARY</a></li>
            <li><a href="#section-market-overview">2. 시장 개요 & 핵심 트렌드</a></li>
            <li><a href="#section-demand-pricing">3. 수요 & 가격 전략(마진 압력)</a></li>
            <li><a href="#section-policy">4. 정책·규제 Watch</a></li>
            <li><a href="#section-battery">5. 배터리 기술 & 공급망 코어</a></li>
            <li><a href="#section-competition">6. 경쟁 구도 & 지역 하이라이트</a></li>
            <li><a href="#section-implications">7. 전략/투자 시사점</a></li>
            <li><a href="#section-stock">8. 주가/재무 스냅샷</a></li>
            <li><a href="#section-reference">9. REFERENCE</a></li>
            <li><a href="#section-appendix">10. APPENDIX</a></li>
        </ul>
    </div>
    <div class="page-break"></div>
    """

    # 차트 데이터 가져오기 및 중복 제거
    charts = state.get("charts", [])
    chart_by_section = {}
    seen_chart_paths = set()  # 중복 이미지 방지용

    for chart in charts:
        chart_path = chart.get("path", "")
        # 중복된 경로는 스킵
        if chart_path in seen_chart_paths:
            print(f"[ReportCompiler] Skipping duplicate chart: {chart_path}")
            continue

        seen_chart_paths.add(chart_path)
        section = chart.get("section", "unknown")
        if section not in chart_by_section:
            chart_by_section[section] = []
        chart_by_section[section].append(chart)

    # 섹션 조립
    body_parts = []
    body_parts.append(f'<h1 id="section-summary">1. SUMMARY</h1><p>{mb.get("summary","LLM 요약 생성 중...")}</p>')

    trends = mb.get("top_trends", []) or ["트렌드 정보 없음"]
    body_parts.append('<h2 id="section-market-overview">2. 시장 개요 & 핵심 트렌드</h2><ul>' + "".join([f"<li>{t}</li>" for t in trends]) + "</ul>")

    # 시장 트렌드 차트 추가
    if "market" in chart_by_section:
        for chart in chart_by_section["market"]:
            chart_path = Path(chart["path"])
            if chart_path.exists():
                chart_uri = chart_path.resolve().as_uri()
                body_parts.append(f'<div class="chart-container"><img src="{chart_uri}" alt="{chart["alt"]}" class="chart-image"/></div>')
            else:
                body_parts.append(f'<p class="chart-error">차트를 찾을 수 없습니다: {chart["path"]}</p>')

    # LLM으로 각 섹션 콘텐츠 생성
    body_parts.append('<h2 id="section-demand-pricing">3. 수요 & 가격 전략(마진 압력)</h2>')
    demand_content = generate_section_content("demand_pricing", context)
    body_parts.append(demand_content)

    body_parts.append('<h2 id="section-policy">4. 정책·규제 Watch</h2>')
    policy_content = generate_section_content("policy", context)
    body_parts.append(policy_content)

    body_parts.append('<h2 id="section-battery">5. 배터리 기술 & 공급망 코어</h2>')
    battery_content = generate_section_content("battery_supply", context)
    body_parts.append(battery_content)

    # 경쟁 구도 섹션 - 기업 정보가 있으면 표시
    body_parts.append('<h2 id="section-competition">6. 경쟁 구도 & 지역 하이라이트</h2>')

    # 기업 하이라이트 차트 추가
    if "company" in chart_by_section:
        for chart in chart_by_section["company"]:
            chart_path = Path(chart["path"])
            if chart_path.exists():
                chart_uri = chart_path.resolve().as_uri()
                body_parts.append(f'<div class="chart-container"><img src="{chart_uri}" alt="{chart["alt"]}" class="chart-image"/></div>')

    if cds:
        body_parts.append("<h3>주요 기업 하이라이트</h3><ul>")
        for c in cds:
            ticker = c.get('ticker', 'N/A')
            highlights = c.get('business_highlights', [])
            if highlights and len(highlights) > 0:
                body_parts.append(f"<li><strong>{ticker}</strong>: {'; '.join(highlights[:3])}</li>")
            else:
                body_parts.append(f"<li><strong>{ticker}</strong>: 정보 수집 중</li>")
        body_parts.append("</ul>")
    else:
        body_parts.append("<p>기업 데이터가 수집되지 않았습니다.</p>")

    # 전략/투자 시사점 섹션
    body_parts.append('<h2 id="section-implications">7. 전략/투자 시사점</h2>')
    persona = state.get("persona", "corporate_strategy")

    # 실제 데이터 기반 시사점 생성
    implications = []

    # 시장 트렌드 기반 시사점
    if trends and len(trends) > 0:
        implications.append(f"<li><strong>[시장 분석]</strong> {trends[0][:100]}... 에 대한 대응 전략 수립 필요</li>")

    # 기업 리스크 기반 시사점
    if cds:
        for c in cds[:2]:  # 상위 2개 기업만
            risks = c.get('risk_factors', [])
            if risks and len(risks) > 0:
                implications.append(f"<li><strong>[{c['ticker']} 리스크]</strong> {risks[0][:100]}...</li>")

    # 주가 변동성 기반 시사점
    if ss:
        high_vol_stocks = [s for s in ss if s.get('volatility', 0) > 2.0]
        if high_vol_stocks:
            tickers = ', '.join([s['ticker'] for s in high_vol_stocks[:3]])
            implications.append(f"<li><strong>[변동성 모니터링]</strong> {tickers} 등 고변동성 종목에 대한 리스크 관리 강화</li>")

    # 페르소나별 기본 시사점 추가
    if persona == "retail_investor":
        implications.append("<li><strong>[단기 전략]</strong> 실적 발표 시즌 변동성 대응 전략 수립</li>")
        implications.append("<li><strong>[장기 전략]</strong> EV 공급망 관련 테마주 포트폴리오 구성 검토</li>")
    else:
        implications.append("<li><strong>[전략적 과제]</strong> 배터리 공급망 다변화 및 현지화 추진</li>")
        implications.append("<li><strong>[운영 효율화]</strong> 가격 경쟁력 확보를 위한 원가 절감 이니셔티브</li>")

    if implications:
        body_parts.append("<ul>" + "\n".join(implications) + "</ul>")
    else:
        body_parts.append("<p>시사점 생성을 위한 데이터가 부족합니다.</p>")

    # 주가/재무 스냅샷 섹션
    body_parts.append('<h2 id="section-stock">8. 주가/재무 스냅샷</h2>')

    # 주가 수익률 차트 추가
    if "stock" in chart_by_section:
        for chart in chart_by_section["stock"]:
            chart_path = Path(chart["path"])
            if chart_path.exists():
                chart_uri = chart_path.resolve().as_uri()
                body_parts.append(f'<div class="chart-container"><img src="{chart_uri}" alt="{chart["alt"]}" class="chart-image"/></div>')

    if ss:
        body_parts.append("<ul>" + "".join([f"<li>{s['ticker']}: return {s['period_return_pct']}%, vol {s['volatility']}</li>" for s in ss]) + "</ul>")
    else:
        body_parts.append("<p>데이터 준비중</p>")

    refs = state.get('evidence_map', []) or []
    body_parts.append('<h2 id="section-reference">9. REFERENCE</h2><ol>' +
                      "".join([f"<li>{e.get('title')} ({e.get('date')}) - {e.get('url')}</li>" for e in refs]) +
                      "</ol>")

    # Appendix 섹션 - 상세 내용 생성
    body_parts.append('<h2 id="section-appendix">10. APPENDIX</h2>')
    body_parts.append(_generate_appendix_content(state))

    body_html = "\n".join(body_parts)

    # 완전한 HTML 문서(UTF-8 + 폰트 임베딩 + 기본 스타일)
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>EV Trend Report</title>
<style>
  /* 한글 폰트 임베딩 (wkhtmltopdf가 file:// 접근 가능해야 함) */
  {'@font-face { font-family: "NotoSansKR"; src: url("' + font_regular_uri + '") format("truetype"); font-weight: 400; font-style: normal; }' if font_regular_uri else ''}
  {'@font-face { font-family: "NotoSansKR"; src: url("' + font_bold_uri + '") format("truetype"); font-weight: 700; font-style: normal; }' if font_bold_uri else ''}

  html, body {{
    font-family: {"'NotoSansKR'," if font_regular_uri else ""} 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
    font-weight: 400; font-size: 12px; line-height: 1.55;
    color: #111; margin: 0; padding: 0;
  }}

  /* 표지 스타일 - 개선된 디자인 */
  .cover-page {{
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 48px 64px;
    background: linear-gradient(135deg, #f5f7fa 0%, #e8f0ff 50%, #cdd8ff 100%);
    color: #1b263b;
  }}

  .cover-header {{
    text-align: left;
  }}

  .cover-logo {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}

  .logo-icon {{
    font-size: 36px;
    background: #1b263b;
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
  }}

  .logo-text {{
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: #1b263b;
  }}

  .cover-main {{
    text-align: center;
    margin: 40px 0;
  }}

  .cover-title h1 {{
    font-size: 46px;
    font-weight: 700;
    margin: 0 0 20px;
    letter-spacing: -0.5px;
    color: #1b263b;
  }}

  .cover-title h2 {{
    font-size: 30px;
    font-weight: 500;
    margin: 0 0 28px;
    color: #334155;
  }}

  .cover-subtitle {{
    margin-top: 20px;
  }}

  .cover-subtitle p {{
    font-size: 16px;
    font-weight: 400;
    letter-spacing: 0.8px;
    color: #52606d;
  }}

  .cover-info-box {{
    background: #ffffff;
    border-radius: 16px;
    padding: 36px 40px;
    border: 1px solid #d0d7e2;
    box-shadow: 0 12px 24px rgba(27, 38, 59, 0.08);
  }}

  .cover-info-table {{
    width: 100%;
    border-collapse: collapse;
  }}

  .cover-info-table tr {{
    border-bottom: 1px solid #e2e8f0;
  }}

  .cover-info-table tr:last-child {{
    border-bottom: none;
  }}

  .cover-info-table td {{
    padding: 14px 20px;
    text-align: left;
  }}

  .info-label {{
    font-weight: 600;
    font-size: 13px;
    color: #475569;
    width: 35%;
  }}

  .info-value {{
    font-weight: 600;
    font-size: 14px;
    color: #1b263b;
  }}

  .cover-footer {{
    text-align: center;
    margin-top: 40px;
    color: #64748b;
    font-size: 12px;
  }}

  .cover-disclaimer {{
    margin: 8px 0;
  }}

  .cover-confidential {{
    font-weight: 600;
    letter-spacing: 1px;
    color: #475569;
  }}

  /* 목차 스타일 */
  .toc-page {{
    min-height: 100vh;
    padding: 60px 40px;
  }}

  .toc-page h1 {{
    font-size: 32px;
    font-weight: 700;
    margin: 0 0 40px;
    padding-bottom: 16px;
    border-bottom: 3px solid #667eea;
  }}

  .toc-list {{
    list-style: none;
    padding: 0;
    margin: 0;
  }}

  .toc-list li {{
    margin: 18px 0;
    padding: 12px 20px;
    background: #f8f9fa;
    border-radius: 6px;
    transition: background 0.2s;
  }}

  .toc-list li:hover {{
    background: #e9ecef;
  }}

  .toc-list a {{
    font-size: 16px;
    color: #495057;
    text-decoration: none;
    font-weight: 500;
  }}

  .toc-list a:hover {{
    color: #667eea;
  }}

  /* 페이지 구분 */
  .page-break {{
    page-break-after: always;
  }}

  /* 본문 스타일 */
  body > h1, body > h2, body > h3, body > p, body > ul, body > ol {{
    padding-left: 40px;
    padding-right: 40px;
  }}

  h1 {{
    font-weight: 700;
    font-size: 26px;
    margin: 40px 0 20px;
    padding-top: 20px;
    border-top: 2px solid #dee2e6;
  }}

  h2 {{
    font-weight: 700;
    font-size: 20px;
    margin: 30px 0 16px;
    color: #495057;
  }}

  h3 {{
    font-weight: 600;
    font-size: 16px;
    margin: 20px 0 12px;
    color: #6c757d;
  }}

  ul {{
    margin: 0 0 16px 58px;
    line-height: 1.8;
  }}

  ol {{
    margin: 0 0 16px 58px;
    line-height: 1.8;
  }}

  p {{
    margin: 0 0 12px;
    line-height: 1.7;
  }}

  a {{
    color: #0a58ca;
    text-decoration: none;
  }}

  a:hover {{
    text-decoration: underline;
  }}

  li {{
    margin-bottom: 8px;
  }}

  /* 차트 스타일 */
  .chart-container {{
    margin: 24px 40px;
    padding: 20px;
    background: #f8f9fa;
    border-radius: 8px;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }}

  .chart-image {{
    max-width: 100%;
    height: auto;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }}

  .chart-error {{
    color: #dc3545;
    font-style: italic;
    padding: 20px 40px;
  }}

  /* Appendix 섹션 스타일 */
  .appendix-section {{
    padding: 20px 40px;
  }}

  .appendix-section h3 {{
    font-weight: 700;
    font-size: 18px;
    margin: 30px 0 16px;
    color: #2c3e50;
    padding-bottom: 8px;
    border-bottom: 2px solid #3498db;
  }}

  .appendix-section h4 {{
    font-weight: 600;
    font-size: 15px;
    margin: 24px 0 12px;
    color: #34495e;
  }}

  .appendix-section ul {{
    margin: 12px 0 16px 20px;
    line-height: 1.8;
  }}

  .appendix-section ol {{
    margin: 12px 0 16px 20px;
    line-height: 1.8;
  }}

  .appendix-section li {{
    margin-bottom: 10px;
  }}

  .appendix-section strong {{
    color: #2c3e50;
    font-weight: 600;
  }}
</style>
</head>
<body>
{cover_page}
{toc}
{body_html}
</body>
</html>"""

    return {"draft_report_md": html}


@chain
def export_pdf(state: AgentState) -> Dict[str, Any]:
    """
    PDF 내보내기 노드 (pdfkit → WeasyPrint → ReportLab 폴백)
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[ReportCompiler] export_pdf")

    # 출력 경로
    out_dir = Path("outputs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "ev_trend_report.html"
    pdf_path = out_dir / "ev_trend_report.pdf"

    # HTML 저장
    html_path.write_text(state["draft_report_md"], encoding="utf-8")

    ok = False

    # 1) pdfkit(wkhtmltopdf) 1순위
    try:
        import pdfkit
        wkhtml_bin_candidates = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",  # Windows 기본
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            "/usr/bin/wkhtmltopdf",
            "/usr/local/bin/wkhtmltopdf",
        ]
        config = None
        for cand in wkhtml_bin_candidates:
            if Path(cand).exists():
                config = pdfkit.configuration(wkhtmltopdf=cand)
                _log(f"wkhtmltopdf found: {cand}")
                break

        options = {
            "encoding": "UTF-8",
            "enable-local-file-access": None,  # 로컬 폰트/이미지 접근 허용
            "quiet": "",                       # 과도한 로그 억제(선택)
            "margin-top": "10mm",
            "margin-right": "10mm",
            "margin-bottom": "12mm",
            "margin-left": "10mm",
        }
        _log("try pdfkit(wkhtmltopdf)")
        pdfkit.from_file(str(html_path), str(pdf_path), configuration=config, options=options)
        ok = True
        _log("pdfkit success")
    except Exception as e:
        _log(f"pdfkit failed: {e}")

    # 2) WeasyPrint 시도
    if not ok:
        try:
            from weasyprint import HTML
            _log("try WeasyPrint")
            HTML(string=state["draft_report_md"]).write_pdf(str(pdf_path))
            ok = True
            _log("WeasyPrint success")
        except Exception as e:
            _log(f"WeasyPrint failed: {e}")

    # 3) ReportLab 폴백 (한글 폰트 등록)
    if not ok:
        _log("fallback to ReportLab")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import re

            # 한글 폰트 등록 시도
            font_name = "Helvetica"
            font_regular = Path("assets/fonts/NotoSansKR-Regular.ttf")
            if font_regular.exists():
                try:
                    pdfmetrics.registerFont(TTFont("NotoSansKR", str(font_regular)))
                    font_name = "NotoSansKR"
                    _log("ReportLab: NotoSansKR registered")
                except Exception as fe:
                    _log(f"ReportLab font register failed: {fe} (fallback Helvetica)")

            c = canvas.Canvas(str(pdf_path), pagesize=A4)
            c.setFont(font_name, 10)
            text = c.beginText(40, 800)

            # HTML 태그 제거용 아주 단순한 스트립(정교한 렌더링은 상위 엔진에서 처리)
            plain = re.sub(r"<[^>]+>", "", state["draft_report_md"])
            for line in plain.split("\n"):
                # 너무 긴 줄은 잘라서 넣기 (간단 폴백)
                line = line.strip()
                while len(line) > 110:
                    text.textLine(line[:110])
                    line = line[110:]
                    if text.getY() < 60:
                        c.drawText(text)
                        c.showPage()
                        text = c.beginText(40, 800)
                        c.setFont(font_name, 10)
                text.textLine(line)
                if text.getY() < 60:
                    c.drawText(text)
                    c.showPage()
                    text = c.beginText(40, 800)
                    c.setFont(font_name, 10)

            c.drawText(text)
            c.showPage()
            c.save()
            ok = True
            _log("ReportLab fallback success")
        except Exception as e:
            _log(f"ReportLab failed: {e}")

    report_path = str(pdf_path if ok else html_path)

    # _qa_document_ok는 post_export_qc에서 업데이트하므로 여기서는 제거
    return {
        "report_path": report_path
    }


@chain
def post_export_qc(state: AgentState) -> Dict[str, Any]:
    """
    사후 QC 노드 (간단 플래그)
    LangChain Runnable로 래핑되어 LangSmith에 트레이싱됩니다.
    """
    print(f"[ReportCompiler] post_export_qc")

    # PDF 생성 여부만 확인
    document_ok = Path(state.get("report_path", "")).suffix.lower() == ".pdf"
    print(f"[ReportCompiler] post_export_qc - document_ok: {document_ok}")

    # _qa_document_ok 필드 업데이트 (버그 수정)
    return {"_qa_document_ok": document_ok}
