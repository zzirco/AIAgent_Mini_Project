# compiler/report_compiler.py
"""
Report_Compiler Agent
LangGraph 노드 함수들로 구성
"""
from typing import Dict, Any
from pathlib import Path
from state import AgentState


def _log(msg: str):
    print(f"[ReportCompiler] {msg}")


def assemble_outline(state: AgentState) -> Dict[str, Any]:
    """아웃라인 결정을 위한 사전 단계 노드"""
    print(f"[ReportCompiler] assemble_outline")

    outline = state["output"].get("sections", [])

    return {"_outline": outline}


def compose_sections(state: AgentState) -> Dict[str, Any]:
    """
    HTML 문서 생성 노드 (UTF-8, 한글 폰트 임베딩)
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

    # 섹션 조립
    body_parts = []
    body_parts.append(f"<h1>SUMMARY</h1><p>{mb.get('summary','LLM 요약 생성 중...')}</p>")

    trends = mb.get("top_trends", []) or ["트렌드 정보 없음"]
    body_parts.append("<h2>시장 개요 & 핵심 트렌드</h2><ul>" + "".join([f"<li>{t}</li>" for t in trends]) + "</ul>")

    # LLM으로 각 섹션 콘텐츠 생성
    body_parts.append("<h2>수요 & 가격 전략(마진 압력)</h2>")
    demand_content = generate_section_content("demand_pricing", context)
    body_parts.append(demand_content)

    body_parts.append("<h2>정책·규제 Watch</h2>")
    policy_content = generate_section_content("policy", context)
    body_parts.append(policy_content)

    body_parts.append("<h2>배터리 기술 & 공급망 코어</h2>")
    battery_content = generate_section_content("battery_supply", context)
    body_parts.append(battery_content)

    # 경쟁 구도 섹션 - 기업 정보가 있으면 표시
    body_parts.append("<h2>경쟁 구도 & 지역 하이라이트</h2>")
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
    body_parts.append("<h2>전략/투자 시사점</h2>")
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

    if ss:
        body_parts.append("<h2>주가/재무 스냅샷</h2>"
                          "<ul>" + "".join([f"<li>{s['ticker']}: return {s['period_return_pct']}%, vol {s['volatility']}</li>" for s in ss]) + "</ul>")
    else:
        body_parts.append("<h2>주가/재무 스냅샷</h2><p>데이터 준비중</p>")

    refs = state.get('evidence_map', []) or []
    body_parts.append("<h2>REFERENCE</h2><ol>" +
                      "".join([f"<li>{e.get('title')} ({e.get('date')}) - {e.get('url')}</li>" for e in refs]) +
                      "</ol>")

    body_parts.append(f"<h2>APPENDIX</h2>"
                      f"<p>Data snapshot: {state.get('snapshot_date')}</p>"
                      "<p>지표 정의·산식 / 데이터 검증 절차(날짜·수치 일관성 기준) — 데이터 준비중</p>")

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
    color: #111; margin: 0; padding: 24px;
  }}
  h1 {{ font-weight:700; font-size: 22px; margin: 0 0 12px; }}
  h2 {{ font-weight:700; font-size: 16px; margin: 18px 0 8px; }}
  ul {{ margin: 0 0 8px 18px; }}
  ol {{ margin: 0 0 8px 18px; }}
  p  {{ margin: 0 0 8px; }}
  a  {{ color: #0a58ca; text-decoration: none; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""

    return {"draft_report_md": html}


def export_pdf(state: AgentState) -> Dict[str, Any]:
    """
    PDF 내보내기 노드 (pdfkit → WeasyPrint → ReportLab 폴백)
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


def post_export_qc(state: AgentState) -> Dict[str, Any]:
    """
    사후 QC 노드 (간단 플래그)
    """
    print(f"[ReportCompiler] post_export_qc")

    # PDF 생성 여부만 확인
    document_ok = Path(state.get("report_path", "")).suffix.lower() == ".pdf"
    print(f"[ReportCompiler] post_export_qc - document_ok: {document_ok}")

    # _qa_document_ok 필드 업데이트 (버그 수정)
    return {"_qa_document_ok": document_ok}
