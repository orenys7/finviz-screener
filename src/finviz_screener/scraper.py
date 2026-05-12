import logging
import time
from contextlib import contextmanager
from typing import Generator

from playwright.sync_api import Browser, sync_playwright

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
_TICKER_SELECTOR = "tr.styled-row a.tab-link"
_MAX_RETRIES = 3


@contextmanager
def browser_session() -> Generator[Browser, None, None]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


def fetch_tickers(url: str, browser: Browser | None = None) -> list[str]:
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


def _scrape(url: str, browser: Browser) -> list[str]:
    ctx = browser.new_context(user_agent=_USER_AGENT)
    page = ctx.new_page()
    try:
        logger.info("navigating to %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        page.wait_for_selector(_TICKER_SELECTOR, timeout=20_000)

        tickers: list[str] = page.eval_on_selector_all(
            _TICKER_SELECTOR,
            "els => els.map(el => el.innerText.trim()).filter(t => t.length > 0)",
        )

        unique = list(dict.fromkeys(tickers))
        logger.info("found %d ticker(s)", len(unique))

        if not unique:
            body = page.inner_text("body")
            if "No results found" in body:
                logger.info("screener returned no results")

        return unique
    finally:
        ctx.close()
