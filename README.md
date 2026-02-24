# StockPlay

> 수출 데이터 기반 투자 시그널 플랫폼

## 📌 프로젝트 개요

**StockPlay**는 수출 데이터 기반 투자 시그널 플랫폼입니다. 수출 벤더가 제공하는 데이터로부터 ARIMA 시계열 예측 모델을 적용하여 Surprise Z-Score를 산출하고, 이를 기반으로 BUY/HOLD/SELL 시그널을 생성합니다.

### 핵심 질문
> **"수출 데이터로 주식 투자 시그널을 만들어 낼 수 있는가?"**

### 분석 결과
- **최적 모델**: ARIMA(1,2,1), Rolling one-step ahead 예측
- **유효 시그널**: Positive Signal (Z > +2σ), Long-Only 전략
- **최적 조건**: GICS Sector 35 (Healthcare) + 20일 보유 → **BUY Precision 60%, 평균 수익률 +1.93%**
- **벤더 데이터 검증**: 데이터 공개 전 이미 가격에 선반영 → 단독 시그널로는 투자 가치 제한적

### 아키텍처
```
[React FE] → [CloudFront] → [API Gateway] → [Lambda (FastAPI + Docker)]
                                                    ↓
                                S3 (데이터/리포트) + DynamoDB (구독) + SES (이메일)

[EventBridge 매일 9AM KST] → [Email Lambda] → 구독자 일일 리포트 발송
[EventBridge 매월 20일]    → [DataUpdater Lambda] → 관세청 API 수출 데이터 자동 갱신
```

### 레포지토리 구성

| 레포 | 설명 | 기술 스택 |
|---|---|---|
| **StockPlay-FE** | 프론트엔드 대시보드 | React 19 + TypeScript + Vite + CloudFront |
| **StockPlay-BE** | 백엔드 API + 인프라 | FastAPI + AWS Lambda (Docker) + SAM + S3 + DynamoDB + SES |
| **StockPlay-Data-analysis** | 데이터 분석 + 모델링 | Python + Pandas + Statsmodels + CRISP-DM |

### 주요 기능
- **Dashboard**: 실시간 투자 시그널 카드 (BUY/HOLD/SELL), 섹터별 필터링
- **Reports**: 47개월 월별 리포트 열람, AI 분석 포함 3페이지 프리미엄 PDF 다운로드
- **Subscribe**: 이메일 구독 → 일일 트레이딩 리포트 자동 발송
- **PDF 리포트**: Jinja2 + WeasyPrint 템플릿 기반, KOSPI 차트 + Surprise Z-Score + 기술적 지표

---

## 📚 Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📱 Contributors

| 양정우 (PM / Full-Stack) <br> [@mrangjw](https://github.com/mrangjw) | 김민규 (Data Analysis / ML) <br> [@edit0rsky](https://github.com/edit0rsky) | 송진우 (Data Strategy) <br> [@HSSJW](https://github.com/HSSJW) |
|:---:|:---:|:---:|
| <img width="150" src="https://avatars.githubusercontent.com/u/157506327?v=4"/> | <img width="150" src="https://avatars.githubusercontent.com/u/126232823?v=4"/> | <img width="150" src="https://avatars.githubusercontent.com/u/132650844?v=4"/> |
| 프로젝트 기획 및 총괄<br>Frontend 개발 (React 19 + TS)<br>Backend API 개발 (FastAPI)<br>AWS 인프라 구축 및 배포 | CRISP-DM 기반 데이터 분석<br>ARIMA/SMA/EWMA 모델 구현<br>Surprise Z-Score 시그널 생성<br>백테스팅 및 전략 검증 | 데이터셋 분석 방향 설계<br>분석 전략 자문 및 피드백<br>비즈니스 요구사항 정의 |
