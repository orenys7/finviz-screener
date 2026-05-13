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

    existing = {r["name"] for r in conn.execute("PRAGMA table_info(signals)")}
    for col, ddl in (
        ("price", "REAL"),
        ("change_pct", "REAL"),
        ("volume", "INTEGER"),
    ):
        if col not in existing:
            conn.execute(f"ALTER TABLE signals ADD COLUMN {col} {ddl}")
    conn.commit()


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
        "INSERT OR REPLACE INTO signals "
        "(run_id, ticker, screener, score, analysis, price, change_pct, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                run_id,
                s.ticker,
                s.screener,
                s.score,
                s.analysis,
                s.price,
                s.change_pct,
                s.volume,
            )
            for s in signals
        ],
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


def get_signal_counts(conn: sqlite3.Connection, run_ids: list[int]) -> dict[int, int]:
    if not run_ids:
        return {}
    placeholders = ",".join("?" * len(run_ids))
    rows = conn.execute(
        f"SELECT run_id, COUNT(*) AS n FROM signals"
        f" WHERE run_id IN ({placeholders}) GROUP BY run_id",
        run_ids,
    ).fetchall()
    return {r["run_id"]: r["n"] for r in rows}


def get_new_hit_counts(
    conn: sqlite3.Connection, threshold: int, lookback: int
) -> dict[int, int]:
    rows = conn.execute(
        """
        SELECT s.run_id, COUNT(*) AS n
        FROM signals s
        WHERE s.score >= :threshold
          AND NOT EXISTS (
              SELECT 1 FROM signals h
              WHERE h.ticker   = s.ticker
                AND h.screener = s.screener
                AND h.score   >= :threshold
                AND h.run_id IN (
                    SELECT id FROM runs r2
                    WHERE r2.id < s.run_id
                    ORDER BY r2.id DESC
                    LIMIT :lookback
                )
          )
        GROUP BY s.run_id
        """,
        {"threshold": threshold, "lookback": lookback},
    ).fetchall()
    return {r["run_id"]: r["n"] for r in rows}


def get_ticker_history(
    conn: sqlite3.Connection, run_id: int
) -> dict[str, dict[str, object]]:
    """For each ticker in `run_id`, return {first_seen, streak} where:

    - first_seen: ISO date (YYYY-MM-DD) of the first scan-day this ticker
      appeared in any signals row.
    - streak: number of consecutive scan-days ending at this run's date that
      the ticker appeared on. Scan-days are *distinct dates on which any run
      started*, so weekend/holiday gaps don't break the streak.
    """
    anchor = conn.execute(
        "SELECT DATE(started_at) AS d FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    if anchor is None:
        return {}
    anchor_day = anchor["d"]

    tickers = [
        r["ticker"]
        for r in conn.execute(
            "SELECT DISTINCT ticker FROM signals WHERE run_id = ?", (run_id,)
        )
    ]
    if not tickers:
        return {}

    all_days = [
        r["d"]
        for r in conn.execute(
            "SELECT DISTINCT DATE(started_at) AS d FROM runs"
            " WHERE status != 'running' AND DATE(started_at) <= ?"
            " ORDER BY d DESC",
            (anchor_day,),
        )
    ]

    out: dict[str, dict[str, object]] = {}
    for ticker in tickers:
        days = {
            r["d"]
            for r in conn.execute(
                "SELECT DISTINCT DATE(r.started_at) AS d"
                " FROM signals s JOIN runs r ON r.id = s.run_id"
                " WHERE s.ticker = ?"
                "   AND r.status != 'running'"
                "   AND DATE(r.started_at) <= ?",
                (ticker, anchor_day),
            )
        }
        if not days:
            continue
        first_seen = min(days)
        streak = 0
        for d in all_days:
            if d in days:
                streak += 1
            else:
                break
        out[ticker] = {"first_seen": first_seen, "streak": streak}

    return out


def get_signals_for_run(conn: sqlite3.Connection, run_id: int) -> list[Signal]:
    rows = conn.execute(
        "SELECT ticker, screener, score, analysis, price, change_pct, volume "
        "FROM signals WHERE run_id = ? ORDER BY score DESC, ticker",
        (run_id,),
    ).fetchall()
    return [
        Signal(
            ticker=r["ticker"],
            screener=r["screener"],
            score=r["score"],
            analysis=r["analysis"],
            price=r["price"],
            change_pct=r["change_pct"],
            volume=r["volume"],
        )
        for r in rows
    ]
