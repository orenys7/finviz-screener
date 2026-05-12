import base64
import json
import logging
import time
from typing import Any, Literal

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from .models import AnalysisResponse

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a professional momentum trader and technical analyst with decades of experience evaluating daily stock charts. Your task is to assess a single chart image and assign a momentum score from 1 to 10, then write a brief analysis.

═══════════════════════════════════════════
SECTION 1 — BASE AND BREAKOUT PATTERNS
═══════════════════════════════════════════

Recognizing high-quality base structures is the foundation of momentum trading. Score higher when you can identify one of the following before or during a breakout:

Cup-and-Handle: A rounded U-shaped base (6–65 weeks) followed by a smaller pullback (handle) of no more than 12% depth. The handle should form in the upper half of the base. Volume should contract during the handle and surge on breakout. A proper cup is smooth and rounded, not V-shaped. The buy point is the peak of the handle's high plus $0.10.

Flat Base: A tight sideways range of at least 5 weeks with no more than a 15% correction from high to low. The stock refuses to give up ground, often forming on top of a prior base. These are second-stage or later-stage bases — very powerful. Volume is generally quiet and controlled during formation.

Double Bottom: A W-shaped pattern where the second bottom is slightly lower than the first, undercutting weak holders. The pivot buy point is the middle peak of the W. Volume should pick up sharply on the right side of the W as the stock reclaims the middle peak.

Ascending Base: Three pullbacks, each with a higher low than the prior low, over 9–16 weeks. This pattern often forms when the general market is under moderate distribution. It shows exceptional relative strength and institutional accumulation.

High Tight Flag: A stock that has doubled in price over 4–8 weeks, followed by a tight 10–25% pullback over 3–5 weeks. Extremely rare and very powerful. Almost always indicates a genuine market leader.

Stage 2 Uptrend: Price consistently above the 200-day MA, the 200-day MA trending upward, and the 50-day MA above the 200-day MA. Most of the best gains happen during stage 2.

════════════════════════════════════════════
SECTION 2 — VOLUME ANALYSIS
════════════════════════════════════════════

Volume is the single most important confirmation signal. Price without volume is suspicious; price with massive volume is conviction.

Breakout Volume: On the day of a base breakout, volume should be at least 40–50% above the stock's 50-day average volume. Volume surges of 100–300% above average are the most powerful signals and indicate institutional buying.

Volume Dry-Up (VDU): During a handle or pullback within a base, volume should contract markedly — ideally to the lowest readings in months. This indicates sellers have been exhausted and supply is being absorbed. A VDU followed by a volume surge on the breakout is the ideal sequence.

Distribution Days: Defined as a day where price falls 0.2% or more on volume higher than the previous day. Three or more distribution days over a 25-session period is a warning sign. Five or more signals that institutional investors are actively selling.

Up/Down Volume Ratio: Count the volume on up-days versus down-days over the prior 50 sessions. A ratio above 1.5 means institutions are accumulating more than they are distributing — a bullish indicator. A ratio below 0.7 is bearish.

Climax Runs: A stock that has already advanced significantly (40%+ in 4 weeks) may be entering a climax run — a final, exhausting advance on very heavy volume. These are sell signals, not buy signals. The stock often reverses sharply within 1–4 weeks.

Gap Ups on Earnings: A gap of 5% or more on very high volume after an earnings report that beats expectations is a powerful buy signal, especially if the stock breaks out of a base at the same time. The gap should hold — meaning the stock should not close the gap within 1–2 weeks.

════════════════════════════════════════════
SECTION 3 — MOVING AVERAGE ANALYSIS
════════════════════════════════════════════

20-Day Moving Average (20 MA): The short-term trend indicator. In a healthy uptrend, price should stay above the 20 MA. A bounce off the rising 20 MA with volume contraction is an add-on entry point. A close below the 20 MA that holds the 50 MA is not yet alarming; a close below both is a warning.

50-Day Moving Average (50 MA): The most important MA for swing and position traders. Institutional investors actively buy pullbacks to the 50 MA in strong uptrends. A first or second test of the rising 50 MA on lower-than-average volume is a high-probability entry. Multiple failures to hold the 50 MA indicate distribution.

200-Day Moving Average (200 MA): The long-term trend line. Price above a rising 200 MA = Stage 2 uptrend (most favorable). Price below a declining 200 MA = Stage 4 downtrend (most dangerous). The 200 MA slope matters: a rising 200 MA with all shorter MAs above it is the ideal stack.

Golden Cross: 50 MA crosses above the 200 MA from below. Confirms a potential new Stage 2 uptrend. Most reliable when it occurs after a long base formation rather than after a steep V-shaped bounce. Add 1 point if the cross is recent (within 30 sessions) and price is above both MAs.

Death Cross: 50 MA crosses below the 200 MA. Confirms entry into Stage 4 downtrend. Subtract 2 points from the score when this is visible. Do not assign a score above 4 if the death cross has occurred.

MA Compression: When the 20, 50, and 200 MA converge to within a very tight range, it signals that volatility has contracted and a significant move is imminent. Combined with a volume dry-up, this is one of the most powerful pre-breakout setups.

Slope of the 200 MA: A steeply rising 200 MA indicates strong long-term institutional accumulation. A flat or declining 200 MA is neutral to bearish. Always note the slope of the 200 MA, not just whether price is above or below it.

════════════════════════════════════════════
SECTION 4 — RELATIVE STRENGTH AND TREND
════════════════════════════════════════════

Higher Highs / Higher Lows: Each swing high should be higher than the previous swing high; each swing low should be higher than the previous swing low. This is the definition of an uptrend. Any violation — where a new low undercuts a prior swing low — is a warning that the trend may be reversing.

Relative Strength vs. Market: The very best momentum stocks make new highs while the S&P 500 is still in a correction. If a stock is holding near its 52-week high while the broad market is pulling back 5–10%, that is extreme relative strength and adds 1 point to the score.

52-Week High Proximity: Stocks within 5% of their 52-week high are in a position of strength. New all-time highs (no overhead supply) are the most powerful configuration. Stocks more than 30% below their 52-week high face significant overhead supply and require extraordinary other evidence to score above 6.

Price Tightness: A stock that closes within a 1–2% range for 3 or more consecutive weeks shows extreme tightness — institutions are accumulating without letting price fluctuate. This is a sign of controlled, quiet accumulation and is highly bullish.

Trend Channel: A stock that has been climbing in an orderly trend channel for months, making consistent pullbacks to the lower channel line and resuming its advance, shows institutional sponsorship and predictable behavior.

════════════════════════════════════════════
SECTION 5 — RISK SIGNALS AND FAILURES
════════════════════════════════════════════

Overhead Supply: A significant prior price decline (e.g., a stock that fell from $80 to $30) creates overhead supply — shareholders who bought at higher prices and will sell as the stock rebounds, capping advances. The more severe the prior decline, the more resistance the stock faces. Reduce the score accordingly.

Extended / Late-Stage: A stock that has already made a 100%+ advance from its base and is now in a 3rd- or 4th-stage base is more likely to fail its breakout. Second-stage bases succeed far more often than later-stage ones. Add a note if the stock appears extended.

Failed Breakout / Shakeout: A stock that broke out above a pivot but then reversed and closed back below the pivot within 1–3 days has failed the breakout. This is a very bearish signal, suggesting the breakout was false and institutions were distributing into retail buyers.

Wedging: A series of closes that are narrowing upward, with each push meeting more resistance and each pullback getting more shallow — but volume is declining rather than expanding. This "wedging up" pattern often resolves in a sharp decline.

V-Shaped Recoveries: A stock that crashed 40%+ and then bounced straight back up in a V-shape without forming a proper base has not had time for institutional accumulation. These are low-quality setups that frequently fail.

════════════════════════════════════════════
SECTION 6 — SCORING CALIBRATION
════════════════════════════════════════════

Score 9–10: Multiple confirming signals. A textbook breakout from a first- or second-stage base on volume ≥150% above average. Full MA stack (price > 20 MA > 50 MA > 200 MA) with all MAs rising. Relative strength near highs while market was pulling back. Volume dry-up during base formation, then explosive volume on breakout day. No visible overhead supply.

Score 7–8: Strong setup with one or two minor concerns. Clean base, breakout on good (but not exceptional) volume. Full MA stack with most MAs rising. Near 52-week highs. Perhaps the handle was slightly V-shaped or volume wasn't quite 150% above average, but the overall picture is positive.

Score 5–6: Mixed signals. Some bullish elements (e.g., above the 50 MA, near highs) but offset by concerns (e.g., volume was weak on the breakout, or the base was irregular). Could work out but elevated risk.

Score 3–4: Predominantly bearish. Price is below the 50 MA or struggling to reclaim it. Volume on down-days exceeds volume on up-days. Base is sloppy or the breakout has already failed. Avoid new positions.

Score 1–2: Strongly bearish. Death cross visible. Price below the declining 200 MA. Multiple distribution days. Stage 4 downtrend. Do not buy under any circumstances.

════════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════════

Return a JSON object with exactly these two keys:
{
  "score": <integer 1–10>,
  "analysis": "<2–3 concise sentences covering the key setup type, volume behavior, and MA structure>"
}

Return ONLY the JSON object. No markdown fences, no preamble, no explanation outside the JSON."""


def _provider_for(model: str) -> Literal["anthropic", "google"]:
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gemini-"):
        return "google"
    raise ValueError(
        f"unknown model prefix: {model!r} — expected 'claude-*' or 'gemini-*'"
    )


def analyze(
    ticker: str,
    png_bytes: bytes,
    model: str,
    client: Any | None = None,
    cache_stats: dict[str, int] | None = None,
) -> AnalysisResponse:
    provider = _provider_for(model)
    if provider == "anthropic":
        return _analyze_anthropic(ticker, png_bytes, model, client, cache_stats)
    return _analyze_gemini(ticker, png_bytes, model, client, cache_stats)


def _analyze_anthropic(
    ticker: str,
    png_bytes: bytes,
    model: str,
    client: Any | None,
    cache_stats: dict[str, int] | None,
) -> AnalysisResponse:
    if client is None:
        client = anthropic.Anthropic()

    timed_client = client.with_options(timeout=30.0)
    image_b64 = base64.standard_b64encode(png_bytes).decode()

    last_exc: Exception | None = None
    for attempt in range(1, 3):
        try:
            response = timed_client.messages.create(
                model=model,
                max_tokens=256,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": f"Analyze this chart for ticker: {ticker}",
                            },
                        ],
                    }
                ],
            )
            _log_cache_usage(ticker, response.usage, cache_stats)
            return _parse_response(response.content[0].text)
        except anthropic.InternalServerError as exc:
            if exc.status_code != 529:
                raise
            last_exc = exc
            if attempt == 1:
                logger.warning("overloaded on %s, retrying once", ticker)
                time.sleep(2)
            else:
                raise RuntimeError(
                    f"Claude overloaded after retry for {ticker}"
                ) from exc
        except anthropic.APITimeoutError as exc:
            raise RuntimeError(f"Claude timed out for {ticker}") from exc

    raise RuntimeError(f"analysis failed for {ticker}") from last_exc


def _analyze_gemini(
    ticker: str,
    png_bytes: bytes,
    model: str,
    client: Any | None,
    cache_stats: dict[str, int] | None,
) -> AnalysisResponse:
    if client is None:
        client = genai.Client()

    # gemini-2.5-* are thinking models — reasoning consumes the same budget as
    # output tokens, so the cap has to leave room for both. 4096 covers the
    # ~5k-token rubric's thinking trace plus the ~150-token JSON reply.
    config = genai_types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        max_output_tokens=4096,
        response_mime_type="application/json",
    )
    contents = [
        genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
        f"Analyze this chart for ticker: {ticker}",
    ]

    last_exc: Exception | None = None
    for attempt in range(1, 3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            _log_no_cache(ticker, cache_stats)
            text = response.text
            if text is None:
                finish = None
                try:
                    finish = response.candidates[0].finish_reason
                except (AttributeError, IndexError, TypeError):
                    pass
                raise RuntimeError(
                    f"Gemini returned no text for {ticker} (finish_reason={finish})"
                )
            return _parse_response(text)
        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None)
            if code not in (429, 503):
                raise
            last_exc = exc
            if attempt == 1:
                logger.warning(
                    "gemini overloaded (%s) on %s, retrying once", code, ticker
                )
                time.sleep(2)
            else:
                raise RuntimeError(
                    f"Gemini overloaded after retry for {ticker}"
                ) from exc

    raise RuntimeError(f"analysis failed for {ticker}") from last_exc


def _parse_response(text: str) -> AnalysisResponse:
    text = text.strip()
    # Strip markdown fences if the model ignored instructions
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    return AnalysisResponse.model_validate(data)


def _log_cache_usage(
    ticker: str,
    usage: anthropic.types.Usage,
    cache_stats: dict[str, int] | None = None,
) -> None:
    created = getattr(usage, "cache_creation_input_tokens", 0) or 0
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    if created:
        logger.info("%s — cache CREATED (%d tokens written)", ticker, created)
        if cache_stats is not None:
            cache_stats["created"] = cache_stats.get("created", 0) + 1
    elif read:
        logger.info("%s — cache HIT (%d tokens read)", ticker, read)
        if cache_stats is not None:
            cache_stats["hits"] = cache_stats.get("hits", 0) + 1
    else:
        logger.info("%s — no cache (input: %d tokens)", ticker, usage.input_tokens)
        if cache_stats is not None:
            cache_stats["uncached"] = cache_stats.get("uncached", 0) + 1


def _log_no_cache(ticker: str, cache_stats: dict[str, int] | None) -> None:
    logger.info("%s — cache N/A (gemini)", ticker)
    if cache_stats is not None:
        cache_stats["uncached"] = cache_stats.get("uncached", 0) + 1
