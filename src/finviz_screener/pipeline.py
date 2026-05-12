import logging
import sqlite3
import time

from .analyzer import analyze
from .charts import download_chart, make_chart_client
from .config import AppConfig
from .db import insert_run, insert_signals, mark_run_finished
from .diff import find_new_hits
from .models import NewHit, Signal
from .notify import post_discord
from .scraper import browser_session, fetch_screener_rows

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 900  # 15 minutes


class _DeadlineExceeded(Exception):
    pass


def run_once(
    config: AppConfig,
    conn: sqlite3.Connection,
    *,
    screener_filter: str | None = None,
    dry_run: bool = False,
    webhook_url: str = "",
    client: object | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT,
) -> list[NewHit]:
    screeners = config.screeners
    if screener_filter:
        screeners = [s for s in screeners if s.name == screener_filter]
        if not screeners:
            raise ValueError(f"no screener named {screener_filter!r} in config")

    run_id = insert_run(conn)
    logger.info(
        "run %d started — screeners=%d timeout=%ds",
        run_id,
        len(screeners),
        timeout_seconds,
    )

    all_signals: list[Signal] = []
    ticker_count = 0
    error_count = 0
    cache_stats: dict[str, int] = {"hits": 0, "created": 0, "uncached": 0}
    deadline = time.monotonic() + timeout_seconds
    t0 = time.monotonic()
    timed_out = False
    screener_signals: list[Signal] = []  # kept in outer scope for timeout flush

    with make_chart_client() as http_client, browser_session() as browser:
        try:
            for screener in screeners:
                logger.info("screener %r — fetching tickers", screener.name)
                try:
                    rows = fetch_screener_rows(screener.url, browser=browser)
                except Exception as exc:
                    logger.error(
                        "screener %r failed to fetch tickers: %s", screener.name, exc
                    )
                    error_count += 1
                    continue

                logger.info("screener %r — %d ticker(s)", screener.name, len(rows))
                screener_signals = []

                for row in rows:
                    if time.monotonic() >= deadline:
                        raise _DeadlineExceeded()
                    ticker_count += 1
                    try:
                        png = download_chart(row.ticker, client=http_client)
                        result = analyze(
                            row.ticker,
                            png,
                            config.model,
                            client=client,
                            cache_stats=cache_stats,
                        )
                        if result.score < config.min_score_to_store:
                            logger.info(
                                "ticker %s — score=%d (skipped, below %d)",
                                row.ticker,
                                result.score,
                                config.min_score_to_store,
                            )
                            continue
                        screener_signals.append(
                            Signal(
                                ticker=row.ticker,
                                screener=screener.name,
                                score=result.score,
                                analysis=result.analysis,
                                price=row.price,
                                change_pct=row.change_pct,
                                volume=row.volume,
                            )
                        )
                        logger.info("ticker %s — score=%d", row.ticker, result.score)
                    except Exception as exc:
                        logger.error("ticker %s failed: %s", row.ticker, exc)
                        error_count += 1

                insert_signals(conn, run_id, screener_signals)
                all_signals.extend(screener_signals)
                screener_signals = []

        except _DeadlineExceeded:
            # Flush signals collected for the in-progress screener before bailing out.
            if screener_signals:
                insert_signals(conn, run_id, screener_signals)
                all_signals.extend(screener_signals)
            timed_out = True
            logger.warning(
                "wall-clock cap of %ds reached — stopping early", timeout_seconds
            )
            error_count += 1

    elapsed = time.monotonic() - t0

    if error_count == 0:
        status = "ok"
    elif all_signals:
        status = "partial"
    else:
        status = "failed"

    mark_run_finished(conn, run_id, status)

    new_hits = find_new_hits(conn, run_id, config.score_threshold, config.lookback_runs)

    total_analyzed = sum(cache_stats.values())
    hit_rate = cache_stats["hits"] / total_analyzed if total_analyzed > 0 else 0.0

    logger.info(
        "run %d finished — status=%s elapsed=%.1fs tickers=%d signals=%d "
        "new_hits=%d cache_hit_rate=%d%% timed_out=%s",
        run_id,
        status,
        elapsed,
        ticker_count,
        len(all_signals),
        len(new_hits),
        int(hit_rate * 100),
        timed_out,
    )

    if dry_run:
        logger.info("dry-run — skipping Discord notification")
    else:
        post_discord(new_hits, webhook_url)

    export_dir = config.export_dir
    if export_dir and not dry_run:
        try:
            from .exporter import export as do_export

            do_export(
                conn,
                export_dir,
                score_threshold=config.score_threshold,
                lookback_runs=config.lookback_runs,
            )
        except Exception as exc:
            logger.error("export failed: %s", exc)

    return new_hits
