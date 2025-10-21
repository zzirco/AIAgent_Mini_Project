# EV Market Trend Analysis Agent

본 프로젝트는 **전기차(EV) 시장 트렌드 분석** 에이전트를 설계하고 구현한 실습 프로젝트입니다.

## Overview

* **Objective** : 글로벌 EV 시장·배터리 밸류체인·정책 이슈를 자동 수집·요약·정량화하여 **투자·전략 의사결정용 리포트**를 생성
* **Methods** : Multi-Agent Orchestration, Agentic RAG, Evidence-grounded Summarization, Financial Snapshotting
* **Tools** : LangGraph, LangChain, yfinance/재무API, PDF/HTML Parsers, WeasyPrint(or LaTeX)

## Features

* **시장·정책·기술 이슈 자동 수집/요약**(기간/지역/이슈/세그먼트 기반)
* **기업 동향 & 밸류에이션 비교**(완성차/배터리사 바스켓 기준)
* **근거 각주(REFERENCE)와 차트 포함 PDF 리포트** 자동 생성

## Tech Stack

| Category  | Details                                            |
| --------- | -------------------------------------------------- |
| Framework | LangGraph, LangChain, Python                       |
| LLM       | GPT-4o-mini via OpenAI API (configurable)          |
| Retrieval | FAISS or Chroma (Agentic RAG)                      |
| Embedding | multilingual-e5-large or OpenAI Embeddings         |
| Data      | yfinance/재무API, 뉴스/IR/PDF 로더                       |
| Report    | WeasyPrint(or LaTeX), matplotlib/plotly            |
| Storage   | Object Storage(S3 호환), Vector DB, PostgreSQL(meta) |

## Agents

* **Supervisor** : 사용자 입력 파싱, 실행계획/병렬화, 실패 재시도·가드레일
* **Market_Researcher** : EV/배터리/정책/인프라 **시장 트렌드** 수집·요약(증거 링크 포함)
* **Company_Analyzer** : 기업 **사업전개/리스크/로드맵** 정리(공시/IR/PDF 파싱)
* **Stock_Analyzer** : 티커별 **수익률/변동성/멀티플/이벤트** 스냅샷
* **Chart_Generator** : 점유율·가격·주가 비교 등 **시각화 자산** 생성
* **Report_Compiler** : SUMMARY·본문·REFERENCE·(옵션)APPENDIX를 합쳐 **PDF** 생성

## State

* **period** : 분석 기간(e.g., `last_90d`, `2025-01-01~2025-09-30`)
* **regions** : 분석 지역 리스트(e.g., `["global","US","EU","CN","KR"]`)
* **focus_issues** : 이슈 키워드(e.g., 수요둔화/보조금/배터리케미스트리/충전)
* **segments** : 세그먼트(e.g., 승용/SUV/픽업/상용)
* **depth** : 분석 깊이(`quick|standard|deep`)
* **snapshot_date** : 데이터 기준일(재현성)
* **output** : 형식·언어·섹션 포함 설정(PDF/HTML/MD, KO/EN)
* **constraints** : 페이지/차트/참고문헌 최소 수 등 제한
* **benchmarks** : 비교 바스켓(티커/심볼, 선택)
* **policies** : 정책 관심사(IRA, EU 규제 등)
* **financials** : 통화/멀티플/이벤트 윈도우
* **data_prefs** : 소스/언어 우선순위
* **risk_lens** : 리스크 가중치(수요/정책/공급망/기술)
* **cadence** : 배치 주기(주간/월간/애드혹)
* **persona** : 리포트 톤(전략/투자 등)
* **market_brief** : 시장 브리핑 아티팩트(트렌드/지표/증거)
* **company_dossiers** : 기업별 도시에(하이라이트/리스크/증거)
* **stock_snapshots** : 주가·멀티플·이벤트 스냅샷
* **charts** : 생성된 차트 자산 목록
* **report_path** : 최종 리포트 파일 경로

## Architecture

(그래프 이미지)

> 구성: **Supervisor → (Market/Company/Stock) → Chart → Report**
> RAG(Vector DB)와 Object Storage에 증거·차트·PDF를 아카이빙.

## Directory Structure

```
├── data/                  # 원본 스냅샷(RAW) & 가공 자료
├── agents/                # Agent 모듈(Supervisor/Market/Company/Stock/Chart)
├── compiler/              # 리포트 템플릿 & 컴파일러(WeasyPrint/LaTeX)
├── prompts/               # 프롬프트 템플릿
├── services/              # ingest/finance/rag 유틸리티
├── outputs/               # charts/, reports/, evidence.jsonl
├── app.py                 # 실행 스크립트(CLI/Batch)
└── README.md
```

## Usage (예시)

```bash
# Weekly Global Pulse (빠른 분석, 7일)
ev-agent run \
  --period last_7d --regions global \
  --issues demand_softness subsidy_policy battery_chemistry charging \
  --depth quick --output pdf --lang ko \
  --sections summary,market,company_compare,stock,risk,reference \
  --max-pages 4 --max-charts 3
```

## Output

* **PDF**: `outputs/EV_Trend_{YYYYMMDD}.pdf`
* **Charts**: `outputs/charts/*.png`
* **Evidence**: `outputs/evidence.jsonl`(본문 각주 ↔ 링크 매핑)

## Contributors

* (예) 김철수 : Prompt Engineering, Agent Design
* (예) 최영희 : PDF Parsing, Retrieval Agent

> 필요 시 리포트 템플릿(WeasyPrint/LaTeX), 입력 JSON 스키마, LangGraph 노드 정의 스캐폴드를 추가 제공 가능합니다.
