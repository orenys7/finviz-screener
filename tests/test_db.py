import sqlite3

import pytest

from finviz_screener.db import (
    connect,
    insert_run,
    insert_signals,
    mark_run_finished,
    migrate,
)
from finviz_screener.models import Signal


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect(":memory:")
    migrate(conn)
    return conn


def test_migrate_is_idempotent(db):
    migrate(db)
    migrate(db)
    tables = {
        r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"runs", "signals"}.issubset(tables)


def test_migrate_adds_market_data_columns(db):
    cols = {r["name"] for r in db.execute("PRAGMA table_info(signals)")}
    assert {"price", "change_pct", "volume"}.issubset(cols)


def test_migrate_preserves_existing_signal_rows(db):
    # Simulate an old DB by dropping the new columns and re-adding them via migrate.
    run_id = insert_run(db)
    insert_signals(
        db,
        run_id,
        [Signal(ticker="AAPL", screener="s1", score=9, analysis="Old.")],
    )
    migrate(db)  # second call must not destroy data
    row = db.execute(
        "SELECT ticker, score FROM signals WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert row["ticker"] == "AAPL"
    assert row["score"] == 9


def test_insert_run_returns_incrementing_ids(db):
    id1 = insert_run(db)
    id2 = insert_run(db)
    assert id1 == 1
    assert id2 == 2


def test_insert_run_sets_running_status(db):
    run_id = insert_run(db)
    row = db.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
    assert row["status"] == "running"


def test_mark_run_finished_updates_status(db):
    run_id = insert_run(db)
    mark_run_finished(db, run_id, "ok")
    row = db.execute(
        "SELECT status, finished_at FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row["status"] == "ok"
    assert row["finished_at"] is not None


def test_insert_signals_persists_all(db):
    run_id = insert_run(db)
    signals = [
        Signal(ticker="AAPL", screener="s1", score=9, analysis="Strong."),
        Signal(ticker="MSFT", screener="s1", score=7, analysis="Decent."),
    ]
    insert_signals(db, run_id, signals)
    rows = db.execute("SELECT * FROM signals WHERE run_id = ?", (run_id,)).fetchall()
    assert len(rows) == 2
    tickers = {r["ticker"] for r in rows}
    assert tickers == {"AAPL", "MSFT"}


def test_insert_signals_empty_list_is_noop(db):
    run_id = insert_run(db)
    insert_signals(db, run_id, [])
    count = db.execute(
        "SELECT COUNT(*) FROM signals WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    assert count == 0


def test_insert_signals_replace_on_duplicate(db):
    run_id = insert_run(db)
    s = Signal(ticker="NVDA", screener="s1", score=7, analysis="Old.")
    insert_signals(db, run_id, [s])
    s_updated = Signal(ticker="NVDA", screener="s1", score=9, analysis="Updated.")
    insert_signals(db, run_id, [s_updated])
    rows = db.execute(
        "SELECT score FROM signals WHERE run_id = ? AND ticker = 'NVDA'", (run_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["score"] == 9
