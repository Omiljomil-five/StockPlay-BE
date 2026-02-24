# StockPlay

> 수출 데이터 기반 투자 시그널 서비스

## Contributors

| 양정우 (Full-Stack) <br> [@mrangjw](https://github.com/mrangjw) | 김민규 (Data Analysis) <br> [@edit0rsky](https://github.com/edit0rsky) | 송진우 (PM/Data Strategy) <br> [@HSSJW](https://github.com/HSSJW) |
|:---:|:---:|:---:|
| <img width="150" src="https://avatars.githubusercontent.com/u/157506327?v=4"/> | <img width="150" src="https://avatars.githubusercontent.com/u/126232823?v=4"/> | <img width="150" src="https://avatars.githubusercontent.com/u/132650844?v=4"/> |
| Frontend 개발 (React 19 + TS)<br>Backend API 개발 (FastAPI)<br>AWS 인프라 구축 및 배포 | CRISP-DM 기반 데이터 분석<br>ARIMA/SMA/EWMA 모델 구현<br>Surprise Z-Score 시그널 생성<br>백테스팅 및 전략 검증 | 프로젝트 기획 및 총괄<br>데이터셋 분석 방향 설계<br>분석 전략 자문 및 피드백<br>비즈니스 요구사항 정의 |

---

## 프로젝트 개요

**StockPlay**는 관세청 수출 데이터에 ARIMA 시계열 예측 모델을 적용하여 Surprise Z-Score를 산출하고, BUY/HOLD/SELL 투자 시그널을 생성하는 **데이터 분석 중심** 프로젝트입니다.

CRISP-DM 방법론에 따라 수출 데이터의 주가 예측력을 검증하는 것이 핵심이며, AWS 서버리스 아키텍처를 활용해 **사용자가 서비스에 직접 접속하지 않아도** EventBridge + SES를 통해 매일 투자 리포트를 이메일로 자동 수신할 수 있습니다.

### 핵심 질문
> **"수출 데이터로 주식 투자 시그널을 만들어 낼 수 있는가?"**

### 분석 결과
- **최적 모델**: ARIMA(1,2,1), Rolling one-step ahead 예측
- **유효 시그널**: Positive Signal (Z > +2σ), Long-Only 전략
- **최적 조건**: GICS Sector 35 (Healthcare) + 20일 보유 → **BUY Precision 60%, 평균 수익률 +1.93%**
- **벤더 데이터 검증**: 데이터 공개 전 이미 가격에 선반영 → 단독 시그널로는 투자 가치 제한적

---

## 주요 기능

### Dashboard
실시간 투자 시그널 카드 (BUY/HOLD/SELL) 표시, 섹터별 필터링 지원. 8개 섹터 16종목에 대한 시그널과 성과 지표를 한눈에 확인할 수 있습니다.

<!-- 스크린샷: Dashboard 전체 화면 -->

### Reports
47개월치 월별 리포트 열람 및 AI 분석이 포함된 3페이지 프리미엄 PDF 다운로드. Jinja2 + WeasyPrint 기반 템플릿으로 KOSPI 차트, Surprise Z-Score, 기술적 지표를 시각화합니다.

<!-- 스크린샷: Reports 목록 + PDF 미리보기 -->

### Subscribe
이메일 구독 등록 시 SES를 통한 환영 메일 발송. EventBridge 스케줄러가 매일 오전 9시(KST)에 구독자 전원에게 일일 트레이딩 리포트를 자동 발송합니다.

<!-- 스크린샷: Subscribe 화면 -->

---

## 시스템 아키텍처

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────────────────┐
│  React FE   │────▶│  CloudFront  │────▶│  API Gateway  │────▶│  StockPlayAPI Lambda     │
│  (Vite+TS)  │     │  (SPA 라우팅) │     │  (REST, CORS) │     │  (FastAPI + Docker)      │
└─────────────┘     └──────────────┘     └───────────────┘     └────────┬─────────────────┘
                                                                        │
                                          ┌─────────────────────────────┼─────────────────┐
                                          │                             │                 │
                                   ┌──────▼──────┐             ┌───────▼───────┐  ┌──────▼──────┐
                                   │     S3      │             │   DynamoDB    │  │     SES     │
                                   │ data/reports│             │  구독자 관리   │  │  이메일 발송  │
                                   └─────────────┘             └───────────────┘  └─────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  EventBridge Scheduler                                                                      │
│                                                                                             │
│  [매일 00:00 UTC (9AM KST)] ──▶ EmailSender Lambda ──▶ 구독자 일일 리포트 발송              │
│  [매월 20일 03:00 UTC]      ──▶ DataUpdater Lambda  ──▶ 관세청 API → S3 데이터 갱신         │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 데이터 파이프라인

```
관세청 OpenAPI ──▶ DataUpdater Lambda (매월 20일)
                         │
                         ▼
                   S3 Data Bucket (CSV: export_by_sector, merged_signals, kospi 등)
                         │
                         ▼
                   MLPredictor (Lambda 시작 시 로드)
                         │
                    ┌────┴────┐
                    ▼         ▼
             GET /signals   POST /reports/generate
             (시그널 조회)   (PDF 생성)
                              │
                         ┌────┴────┐
                         ▼         ▼
                   Claude AI   Jinja2 + WeasyPrint
                   (분석 텍스트)  (3페이지 PDF)
                         │         │
                         ▼         ▼
                   S3 Reports Bucket → SES 이메일 발송
```

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| **Backend** | FastAPI 0.115 · Python 3.12 · Mangum (Lambda ASGI 어댑터) · Pydantic 2.10 |
| **AWS Compute** | Lambda (Docker Image / ZIP) · API Gateway REST API · EventBridge Scheduler |
| **AWS Storage** | S3 (데이터 · 리포트 · 프론트엔드) · DynamoDB (구독자 관리) |
| **AWS Messaging** | SES (이메일 발송, 프로덕션 50,000건/일) |
| **AWS CDN** | CloudFront (SPA 라우팅, 403/404 → /index.html) |
| **PDF 생성** | Jinja2 3.1 + WeasyPrint 60 (HTML→PDF) · Pillow 11 (차트 렌더링) |
| **AI 분석** | Anthropic Claude API (투자 분석 텍스트 생성) |
| **IaC / 배포** | AWS SAM (CloudFormation) · Docker (AL2023 기반) |
| **Frontend** | React 19 + TypeScript + Vite (별도 레포) |

---

## 인프라

### Lambda Functions

| Function | 패키징 | 트리거 | Timeout / Memory | 역할 |
|----------|--------|--------|-------------------|------|
| **StockPlayAPI** | Docker Image | API Gateway (ANY `/api/{proxy+}`) | 30s / 1GB | FastAPI 메인 API (시그널, 리포트, 구독) |
| **EmailSenderFunction** | ZIP (Python 3.12) | EventBridge cron `0 0 * * ?` (매일 9AM KST) | 60s / 128MB | 구독자 일일 리포트 이메일 발송 |
| **DataUpdaterFunction** | Docker Image | EventBridge cron `0 3 20 * ?` (매월 20일) | 900s / 2GB | 관세청 API 호출 → S3 데이터 갱신 |

### AWS 리소스 구성

**API Gateway**
- REST API, CORS 설정 (localhost:5173/4173/3000 + CloudFront 도메인)
- `BinaryMediaTypes: */*` — PDF 바이너리 응답 지원을 위해 필수

**S3 Buckets**

| 버킷 | 용도 |
|------|------|
| `stockplay-data-*` | CSV 데이터 (merged_signals, export_by_sector, kospi, sector_mapping 등) |
| `stockplay-reports-*` | 생성된 PDF 리포트 저장 |
| `stockplay-frontend-*` | React 빌드 정적 파일 (CloudFront Origin) |

**DynamoDB**
- 테이블: `stockplay-main`
- PK: `SUBSCRIBER#{email}`, SK: `METADATA`
- GSI: `SubscriberIndex` (구독자 전체 조회용)
- 용도: 이메일 구독/해지, 알림 on/off 토글, 발송 이력 관리

**SES (Simple Email Service)**
- 발신자 Identity 인증 완료
- 프로덕션 승인 완료 (50,000건/일, 14건/초)
- 환영 메일 + 일일 리포트 HTML 메일 발송

**CloudFront**
- S3 프론트엔드 버킷을 Origin으로 설정
- SPA 라우팅: CustomErrorResponses에서 403/404 → `/index.html` (HTTP 200)

**EventBridge**
- `DailySchedule`: 매일 00:00 UTC → EmailSenderFunction (구독자 리포트)
- `MonthlySchedule`: 매월 20일 03:00 UTC → DataUpdaterFunction (데이터 갱신)

### Docker 빌드

StockPlayAPI와 DataUpdater는 Docker 기반 Lambda로 배포됩니다.

**StockPlayAPI Dockerfile 핵심:**
```dockerfile
FROM public.ecr.aws/lambda/python:3.12

# WeasyPrint 시스템 의존성 (AL2023 = dnf)
RUN dnf install -y pango cairo gdk-pixbuf2 gobject-introspection libffi-devel

# 한국어 폰트 (NanumGothic) + FontConfig
COPY fonts/ ./fonts/
ENV FONTCONFIG_FILE=/var/task/fonts/fonts.conf

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY templates/ ./templates/
COPY data/ ./data/

CMD ["lambda_handler.handler"]
```

> WeasyPrint는 pango/cairo 시스템 라이브러리가 필요하므로 ZIP 패키징이 불가능하여 Docker Image로 배포합니다. AL2023 기반이므로 `yum`이 아닌 `dnf`를 사용합니다.

### 배포 (SAM)

```bash
# 빌드
sam build

# 배포 (samconfig.toml 설정 사용)
sam deploy

# 또는 직접 파라미터 지정
sam deploy --stack-name stockplay-api \
           --region ap-northeast-2 \
           --capabilities CAPABILITY_IAM \
           --resolve-image-repos
```

배포 시 CloudFormation 스택 `stockplay-api`가 생성/업데이트됩니다.

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/signals` | 투자 시그널 조회 (sector, period, limit 파라미터) |
| POST | `/api/reports/generate` | PDF 리포트 생성 |
| POST | `/api/reports/generate-full` | AI 분석 포함 전체 리포트 생성 |
| GET | `/api/reports` | 월별 리포트 목록 조회 |
| GET | `/api/reports/{report_id}/download` | 월별 리포트 PDF 다운로드 |
| POST | `/api/subscribe` | 이메일 구독 등록 (환영 메일 발송) |
| GET | `/api/subscribe/{email}` | 구독 상태 조회 |
| PATCH | `/api/subscribe/{email}` | 알림 on/off 토글 |
| DELETE | `/api/subscribe/{email}` | 구독 해지 |
| GET | `/api/health` | 헬스체크 |

**API 문서**: 로컬 실행 시 Swagger UI (`/docs`) 및 ReDoc (`/redoc`) 제공

---

## 프로젝트 구조

```
StockPlay-BE/
├── lambda_handler.py          # Lambda 진입점 (Mangum + FastAPI)
├── email_sender.py            # 일일 리포트 발송 Lambda
├── template.yaml              # AWS SAM 인프라 정의
├── samconfig.toml             # SAM 배포 설정
├── Dockerfile                 # StockPlayAPI Docker 이미지
├── requirements.txt
│
├── src/
│   ├── main.py                # FastAPI 앱 초기화 + CORS
│   ├── config.py              # 환경변수 기반 설정 (Pydantic Settings)
│   ├── api/
│   │   ├── signals.py         # GET /api/signals
│   │   ├── reports.py         # PDF 생성 · 다운로드 엔드포인트
│   │   └── subscribe.py       # 이메일 구독 CRUD
│   ├── services/
│   │   ├── ml_predictor.py    # ARIMA 예측 + 시그널 데이터 로딩 (S3/로컬)
│   │   ├── pdf_generator.py   # Jinja2 + WeasyPrint PDF 생성
│   │   ├── chart_generator.py # Matplotlib 차트 7종
│   │   ├── chart_generator_pillow.py  # Pillow 경량 차트 (Lambda 폴백)
│   │   ├── ai_analyzer.py     # Claude API 투자 분석 텍스트
│   │   ├── dynamodb_service.py # DynamoDB 구독자 CRUD
│   │   ├── email_service.py   # SES 이메일 발송
│   │   └── signal_generator.py # 5-Factor 시그널 생성기
│   └── schemas/               # Pydantic 요청/응답 모델
│
├── data_updater/
│   ├── Dockerfile             # DataUpdater Lambda Docker
│   ├── handler.py             # 관세청 API → S3 데이터 동기화
│   └── requirements.txt
│
├── templates/                 # Jinja2 HTML 템플릿 (PDF 렌더링용)
├── fonts/                     # NanumGothic 한국어 폰트 + FontConfig
├── data/                      # CSV 데이터 (S3와 동기화)
├── models/                    # ML 모델 아티팩트 (.pkl)
└── tests/
```

---

## 로컬 개발 환경

### 환경변수 설정

```bash
# .env
USE_S3_DATA=false          # 로컬 data/ 디렉토리 사용
DEBUG=true
DYNAMODB_TABLE=stockplay-main
SES_FROM_EMAIL=your@email.com
ANTHROPIC_API_KEY=sk-ant-...
```

### 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 로컬 서버 실행
uvicorn src.main:app --reload --port 8000

# API 문서 확인
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

---

## 레포지토리 구성

| 레포 | 설명 | 기술 스택 |
|------|------|-----------|
| **StockPlay-FE** | 프론트엔드 대시보드 | React 19 + TypeScript + Vite + CloudFront |
| **StockPlay-BE** | 백엔드 API + 인프라 | FastAPI + AWS Lambda (Docker) + SAM + S3 + DynamoDB + SES |
| **StockPlay-Data-analysis** | 데이터 분석 + 모델링 | Python + Pandas + Statsmodels + CRISP-DM |
