import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .models import RunRow, Signal


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT    NOT NULL,
            finished_at TEXT,
            status      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS signals (
            run_id      INTEGER NOT NULL REFERENCES runs(id),
            ticker      TEXT    NOT NULL,
            screener    TEXT    NOT NULL,
            score       INTEGER NOT NULL,
            analysis    TEXT    NOT NULL,
            PRIMARY KEY (run_id, ticker, screener)
        );

        CREATE INDEX IF NOT EXISTS idx_signals_ticker_score
            ON signals(ticker, score);
    """)


def insert_run(conn: sqlite3.Connection) -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO runs (started_at, status) VALUES (?, ?)",
        (started_at, "running"),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def mark_run_finished(conn: sqlite3.Connection, run_id: int, status: str) -> None:
    finished_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE runs SET finished_at = ?, status = ? WHERE id = ?",
        (finished_at, status, run_id),
    )
    conn.commit()


def insert_signals(
    conn: sqlite3.Connection, run_id: int, signals: Sequence[Signal]
) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO signals (run_id, ticker, screener, score, analysis) "
        "VALUES (?, ?, ?, ?, ?)",
        [(run_id, s.ticker, s.screener, s.score, s.analysis) for s in signals],
    )
    conn.commit()


def get_finished_run_ids(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM runs WHERE status != 'running' ORDER BY id DESC"
    ).fetchall()
    return [r["id"] for r in rows]


def get_run_by_id(conn: sqlite3.Connection, run_id: int) -> RunRow | None:
    row = conn.execute(
        "SELECT id, started_at, finished_at, status FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return RunRow(
        id=row["id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=row["status"],
    )


def get_signals_for_run(conn: sqlite3.Connection, run_id: int) -> list[Signal]:
    rows = conn.execute(
        "SELECT ticker, screener, score, analysis FROM signals "
        "WHERE run_id = ? ORDER BY score DESC, ticker",
        (run_id,),
    ).fetchall()
    return [
        Signal(
            ticker=r["ticker"],
            screener=r["screener"],
            score=r["score"],
            analysis=r["analysis"],
        )
        for r in rows
    ]
