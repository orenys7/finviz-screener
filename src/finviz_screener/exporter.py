import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import (
    get_finished_run_ids,
    get_run_by_id,
    get_signals_for_run,
    get_ticker_history,
)
from .diff import find_new_hits
from .models import Manifest, RunDetailResponse, RunSummary, SignalRow

logger = logging.getLogger(__name__)


def _build_run_detail(
    conn: sqlite3.Connection,
    run_id: int,
    score_threshold: int,
    lookback_runs: int,
) -> RunDetailResponse | None:
    run_row = get_run_by_id(conn, run_id)
    if run_row is None:
        return None

    signals = get_signals_for_run(conn, run_id)
    new_hits = find_new_hits(conn, run_id, score_threshold, lookback_runs)
    new_tickers = {(h.ticker, h.screener) for h in new_hits}
    history = get_ticker_history(conn, run_id)

    signal_rows = [
        SignalRow(
            ticker=s.ticker,
            screener=s.screener,
            score=s.score,
            analysis=s.analysis,
            is_new_hit=(s.ticker, s.screener) in new_tickers,
            price=s.price,
            change_pct=s.change_pct,
            volume=s.volume,
            first_seen=history.get(s.ticker, {}).get("first_seen"),  # type: ignore[arg-type]
            streak=history.get(s.ticker, {}).get("streak"),  # type: ignore[arg-type]
        )
        for s in signals
    ]

    run_summary = RunSummary(
        id=run_row.id,
        started_at=run_row.started_at,
        finished_at=run_row.finished_at,
        status=run_row.status,
        n_signals=len(signals),
        n_new_hits=len(new_hits),
    )

    return RunDetailResponse(run=run_summary, signals=signal_rows)


def export(
    conn: sqlite3.Connection,
    out_dir: str | Path,
    *,
    score_threshold: int = 8,
    lookback_runs: int = 6,
) -> None:
    out = Path(out_dir)
    runs_dir = out / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    run_ids = get_finished_run_ids(conn)

    run_summaries: list[RunSummary] = []
    latest_id: int | None = run_ids[0] if run_ids else None
    latest_detail: RunDetailResponse | None = None

    for run_id in run_ids:
        detail = _build_run_detail(conn, run_id, score_threshold, lookback_runs)
        if detail is None:
            continue
        run_summaries.append(detail.run)
        (runs_dir / f"{run_id}.json").write_text(
            detail.model_dump_json(indent=2), encoding="utf-8"
        )
        if run_id == latest_id:
            latest_detail = detail

    (out / "runs.json").write_text(
        json.dumps([s.model_dump() for s in run_summaries], indent=2),
        encoding="utf-8",
    )

    if latest_detail is not None:
        (out / "latest.json").write_text(
            latest_detail.model_dump_json(indent=2), encoding="utf-8"
        )

    manifest = Manifest(
        generated_at=datetime.now(timezone.utc).isoformat(),
        latest_run_id=latest_id,
        score_threshold=score_threshold,
    )
    (out / "manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )

    logger.info(
        "export done — runs=%d latest_run_id=%s out_dir=%s",
        len(run_summaries),
        latest_id,
        out,
    )
