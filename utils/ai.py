"""
utils/ai.py — Gemini 기반 포트폴리오 분석
SDK 우선순위:
  1. google-genai (신규 SDK, pip install google-genai)
  2. google-generativeai (구 SDK, pip install google-generativeai)
모델 우선순위: gemini-2.0-flash → gemini-1.5-flash → gemini-pro
"""
import os
from datetime import datetime


# ── 사용 가능한 모델 후보 (최신 → 구버전 순) ──────────────────────────────────
CANDIDATE_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-pro",
]


def _call_new_sdk(api_key: str, prompt: str) -> str:
    """google-genai (신규 SDK) 로 호출"""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.65,
                    max_output_tokens=2500,
                ),
            )
            return response.text
        except Exception as e:
            err = str(e)
            # 모델 없음 → 다음 모델 시도
            if "not found" in err.lower() or "invalid" in err.lower() and "model" in err.lower():
                continue
            # API 키 오류 등 치명적 오류 → 즉시 raise
            raise
    raise RuntimeError("사용 가능한 Gemini 모델이 없습니다.")


def _call_old_sdk(api_key: str, prompt: str) -> str:
    """google-generativeai (구 SDK) 로 호출"""
    import google.generativeai as genai
    genai.configure(api_key=api_key)

    for model_name in CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                generation_config={"temperature": 0.65, "max_output_tokens": 2500},
            )
            return resp.text
        except Exception as e:
            err = str(e)
            if "not found" in err.lower() or "404" in err:
                continue
            raise
    raise RuntimeError("사용 가능한 Gemini 모델이 없습니다.")


def _build_prompt(portfolio_df, scraps: list, market_indices: list, prompt_extra: str) -> str:
    """분석 프롬프트 조립"""

    # 포트폴리오 섹션
    if portfolio_df is not None and not portfolio_df.empty:
        total_value_krw = portfolio_df["현재가치(KRW)"].sum()
        total_pl_krw    = portfolio_df["손익(KRW)"].sum()
        cost_krw        = total_value_krw - total_pl_krw
        total_pl_pct    = (total_pl_krw / cost_krw * 100) if cost_krw else 0

        type_weights = portfolio_df.groupby("유형")["현재가치(KRW)"].sum()
        type_pct     = (type_weights / type_weights.sum() * 100).round(1)
        type_summary = ", ".join(f"{t}: {p}%" for t, p in type_pct.items())

        portfolio_section = (
            f"## 📊 현재 포트폴리오\n"
            f"- 총 평가가치: {total_value_krw:,.0f} KRW\n"
            f"- 총 손익: {total_pl_krw:+,.0f} KRW ({total_pl_pct:+.1f}%)\n"
            f"- 자산 유형 비중: {type_summary}\n\n"
            f"### 종목별 현황\n"
            f"{portfolio_df[['티커','종목명','유형','현재가치(KRW)','손익률(%)','섹터','등락률(%)']].to_string(index=False)}"
        )
    else:
        portfolio_section = "## 📊 포트폴리오\n(등록된 자산 없음)"

    # 시장 지표 섹션
    indices_lines   = [f"- {m['name']}: {m['value']:,} ({m['change_pct']:+.2f}%)" for m in market_indices]
    indices_section = "## 🌍 주요 시장 지표\n" + "\n".join(indices_lines) if indices_lines else ""

    # 스크랩 섹션 (최근 15개)
    recent = sorted(scraps, key=lambda x: x.get("scraped_at", ""), reverse=True)[:15]
    if recent:
        lines           = [f"[{s['ticker']}][{s['category']}] {s['title']} ({s.get('scraped_at','')[:10]})" for s in recent]
        scraps_section  = "## 📎 최근 스크랩 정보\n" + "\n".join(lines)
    else:
        scraps_section  = "## 📎 스크랩\n(없음)"

    system_prompt = """당신은 20년 경력의 멀티에셋 포트폴리오 매니저입니다.

투자 철학:
• 자본 보전 우선 + 중장기 알파 추구
• 변동성 대비 수익률(샤프비율) 최적화
• 헷지 포지션(인버스 ETF, 금, 채권, 달러 현금)을 적극 활용
• 섹터/국가/자산군 분산으로 상관관계 리스크 최소화

응답 형식 (마크다운):
1. **종합 진단** — 포트폴리오 강점·취약점 (3줄)
2. **시황 해석** — 현재 지표가 말하는 것 (금리, 달러, VIX 등)
3. **즉시 액션 플랜** — 매수/매도/비중조정 구체 제안 (종목명 포함)
4. **헷지 전략** — 리스크 유형별 헷지 방법 제안
5. **단기(1개월) / 중기(3-6개월) 로드맵**
6. **핵심 리스크 요인** — 주의해야 할 3가지

한국어로, 실제 투자자에게 브리핑하듯 명확하고 구체적으로 작성하세요."""

    user_msg = (
        f"{portfolio_section}\n\n"
        f"{indices_section}\n\n"
        f"{scraps_section}\n\n"
        f"현재 날짜: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n"
        + (f"추가 요청: {prompt_extra}\n" if prompt_extra else "")
        + "\n위 데이터를 종합해 포트폴리오 운용 전략을 브리핑해주세요."
    )

    return system_prompt + "\n\n" + user_msg


def get_gemini_analysis(portfolio_df, scraps: list, market_indices: list, prompt_extra: str = "") -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return "⚠️ Gemini API 키가 설정되지 않았습니다. 사이드바에서 입력해주세요."

    prompt = _build_prompt(portfolio_df, scraps, market_indices, prompt_extra)

    # ── 신규 SDK 우선 시도 ───────────────────────────────────────────────────
    try:
        from google import genai  # noqa: F401  — import 가능 여부 확인
        try:
            return _call_new_sdk(api_key, prompt)
        except Exception as e:
            new_sdk_err = str(e)
    except ImportError:
        new_sdk_err = "google-genai 미설치"

    # ── 구 SDK 폴백 ──────────────────────────────────────────────────────────
    try:
        import google.generativeai  # noqa: F401
        try:
            return _call_old_sdk(api_key, prompt)
        except Exception as e:
            old_sdk_err = str(e)
    except ImportError:
        old_sdk_err = "google-generativeai 미설치"

    # ── 둘 다 실패 ────────────────────────────────────────────────────────────
    return (
        f"⚠️ Gemini 연결 실패\n\n"
        f"**신규 SDK (google-genai):** {new_sdk_err}\n\n"
        f"**구 SDK (google-generativeai):** {old_sdk_err}\n\n"
        "**해결 방법:**\n"
        "```bash\n"
        "pip install -U google-genai\n"
        "# 또는\n"
        "pip install -U google-generativeai\n"
        "```\n"
        "API 키는 https://aistudio.google.com/app/apikey 에서 발급받으세요."
    )
