# 📊 Portfolio AI — Notion DB 기반 Streamlit 앱

> 한국/미국 주식 · ETF · 암호화폐 포트폴리오 관리 + AI 투자 전략 분석  
> **포트폴리오 & 스크랩 데이터는 모두 Notion에 영구 저장됩니다.**

---

## 🗄️ Notion 데이터베이스 2개 설정 (필수)

Notion Integration 1개 + 데이터베이스 2개가 필요합니다.

### Step 1 — Notion Integration 생성
1. https://www.notion.so/my-integrations 접속
2. **"+ New integration"** 클릭
3. 이름 입력 (예: `Portfolio AI`) → **Submit**
4. **Internal Integration Token** 복사 → `NOTION_API_KEY`

---

### Step 2 — 포트폴리오 DB 생성

새 Notion 페이지에 **데이터베이스(전체 페이지)** 생성 후 아래 속성 추가:

| 속성명 | 타입 | 비고 |
|--------|------|------|
| 티커 | 제목(기본값) | 예: AAPL, 005930.KS, BTC-USD |
| 종목명 | 텍스트 | |
| 수량 | 숫자 | |
| 평균단가 | 숫자 | |
| 자산유형 | 선택(Select) | 한국주식/미국주식/ETF/암호화폐/채권/원자재/기타 |
| 메모 | 텍스트 | |
| 추가일 | 날짜 | |

→ DB URL에서 ID 복사 (notion.so/**xxxxxxxx**?v=...) → `NOTION_PORTFOLIO_DB_ID`

---

### Step 3 — 스크랩 DB 생성

새 Notion 페이지에 **데이터베이스(전체 페이지)** 생성 후 아래 속성 추가:

| 속성명 | 타입 | 비고 |
|--------|------|------|
| 제목 | 제목(기본값) | |
| 자산 | 텍스트 | |
| 카테고리 | 선택(Select) | 시장뉴스/코인뉴스/리서치/AI분석 등 |
| 출처 | 텍스트 | |
| 요약 | 텍스트 | |
| 링크 | URL | |
| 날짜 | 날짜 | |

→ DB URL에서 ID 복사 → `NOTION_SCRAP_DB_ID`

---

### Step 4 — Integration을 두 DB에 연결

각 데이터베이스 페이지에서:  
우측 상단 `···` → **Connections** → 생성한 Integration 선택

---

## 🚀 GitHub → Streamlit Cloud 배포

```bash
git init
git add .
git commit -m "Portfolio AI - Notion DB"
git remote add origin https://github.com/YOUR_USERNAME/portfolio-ai.git
git push -u origin main
```

1. https://share.streamlit.io → GitHub 로그인 → **New app**
2. repo / branch(`main`) / file(`app.py`) 선택
3. **Advanced settings → Secrets** 에 입력:

```toml
GEMINI_API_KEY         = "AIza..."
NOTION_API_KEY         = "secret_..."
NOTION_PORTFOLIO_DB_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
NOTION_SCRAP_DB_ID     = "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
```

4. **Deploy!** → 2~3분 후 앱 URL 발급

---

## 💻 로컬 실행

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env       # 키 입력
streamlit run app.py
```

---

## 📁 구조

```
portfolio-ai/
├── app.py                     ← 메인 앱 (Notion DB 연동)
├── requirements.txt
├── .gitignore
├── .env.example
├── .streamlit/
│   ├── config.toml            ← 다크 테마
│   └── secrets.toml           ← 로컬 전용 (git 제외)
└── utils/
    ├── notion_db.py           ← Notion DB CRUD 레이어
    ├── data.py                ← 주가/뉴스 유틸
    └── ai.py                  ← Gemini AI 분석
```

---

## 🔑 환경변수 요약

| 변수명 | 설명 |
|--------|------|
| `GEMINI_API_KEY` | Google AI Studio API 키 |
| `NOTION_API_KEY` | Notion Integration 토큰 |
| `NOTION_PORTFOLIO_DB_ID` | 포트폴리오 전용 DB ID |
| `NOTION_SCRAP_DB_ID` | 스크랩 전용 DB ID |
