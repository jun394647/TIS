"""
utils/notion_db.py — Notion을 완전한 DB로 활용

포트폴리오 DB 속성 (영어):
  Name        : title   — 티커 심볼
  StockName   : text    — 종목명
  Quantity    : number  — 수량
  AvgPrice    : number  — 평균단가
  AssetType   : select  — 자산유형
  Note        : text    — 메모
  AddedDate   : date    — 추가일

스크랩 DB 속성 (영어):
  Name        : title   — 뉴스 제목
  Ticker      : text    — 자산 티커
  Category    : select  — 카테고리
  Source      : text    — 출처
  Summary     : text    — 요약
  Link        : url     — 링크
  ScrapDate   : date    — 날짜
"""

import os, time, requests
from datetime import datetime

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"

# ── 속성명 매핑 ────────────────────────────────────────────────────────────────
P = {
    "ticker":     "Name",
    "name":       "StockName",
    "quantity":   "Quantity",
    "avg_price":  "AvgPrice",
    "asset_type": "AssetType",
    "note":       "Note",
    "added_at":   "AddedDate",
}
S = {
    "title":    "Name",
    "ticker":   "Ticker",
    "category": "Category",
    "source":   "Source",
    "summary":  "Summary",
    "link":     "Link",
    "date":     "ScrapDate",
}


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _api_key() -> str:
    return os.getenv("NOTION_API_KEY", "").strip()

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

def _portfolio_db_id() -> str:
    return os.getenv("NOTION_PORTFOLIO_DB_ID", "").strip()

def _scrap_db_id() -> str:
    return os.getenv("NOTION_SCRAP_DB_ID", "").strip()

def _is_configured(db_type: str = "portfolio") -> bool:
    key = _api_key()
    if not key or key.startswith("your_") or key.startswith("secret_your"):
        return False
    db_id = _portfolio_db_id() if db_type == "portfolio" else _scrap_db_id()
    return bool(db_id and not db_id.startswith("your_"))

def _rich_text(text: str, limit: int = 2000) -> list:
    return [{"text": {"content": str(text)[:limit]}}]

def _get_text(prop: dict) -> str:
    items = prop.get("rich_text") or prop.get("title") or []
    return "".join(t.get("text", {}).get("content", "") for t in items)

def _get_num(prop: dict) -> float:
    return float(prop.get("number") or 0)

def _get_select(prop: dict) -> str:
    sel = prop.get("select")
    return sel.get("name", "") if sel else ""

def _get_date(prop: dict) -> str:
    d = prop.get("date")
    return d.get("start", "") if d else ""

def _get_url(prop: dict) -> str:
    return prop.get("url") or ""

def _request_with_retry(method: str, url: str, max_retry: int = 3, **kwargs) -> requests.Response:
    """재시도 로직 포함 HTTP 요청 — 실패 시 예외를 그대로 raise"""
    last_exc = None
    for attempt in range(max_retry):
        try:
            r = getattr(requests, method)(url, headers=_headers(), timeout=20, **kwargs)
            # 429 Rate limit: 잠깐 대기 후 재시도
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            return r
        except requests.exceptions.Timeout as e:
            last_exc = e
            time.sleep(1)
        except requests.exceptions.ConnectionError as e:
            last_exc = e
            time.sleep(2 ** attempt)
    raise last_exc or RuntimeError(f"Notion API 요청 실패: {url}")


# ══════════════════════════════════════════════════════════════════════════════
# 포트폴리오 CRUD
# ══════════════════════════════════════════════════════════════════════════════

def load_assets() -> tuple[list, str]:
    """
    Notion 포트폴리오 DB에서 자산 조회.
    Returns: (assets_list, error_message)
      - 성공: (list, "")
      - 실패: ([], "오류 설명")
    """
    if not _is_configured("portfolio"):
        return [], "포트폴리오 DB ID 또는 API 키가 설정되지 않았습니다."
    try:
        r = _request_with_retry(
            "post",
            f"{BASE_URL}/databases/{_portfolio_db_id()}/query",
            json={"page_size": 100},
        )
        if r.status_code != 200:
            msg = r.json().get("message", r.text[:200])
            return [], f"Notion API 오류 ({r.status_code}): {msg}"

        assets = []
        for page in r.json().get("results", []):
            props = page.get("properties", {})
            ticker = _get_text(props.get(P["ticker"], {}))
            if not ticker:
                continue
            assets.append({
                "page_id":    page["id"],
                "ticker":     ticker,
                "name":       _get_text(props.get(P["name"], {})),
                "quantity":   _get_num(props.get(P["quantity"], {})),
                "avg_price":  _get_num(props.get(P["avg_price"], {})),
                "asset_type": _get_select(props.get(P["asset_type"], {})) or "미국주식",
                "note":       _get_text(props.get(P["note"], {})),
                "added_at":   _get_date(props.get(P["added_at"], {})),
            })
        return assets, ""

    except requests.exceptions.Timeout:
        return [], "Notion 연결 시간 초과 (20초). 네트워크를 확인하세요."
    except requests.exceptions.ConnectionError:
        return [], "Notion 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요."
    except Exception as e:
        return [], f"예상치 못한 오류: {e}"


def add_asset_notion(ticker: str, name: str, quantity: float,
                     avg_price: float, asset_type: str = "미국주식",
                     note: str = "") -> tuple[bool, str]:
    if not _is_configured("portfolio"):
        return False, "Notion 포트폴리오 DB가 설정되지 않았습니다."
    # 중복 체크
    existing, err = load_assets()
    if err:
        return False, f"중복 확인 실패: {err}"
    for a in existing:
        if a["ticker"].upper() == ticker.upper():
            return False, f"⚠️ {ticker} 이미 존재합니다."
    props = {
        P["ticker"]:     {"title": _rich_text(ticker.upper())},
        P["name"]:       {"rich_text": _rich_text(name)},
        P["quantity"]:   {"number": float(quantity)},
        P["avg_price"]:  {"number": float(avg_price)},
        P["asset_type"]: {"select": {"name": asset_type}},
        P["note"]:       {"rich_text": _rich_text(note)},
        P["added_at"]:   {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
    }
    try:
        r = _request_with_retry(
            "post", f"{BASE_URL}/pages",
            json={"parent": {"database_id": _portfolio_db_id()}, "properties": props},
        )
        if r.status_code == 200:
            return True, f"✅ {ticker} 추가 완료!"
        return False, f"Notion 오류: {r.json().get('message', r.text[:200])}"
    except Exception as e:
        return False, f"오류: {e}"


def update_asset_notion(page_id: str, quantity: float, avg_price: float) -> tuple[bool, str]:
    if not _is_configured("portfolio"):
        return False, "Notion 포트폴리오 DB 미설정"
    props = {
        P["quantity"]:  {"number": float(quantity)},
        P["avg_price"]: {"number": float(avg_price)},
    }
    try:
        r = _request_with_retry("patch", f"{BASE_URL}/pages/{page_id}", json={"properties": props})
        if r.status_code == 200:
            return True, "✅ 수정 완료"
        return False, f"Notion 오류: {r.json().get('message','')}"
    except Exception as e:
        return False, f"오류: {e}"


def remove_asset_notion(page_id: str) -> tuple[bool, str]:
    if not _is_configured("portfolio"):
        return False, "Notion 포트폴리오 DB 미설정"
    try:
        r = _request_with_retry("patch", f"{BASE_URL}/pages/{page_id}", json={"archived": True})
        if r.status_code == 200:
            return True, "✅ 삭제 완료"
        return False, f"Notion 오류: {r.json().get('message','')}"
    except Exception as e:
        return False, f"오류: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 스크랩 CRUD
# ══════════════════════════════════════════════════════════════════════════════

def load_scraps(limit: int = 100) -> tuple[list, str]:
    """
    Returns: (scraps_list, error_message)
    """
    if not _is_configured("scrap"):
        return [], "스크랩 DB ID 또는 API 키가 설정되지 않았습니다."
    try:
        r = _request_with_retry(
            "post",
            f"{BASE_URL}/databases/{_scrap_db_id()}/query",
            json={
                "page_size": limit,
                "sorts": [{"property": S["date"], "direction": "descending"}],
            },
        )
        if r.status_code != 200:
            msg = r.json().get("message", r.text[:200])
            return [], f"Notion API 오류 ({r.status_code}): {msg}"

        scraps = []
        for page in r.json().get("results", []):
            props = page.get("properties", {})
            scraps.append({
                "page_id":    page["id"],
                "id":         page["id"],
                "title":      _get_text(props.get(S["title"], {})),
                "ticker":     _get_text(props.get(S["ticker"], {})),
                "category":   _get_select(props.get(S["category"], {})),
                "source":     _get_text(props.get(S["source"], {})),
                "summary":    _get_text(props.get(S["summary"], {})),
                "link":       _get_url(props.get(S["link"], {})),
                "scraped_at": _get_date(props.get(S["date"], {})),
            })
        return scraps, ""

    except requests.exceptions.Timeout:
        return [], "Notion 연결 시간 초과"
    except requests.exceptions.ConnectionError:
        return [], "Notion 서버 연결 실패"
    except Exception as e:
        return [], f"예상치 못한 오류: {e}"


def add_scrap_notion(title: str, link: str, summary: str,
                     ticker: str, category: str, source: str = "") -> tuple[bool, str]:
    if not _is_configured("scrap"):
        return False, "Notion 스크랩 DB가 설정되지 않았습니다."
    props = {
        S["title"]:    {"title": _rich_text(title[:100])},
        S["ticker"]:   {"rich_text": _rich_text(ticker[:50])},
        S["category"]: {"select": {"name": category[:50]}},
        S["source"]:   {"rich_text": _rich_text(source[:100])},
        S["summary"]:  {"rich_text": _rich_text(summary[:1800])},
        S["date"]:     {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
    }
    if link:
        props[S["link"]] = {"url": link[:2000]}
    try:
        r = _request_with_retry(
            "post", f"{BASE_URL}/pages",
            json={"parent": {"database_id": _scrap_db_id()}, "properties": props},
        )
        if r.status_code == 200:
            return True, "✅ Notion 저장 완료!"
        return False, f"Notion 오류: {r.json().get('message', r.text[:200])}"
    except Exception as e:
        return False, f"오류: {e}"


def delete_scrap_notion(page_id: str) -> tuple[bool, str]:
    if not _is_configured("scrap"):
        return False, "Notion 스크랩 DB 미설정"
    try:
        r = _request_with_retry("patch", f"{BASE_URL}/pages/{page_id}", json={"archived": True})
        if r.status_code == 200:
            return True, "✅ 삭제 완료"
        return False, f"Notion 오류: {r.json().get('message','')}"
    except Exception as e:
        return False, f"오류: {e}"


# ── 연결 상태 확인 ────────────────────────────────────────────────────────────

def check_notion_connection() -> dict:
    api_ok       = bool(_api_key()) and not _api_key().startswith("your_")
    portfolio_ok = _is_configured("portfolio")
    scrap_ok     = _is_configured("scrap")
    return {
        "api_key":      api_ok,
        "portfolio_db": portfolio_ok,
        "scrap_db":     scrap_ok,
        "fully_ready":  api_ok and portfolio_ok and scrap_ok,
    }
