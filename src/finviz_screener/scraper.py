import logging
import re
import time
from contextlib import contextmanager
from typing import Generator

from playwright.sync_api import Browser, sync_playwright

from .models import ScreenerRow

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
_ROW_SELECTOR = "tr.styled-row"
_TICKER_SELECTOR = "tr.styled-row a.tab-link"
_MAX_RETRIES = 3

# Read column header text once per page, then map each scraped row's cells by
# the header index so we don't bake Finviz's view-specific column order into
# the code. The selector matches Finviz's screener-table header row.
_TABLE_JS = """
() => {
  const headerCells = Array.from(
    document.querySelectorAll(
      'tr.table-header > th, tr.table-top > th, tr.styled-header > th'
    )
  ).map(th => th.innerText.trim());
  const rows = Array.from(document.querySelectorAll('tr.styled-row')).map(
    tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
  );
  return {headers: headerCells, rows};
}
"""


@contextmanager
def browser_session() -> Generator[Browser, None, None]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


def fetch_screener_rows(url: str, browser: Browser | None = None) -> list[ScreenerRow]:
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            if browser is not None:
                return _scrape(url, browser)
            with browser_session() as b:
                return _scrape(url, b)
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = 2**attempt
                logger.warning(
                    "scrape attempt %d failed (%s) — retrying in %ds",
                    attempt,
                    exc,
                    wait,
                )
                time.sleep(wait)
    raise RuntimeError(f"all {_MAX_RETRIES} scrape attempts failed") from last_exc


def _scrape(url: str, browser: Browser) -> list[ScreenerRow]:
    ctx = browser.new_context(user_agent=_USER_AGENT)
    page = ctx.new_page()
    try:
        logger.info("navigating to %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_selector(_TICKER_SELECTOR, timeout=20_000)

        data = page.evaluate(_TABLE_JS)
        headers: list[str] = data.get("headers", []) or []
        raw_rows: list[list[str]] = data.get("rows", []) or []

        col_idx = _column_indices(headers)
        rows = _build_rows(raw_rows, col_idx)

        seen: set[str] = set()
        unique: list[ScreenerRow] = []
        for r in rows:
            if r.ticker and r.ticker not in seen:
                seen.add(r.ticker)
                unique.append(r)

        logger.info("found %d ticker(s)", len(unique))
        if not unique:
            body = page.inner_text("body")
            if "No results found" in body:
                logger.info("screener returned no results")

        return unique
    finally:
        ctx.close()


def fetch_tickers(url: str, browser: Browser | None = None) -> list[str]:
    """Back-compat shim — returns just the ticker symbols."""
    return [r.ticker for r in fetch_screener_rows(url, browser=browser)]


def _column_indices(headers: list[str]) -> dict[str, int]:
    """Locate Ticker / Price / Change / Volume cell positions from headers.

    Finviz's column order varies by view (v=111 vs v=152 etc.). Resolving by
    header text rather than fixed index keeps the scraper view-agnostic.
    """
    lower = [h.lower() for h in headers]

    def find(*candidates: str) -> int | None:
        for cand in candidates:
            if cand in lower:
                return lower.index(cand)
        return None

    ticker_idx = find("ticker")
    return {
        "ticker": ticker_idx if ticker_idx is not None else 1,
        "price": find("price", "last"),
        "change_pct": find("change"),
        "volume": find("volume"),
    }


def _build_rows(
    raw_rows: list[list[str]], idx: dict[str, int | None]
) -> list[ScreenerRow]:
    out: list[ScreenerRow] = []
    for cells in raw_rows:
        ticker = _cell(cells, idx["ticker"])
        if not ticker:
            continue
        out.append(
            ScreenerRow(
                ticker=ticker,
                price=_parse_price(_cell(cells, idx.get("price"))),
                change_pct=_parse_change(_cell(cells, idx.get("change_pct"))),
                volume=_parse_volume(_cell(cells, idx.get("volume"))),
            )
        )
    return out


def _cell(cells: list[str], idx: int | None) -> str | None:
    if idx is None or idx < 0 or idx >= len(cells):
        return None
    return cells[idx].strip() or None


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_change(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace("%", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


_VOLUME_SUFFIXES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
_VOLUME_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)([KMB]?)$")


def _parse_volume(text: str | None) -> int | None:
    if not text:
        return None
    cleaned = text.replace(",", "").strip().upper()
    m = _VOLUME_RE.match(cleaned)
    if not m:
        return None
    num = float(m.group(1))
    suffix = m.group(2)
    mult = _VOLUME_SUFFIXES.get(suffix, 1)
    return int(num * mult)
