import logging
from typing import Sequence

import httpx

from .charts import CHART_URL
from .models import NewHit

logger = logging.getLogger(__name__)

_FINVIZ_QUOTE = "https://finviz.com/quote.ashx?t={ticker}"
_MAX_EMBEDS = 10  # Discord hard limit per request

_COLOR_BY_SCORE: list[tuple[int, int]] = [
    (9, 0x2ECC71),  # green
    (7, 0xF1C40F),  # gold
    (5, 0xE67E22),  # orange
    (0, 0xE74C3C),  # red
]


def _color(score: int) -> int:
    for threshold, color in _COLOR_BY_SCORE:
        if score >= threshold:
            return color
    return _COLOR_BY_SCORE[-1][1]


def _embed(hit: NewHit) -> dict:
    return {
        "title": f"{hit.ticker} — Score {hit.score}/10",
        "description": hit.analysis,
        "url": _FINVIZ_QUOTE.format(ticker=hit.ticker),
        "color": _color(hit.score),
        "fields": [
            {"name": "Screener", "value": hit.screener, "inline": True},
            {
                "name": "Chart",
                "value": f"[View]({CHART_URL.format(ticker=hit.ticker)})",
                "inline": True,
            },
        ],
    }


def post_discord(hits: Sequence[NewHit], webhook_url: str) -> None:
    if not hits:
        logger.info("no new hits — skipping Discord notification")
        return
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not configured — skipping notification")
        return

    n = len(hits)
    logger.info("posting %d new hit(s) to Discord", n)

    embeds = [_embed(h) for h in hits]
    batches = [embeds[i : i + _MAX_EMBEDS] for i in range(0, len(embeds), _MAX_EMBEDS)]

    for idx, batch in enumerate(batches):
        payload: dict = {"embeds": batch}
        if idx == 0:
            noun = "signal" if n == 1 else "signals"
            payload["content"] = f"**{n} new momentum {noun}**"
        _send(payload, webhook_url)


def _send(payload: dict, webhook_url: str) -> None:
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook_url, json=payload)
        if resp.status_code == 204:
            return
        if resp.is_client_error:
            logger.error(
                "Discord webhook rejected payload (HTTP %d): %s",
                resp.status_code,
                resp.text[:200],
            )
        elif resp.is_server_error:
            logger.error("Discord webhook server error (HTTP %d)", resp.status_code)
        else:
            logger.warning("Discord webhook unexpected status %d", resp.status_code)
    except httpx.TimeoutException:
        logger.error("Discord webhook request timed out")
    except httpx.HTTPError as exc:
        logger.error("Discord webhook request failed: %s", exc)
