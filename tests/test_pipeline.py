import sqlite3
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from finviz_screener.config import AppConfig, ScreenerConfig
from finviz_screener.db import connect, migrate
from finviz_screener.models import ScreenerRow
from finviz_screener.pipeline import run_once


@pytest.fixture(autouse=True)
def _mock_io_resources():
    @contextmanager
    def fake_browser_session():
        yield MagicMock()

    with (
        patch("finviz_screener.pipeline.browser_session", fake_browser_session),
        patch("finviz_screener.pipeline.make_chart_client", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect(":memory:")
    migrate(conn)
    return conn


def _make_config(
    score_threshold: int = 8,
    lookback_runs: int = 6,
    min_score_to_store: int = 7,
) -> AppConfig:
    return AppConfig(
        model="claude-sonnet-4-6",
        score_threshold=score_threshold,
        min_score_to_store=min_score_to_store,
        lookback_runs=lookback_runs,
        screeners=[
            ScreenerConfig(
                name="test-screener", url="https://finviz.com/screener.ashx?test"
            ),
        ],
    )


def _rows(*tickers: str, **fields: object) -> list[ScreenerRow]:
    return [ScreenerRow(ticker=t, **fields) for t in tickers]  # type: ignore[arg-type]


def _mock_client(score: int = 9) -> MagicMock:
    client = MagicMock()
    timed = MagicMock()
    client.with_options.return_value = timed
    import json

    msg = MagicMock()
    msg.content = [
        MagicMock(text=json.dumps({"score": score, "analysis": "Strong setup."}))
    ]
    usage = MagicMock()
    usage.input_tokens = 100
    usage.cache_read_input_tokens = 2048
    usage.cache_creation_input_tokens = 0
    msg.usage = usage
    timed.messages.create.return_value = msg
    return client


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_returns_new_hits(mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("AAPL", "MSFT")
    mock_chart.return_value = b"\x89PNG\r\nfake"
    client = _mock_client(score=9)

    hits = run_once(_make_config(), db, client=client, dry_run=True)

    assert len(hits) == 2
    tickers = {h.ticker for h in hits}
    assert tickers == {"AAPL", "MSFT"}


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_below_threshold_no_hits(mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("LOW")
    mock_chart.return_value = b"\x89PNG\r\nfake"
    client = _mock_client(score=5)

    hits = run_once(
        _make_config(score_threshold=8, min_score_to_store=0),
        db,
        client=client,
        dry_run=True,
    )

    assert hits == []


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_skips_low_score_signals(mock_chart, mock_rows, db):
    """score < min_score_to_store → not persisted at all."""
    mock_rows.return_value = _rows("WEAK")
    mock_chart.return_value = b"\x89PNG\r\nfake"

    run_once(
        _make_config(min_score_to_store=7),
        db,
        client=_mock_client(score=5),
        dry_run=True,
    )

    n = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    assert n == 0
    status = db.execute("SELECT status FROM runs WHERE id = 1").fetchone()["status"]
    assert status == "ok"  # nothing failed, just nothing met the bar


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_persists_market_data(mock_chart, mock_rows, db):
    mock_rows.return_value = [
        ScreenerRow(ticker="NVDA", price=123.45, change_pct=2.5, volume=12_345_678)
    ]
    mock_chart.return_value = b"\x89PNG\r\nfake"

    run_once(_make_config(), db, client=_mock_client(score=9), dry_run=True)

    row = db.execute(
        "SELECT ticker, score, price, change_pct, volume FROM signals"
    ).fetchone()
    assert row["ticker"] == "NVDA"
    assert row["score"] == 9
    assert row["price"] == 123.45
    assert row["change_pct"] == 2.5
    assert row["volume"] == 12_345_678


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_repeat_ticker_not_new_hit(mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("NVDA")
    mock_chart.return_value = b"\x89PNG\r\nfake"
    client = _mock_client(score=9)

    run_once(_make_config(), db, client=client, dry_run=True)
    hits = run_once(_make_config(), db, client=client, dry_run=True)

    assert hits == []


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_writes_run_record(mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("AAPL")
    mock_chart.return_value = b"\x89PNG\r\nfake"

    run_once(_make_config(), db, client=_mock_client(), dry_run=True)

    row = db.execute("SELECT status FROM runs WHERE id = 1").fetchone()
    assert row["status"] == "ok"


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_chart_failure_marks_partial(mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("AAPL", "FAIL")
    mock_chart.side_effect = lambda t, **kw: (
        b"\x89PNG\r\nfake"
        if t == "AAPL"
        else (_ for _ in ()).throw(RuntimeError("network error"))
    )

    run_once(_make_config(), db, client=_mock_client(), dry_run=True)

    row = db.execute("SELECT status FROM runs WHERE id = 1").fetchone()
    assert row["status"] == "partial"


@patch("finviz_screener.pipeline.fetch_screener_rows")
def test_run_once_screener_fetch_failure_marks_failed(mock_rows, db):
    mock_rows.side_effect = RuntimeError("scraper error")

    run_once(_make_config(), db, client=_mock_client(), dry_run=True)

    row = db.execute("SELECT status FROM runs WHERE id = 1").fetchone()
    assert row["status"] == "failed"


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_screener_filter_unknown_raises(mock_chart, mock_rows, db):
    with pytest.raises(ValueError, match="no screener named"):
        run_once(
            _make_config(),
            db,
            client=_mock_client(),
            dry_run=True,
            screener_filter="nope",
        )


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
@patch("finviz_screener.pipeline.post_discord")
def test_run_once_dry_run_skips_discord(mock_post, mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("AAPL")
    mock_chart.return_value = b"\x89PNG\r\nfake"

    run_once(
        _make_config(),
        db,
        client=_mock_client(score=9),
        dry_run=True,
        webhook_url="https://example.com",
    )

    mock_post.assert_not_called()


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
@patch("finviz_screener.pipeline.post_discord")
def test_run_once_calls_discord_when_not_dry_run(mock_post, mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("AAPL")
    mock_chart.return_value = b"\x89PNG\r\nfake"

    run_once(
        _make_config(),
        db,
        client=_mock_client(score=9),
        dry_run=False,
        webhook_url="https://example.com",
    )

    mock_post.assert_called_once()
    hits_arg = mock_post.call_args[0][0]
    assert len(hits_arg) == 1
    assert hits_arg[0].ticker == "AAPL"


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
@patch("finviz_screener.pipeline.time")
def test_run_once_timeout_stops_early(mock_time, mock_chart, mock_rows, db):
    # monotonic calls: deadline(0.0), t0(0.0), T0-check(<100), T1-check(>100), elapsed
    mock_time.monotonic.side_effect = [0.0, 0.0, 0.0, 999.0, 999.0]

    mock_rows.return_value = _rows("T0", "T1", "T2")
    mock_chart.return_value = b"\x89PNG\r\nfake"

    run_once(
        _make_config(),
        db,
        client=_mock_client(score=9),
        dry_run=True,
        timeout_seconds=100,
    )

    row = db.execute("SELECT status FROM runs WHERE id = 1").fetchone()
    processed = db.execute("SELECT COUNT(*) FROM signals WHERE run_id = 1").fetchone()[
        0
    ]
    # T0 processed and flushed; T1 triggers deadline → partial run
    assert processed == 1
    assert row["status"] == "partial"


@patch("finviz_screener.pipeline.fetch_screener_rows")
@patch("finviz_screener.pipeline.download_chart")
def test_run_once_cache_stats_logged(mock_chart, mock_rows, db):
    mock_rows.return_value = _rows("AAPL", "MSFT")
    mock_chart.return_value = b"\x89PNG\r\nfake"

    client = MagicMock()
    timed = MagicMock()
    client.with_options.return_value = timed
    import json

    def make_msg(cache_read, cache_created):
        msg = MagicMock()
        msg.content = [MagicMock(text=json.dumps({"score": 9, "analysis": "ok"}))]
        usage = MagicMock()
        usage.input_tokens = 100
        usage.cache_read_input_tokens = cache_read
        usage.cache_creation_input_tokens = cache_created
        msg.usage = usage
        return msg

    # First call writes cache, second call hits it
    timed.messages.create.side_effect = [
        make_msg(cache_read=0, cache_created=2048),
        make_msg(cache_read=2048, cache_created=0),
    ]

    # Should complete without error — cache stats are tracked internally
    hits = run_once(_make_config(), db, client=client, dry_run=True)
    assert len(hits) == 2
