# app.py
"""
EV Market Trend Analysis Agent - Main Entry Point
LangGraph 기반 Multi-Agent 워크플로우 실행
"""
from pathlib import Path
import uuid
import json
import sys
import yaml
from datetime import datetime
import os

# .env 파일 로드 (OPENAI_API_KEY, LANGCHAIN_API_KEY 등)
# 중요: 이 설정은 다른 모든 import 전에 실행되어야 합니다
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[Main] .env file loaded")

    # OpenAI API Key 확인
    if os.getenv("OPENAI_API_KEY"):
        print("[Main] ✓ OPENAI_API_KEY found")
    else:
        print("[Main] ✗ WARNING: OPENAI_API_KEY not found in environment")

    # LangSmith 트레이싱 설정 (LLM 생성 전에 반드시 설정되어야 함)
    langchain_api_key = os.getenv("LANGCHAIN_API_KEY")
    if langchain_api_key:
        # 트레이싱 활성화
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_API_KEY"] = langchain_api_key

        # 프로젝트 이름 설정
        project_name = os.getenv("LANGCHAIN_PROJECT", "ev-market-trend-analysis")
        os.environ["LANGCHAIN_PROJECT"] = project_name

        print(f"[Main] ✓ LangSmith tracing ENABLED")
        print(f"[Main]   - Project: {project_name}")
        print(f"[Main]   - Endpoint: {os.environ['LANGCHAIN_ENDPOINT']}")
        print(f"[Main]   - API Key: {langchain_api_key[:10]}...")
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        print("[Main] ✗ LangSmith tracing DISABLED (LANGCHAIN_API_KEY not found)")
        print("[Main]   To enable: Set LANGCHAIN_API_KEY in .env file")

except ImportError:
    print("[Main] WARNING: python-dotenv not installed. Run: pip install python-dotenv")
except Exception as e:
    print(f"[Main] WARNING: Failed to load .env file: {e}")

from workflow import compile_workflow


def main(cfg_path: str = "config.yaml"):
    """
    메인 실행 함수
    1. 설정 파일 로드
    2. 초기 State 구성
    3. LangGraph 워크플로우 실행
    4. 결과 저장
    """
    # 설정 파일 로드
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 출력 디렉토리 생성
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/charts").mkdir(parents=True, exist_ok=True)
    Path("outputs/reports").mkdir(parents=True, exist_ok=True)

    # 초기 State 구성
    initial_state = {
        "run_id": f"run-{uuid.uuid4().hex[:8]}",
        "period": cfg["period"],
        "regions": cfg.get("regions", ["global"]),
        "focus_issues": cfg.get("focus_issues", []),
        "segments": cfg.get("segments", []),
        "depth": cfg.get("depth", "standard"),
        "snapshot_date": cfg.get("snapshot_date", datetime.now().strftime("%Y-%m-%d")),
        "output": cfg.get("output", {"format": "pdf", "language": "ko", "sections": []}),
        "constraints": cfg.get("constraints", {"max_pages": 12, "max_charts": 6, "min_references": 8}),
        "benchmarks": cfg.get("benchmarks", []),
        "policies": cfg.get("policies", []),
        "financials": cfg.get("financials", {
            "base_currency": "USD",
            "multiples": ["PS", "EV_EBITDA"],
            "event_window_days": 7
        }),
        "data_prefs": cfg.get("data_prefs", {
            "language_priority": ["ko", "en"],
            "source_priority": ["공시", "IR", "정부통계", "언론"]
        }),
        "risk_lens": cfg.get("risk_lens", {
            "demand": 0.35,
            "policy": 0.25,
            "supply_chain": 0.2,
            "tech": 0.2
        }),
        "cadence": cfg.get("cadence", {"mode": "adhoc"}),
        "persona": cfg.get("persona", "corporate_strategy"),
        # 산출물 컨테이너 (빈 리스트/딕셔너리로 초기화)
        "raw_docs": [],
        "indexed_ids": [],
        "market_brief": {},
        "company_dossiers": [],
        "stock_snapshots": [],
        "charts": [],
        "evidence_map": [],
        "draft_report_md": "",
        "report_path": "",
        "qa_metrics": {},
        "errors": [],
        # 내부 캐시
        "_chart_specs": [],
        "_outline": [],
        "_company_index": None,
        "_series": {},
        "_funds": {},
        # QA 관련 개별 필드
        "_qa_citation_coverage": 0.0,
        "_qa_number_consistency": True,
        "_qa_document_ok": False,
    }

    print(f"[Main] Starting EV Market Trend Analysis - run_id: {initial_state['run_id']}")
    print(f"[Main] Period: {initial_state['period']}, Regions: {initial_state['regions']}")
    print(f"[Main] Benchmarks: {initial_state['benchmarks']}")

    # LangGraph 워크플로우 컴파일
    print("[Main] Compiling LangGraph workflow...")
    app = compile_workflow()

    # 워크플로우 실행
    print("[Main] Executing workflow...")
    final_state = app.invoke(initial_state)

    # 결과 저장
    print("[Main] Saving results...")
    evidence_path = Path("outputs/evidence.jsonl")
    with open(evidence_path, "w", encoding="utf-8") as f:
        for ev in final_state.get("evidence_map", []):
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # 결과 출력
    print(f"\n{'='*60}")
    print(f"[OK] Report generated: {final_state.get('report_path', 'N/A')}")
    print(f"[OK] Evidence saved: {evidence_path}")
    print(f"[OK] QA Metrics:")
    qa_metrics = final_state.get("qa_metrics", {})
    print(f"     - Citation Coverage: {qa_metrics.get('citation_coverage', 0):.2%}")
    print(f"     - Number Consistency: {qa_metrics.get('number_consistency', False)}")
    print(f"     - Document OK: {qa_metrics.get('document_ok', False)}")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) if len(sys.argv) > 1 else main())
