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

# Resolve column positions by finding the header row in the same <table> as the
# data rows, rather than guessing at Finviz's class names (which change between
# views and across redesigns).
_TABLE_JS = """
() => {
  const dataRows = Array.from(document.querySelectorAll('tr.styled-row'));
  let headers = [];
  if (dataRows.length > 0) {
    const table = dataRows[0].closest('table');
    if (table) {
      // Header row = first <tr> in the same table that has <th> children, or
      // any <tr> whose cells differ from <td>-only rows. Try <thead> first.
      const theadRow = table.querySelector('thead tr');
      let headerRow = theadRow;
      if (!headerRow) {
        // Walk previous siblings of the first data row up to the table top.
        for (const tr of Array.from(table.querySelectorAll('tr'))) {
          if (tr === dataRows[0]) break;
          if (tr.querySelector('th') || tr.classList.contains('table-top')) {
            headerRow = tr;
          }
        }
      }
      if (headerRow) {
        headers = Array.from(
          headerRow.querySelectorAll('th, td')
        ).map(c => c.innerText.trim());
      }
    }
  }
  const rows = dataRows.map(
    tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
  );
  return {headers, rows};
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
        logger.info("scraper headers=%r col_idx=%r", headers, col_idx)
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

    # When headers can't be read, fall back to Finviz's v=111 layout
    # (col 0=No., 1=Ticker, 2=Last, 3=Change, 4=Volume). The configured
    # screeners all use v=111 today.
    ticker_idx = find("ticker")
    price_idx = find("price", "last")
    change_idx = find("change")
    volume_idx = find("volume")
    return {
        "ticker": ticker_idx if ticker_idx is not None else 1,
        "price": price_idx if price_idx is not None else 2,
        "change_pct": change_idx if change_idx is not None else 3,
        "volume": volume_idx if volume_idx is not None else 4,
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
