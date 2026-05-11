import sqlite3

import pytest

from finviz_screener.db import (
    connect,
    insert_run,
    insert_signals,
    mark_run_finished,
    migrate,
)
from finviz_screener.diff import find_new_hits
from finviz_screener.models import Signal


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect(":memory:")
    migrate(conn)
    return conn


def sig(ticker: str, score: int, screener: str = "test-screener") -> Signal:
    return Signal(ticker=ticker, screener=screener, score=score, analysis="n/a")


def make_run(db: sqlite3.Connection, signals: list[Signal]) -> int:
    run_id = insert_run(db)
    insert_signals(db, run_id, signals)
    mark_run_finished(db, run_id, "ok")
    return run_id


# ── first run edge cases ──────────────────────────────────────────────────────


def test_first_run_above_threshold_are_all_new(db):
    run_id = make_run(db, [sig("AAPL", 9), sig("MSFT", 8)])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert {h.ticker for h in hits} == {"AAPL", "MSFT"}


def test_first_run_below_threshold_not_returned(db):
    run_id = make_run(db, [sig("AAPL", 7), sig("MSFT", 5)])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert hits == []


def test_first_run_empty_signals(db):
    run_id = make_run(db, [])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert hits == []


# ── ticker repeats (in lookback) ──────────────────────────────────────────────


def test_ticker_in_previous_run_not_new(db):
    make_run(db, [sig("NVDA", 9)])
    run_id = make_run(db, [sig("NVDA", 9)])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert hits == []


def test_ticker_high_two_runs_ago_still_not_new(db):
    make_run(db, [sig("AMD", 9)])  # run 1
    make_run(db, [sig("AMD", 4)])  # run 2: score dropped
    run_id = make_run(db, [sig("AMD", 9)])  # run 3: back above
    # lookback=2 covers runs 1 and 2; AMD was >= 8 in run 1 → not new
    hits = find_new_hits(db, run_id, threshold=8, lookback=2)
    assert not any(h.ticker == "AMD" for h in hits)


# ── ticker cooled off outside the lookback window ────────────────────────────


def test_ticker_outside_lookback_is_new_hit(db):
    make_run(db, [sig("TSLA", 9)])  # run 1: very old — outside lookback
    make_run(db, [sig("TSLA", 4)])  # run 2: below threshold
    make_run(db, [sig("TSLA", 4)])  # run 3: below threshold
    make_run(db, [sig("TSLA", 4)])  # run 4: below threshold
    run_id = make_run(db, [sig("TSLA", 9)])  # run 5: current
    # lookback=3 → checks runs 2,3,4 only; run 1 (where TSLA was high) is excluded
    hits = find_new_hits(db, run_id, threshold=8, lookback=3)
    assert any(h.ticker == "TSLA" for h in hits)


def test_ticker_cooled_off_within_lookback_not_new(db):
    make_run(db, [sig("TSLA", 9)])  # run 1: high (within lookback of 2)
    make_run(db, [sig("TSLA", 4)])  # run 2: cooled
    run_id = make_run(db, [sig("TSLA", 9)])  # run 3: current
    # lookback=2 → checks runs 1 and 2; TSLA was >= 8 in run 1 → not new
    hits = find_new_hits(db, run_id, threshold=8, lookback=2)
    assert not any(h.ticker == "TSLA" for h in hits)


# ── screener independence ─────────────────────────────────────────────────────


def test_same_ticker_different_screener_is_new(db):
    make_run(
        db, [Signal(ticker="AAPL", screener="screener-a", score=9, analysis="n/a")]
    )
    run_id = make_run(
        db, [Signal(ticker="AAPL", screener="screener-b", score=9, analysis="n/a")]
    )
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert any(h.ticker == "AAPL" and h.screener == "screener-b" for h in hits)


def test_same_ticker_same_screener_not_new(db):
    make_run(
        db, [Signal(ticker="AAPL", screener="screener-a", score=9, analysis="n/a")]
    )
    run_id = make_run(
        db, [Signal(ticker="AAPL", screener="screener-a", score=9, analysis="n/a")]
    )
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert hits == []


# ── ordering and mixed threshold ─────────────────────────────────────────────


def test_results_ordered_score_desc(db):
    run_id = make_run(db, [sig("AMD", 8), sig("NVDA", 10), sig("INTC", 9)])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert [h.score for h in hits] == [10, 9, 8]


def test_mixed_scores_only_above_threshold_returned(db):
    run_id = make_run(db, [sig("A", 10), sig("B", 8), sig("C", 7), sig("D", 3)])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    tickers = {h.ticker for h in hits}
    assert tickers == {"A", "B"}
    assert "C" not in tickers
    assert "D" not in tickers


def test_exact_threshold_score_included(db):
    run_id = make_run(db, [sig("EXACT", 8)])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert any(h.ticker == "EXACT" for h in hits)


def test_one_below_threshold_excluded(db):
    run_id = make_run(db, [sig("BELOW", 7)])
    hits = find_new_hits(db, run_id, threshold=8, lookback=6)
    assert hits == []
