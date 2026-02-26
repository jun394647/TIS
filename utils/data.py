"""
utils/data.py  — 포트폴리오 데이터 관리
지원: 한국주식(.KS/.KQ), 미국주식, ETF, 암호화폐(BTC-USD 등)
"""

import yfinance as yf
import pandas as pd
import requests
import feedparser
import json, os, hashlib, urllib.parse
from datetime import datetime
import streamlit as st

# ── 자산 유형 ──────────────────────────────────────────────────────────────────
ASSET_TYPES = ["한국주식", "미국주식", "ETF", "암호화폐", "채권", "원자재", "기타"]
ASSET_TYPE_ICONS = {"한국주식":"🇰🇷","미국주식":"🇺🇸","ETF":"📦","암호화폐":"₿","채권":"📄","원자재":"🏗️","기타":"💼"}
CRYPTO_SUFFIXES = ["-USD","-KRW","-USDT","-BTC"]
CRYPTO_KEYWORDS = ["BTC","ETH","XRP","SOL","ADA","DOGE","DOT","MATIC","AVAX","LINK","BNB","TRX","SUI"]

MARKET_INDICES = {
    "S&P 500":    "^GSPC",
    "NASDAQ":     "^IXIC",
    "DOW JONES":  "^DJI",
    "러셀2000":   "^RUT",
    "KOSPI":      "^KS11",
    "KOSDAQ":     "^KQ11",
    "닛케이225":  "^N225",
    "항셍":       "^HSI",
    "상하이":     "000001.SS",
    "유로스톡스": "^STOXX50E",
    "VIX":        "^VIX",
    "달러인덱스": "DX-Y.NYB",
    "금":         "GC=F",
    "은":         "SI=F",
    "WTI":        "CL=F",
    "천연가스":   "NG=F",
    "미국10Y":    "^TNX",
    "미국2Y":     "^IRX",
    "USD/KRW":    "KRW=X",
    "USD/JPY":    "JPY=X",
    "EUR/USD":    "EURUSD=X",
    "BTC/USD":    "BTC-USD",
    "ETH/USD":    "ETH-USD",
}

# ── 티커 유틸리티 ──────────────────────────────────────────────────────────────

def detect_asset_type(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith(".KS") or t.endswith(".KQ"): return "한국주식"
    if any(t.endswith(s) for s in CRYPTO_SUFFIXES): return "암호화폐"
    if t in CRYPTO_KEYWORDS: return "암호화폐"
    return "미국주식"

def normalize_crypto_ticker(ticker: str) -> str:
    t = ticker.upper()
    if not any(t.endswith(s) for s in CRYPTO_SUFFIXES) and t in CRYPTO_KEYWORDS:
        return f"{t}-USD"
    return ticker

# ── 환율 ───────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def get_usd_krw_rate() -> float:
    try:
        hist = yf.Ticker("KRW=X").history(period="2d")
        if not hist.empty: return round(float(hist["Close"].iloc[-1]), 2)
    except: pass
    return 1350.0

@st.cache_data(ttl=600)
def get_jpy_krw_rate() -> float:
    """JPY/KRW 환율 (100엔 기준)"""
    try:
        usd_jpy = yf.Ticker("JPY=X").history(period="2d")
        usd_krw = yf.Ticker("KRW=X").history(period="2d")
        if not usd_jpy.empty and not usd_krw.empty:
            jpy_per_usd = float(usd_jpy["Close"].iloc[-1])
            krw_per_usd = float(usd_krw["Close"].iloc[-1])
            return round((krw_per_usd / jpy_per_usd) * 100, 2)
    except: pass
    return 900.0

# ── 주가 데이터 ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_stock_info(ticker: str) -> dict:
    ticker = normalize_crypto_ticker(ticker)
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="5d")
        if hist.empty: return {"ticker":ticker,"valid":False,"error":"데이터 없음"}
        current_price = float(hist["Close"].iloc[-1])
        prev_price = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price
        change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price else 0
        currency = info.get("currency","USD")
        decimals = 6 if "BTC" in ticker or "ETH" in ticker else 2
        return {
            "ticker": ticker,
            "name": info.get("longName", info.get("shortName", ticker)),
            "current_price": round(current_price, decimals),
            "change_pct": round(change_pct, 2),
            "currency": currency,
            "sector": info.get("sector", info.get("category","—")),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", None),
            "52w_high": info.get("fiftyTwoWeekHigh", None),
            "52w_low": info.get("fiftyTwoWeekLow", None),
            "volume": info.get("volume", 0),
            "valid": True,
        }
    except Exception as e:
        return {"ticker":ticker,"valid":False,"error":str(e)}

@st.cache_data(ttl=300)
def get_price_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    ticker = normalize_crypto_ticker(ticker)
    try: return yf.Ticker(ticker).history(period=period)
    except: return pd.DataFrame()

def get_portfolio_summary(assets: list) -> pd.DataFrame:
    usd_krw = get_usd_krw_rate()
    rows = []
    for asset in assets:
        ticker = normalize_crypto_ticker(asset["ticker"])
        info = get_stock_info(ticker)
        if not info["valid"]: continue
        current_price = info["current_price"]
        quantity = float(asset.get("quantity", 0))
        avg_price = float(asset.get("avg_price", current_price))
        currency = info["currency"]
        current_value = current_price * quantity
        cost_basis = avg_price * quantity
        profit_loss = current_value - cost_basis
        profit_loss_pct = (profit_loss / cost_basis * 100) if cost_basis else 0
        rate = usd_krw if currency == "USD" else 1.0
        rows.append({
            "티커": ticker,
            "종목명": info["name"][:22],
            "유형": asset.get("asset_type", detect_asset_type(ticker)),
            "현재가": current_price,
            "통화": currency,
            "수량": quantity,
            "평균단가": avg_price,
            "현재가치": round(current_value, 2),
            "현재가치(KRW)": round(current_value * rate, 0),
            "손익": round(profit_loss, 2),
            "손익(KRW)": round(profit_loss * rate, 0),
            "손익률(%)": round(profit_loss_pct, 2),
            "섹터": info.get("sector","—"),
            "등락률(%)": info["change_pct"],
            "메모": asset.get("note",""),
        })
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def get_market_indices() -> list:
    results = []
    for name, ticker in MARKET_INDICES.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                chg = ((current - prev) / prev * 100) if prev else 0
                results.append({"name":name,"ticker":ticker,"value":round(current,2),"change_pct":round(chg,2)})
        except: pass
    return results

# ── 뉴스 ───────────────────────────────────────────────────────────────────────

def _build_url(query: str, lang: str = "ko") -> str:
    q = urllib.parse.quote(query)
    if lang == "ko": return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    return f"https://news.google.com/rss/search?q={q}&hl=en&gl=US&ceid=US:en"

def _parse_feed(url: str, n: int) -> list:
    """RSS 피드 파싱 — 최신순으로 n개 반환"""
    items = []
    try:
        for entry in feedparser.parse(url).entries[:n]:
            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", "")[:25],
                "source": entry.get("source", {}).get("title", ""),
                "summary": entry.get("summary", "")[:300],
            })
    except:
        pass
    return items

def _dedup(news_list: list) -> list:
    seen, out = set(), []
    for n in news_list:
        if n["title"] not in seen:
            seen.add(n["title"]); out.append(n)
    return out

def get_news_for_asset(ticker: str, company_name: str = "", asset_type: str = "", max_items: int = 10) -> list:
    """보유 자산 최신 뉴스 & 리서치"""
    base = company_name if company_name else ticker.split("-")[0].replace(".KS","").replace(".KQ","")
    is_intl = asset_type in ["미국주식","ETF","암호화폐"]
    items = _parse_feed(_build_url(f"{base} 주식 투자", "ko"), 8)
    if is_intl:
        items += _parse_feed(_build_url(f"{base} stock investment", "en"), 8)
    return _dedup(items)[:max_items]

def get_general_market_news(max_items: int = 12) -> list:
    """시장 전반 최신 뉴스"""
    ko = _parse_feed(_build_url("주식 증시 금리 시황 경제", "ko"), 8)
    en = _parse_feed(_build_url("stock market fed rate economy", "en"), 8)
    return _dedup(ko + en)[:max_items]

def get_crypto_news(max_items: int = 10) -> list:
    """암호화폐 최신 뉴스"""
    ko = _parse_feed(_build_url("비트코인 이더리움 암호화폐 코인", "ko"), 7)
    en = _parse_feed(_build_url("bitcoin ethereum crypto DeFi", "en"), 7)
    return _dedup(ko + en)[:max_items]

def get_research_news(query: str, max_items: int = 8) -> list:
    """리서치 & 분석 자료 최신순"""
    ko = _parse_feed(_build_url(f"{query} 리서치 분석 전망", "ko"), 6)
    en = _parse_feed(_build_url(f"{query} research analysis outlook", "en"), 6)
    return _dedup(ko + en)[:max_items]

# ── 포트폴리오 DB ──────────────────────────────────────────────────────────────

# Streamlit Cloud는 /tmp만 쓰기 가능 → 로컬이면 utils/ 폴더, 클라우드면 /tmp 사용
def _get_db_path() -> str:
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_db.json")
    # 로컬: utils 폴더에 쓰기 가능하면 그대로 사용
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        open(local_path, "a").close()
        return local_path
    except (OSError, PermissionError):
        # 클라우드(읽기전용 파일시스템): /tmp 사용
        return "/tmp/portfolio_db.json"

DB_PATH = _get_db_path()

def load_portfolio() -> dict:
    if os.path.exists(DB_PATH):
        with open(DB_PATH,"r",encoding="utf-8") as f:
            d = json.load(f); d.setdefault("assets",[]); d.setdefault("scraps",[]); return d
    return {"assets":[],"scraps":[]}

def save_portfolio(data: dict):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH,"w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_asset(ticker, name, quantity, avg_price, asset_type="미국주식", note=""):
    ticker = normalize_crypto_ticker(ticker).upper()
    db = load_portfolio()
    for a in db["assets"]:
        if a["ticker"].upper() == ticker:
            return False, f"⚠️ {ticker} 이미 존재합니다."
    db["assets"].append({
        "ticker": ticker, "name": name, "quantity": quantity,
        "avg_price": avg_price, "asset_type": asset_type, "note": note,
        "added_at": datetime.now().isoformat()
    })
    save_portfolio(db)
    return True, f"✅ {ticker} 추가 완료!"

def update_asset(ticker, new_qty, new_avg):
    db = load_portfolio()
    for a in db["assets"]:
        if a["ticker"].upper() == ticker.upper():
            a["quantity"] = new_qty; a["avg_price"] = new_avg
            a["updated_at"] = datetime.now().isoformat()
    save_portfolio(db)

def remove_asset(ticker):
    db = load_portfolio()
    db["assets"] = [a for a in db["assets"] if a["ticker"].upper() != ticker.upper()]
    save_portfolio(db)

def add_scrap(title, link, summary, ticker, category, source=""):
    db = load_portfolio()
    if link and any(s.get("link") == link for s in db["scraps"]): return False
    scrap_id = hashlib.md5(f"{title}{ticker}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
    db["scraps"].append({
        "id": scrap_id, "title": title, "link": link, "summary": summary,
        "ticker": ticker, "category": category, "source": source,
        "scraped_at": datetime.now().isoformat()
    })
    save_portfolio(db)
    return True

def get_scraps() -> list:
    return load_portfolio().get("scraps",[])

def delete_scrap(scrap_id):
    db = load_portfolio()
    db["scraps"] = [s for s in db["scraps"] if s.get("id") != scrap_id]
    save_portfolio(db)

# ── Notion ─────────────────────────────────────────────────────────────────────

def save_to_notion(title, link, summary, ticker, category, source=""):
    api_key = os.getenv("NOTION_API_KEY","").strip()
    db_id = os.getenv("NOTION_DATABASE_ID","").strip()
    if not api_key or api_key.startswith("your_") or not db_id or db_id.startswith("your_"):
        return False, "Notion API 키/DB ID 미설정"
    headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json","Notion-Version":"2022-06-28"}
    props = {
        "제목": {"title":[{"text":{"content":title[:100]}}]},
        "날짜": {"date":{"start":datetime.now().strftime("%Y-%m-%d")}},
        "자산": {"rich_text":[{"text":{"content":ticker[:50]}}]},
        "카테고리": {"rich_text":[{"text":{"content":category[:50]}}]},
        "출처": {"rich_text":[{"text":{"content":source[:100]}}]},
        "요약": {"rich_text":[{"text":{"content":summary[:1800]}}]},
    }
    if link: props["링크"] = {"url": link}
    try:
        r = requests.post("https://api.notion.com/v1/pages", headers=headers,
                          json={"parent":{"database_id":db_id},"properties":props}, timeout=12)
        if r.status_code == 200: return True, "✅ Notion 저장 완료!"
        return False, f"Notion 오류: {r.json().get('message','')}"
    except requests.exceptions.Timeout:
        return False, "Notion 연결 시간 초과"
    except Exception as e:
        return False, f"오류: {e}"
