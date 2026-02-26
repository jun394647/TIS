import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os, sys
from datetime import datetime

# ── 환경변수: Streamlit Cloud(st.secrets) 우선, 로컬(.env) 폴백 ───────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def _get_secret(key: str, default: str = "") -> str:
    try:
        val = st.secrets.get(key, "")
        if val: return val
    except Exception:
        pass
    return os.getenv(key, default)

for _k in ("GEMINI_API_KEY", "NOTION_API_KEY",
           "NOTION_PORTFOLIO_DB_ID", "NOTION_SCRAP_DB_ID"):
    _v = _get_secret(_k)
    if _v: os.environ[_k] = _v

sys.path.insert(0, os.path.dirname(__file__))

# ── Notion DB 레이어 ───────────────────────────────────────────────────────────
from utils.notion_db import (
    load_assets, add_asset_notion, update_asset_notion, remove_asset_notion,
    load_scraps, add_scrap_notion, delete_scrap_notion,
    check_notion_connection,
)

# ── 주가/뉴스 유틸 ──────────────────────────────────────────────────────────────
from utils.data import (
    get_stock_info, get_price_history, get_portfolio_summary,
    get_market_indices, get_news_for_asset, get_general_market_news,
    get_crypto_news, get_research_news,
    ASSET_TYPES, ASSET_TYPE_ICONS, detect_asset_type,
    get_usd_krw_rate, get_jpy_krw_rate, normalize_crypto_ticker,
)
from utils.ai import get_gemini_analysis

# ── 페이지 설정 ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Portfolio AI", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&family=Space+Mono:wght@400;700&display=swap');
:root {
    --bg:#06090f; --bg1:#0c1220; --bg2:#111c2e; --bg3:#172238;
    --accent:#00e5b4; --accent2:#4d9fff; --accent3:#f59e0b;
    --red:#ff4466; --text:#dde5f0; --muted:#6b7f99; --border:#1a2d47;
}
*,html,body{box-sizing:border-box;}
html,body,[class*="css"]{font-family:'Noto Sans KR',sans-serif!important;background:var(--bg)!important;color:var(--text);}
.stApp{background:var(--bg)!important;}
[data-testid="stSidebar"]{background:var(--bg1)!important;border-right:1px solid var(--border);}
[data-testid="stSidebar"] *{color:var(--text)!important;}
.header-bar{background:linear-gradient(135deg,var(--bg1) 0%,var(--bg2) 100%);border:1px solid var(--border);border-radius:16px;padding:20px 28px;margin-bottom:20px;}
.logo-main{font-size:28px;font-weight:900;letter-spacing:-1px;background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.logo-sub{font-size:12px;color:var(--muted);margin-top:2px;}
.stat-card{background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:18px 22px;transition:border-color 0.2s,transform 0.15s;}
.stat-card:hover{border-color:var(--accent2);transform:translateY(-2px);}
.stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px;}
.stat-value{font-family:'Space Mono',monospace;font-size:20px;font-weight:700;color:var(--text);}
.stat-sub{font-family:'Space Mono',monospace;font-size:12px;margin-top:4px;}
.up{color:var(--accent)!important;} .dn{color:var(--red)!important;}
.idx-pill{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:10px 14px;text-align:center;transition:border-color 0.2s;}
.idx-pill:hover{border-color:var(--accent2);}
.idx-name{font-size:9px;color:var(--muted);letter-spacing:0.8px;text-transform:uppercase;margin-bottom:4px;}
.idx-val{font-family:'Space Mono',monospace;font-size:14px;font-weight:700;}
.idx-chg{font-family:'Space Mono',monospace;font-size:10px;margin-top:2px;}
.nc{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin-bottom:8px;transition:border-color 0.15s;}
.nc:hover{border-color:var(--accent2);}
.nc-title{font-size:13px;font-weight:500;margin-bottom:4px;}
.nc-title a{color:var(--text);text-decoration:none;}
.nc-title a:hover{color:var(--accent2);}
.nc-meta{font-size:10px;color:var(--muted);}
.sec{font-size:16px;font-weight:700;color:var(--text);border-left:3px solid var(--accent);padding-left:10px;margin:20px 0 12px 0;}
.tag{display:inline-block;background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:2px 9px;font-size:10px;color:var(--accent2);margin-right:4px;}
.ai-box{background:linear-gradient(135deg,#0c1e38 0%,#071428 100%);border:1px solid #1e3d63;border-left:3px solid var(--accent2);border-radius:14px;padding:24px 28px;font-size:14px;line-height:1.85;color:var(--text);}
.notion-badge{display:inline-flex;align-items:center;gap:6px;background:#1a2635;border:1px solid #2a4060;border-radius:8px;padding:4px 10px;font-size:11px;color:#60a5fa;}
.stButton>button{background:var(--bg3)!important;color:var(--text)!important;border:1px solid var(--border)!important;border-radius:8px!important;font-family:'Noto Sans KR',sans-serif!important;transition:all 0.15s!important;}
.stButton>button:hover{border-color:var(--accent)!important;color:var(--accent)!important;}
.stTextInput input,.stNumberInput input{background:var(--bg2)!important;color:var(--text)!important;border-color:var(--border)!important;}
hr{border-color:var(--border)!important;}
</style>
""", unsafe_allow_html=True)

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
def chg_cls(v): return "up" if v >= 0 else "dn"
def chg_arrow(v): return "▲" if v >= 0 else "▼"

def _scrap_btn(key: str, title: str, link: str, summary: str,
               ticker: str, category: str, source: str = ""):
    """공통 스크랩 버튼 — Notion에 직접 저장"""
    if st.button("📎 스크랩", key=key):
        ok, msg = add_scrap_notion(title, link, summary, ticker, category, source)
        if ok:
            st.success(msg)
        else:
            st.warning(msg)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="padding:12px 0 8px">
        <div style="font-size:22px;font-weight:900;letter-spacing:-0.5px;
            background:linear-gradient(90deg,#00e5b4,#4d9fff);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            📊 Portfolio AI</div>
        <div style="font-size:11px;color:#6b7f99;margin-top:2px;">스마트 자산 관리 시스템</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("---")

    page = st.radio("", [
        "🏠 대시보드", "💼 포트폴리오 관리", "₿ 암호화폐",
        "📰 뉴스 & 리서치", "📎 스크랩북", "🤖 AI 분석",
    ], label_visibility="collapsed")

    st.markdown("---")

    # API 설정
    # with st.expander("⚙️ API 설정", expanded=False):
    #     st.markdown("<div style='font-size:11px;color:#6b7f99;margin-bottom:8px;'>Streamlit Cloud → Secrets에서 자동 로드</div>", unsafe_allow_html=True)
    #     g_key = st.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY",""), type="password", key="gkey")
    #     n_key = st.text_input("Notion API Key", value=os.getenv("NOTION_API_KEY",""), type="password", key="nkey")
    #     p_db  = st.text_input("포트폴리오 DB ID", value=os.getenv("NOTION_PORTFOLIO_DB_ID",""), key="pdb")
    #     s_db  = st.text_input("스크랩 DB ID",     value=os.getenv("NOTION_SCRAP_DB_ID",""), key="sdb")
    #     if g_key: os.environ["GEMINI_API_KEY"] = g_key
    #     if n_key: os.environ["NOTION_API_KEY"] = n_key
    #     if p_db:  os.environ["NOTION_PORTFOLIO_DB_ID"] = p_db
    #     if s_db:  os.environ["NOTION_SCRAP_DB_ID"] = s_db

    # 연결 상태
    nc = check_notion_connection()
    gemini_ok = bool(os.getenv("GEMINI_API_KEY","")) and not os.getenv("GEMINI_API_KEY","").startswith("your_")
    st.markdown(f"{'🟢' if gemini_ok else '🔴'} Gemini {'연결됨' if gemini_ok else '미설정'}")
    st.markdown(f"{'🟢' if nc['api_key'] else '🔴'} Notion API {'연결됨' if nc['api_key'] else '미설정'}")
    st.markdown(f"{'🟢' if nc['portfolio_db'] else '🔴'} 포트폴리오 DB {'연결됨' if nc['portfolio_db'] else '미설정'}")
    st.markdown(f"{'🟢' if nc['scrap_db'] else '🔴'} 스크랩 DB {'연결됨' if nc['scrap_db'] else '미설정'}")

    usd_krw = get_usd_krw_rate()
    jpy_krw = get_jpy_krw_rate()
    st.markdown(f"""<div style='font-size:11px;color:#6b7f99;margin-top:8px;line-height:2;'>
        💱 USD/KRW &nbsp;<b style='color:#dde5f0;font-family:Space Mono,monospace;'>{usd_krw:,.0f}</b><br>
        💴 JPY/KRW &nbsp;<b style='color:#dde5f0;font-family:Space Mono,monospace;'>{jpy_krw:.2f}</b>
        <span style='font-size:10px;'>(100엔)</span>
    </div>""", unsafe_allow_html=True)

# ── 공통: Notion에서 자산 목록 로드 ──────────────────────────────────────────
@st.cache_data(ttl=60)
def _cached_assets():
    return load_assets()

@st.cache_data(ttl=60)
def _cached_scraps():
    return load_scraps()

assets = _cached_assets()


# ════════════════════════════════════════════════════════════════════════════════
# 1) 대시보드
# ════════════════════════════════════════════════════════════════════════════════
if page == "🏠 대시보드":
    st.markdown("""<div class="header-bar">
        <div>
            <div class="logo-main">📊 Portfolio AI</div>
            <div class="logo-sub">실시간 자산 관리 & AI 투자 전략 플랫폼 · Powered by Notion DB</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Notion 미설정 안내
    if not nc["fully_ready"]:
        st.warning("⚠️ Notion DB가 완전히 설정되지 않았습니다. 사이드바 → API 설정에서 포트폴리오 DB ID와 스크랩 DB ID를 입력해주세요.")

    # 시장 지수
    st.markdown('<div class="sec">📡 실시간 시장 지표</div>', unsafe_allow_html=True)
    with st.spinner("시장 데이터 로딩 중…"):
        indices = get_market_indices()
    if indices:
        cols_per_row = 6
        for i in range(0, len(indices), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, idx in enumerate(indices[i:i+cols_per_row]):
                chg = idx["change_pct"]
                cls = chg_cls(chg)
                with cols[j]:
                    st.markdown(f"""<div class="idx-pill">
                        <div class="idx-name">{idx['name']}</div>
                        <div class="idx-val {cls}">{idx['value']:,.2f}</div>
                        <div class="idx-chg {cls}">{chg_arrow(chg)} {abs(chg):.2f}%</div>
                    </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # 포트폴리오 요약
    if not assets:
        st.info("💡 '포트폴리오 관리' 메뉴에서 자산을 추가해보세요. (Notion DB 연동 필요)")
    else:
        st.markdown('<div class="sec">💼 포트폴리오 현황</div>', unsafe_allow_html=True)
        with st.spinner("포트폴리오 데이터 로딩…"):
            df = get_portfolio_summary(assets)

        if not df.empty:
            total_val_krw = df["현재가치(KRW)"].sum()
            total_pl_krw  = df["손익(KRW)"].sum()
            cost_krw      = total_val_krw - total_pl_krw
            total_pl_pct  = (total_pl_krw / cost_krw * 100) if cost_krw else 0
            day_chg_pct   = df["등락률(%)"].mean()

            c1, c2, c3, c4 = st.columns(4)
            for col, (label, val, sub, cls) in zip([c1,c2,c3,c4], [
                ("총 평가가치",   f"₩{total_val_krw:,.0f}", "",                       ""),
                ("총 투자비용",   f"₩{cost_krw:,.0f}",      "",                       ""),
                ("총 손익",       f"₩{total_pl_krw:+,.0f}", f"{total_pl_pct:+.2f}%",  chg_cls(total_pl_krw)),
                ("오늘 평균 등락",f"{day_chg_pct:+.2f}%",   f"{len(assets)}개 종목",  chg_cls(day_chg_pct)),
            ]):
                with col:
                    st.markdown(f"""<div class="stat-card">
                        <div class="stat-label">{label}</div>
                        <div class="stat-value {cls}">{val}</div>
                        {f'<div class="stat-sub {cls}">{sub}</div>' if sub else ''}
                    </div>""", unsafe_allow_html=True)

            col_l, col_r = st.columns(2)
            with col_l:
                fig = px.pie(df, values="현재가치(KRW)", names="티커", title="자산 비중",
                    color_discrete_sequence=["#00e5b4","#4d9fff","#f59e0b","#f472b6","#a78bfa","#34d399","#60a5fa"])
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(paper_bgcolor="#0c1220", plot_bgcolor="#0c1220",
                    font_color="#dde5f0", title_font_color="#dde5f0",
                    legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig, use_container_width=True)
            with col_r:
                colors = ["#00e5b4" if v>=0 else "#ff4466" for v in df["손익률(%)"]]
                fig2 = go.Figure(go.Bar(x=df["티커"], y=df["손익률(%)"],
                    marker_color=colors, text=[f"{v:+.1f}%" for v in df["손익률(%)"]],
                    textposition="outside", textfont=dict(size=11)))
                fig2.update_layout(title="종목별 수익률 (%)",
                    paper_bgcolor="#0c1220", plot_bgcolor="#0c1220",
                    font_color="#dde5f0", title_font_color="#dde5f0",
                    xaxis=dict(gridcolor="#1a2d47"),
                    yaxis=dict(gridcolor="#1a2d47", zeroline=True, zerolinecolor="#2a4060"),
                    margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig2, use_container_width=True)

    # 시장 뉴스 (스크랩 버튼 포함)
    st.markdown('<div class="sec">📰 시장 뉴스</div>', unsafe_allow_html=True)
    with st.spinner("뉴스 로딩…"):
        market_news = get_general_market_news(10)
    if not market_news:
        st.info("최신 뉴스가 없습니다.")
    for n in market_news:
        c_n, c_s = st.columns([6, 1])
        with c_n:
            st.markdown(f"""<div class="nc">
                <div class="nc-title"><a href="{n['link']}" target="_blank">🔗 {n['title']}</a></div>
                <div class="nc-meta">📰 {n.get('source','—')} &nbsp;·&nbsp; 🕐 {n.get('published','')[:16]}</div>
            </div>""", unsafe_allow_html=True)
        with c_s:
            _scrap_btn(f"db_sc_{hash(n['title'])%99999}",
                       n["title"], n["link"], n.get("summary",""), "시장전반", "시장뉴스", n.get("source",""))


# ════════════════════════════════════════════════════════════════════════════════
# 2) 포트폴리오 관리
# ════════════════════════════════════════════════════════════════════════════════
elif page == "💼 포트폴리오 관리":
    st.markdown('<div class="sec">💼 자산 포트폴리오 (Notion DB)</div>', unsafe_allow_html=True)

    if not nc["portfolio_db"]:
        st.error("❌ Notion 포트폴리오 DB ID가 설정되지 않았습니다. 사이드바 → API 설정에서 입력해주세요.")
        st.stop()

    tab_view, tab_add, tab_edit = st.tabs(["📋 보유 현황", "➕ 자산 추가", "✏️ 수정 / 삭제"])

    with tab_add:
        st.markdown("#### 새 자산 추가")
        st.markdown("""<div style="font-size:12px;color:#6b7f99;background:#0c1220;border:1px solid #1a2d47;border-radius:8px;padding:10px 14px;margin-bottom:16px;">
        💡 <b>티커 예시</b>: 한국 <code>005930.KS</code> &nbsp;|&nbsp; 미국 <code>AAPL</code>, <code>TSLA</code> &nbsp;|&nbsp;
        ETF <code>QQQ</code>, <code>069500.KS</code> &nbsp;|&nbsp; 암호화폐 <code>BTC</code>, <code>ETH</code>
        </div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            new_ticker = st.text_input("티커 심볼 *", placeholder="예: AAPL / 005930.KS / BTC")
            auto_type  = detect_asset_type(new_ticker) if new_ticker else "미국주식"
            new_type   = st.selectbox("자산 유형", ASSET_TYPES,
                           index=ASSET_TYPES.index(auto_type) if auto_type in ASSET_TYPES else 0)
            new_note   = st.text_input("메모 (선택)")
        with c2:
            new_qty  = st.number_input("보유 수량 *", min_value=0.000001, value=1.0, format="%.6f")
            new_avg  = st.number_input("평균 매입단가 *", min_value=0.000001, value=100.0, format="%.4f")
            new_name = st.text_input("종목명 (비우면 자동 조회)")

        if st.button("✅ Notion에 추가", use_container_width=True):
            if not new_ticker.strip():
                st.error("티커를 입력해주세요.")
            else:
                with st.spinner("종목 확인 & Notion 저장 중…"):
                    info = get_stock_info(new_ticker.strip())
                    final_name = new_name.strip() if new_name.strip() else info.get("name", new_ticker)
                    ok, msg = add_asset_notion(new_ticker.strip(), final_name, new_qty, new_avg, new_type, new_note)
                if ok:
                    st.success(msg)
                    if info.get("valid"):
                        st.info(f"📌 현재가: {info['current_price']:,.4f} {info['currency']} | 섹터: {info.get('sector','—')}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning(msg)

    with tab_view:
        if not assets:
            st.info("보유 자산이 없습니다. '자산 추가' 탭에서 추가하세요.")
        else:
            with st.spinner("실시간 시세 조회 중…"):
                df = get_portfolio_summary(assets)

            if not df.empty:
                def highlight(val):
                    if isinstance(val, (int, float)):
                        if val > 0: return "color:#00e5b4;font-weight:600"
                        elif val < 0: return "color:#ff4466;font-weight:600"
                    return ""
                styled = df.style.applymap(highlight, subset=["손익","손익(KRW)","손익률(%)","등락률(%)"])
                st.dataframe(styled, use_container_width=True, height=400)

                total_val_krw = df["현재가치(KRW)"].sum()
                total_pl_krw  = df["손익(KRW)"].sum()
                st.markdown(f"""<div style="display:flex;gap:16px;margin-top:10px;">
                    <div class="stat-card" style="flex:1">
                        <div class="stat-label">총 평가가치 (KRW)</div>
                        <div class="stat-value">₩{total_val_krw:,.0f}</div>
                    </div>
                    <div class="stat-card" style="flex:1">
                        <div class="stat-label">총 손익 (KRW)</div>
                        <div class="stat-value {chg_cls(total_pl_krw)}">₩{total_pl_krw:+,.0f}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                sel_ticker = st.selectbox("📈 차트 조회 종목", [a["ticker"] for a in assets],
                    format_func=lambda t: next((f"{a['ticker']} — {a['name']}" for a in assets if a['ticker']==t), t))
                period = st.select_slider("기간", ["1mo","3mo","6mo","1y","2y","5y"], value="3mo")
                with st.spinner("차트 로딩…"):
                    hist = get_price_history(sel_ticker, period)
                if not hist.empty:
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                        vertical_spacing=0.05, row_heights=[0.75,0.25])
                    fig.add_trace(go.Candlestick(
                        x=hist.index, open=hist["Open"], high=hist["High"],
                        low=hist["Low"], close=hist["Close"],
                        increasing_line_color="#00e5b4", decreasing_line_color="#ff4466", name="주가"
                    ), row=1, col=1)
                    for w, color in [(20,"#f59e0b"),(60,"#f472b6")]:
                        if len(hist) >= w:
                            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"].rolling(w).mean(),
                                mode="lines", line=dict(color=color, width=1.5), name=f"MA{w}"), row=1, col=1)
                    fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"],
                        marker_color="#4d9fff", opacity=0.5, name="거래량"), row=2, col=1)
                    fig.update_layout(height=480, paper_bgcolor="#0c1220", plot_bgcolor="#0c1220",
                        font_color="#dde5f0", xaxis_rangeslider_visible=False,
                        xaxis=dict(gridcolor="#1a2d47"), xaxis2=dict(gridcolor="#1a2d47"),
                        yaxis=dict(gridcolor="#1a2d47"), yaxis2=dict(gridcolor="#1a2d47"),
                        legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(l=10,r=10,t=20,b=10))
                    st.plotly_chart(fig, use_container_width=True)

    with tab_edit:
        if not assets:
            st.info("보유 자산이 없습니다.")
        else:
            st.markdown("#### 수량 / 단가 수정")
            edit_ticker = st.selectbox("수정할 종목", [a["ticker"] for a in assets], key="edit_sel",
                format_func=lambda t: next((f"{a['ticker']} — {a['name']}" for a in assets if a['ticker']==t), t))
            cur = next((a for a in assets if a["ticker"] == edit_ticker), {})
            c1, c2 = st.columns(2)
            with c1: new_qty2 = st.number_input("수량", value=float(cur.get("quantity",1)), format="%.6f", key="eq")
            with c2: new_avg2 = st.number_input("평균단가", value=float(cur.get("avg_price",0)), format="%.4f", key="ea")
            if st.button("💾 Notion에 수정 저장", use_container_width=True):
                with st.spinner("Notion 업데이트 중…"):
                    ok, msg = update_asset_notion(cur["page_id"], new_qty2, new_avg2)
                if ok:
                    st.success(msg); st.cache_data.clear(); st.rerun()
                else:
                    st.error(msg)

            st.markdown("---")
            st.markdown("#### 자산 삭제")
            del_ticker = st.selectbox("삭제할 종목", [a["ticker"] for a in assets], key="del_sel",
                format_func=lambda t: next((f"{a['ticker']} — {a['name']}" for a in assets if a['ticker']==t), t))
            del_asset = next((a for a in assets if a["ticker"] == del_ticker), {})
            if st.button(f"🗑️ {del_ticker} 삭제 (Notion)", type="secondary", use_container_width=True):
                with st.spinner("Notion에서 삭제 중…"):
                    ok, msg = remove_asset_notion(del_asset["page_id"])
                if ok:
                    st.success(msg); st.cache_data.clear(); st.rerun()
                else:
                    st.error(msg)


# ════════════════════════════════════════════════════════════════════════════════
# 3) 암호화폐
# ════════════════════════════════════════════════════════════════════════════════
elif page == "₿ 암호화폐":
    st.markdown('<div class="sec">₿ 암호화폐 현황</div>', unsafe_allow_html=True)
    MAJOR_COINS = [("BTC-USD","비트코인"),("ETH-USD","이더리움"),("SOL-USD","솔라나"),
                   ("XRP-USD","리플"),("ADA-USD","에이다"),("DOGE-USD","도지")]
    cols = st.columns(3)
    for i, (ticker, name) in enumerate(MAJOR_COINS):
        info = get_stock_info(ticker)
        with cols[i % 3]:
            if info.get("valid"):
                chg = info["change_pct"]; cls = chg_cls(chg)
                st.markdown(f"""<div class="stat-card">
                    <div class="stat-label">{name}</div>
                    <div class="stat-value">${info['current_price']:,.2f}</div>
                    <div class="stat-sub {cls}">{chg_arrow(chg)} {abs(chg):.2f}%</div>
                </div>""", unsafe_allow_html=True)

    st.markdown("---")
    crypto_assets = [a for a in assets if a.get("asset_type") == "암호화폐"]
    if crypto_assets:
        st.markdown('<div class="sec">📦 보유 코인</div>', unsafe_allow_html=True)
        with st.spinner("코인 데이터 로딩…"):
            c_df = get_portfolio_summary(crypto_assets)
        if not c_df.empty:
            def color_num(v):
                if isinstance(v,(int,float)):
                    return ("color:#00e5b4;font-weight:600" if v>0
                            else "color:#ff4466;font-weight:600" if v<0 else "")
                return ""
            st.dataframe(c_df.style.applymap(color_num, subset=["손익","손익(KRW)","손익률(%)"]),
                use_container_width=True)
    else:
        st.info("보유 암호화폐가 없습니다. 포트폴리오 관리에서 유형을 '암호화폐'로 추가하세요.")

    st.markdown("---")
    st.markdown('<div class="sec">📰 암호화폐 뉴스</div>', unsafe_allow_html=True)
    with st.spinner("코인 뉴스 로딩…"):
        crypto_news = get_crypto_news(10)
    for n in crypto_news:
        c_n, c_s = st.columns([5,1])
        with c_n:
            st.markdown(f"""<div class="nc">
                <div class="nc-title"><a href="{n['link']}" target="_blank">🔗 {n['title']}</a></div>
                <div class="nc-meta">📰 {n.get('source','—')} &nbsp;·&nbsp; {n.get('published','')[:16]}</div>
            </div>""", unsafe_allow_html=True)
        with c_s:
            _scrap_btn(f"cs_{hash(n['title'])%99999}", n["title"], n["link"],
                       n.get("summary",""), "암호화폐", "코인뉴스", n.get("source",""))


# ════════════════════════════════════════════════════════════════════════════════
# 4) 뉴스 & 리서치
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📰 뉴스 & 리서치":
    st.markdown('<div class="sec">📰 뉴스 & 리서치</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📌 보유 자산 뉴스", "🌍 시장 전반", "🔬 리서치 & 분석"])

    with tab1:
        if not assets:
            st.info("보유 자산이 없습니다.")
        else:
            sel = st.selectbox("자산 선택", [a["ticker"] for a in assets],
                format_func=lambda t: f"{ASSET_TYPE_ICONS.get(next((a['asset_type'] for a in assets if a['ticker']==t),'기타'),'💼')} {t} — {next((a['name'] for a in assets if a['ticker']==t), t)}")
            a_info = next((a for a in assets if a["ticker"] == sel), {})
            with st.spinner(f"{sel} 뉴스 검색 중…"):
                news_list = get_news_for_asset(sel, a_info.get("name",""), a_info.get("asset_type",""))
            if not news_list:
                st.warning("검색된 뉴스가 없습니다.")
            for n in news_list:
                c_n, c_s = st.columns([5,1])
                with c_n:
                    st.markdown(f"""<div class="nc">
                        <div class="nc-title"><a href="{n['link']}" target="_blank">🔗 {n['title']}</a></div>
                        <div class="nc-meta">📰 {n.get('source','—')} &nbsp;·&nbsp; {n.get('published','')[:16]}</div>
                        <div style="font-size:11px;color:#6b7f99;margin-top:5px;">{n.get('summary','')}</div>
                    </div>""", unsafe_allow_html=True)
                with c_s:
                    _scrap_btn(f"ns_{sel}_{hash(n['title'])%99999}", n["title"], n["link"],
                               n.get("summary",""), sel, a_info.get("asset_type","주식"), n.get("source",""))

    with tab2:
        with st.spinner("뉴스 로딩…"):
            m_news = get_general_market_news(14)
        if not m_news: st.info("최신 뉴스가 없습니다.")
        for n in m_news:
            c_n, c_s = st.columns([5,1])
            with c_n:
                st.markdown(f"""<div class="nc">
                    <div class="nc-title"><a href="{n['link']}" target="_blank">🔗 {n['title']}</a></div>
                    <div class="nc-meta">📰 {n.get('source','—')} &nbsp;·&nbsp; {n.get('published','')[:16]}</div>
                </div>""", unsafe_allow_html=True)
            with c_s:
                _scrap_btn(f"mn_{hash(n['title'])%99999}", n["title"], n["link"],
                           n.get("summary",""), "시장전반", "시장뉴스", n.get("source",""))

    with tab3:
        st.markdown("<div style='font-size:11px;color:#6b7f99;margin-bottom:10px;'>📊 최신 리서치 & 분석 자료</div>", unsafe_allow_html=True)
        r_options = ["전체 시장"] + ([f"{a['ticker']} {a['name']}" for a in assets] if assets else [])
        r_sel     = st.selectbox("리서치 주제", r_options, key="research_sel")
        r_query   = r_sel if r_sel != "전체 시장" else "주식시장 경제 전망 리포트"
        r_ticker  = r_sel.split(" ")[0] if r_sel != "전체 시장" else "시장전반"
        with st.spinner("리서치 자료 검색 중…"):
            r_news = get_research_news(r_query, max_items=10)
        if not r_news: st.info("리서치 자료가 없습니다.")
        for n in r_news:
            c_n, c_s = st.columns([5,1])
            with c_n:
                st.markdown(f"""<div class="nc">
                    <div class="nc-title"><a href="{n['link']}" target="_blank">🔗 {n['title']}</a></div>
                    <div class="nc-meta">📰 {n.get('source','—')} &nbsp;·&nbsp; {n.get('published','')[:16]}</div>
                    <div style="font-size:11px;color:#6b7f99;margin-top:5px;">{n.get('summary','')}</div>
                </div>""", unsafe_allow_html=True)
            with c_s:
                _scrap_btn(f"rn_{hash(n['title'])%99999}", n["title"], n["link"],
                           n.get("summary",""), r_ticker, "리서치", n.get("source",""))


# ════════════════════════════════════════════════════════════════════════════════
# 5) 스크랩북 (Notion DB 직접 조회)
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📎 스크랩북":
    st.markdown('<div class="sec">📎 스크랩북 (Notion DB)</div>', unsafe_allow_html=True)

    if not nc["scrap_db"]:
        st.error("❌ Notion 스크랩 DB ID가 설정되지 않았습니다.")
        st.stop()

    with st.spinner("Notion에서 스크랩 목록 로딩…"):
        scraps = _cached_scraps()

    if not scraps:
        st.info("스크랩된 항목이 없습니다. 뉴스 탭에서 스크랩해보세요!")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            all_tickers = sorted(set(s.get("ticker","") for s in scraps))
            f_ticker = st.selectbox("자산 필터", ["전체"] + all_tickers)
        with c2:
            all_cats = sorted(set(s.get("category","") for s in scraps if s.get("category")))
            f_cat = st.selectbox("카테고리", ["전체"] + all_cats)
        with c3:
            sort_opt = st.selectbox("정렬", ["최신순", "오래된순", "자산순"])

        filtered = [s for s in scraps
            if (f_ticker == "전체" or s.get("ticker") == f_ticker)
            and (f_cat == "전체" or s.get("category") == f_cat)]
        if sort_opt == "오래된순": filtered = sorted(filtered, key=lambda x: x.get("scraped_at",""))
        elif sort_opt == "자산순":  filtered = sorted(filtered, key=lambda x: x.get("ticker",""))

        st.markdown(f"<div style='font-size:12px;color:#6b7f99;margin-bottom:12px;'>총 <b>{len(filtered)}</b>개</div>",
                    unsafe_allow_html=True)

        for s in filtered:
            c_s, c_d = st.columns([7,1])
            with c_s:
                st.markdown(f"""<div class="nc">
                    <div class="nc-title"><a href="{s.get('link','#')}" target="_blank">🔗 {s['title']}</a></div>
                    <div style="margin:5px 0;">
                        <span class="tag">📌 {s.get('ticker','—')}</span>
                        <span class="tag">🗂️ {s.get('category','—')}</span>
                        <span class="tag">📅 {s.get('scraped_at','')[:10]}</span>
                        <span class="tag">📰 {s.get('source','—')}</span>
                    </div>
                    <div style="font-size:11px;color:#6b7f99;">{s.get('summary','')[:150]}</div>
                </div>""", unsafe_allow_html=True)
            with c_d:
                if st.button("🗑️", key=f"ds_{s.get('page_id','')[:8]}"):
                    with st.spinner("삭제 중…"):
                        ok, msg = delete_scrap_notion(s["page_id"])
                    if ok:
                        st.cache_data.clear(); st.rerun()
                    else:
                        st.error(msg)


# ════════════════════════════════════════════════════════════════════════════════
# 6) AI 분석
# ════════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI 분석":
    st.markdown('<div class="sec">🤖 AI 포트폴리오 분석</div>', unsafe_allow_html=True)

    if not gemini_ok:
        st.warning("⚠️ 사이드바 → API 설정에서 Gemini API 키를 입력해주세요.")

    scraps_all = _cached_scraps()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-label">보유 자산</div>
            <div class="stat-value">{len(assets)}종목</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-label">스크랩 정보</div>
            <div class="stat-value">{len(scraps_all)}건</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        ai_cnt = len([s for s in scraps_all if s.get("category")=="AI분석"])
        st.markdown(f"""<div class="stat-card">
            <div class="stat-label">AI 분석 이력</div>
            <div class="stat-value">{ai_cnt}회</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        focus = st.multiselect("분석 중점 항목",
            ["포트폴리오 진단","헷지 전략","섹터 분석","암호화폐 분석","리스크 관리","단기 매매 포인트"],
            default=["포트폴리오 진단","헷지 전략","리스크 관리"])
    with col2:
        risk_pref = st.select_slider("리스크 선호도",
            ["매우 보수적","보수적","중립","공격적","매우 공격적"], value="보수적")

    prompt_extra = st.text_area("추가 질문 / 특이사항",
        placeholder="예: 미국 금리 인하 시 대응 방법은?\n예: 달러 현금 비중을 높이고 싶습니다.",
        height=90)
    full_prompt = f"[분석 중점: {', '.join(focus)}] [리스크 선호도: {risk_pref}]\n{prompt_extra}"

    if st.button("🤖 AI 분석 시작", use_container_width=True, disabled=not gemini_ok):
        with st.spinner("🧠 Gemini가 포트폴리오를 분석 중입니다… (30초~1분)"):
            df = get_portfolio_summary(assets) if assets else pd.DataFrame()
            indices = get_market_indices()
            result = get_gemini_analysis(df, scraps_all, indices, full_prompt)

        st.markdown('<div class="sec">📊 AI 분석 결과</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-box">{result}</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📎 분석 결과 Notion 스크랩"):
            ok, msg = add_scrap_notion(
                f"AI 분석 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "", result[:1800], "전체포트폴리오", "AI분석", "Gemini AI"
            )
            st.success(msg) if ok else st.warning(msg)
            if ok: st.cache_data.clear()

    # 이전 AI 분석 이력
    ai_scraps = [s for s in scraps_all if s.get("category") == "AI분석"]
    if ai_scraps:
        st.markdown("---")
        st.markdown('<div class="sec">📜 이전 AI 분석 이력</div>', unsafe_allow_html=True)
        for s in ai_scraps[:5]:
            with st.expander(f"📅 {s.get('scraped_at','')[:16]}"):
                st.markdown(s.get("summary",""))
