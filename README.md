# EV Market Trend Analysis Agent

본 프로젝트는 **전기차(EV) 시장 트렌드 분석** 에이전트를 설계하고 구현한 실습 프로젝트입니다.

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
| LLM       | GPT-4o-mini via OpenAI API (configurable) |
| Retrieval | Chroma (Agentic RAG)                      |
| Embedding | OpenAI Embeddings                         |
| Data      | yfinance/재무API, 뉴스/IR/PDF 로더        |
| Report    | WeasyPrint(or LaTeX), matplotlib/plotly   |

## Agents

- **Supervisor** : 사용자 입력 파싱, 실행계획/병렬화, 실패 재시도·가드레일
- **Market_Researcher** : EV/배터리/정책/인프라 **시장 트렌드** 수집·요약(증거 링크 포함)
- **Company_Analyzer** : 기업 **사업전개/리스크/로드맵** 정리(공시/IR/PDF 파싱)
- **Stock_Analyzer** : 티커별 **수익률/변동성/멀티플/이벤트** 스냅샷
- **Chart_Generator** : 점유율·가격·주가 비교 등 **시각화 자산** 생성
- **Report_Compiler** : SUMMARY·본문·REFERENCE·(옵션)APPENDIX를 합쳐 **PDF** 생성

## State

| State Key     | Producer(출력)           | Consumer(입력)                    | 비고                 |
| ------------- | ------------------------ | --------------------------------- | -------------------- |
| run_id        | Supervisor.parse_request | 모든 노드 로그 태깅               | 실행 추적            |
| period        | Supervisor.parse_request | Market/Company/Stock/Chart/Report | 전 에이전트 공통     |
| regions       | Supervisor.parse_request | Market/Company/Report             | 수집 범위            |
| focus_issues  | Supervisor.parse_request | Market/Report                     | RAG 쿼리 키워드      |
| segments      | Supervisor.parse_request | Market/Report                     | 세그먼트 통계        |
| depth         | Supervisor.parse_request | Chart/Report/Supervisor.qa_gate   | 리소스 제한          |
| snapshot_date | Supervisor.parse_request | Market/Company/Report             | 재현성 기준일        |
| output        | Supervisor.parse_request | Report/Chart/Supervisor.handoff   | 포맷/언어/섹션       |
| constraints   | Supervisor.parse_request | Chart/Report/Supervisor.qa_gate   | 페이지/차트/레퍼런스 |
| benchmarks    | Supervisor.parse_request | Company/Stock/Report              | 선택: 비교 바스켓    |
| policies      | Supervisor.parse_request | Market/Report                     | 정책 이슈            |
| financials    | Supervisor.parse_request | Stock/Report                      | 통화/멀티플          |
| data_prefs    | Supervisor.parse_request | Market/Company                    | 소스/언어 우선       |
| risk_lens     | Supervisor.parse_request | Report                            | 리스크 챕터 강조     |
| cadence       | Supervisor.parse_request | (배치) Scheduler                  | 런타임 외부          |
| persona       | Supervisor.parse_request | Report                            | 톤/요약 스타일       |

| 산출물 Key       | Producer                                                      | Consumer                          | 비고           |
| ---------------- | ------------------------------------------------------------- | --------------------------------- | -------------- |
| raw_docs         | Market.collect / Company.collect                              | Market.index / Company.index      | 원문 메타      |
| indexed_ids      | Market.index / Company.index                                  | Market.extract / Company.compose  | VDB keys       |
| market_brief     | Market.extract                                                | Chart/Report/Supervisor.merge     | 산업 핵심 요약 |
| company_dossiers | Company.compose                                               | Report/Supervisor.merge           | 기업 도시에    |
| stock_snapshots  | Stock.compute                                                 | Chart/Report/Supervisor.merge     | 주가/멀티플    |
| charts           | Chart.render                                                  | Report                            | 시각 자산      |
| evidence_map     | Market.validate / Company.validate / Chart.register           | Report/Supervisor.qa_gate         | [n] 매핑       |
| draft_report_md  | Supervisor.merge / Report.compose                             | Report.export, Supervisor.qa_gate | 중간 원문      |
| report_path      | Report.export                                                 | (최종 출력)                       | PDF 경로       |
| qa_metrics       | Supervisor.qa_gate / Stock.validate / Market/Company.validate | (감시/로그)                       | 커버리지/정합  |

| 품질/오류                     | Producer              | Consumer           | 비고          |
| ----------------------------- | --------------------- | ------------------ | ------------- |
| errors[]                      | 모든 노드(예외 시)    | Supervisor         | 리트라이/폴백 |
| qa_metrics.citation_coverage  | Market/Company        | Supervisor.qa_gate | ≥ 0.9 권장    |
| qa_metrics.number_consistency | Stock                 | Supervisor.qa_gate | 수치 정합성   |
| qa_metrics.document_ok        | Report.post_export_qc | 최종 상태          | 배포 전 체크  |

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
- **시각화**: 스파크라인 3~4개 + 임팩트×확실성 2×2.
- **증거**: 주장마다 **[n]** 각주(최소 6개).

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

- **내용**: 에이전트 워크플로우(개요도), 지표 정의서(판매·보급률·ASP·원가 산식), 스냅샷 기준/버전, 요약 가드레일(날짜·수치 정합성 규칙)

### 페이지·차트 가이드

- **Standard**: 총 10–12p / 차트 ≤ 6
- **Quick**: 총 6–8p / 차트 ≤ 3
- **Deep**: 총 16–20p / 차트 ≤ 12

---

## Contributors

- (예) 김철수 : Prompt Engineering, Agent Design
- (예) 최영희 : PDF Parsing, Retrieval Agent

> 필요 시 리포트 템플릿(WeasyPrint/LaTeX), 입력 JSON 스키마, LangGraph 노드 정의 스캐폴드를 추가 제공 가능합니다.
