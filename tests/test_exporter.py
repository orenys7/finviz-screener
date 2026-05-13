import json
import sqlite3

import pytest

from finviz_screener.db import (
    connect,
    insert_run,
    insert_signals,
    mark_run_finished,
    migrate,
)
from finviz_screener.exporter import export
from finviz_screener.models import Signal


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect(":memory:")
    migrate(conn)
    return conn


def _seed_run(conn: sqlite3.Connection, tickers: list[str], score: int = 9) -> int:
    run_id = insert_run(conn)
    signals = [
        Signal(ticker=t, screener="test", score=score, analysis="ok") for t in tickers
    ]
    insert_signals(conn, run_id, signals)
    mark_run_finished(conn, run_id, "ok")
    return run_id


def test_export_creates_expected_files(db, tmp_path):
    _seed_run(db, ["AAPL", "MSFT"])

    export(db, tmp_path)

    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "runs.json").exists()
    assert (tmp_path / "runs" / "1.json").exists()


def test_manifest_has_latest_run_id(db, tmp_path):
    _seed_run(db, ["AAPL"])

    export(db, tmp_path)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["latest_run_id"] == 1
    assert manifest["score_threshold"] == 8
    assert "generated_at" in manifest


def test_latest_json_matches_run_detail(db, tmp_path):
    _seed_run(db, ["NVDA", "AMD"])

    export(db, tmp_path)

    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest["run"]["id"] == 1
    assert latest["run"]["n_signals"] == 2
    tickers = {s["ticker"] for s in latest["signals"]}
    assert tickers == {"NVDA", "AMD"}


def test_runs_json_lists_all_runs(db, tmp_path):
    _seed_run(db, ["AAPL"])
    _seed_run(db, ["MSFT"])

    export(db, tmp_path)

    runs = json.loads((tmp_path / "runs.json").read_text())
    assert len(runs) == 2
    ids = {r["id"] for r in runs}
    assert ids == {1, 2}


def test_new_hit_flag_set_on_first_appearance(db, tmp_path):
    _seed_run(db, ["AAPL"])

    export(db, tmp_path)

    detail = json.loads((tmp_path / "runs" / "1.json").read_text())
    aapl = next(s for s in detail["signals"] if s["ticker"] == "AAPL")
    assert aapl["is_new_hit"] is True


def test_repeat_ticker_not_new_hit(db, tmp_path):
    _seed_run(db, ["AAPL"])
    _seed_run(db, ["AAPL"])

    export(db, tmp_path)

    detail = json.loads((tmp_path / "runs" / "2.json").read_text())
    aapl = next(s for s in detail["signals"] if s["ticker"] == "AAPL")
    assert aapl["is_new_hit"] is False


def test_below_threshold_not_new_hit(db, tmp_path):
    _seed_run(db, ["LOW"], score=5)

    export(db, tmp_path, score_threshold=8)

    detail = json.loads((tmp_path / "runs" / "1.json").read_text())
    low = next(s for s in detail["signals"] if s["ticker"] == "LOW")
    assert low["is_new_hit"] is False


def test_empty_db_exports_gracefully(db, tmp_path):
    export(db, tmp_path)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["latest_run_id"] is None

    runs = json.loads((tmp_path / "runs.json").read_text())
    assert runs == []

    assert not (tmp_path / "latest.json").exists()


def test_export_idempotent(db, tmp_path):
    _seed_run(db, ["AAPL"])

    export(db, tmp_path)
    export(db, tmp_path)

    runs = json.loads((tmp_path / "runs.json").read_text())
    assert len(runs) == 1


def test_export_includes_ticker_history(db, tmp_path):
    """latest.json signals should carry first_seen + streak when available."""
    _seed_run(db, ["AAPL"])  # run 1
    _seed_run(db, ["AAPL"])  # run 2 (same calendar day in test)

    export(db, tmp_path)

    latest = json.loads((tmp_path / "latest.json").read_text())
    aapl = next(s for s in latest["signals"] if s["ticker"] == "AAPL")
    assert "first_seen" in aapl
    assert "streak" in aapl
    assert aapl["first_seen"] is not None
    assert aapl["streak"] is not None
    assert aapl["streak"] >= 1


def test_export_includes_market_data(db, tmp_path):
    run_id = insert_run(db)
    insert_signals(
        db,
        run_id,
        [
            Signal(
                ticker="NVDA",
                screener="test",
                score=9,
                analysis="ok",
                price=123.45,
                change_pct=2.5,
                volume=12_345_678,
            )
        ],
    )
    mark_run_finished(db, run_id, "ok")

    export(db, tmp_path)

    detail = json.loads((tmp_path / "runs" / f"{run_id}.json").read_text())
    nvda = next(s for s in detail["signals"] if s["ticker"] == "NVDA")
    assert nvda["price"] == 123.45
    assert nvda["change_pct"] == 2.5
    assert nvda["volume"] == 12_345_678
