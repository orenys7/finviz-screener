import sqlite3

import pytest

from finviz_screener.db import (
    connect,
    get_ticker_history,
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


def _seed_run_on_date(
    conn: sqlite3.Connection,
    iso_date: str,
    tickers: list[tuple[str, str]],
) -> int:
    """Create a finished run on `iso_date` UTC with the given signals."""
    cur = conn.execute(
        "INSERT INTO runs (started_at, finished_at, status) VALUES (?, ?, ?)",
        (f"{iso_date}T13:00:00+00:00", f"{iso_date}T13:01:00+00:00", "ok"),
    )
    run_id = cur.lastrowid
    insert_signals(
        conn,
        run_id,
        [Signal(ticker=t, screener=s, score=9, analysis="ok") for (t, s) in tickers],
    )
    conn.commit()
    return run_id


def test_ticker_history_first_seen_and_streak(db):
    # day 1: A, B
    # day 2: A, B
    # day 3: A         (B drops out — its streak ends)
    # day 4: A, B      (B comes back — streak resets to 1 for B)
    _seed_run_on_date(db, "2026-05-10", [("A", "s"), ("B", "s")])
    _seed_run_on_date(db, "2026-05-11", [("A", "s"), ("B", "s")])
    _seed_run_on_date(db, "2026-05-12", [("A", "s")])
    run4 = _seed_run_on_date(db, "2026-05-13", [("A", "s"), ("B", "s")])

    hist = get_ticker_history(db, run4)
    assert hist["A"] == {"first_seen": "2026-05-10", "streak": 4}
    assert hist["B"] == {"first_seen": "2026-05-10", "streak": 1}


def test_ticker_history_streak_counts_distinct_scan_days_not_runs(db):
    # 3 runs on the same calendar day — streak should be 1 (1 distinct scan-day).
    _seed_run_on_date(db, "2026-05-12", [("A", "s")])
    _seed_run_on_date(db, "2026-05-12", [("A", "s")])
    run3 = _seed_run_on_date(db, "2026-05-12", [("A", "s")])

    hist = get_ticker_history(db, run3)
    assert hist["A"]["streak"] == 1


def test_ticker_history_streak_ignores_weekend_gaps(db):
    # A appears Fri + Mon. No runs on Sat/Sun. Streak = 2 because the streak
    # is over *distinct scan-days*, which naturally skips days with no scans.
    _seed_run_on_date(db, "2026-05-08", [("A", "s")])  # Fri
    run = _seed_run_on_date(db, "2026-05-11", [("A", "s")])  # Mon

    hist = get_ticker_history(db, run)
    assert hist["A"]["streak"] == 2


def test_ticker_history_empty_run(db):
    run_id = insert_run(db)
    mark_run_finished(db, run_id, "ok")
    assert get_ticker_history(db, run_id) == {}


def test_ticker_history_first_seen_is_first_appearance(db):
    _seed_run_on_date(db, "2026-05-10", [("A", "s")])
    _seed_run_on_date(db, "2026-05-11", [])  # nothing this day
    run = _seed_run_on_date(db, "2026-05-12", [("A", "s")])

    hist = get_ticker_history(db, run)
    assert hist["A"]["first_seen"] == "2026-05-10"
    # streak=2 because A appeared on 2 of the 3 distinct scan-days,
    # but only 1 consecutive trailing day (run on 5-11 had no A signal).
    # Actually: scan-days are 5-10, 5-11, 5-12. A appeared on 5-10 and 5-12.
    # Walking desc from 5-12: hit, miss → streak = 1.
    assert hist["A"]["streak"] == 1
