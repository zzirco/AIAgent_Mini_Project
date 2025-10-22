# EV Market Trend Analysis Agent

본 프로젝트는 **전기차(EV) 시장 트렌드 분석 리포트 생성** 에이전트 구축 프로젝트입니다.

## Overview

- **Objective** : 글로벌 EV 시장·배터리 밸류체인·정책 이슈를 자동 수집·요약·정량화하여 **투자·전략 의사결정용 리포트**를 생성
- **Methods** : Multi-Agent Orchestration, Agentic RAG, Evidence-grounded Summarization, Financial Snapshotting
- **Tools** : LangGraph, LangChain, yfinance/재무API, PDF/HTML Parsers, WeasyPrint(or LaTeX)

## Features

- **시장·정책·기술 이슈 자동 수집/요약**(기간/지역/이슈/세그먼트 기반)
- **기업 동향 & 밸류에이션 비교**(완성차/배터리사 바스켓 기준)
- **근거 각주(REFERENCE)와 차트 포함 PDF 리포트** 자동 생성

## Tech Stack

| Category  | Details                                   |
| --------- | ----------------------------------------- |
| Framework | LangGraph, LangChain, Python              |
| LLM       | GPT-4o-mini                               |
| Retrieval | Hybrid Retrieval (Semantic + BM25)        |
| Embedding | OllamaEmbeddings (nomic-embed-text)       |
| Vector Store | ChromaDB                               |
| Data      | yfinance/재무API, 뉴스/IR/PDF 로더         |
| Chart     | WeasyPrint                                |
| Report    | ReportLab                                 |

## Agents

- **Supervisor** : 사용자 입력 파싱, 실행계획/병렬화, 리포트 품질 평가
- **Market_Researcher** : EV/배터리/정책/인프라 **시장 트렌드** 수집·요약(출처 포함)
- **Company_Analyzer** : 기업 **사업전개/리스크/로드맵** 정리(공시/IR/PDF 파싱)
- **Stock_Analyzer** : 티커별 **수익률/변동성/종목이슈** 스냅샷
- **Chart_Generator** : 점유율·가격·주가 비교 등 **시각화 자료** 생성
- **Report_Compiler** : SUMMARY·본문·REFERENCE·(옵션)APPENDIX를 합쳐 **PDF** 생성

## State

### A) 구성/제어 State (Supervisor가 생성 → 각 에이전트가 참조)

| State Key                                   | Producer(출력 노드)          | Consumer(입력 에이전트/노드)                                                                                                                                     | 비고               |
| ------------------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **run_id**                                  | Supervisor · `parse_request` | 모든 에이전트/노드(로그 태깅)                                                                                                                                    | 실행 추적용        |
| **period**                                  | Supervisor · `parse_request` | Market_Researcher(모든 노드), Company_Analyzer(collect/index/compose), Stock_Analyzer(fetch/compute), Chart_Generator(select), Report_Compiler(assemble/compose) | 분석 기간          |
| **regions**                                 | Supervisor · `parse_request` | Market_Researcher(collect/extract), Company_Analyzer(collect/compose), Report_Compiler(assemble/compose)                                                         | 수집·서술 범위     |
| **focus_issues**                            | Supervisor · `parse_request` | Market_Researcher(collect/extract), Report_Compiler(assemble/compose)                                                                                            | RAG 질의/요약 축   |
| **segments**                                | Supervisor · `parse_request` | Market_Researcher(extract), Report_Compiler(compose)                                                                                                             | 세그먼트 관점      |
| **depth**                                   | Supervisor · `parse_request` | Chart_Generator(select), Report_Compiler(assemble), Supervisor · `qa_gate`                                                                                       | 리소스/분량 제한   |
| **snapshot_date**                           | Supervisor · `parse_request` | Market_Researcher(extract), Company_Analyzer(compose), Report_Compiler(compose)                                                                                  | 재현성 기준일      |
| **output** (format/lang/sections)           | Supervisor · `parse_request` | Report_Compiler(assemble/export), Chart_Generator(select), Supervisor · `handoff_to_compiler`                                                                    | 출력 규격          |
| **constraints** (max_pages/charts/min_refs) | Supervisor · `parse_request` | Chart_Generator(select), Report_Compiler(compose/export), Supervisor · `qa_gate`                                                                                 | 제약 조건          |
| **benchmarks** (티커 바스켓/기업셋)         | Supervisor · `parse_request` | Company_Analyzer(collect/compose), Stock_Analyzer(fetch/compute), Report_Compiler(compose)                                                                       | 선택 입력          |
| **policies**                                | Supervisor · `parse_request` | Market_Researcher(collect/extract), Report_Compiler(compose)                                                                                                     | 정책 관점 강조     |
| **financials** (통화/멀티플 등)             | Supervisor · `parse_request` | Stock_Analyzer(fetch/compute), Report_Compiler(compose)                                                                                                          | 정량 옵션          |
| **data_prefs** (소스/언어 우선)             | Supervisor · `parse_request` | Market_Researcher(collect), Company_Analyzer(collect)                                                                                                            | 수집 우선순위      |
| **risk_lens**                               | Supervisor · `parse_request` | Report_Compiler(compose)                                                                                                                                         | 리스크 챕터 가중치 |
| **cadence**                                 | Supervisor · `parse_request` | 스케줄러(외부), 메타 로깅                                                                                                                                        | 배치 주기          |
| **persona**                                 | Supervisor · `parse_request` | Report_Compiler(assemble/compose)                                                                                                                                | 톤·요약 스타일     |

### B) 콘텐츠/산출물 State

| State Key            | Producer(출력 노드)                                                                                                                                     | Consumer(입력 에이전트/노드)                                                                | 비고                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------- |
| **raw_docs**         | **Market_Researcher · `collect_market_docs`**, **Company_Analyzer · `collect_company_docs`**                                                            | 각 에이전트의 `index_*` 노드                                                                | 원문/기사/IR 메타           |
| **indexed_ids**      | **Market_Researcher · `index_market_docs`**, **Company_Analyzer · `index_company_docs`**                                                                | Market_Researcher · `extract_market_signals`, Company_Analyzer · `compose_company_dossiers` | VDB 키                      |
| **market_brief**     | **Market_Researcher · `extract_market_signals`**                                                                                                        | Supervisor · `merge_artifacts`, Chart_Generator(select/render), Report_Compiler(compose)    | 시장 핵심 요약·지표·근거    |
| **company_dossiers** | **Company_Analyzer · `compose_company_dossiers`**                                                                                                       | Supervisor · `merge_artifacts`, Report_Compiler(compose)                                    | 기업 도시에(비교 포맷)      |
| **stock_snapshots**  | **Stock_Analyzer · `compute_snapshots`**                                                                                                                | Supervisor · `merge_artifacts`, Chart_Generator(select/render), Report_Compiler(compose)    | 수익률/변동성/멀티플/이벤트 |
| **charts**           | **Chart_Generator · `render_charts`**                                                                                                                   | Report_Compiler(compose/export)                                                             | 이미지 경로/alt 포함        |
| **evidence_map**     | **Market_Researcher · `validate_citations_market`**, **Company_Analyzer · `validate_citations_company`**, **Chart_Generator · `register_chart_assets`** | Supervisor · `qa_gate`, Report_Compiler(compose/REFERENCE)                                  | [n] ↔ 링크 매핑             |
| **draft_report_md**  | **Supervisor · `merge_artifacts`**(초안 뼈대) → **Report_Compiler · `compose_sections`**(본문 완성)                                                     | Report_Compiler(export), Supervisor · `qa_gate`                                             | 초안→완성 단계              |
| **report_path**      | **Report_Compiler · `export_pdf`**                                                                                                                      | 리포트 최종 생성                                       | 최종 산출물 경로            |

### C) 품질/메타/오류 State

| State Key                         | Producer(출력 노드)                                                                                                            | Consumer(입력 에이전트/노드)                     | 비고           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ | -------------- |
| **qa_metrics.citation_coverage**  | Market_Researcher · `validate_citations_market`, Company_Analyzer · `validate_citations_company`, Supervisor · `qa_gate`(집계) | Supervisor · `qa_gate`, Report_Compiler(post QC) | 근거 커버리지  |
| **qa_metrics.number_consistency** | Stock_Analyzer · `validate_financial_consistency`, Supervisor · `qa_gate`(집계)                                                | Supervisor · `qa_gate`                           | 수치 정합성    |
| **qa_metrics.document_ok**        | Report_Compiler · `post_export_qc`                                                                                             | 배포 파이프라인                                  | 최종 QC 플래그 |
| **errors[]**                      | 모든 에이전트/노드(예외 발생 시)                                                                                               | Supervisor(집계/리트라이), 로그/알림             | 오류 수집      |

---

## Architecture

<img width="2508" height="3862" alt="Image" src="https://github.com/user-attachments/assets/00de44ea-d73f-4887-af42-e35600b7d397" />

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

- **PDF**: `outputs/EV_Trend_{YYYYMMDD}.pdf`
- **Charts**: `outputs/charts/*.png`
- **Evidence**: `outputs/evidence.jsonl`(본문 각주 ↔ 링크 매핑)

## EV 트렌드 리포트 목차

### 1) SUMMARY

- **목적**: 지난 기간에 “무엇이 바뀌었고, 왜 중요하며, 지금 무엇을 할 것인지” 10문장 이내로.
- **핵심지표**: 글로벌/주요 지역 판매 YoY, 점유율 Top5 변화, 가격/마진 압력 신호, 정책 이벤트 임팩트.

### 2) 시장 개요 & 핵심 트렌드

- **핵심 질문**: 침체/조정의 **구조적 vs 단기** 요인? 지역별 온도차?
- **필수 표/차트**
  - 지역별 판매/보급률 추이(라인), Top 10 국가 성장률 표
- **체크**: 판매/보급률/재고(가능 시) 일관성, 데이터 출처 최신성 표기.

### 3) 수요 & 가격 전략(마진 압력)

- **핵심 질문**: 가격 인하·할인 전략이 수요와 마진에 준 실제 영향은?
- **필수 표/차트**
  - 세그먼트별 점유율(스택드), ASP vs 판매량 산점도, 주요 OEM 가격 인하 타임라인
- **체크**: 가격 변화 ↔ 판매량 상관, 믹스 효과 분리 메모.

### 4) 정책·규제 Watch

- **핵심 질문**: IRA/관세/EU 규제가 **수요·공급망·가격** 경로에 미친 영향은?
- **필수 표/차트**
  - 국가별 보조금/적격성 변화 표, 정책 이벤트 타임라인
- **체크**: 날짜·적격성 정의를 본문 첫 등장에 명시(YYYY-MM-DD).

### 5) 배터리 기술 & 공급망 코어

- **핵심 질문**: LFP/LMFP/4680/SSB 전환 속도와 **원가/성능 트레이드오프**, 벤더 캐파 변화?
- **필수 표/차트**
  - kWh당 원가 추정 테이블, 케미스트리 점유율 추이(라인), 주요 벤더 캐파/고객 매핑
- **체크**: 추정치는 범위로 제시(하·중·상) + 근거 링크.

### 6) 경쟁 구도 & 지역 하이라이트

- **핵심 질문**: 누가 점유율을 얻/잃고 있으며, 지역별 차별 포인트는?
- **필수 표/차트**
  - OEM 포지셔닝 맵(가격×주행거리/성능), 지역 Top 모델 Top5 막대
- **체크**: 3~5개 OEM의 **핵심 사건**만 각주와 함께 요약.

### 7) 전략/투자 시사점

- **핵심 질문**: 그래서 **무엇을 해야 하는가?** (단기/중기 액션 5~7개)
- **형태**: 불릿 + 우선순위 + 트리거(모니터링 지표).

### 8) REFERENCE

- 본문 각주 **[n]** 매핑: `[n] 기관/저자, 제목, 날짜, URL`
- **요건**: 본문 주장 대비 **참고 링크 커버리지 ≥90%**

### 9) APPENDIX

- **내용**: 지표 정의서(판매·보급률·ASP·원가 산식), 스냅샷 기준/버전, 요약 가드레일(날짜·수치 정합성 규칙)

---

## Contributors

- 신호준 : 전기차 시장 트렌트 분석 Agent 설계 및 구축
