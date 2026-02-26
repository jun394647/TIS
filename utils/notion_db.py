"""
utils/notion_db.py
Notion을 완전한 데이터베이스로 활용
- 포트폴리오 DB: 자산 추가/수정/삭제/조회
- 스크랩 DB: 뉴스 및 리서치 스크랩 저장/조회/삭제

필요한 Notion 환경변수:
  NOTION_API_KEY            : Notion Integration 토큰
  NOTION_PORTFOLIO_DB_ID    : 포트폴리오 전용 DB ID
  NOTION_SCRAP_DB_ID        : 스크랩 전용 DB ID
"""

import os
import requests
import streamlit as st
from datetime import datetime

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _get_secret(key: str) -> str:
    try:
        v = st.secrets.get(key, "")
        if v: return v
    except Exception:
        pass
    return os.getenv(key, "")

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_secret('NOTION_API_KEY')}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

def _portfolio_db_id() -> str:
    return _get_secret("NOTION_PORTFOLIO_DB_ID")

def _scrap_db_id() -> str:
    return _get_secret("NOTION_SCRAP_DB_ID")

def _is_configured(db_type: str = "portfolio") -> bool:
    key = _get_secret("NOTION_API_KEY")
    if not key or key.startswith("your_"):
        return False
    db_id = _portfolio_db_id() if db_type == "portfolio" else _scrap_db_id()
    return bool(db_id and not db_id.startswith("your_"))

def _rich_text(text: str, limit: int = 2000) -> list:
    return [{"text": {"content": str(text)[:limit]}}]

def _get_text(prop: dict) -> str:
    """Notion rich_text / title 속성에서 텍스트 추출"""
    items = prop.get("rich_text") or prop.get("title") or []
    return "".join(t.get("text", {}).get("content", "") for t in items)

def _get_num(prop: dict) -> float:
    return prop.get("number") or 0.0

def _get_select(prop: dict) -> str:
    sel = prop.get("select")
    return sel.get("name", "") if sel else ""

def _get_date(prop: dict) -> str:
    d = prop.get("date")
    return d.get("start", "") if d else ""

def _get_url(prop: dict) -> str:
    return prop.get("url") or ""


# ══════════════════════════════════════════════════════════════════════════════
# 포트폴리오 DB
# ══════════════════════════════════════════════════════════════════════════════
# Notion DB 속성 구성 (포트폴리오):
#   티커       : title
#   종목명     : rich_text
#   수량       : number
#   평균단가   : number
#   자산유형   : select
#   메모       : rich_text
#   추가일     : date

def load_assets() -> list:
    """Notion 포트폴리오 DB에서 모든 자산 조회"""
    if not _is_configured("portfolio"):
        return []
    try:
        r = requests.post(
            f"{BASE_URL}/databases/{_portfolio_db_id()}/query",
            headers=_headers(),
            json={"page_size": 100},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        assets = []
        for page in r.json().get("results", []):
            props = page.get("properties", {})
            ticker = _get_text(props.get("티커", {}))
            if not ticker:
                continue
            assets.append({
                "page_id":   page["id"],
                "ticker":    ticker,
                "name":      _get_text(props.get("종목명", {})),
                "quantity":  _get_num(props.get("수량", {})),
                "avg_price": _get_num(props.get("평균단가", {})),
                "asset_type": _get_select(props.get("자산유형", {})) or "미국주식",
                "note":      _get_text(props.get("메모", {})),
                "added_at":  _get_date(props.get("추가일", {})),
            })
        return assets
    except Exception:
        return []


def add_asset_notion(ticker: str, name: str, quantity: float,
                     avg_price: float, asset_type: str = "미국주식",
                     note: str = "") -> tuple[bool, str]:
    """Notion 포트폴리오 DB에 자산 추가"""
    if not _is_configured("portfolio"):
        return False, "Notion 포트폴리오 DB가 설정되지 않았습니다."
    # 중복 체크
    existing = load_assets()
    for a in existing:
        if a["ticker"].upper() == ticker.upper():
            return False, f"⚠️ {ticker} 이미 존재합니다."
    props = {
        "티커":     {"title": _rich_text(ticker.upper())},
        "종목명":   {"rich_text": _rich_text(name)},
        "수량":     {"number": float(quantity)},
        "평균단가": {"number": float(avg_price)},
        "자산유형": {"select": {"name": asset_type}},
        "메모":     {"rich_text": _rich_text(note)},
        "추가일":   {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
    }
    try:
        r = requests.post(
            f"{BASE_URL}/pages",
            headers=_headers(),
            json={"parent": {"database_id": _portfolio_db_id()}, "properties": props},
            timeout=15,
        )
        if r.status_code == 200:
            return True, f"✅ {ticker} 추가 완료!"
        return False, f"Notion 오류: {r.json().get('message', r.text[:100])}"
    except Exception as e:
        return False, f"오류: {e}"


def update_asset_notion(page_id: str, quantity: float, avg_price: float) -> tuple[bool, str]:
    """Notion 포트폴리오 DB에서 수량/단가 수정"""
    if not _is_configured("portfolio"):
        return False, "Notion 포트폴리오 DB 미설정"
    props = {
        "수량":     {"number": float(quantity)},
        "평균단가": {"number": float(avg_price)},
    }
    try:
        r = requests.patch(
            f"{BASE_URL}/pages/{page_id}",
            headers=_headers(),
            json={"properties": props},
            timeout=15,
        )
        if r.status_code == 200:
            return True, "✅ 수정 완료"
        return False, f"Notion 오류: {r.json().get('message','')}"
    except Exception as e:
        return False, f"오류: {e}"


def remove_asset_notion(page_id: str) -> tuple[bool, str]:
    """Notion 페이지 아카이브(삭제)"""
    if not _is_configured("portfolio"):
        return False, "Notion 포트폴리오 DB 미설정"
    try:
        r = requests.patch(
            f"{BASE_URL}/pages/{page_id}",
            headers=_headers(),
            json={"archived": True},
            timeout=15,
        )
        if r.status_code == 200:
            return True, "✅ 삭제 완료"
        return False, f"Notion 오류: {r.json().get('message','')}"
    except Exception as e:
        return False, f"오류: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 스크랩 DB
# ══════════════════════════════════════════════════════════════════════════════
# Notion DB 속성 구성 (스크랩):
#   제목       : title
#   자산       : rich_text
#   카테고리   : select
#   출처       : rich_text
#   요약       : rich_text
#   링크       : url
#   날짜       : date

def load_scraps(limit: int = 100) -> list:
    """Notion 스크랩 DB에서 목록 조회 (최신순)"""
    if not _is_configured("scrap"):
        return []
    try:
        r = requests.post(
            f"{BASE_URL}/databases/{_scrap_db_id()}/query",
            headers=_headers(),
            json={
                "page_size": limit,
                "sorts": [{"property": "날짜", "direction": "descending"}],
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []
        scraps = []
        for page in r.json().get("results", []):
            props = page.get("properties", {})
            scraps.append({
                "page_id":    page["id"],
                "id":         page["id"],
                "title":      _get_text(props.get("제목", {})),
                "ticker":     _get_text(props.get("자산", {})),
                "category":   _get_select(props.get("카테고리", {})),
                "source":     _get_text(props.get("출처", {})),
                "summary":    _get_text(props.get("요약", {})),
                "link":       _get_url(props.get("링크", {})),
                "scraped_at": _get_date(props.get("날짜", {})),
            })
        return scraps
    except Exception:
        return []


def add_scrap_notion(title: str, link: str, summary: str,
                     ticker: str, category: str, source: str = "") -> tuple[bool, str]:
    """Notion 스크랩 DB에 저장"""
    if not _is_configured("scrap"):
        return False, "Notion 스크랩 DB가 설정되지 않았습니다."
    props = {
        "제목":     {"title": _rich_text(title[:100])},
        "자산":     {"rich_text": _rich_text(ticker[:50])},
        "카테고리": {"select": {"name": category[:50]}},
        "출처":     {"rich_text": _rich_text(source[:100])},
        "요약":     {"rich_text": _rich_text(summary[:1800])},
        "날짜":     {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
    }
    if link:
        props["링크"] = {"url": link[:2000]}
    try:
        r = requests.post(
            f"{BASE_URL}/pages",
            headers=_headers(),
            json={"parent": {"database_id": _scrap_db_id()}, "properties": props},
            timeout=15,
        )
        if r.status_code == 200:
            return True, "✅ Notion 저장 완료!"
        return False, f"Notion 오류: {r.json().get('message', r.text[:100])}"
    except Exception as e:
        return False, f"오류: {e}"


def delete_scrap_notion(page_id: str) -> tuple[bool, str]:
    """Notion 스크랩 페이지 아카이브(삭제)"""
    if not _is_configured("scrap"):
        return False, "Notion 스크랩 DB 미설정"
    try:
        r = requests.patch(
            f"{BASE_URL}/pages/{page_id}",
            headers=_headers(),
            json={"archived": True},
            timeout=15,
        )
        if r.status_code == 200:
            return True, "✅ 삭제 완료"
        return False, f"Notion 오류: {r.json().get('message','')}"
    except Exception as e:
        return False, f"오류: {e}"


# ── 연결 상태 확인 ────────────────────────────────────────────────────────────

def check_notion_connection() -> dict:
    """Notion 연결 상태 반환"""
    api_ok = bool(_get_secret("NOTION_API_KEY"))
    portfolio_ok = _is_configured("portfolio")
    scrap_ok = _is_configured("scrap")
    return {
        "api_key": api_ok,
        "portfolio_db": portfolio_ok,
        "scrap_db": scrap_ok,
        "fully_ready": api_ok and portfolio_ok and scrap_ok,
    }
