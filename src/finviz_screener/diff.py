import sqlite3

from .models import NewHit


def find_new_hits(
    conn: sqlite3.Connection,
    run_id: int,
    threshold: int,
    lookback: int,
) -> list[NewHit]:
    """Return signals from run_id where score >= threshold and the ticker+screener
    pair did not score >= threshold in the most recent `lookback` prior runs."""
    rows = conn.execute(
        """
        SELECT s.ticker, s.screener, s.score, s.analysis
        FROM signals s
        WHERE s.run_id = :run_id
          AND s.score >= :threshold
          AND NOT EXISTS (
              SELECT 1
              FROM signals h
              WHERE h.ticker   = s.ticker
                AND h.screener = s.screener
                AND h.score   >= :threshold
                AND h.run_id IN (
                    SELECT id FROM runs
                    WHERE id < :run_id
                    ORDER BY id DESC
                    LIMIT :lookback
                )
          )
        ORDER BY s.score DESC, s.ticker
        """,
        {"run_id": run_id, "threshold": threshold, "lookback": lookback},
    ).fetchall()
    return [
        NewHit(
            ticker=r["ticker"],
            screener=r["screener"],
            score=r["score"],
            analysis=r["analysis"],
        )
        for r in rows
    ]
