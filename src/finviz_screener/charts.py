import logging
import time

import httpx

logger = logging.getLogger(__name__)

CHART_URL = "https://finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finviz.com/",
}
_MAX_RETRIES = 3


def download_chart(ticker: str, timeout: float = 15.0) -> bytes:
    url = CHART_URL.format(ticker=ticker.upper())
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return _fetch(url, ticker, timeout)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (429, 500, 502, 503, 504):
                raise
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = 2 ** attempt
                logger.warning(
                    "chart download attempt %d for %s HTTP %d — retrying in %ds",
                    attempt, ticker, exc.response.status_code, wait,
                )
                time.sleep(wait)
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = 2 ** attempt
                logger.warning(
                    "chart download attempt %d for %s failed (%s) — retrying in %ds",
                    attempt, ticker, exc, wait,
                )
                time.sleep(wait)
    raise RuntimeError(f"chart download for {ticker} failed after {_MAX_RETRIES} attempts") from last_exc


def _fetch(url: str, ticker: str, timeout: float) -> bytes:
    logger.debug("downloading chart for %s", ticker)
    with httpx.Client(headers=_HEADERS, timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
    png = response.content
    if not png:
        raise ValueError(f"empty chart response for {ticker}")
    logger.debug("chart for %s: %d bytes", ticker, len(png))
    return png
