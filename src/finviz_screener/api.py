import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import AppConfig
from .db import get_new_hit_counts, get_signal_counts
from .exporter import _build_run_detail
from .models import LatestRunResponse, RunDetailResponse, RunSummary

_DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def create_app(
    conn: sqlite3.Connection,
    config: AppConfig,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(title="finviz-screener")
    app.state.conn = conn
    app.state.config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins
        if cors_origins is not None
        else _DEFAULT_CORS_ORIGINS,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/api/latest", response_model=LatestRunResponse)
    def get_latest(request: Request) -> LatestRunResponse:
        _conn: sqlite3.Connection = request.app.state.conn
        cfg: AppConfig = request.app.state.config

        rows = _conn.execute(
            "SELECT id FROM runs WHERE status != 'running' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if rows is None:
            raise HTTPException(status_code=404, detail="no finished runs")
        detail = _build_run_detail(
            _conn, rows["id"], cfg.score_threshold, cfg.lookback_runs
        )
        if detail is None:
            raise HTTPException(status_code=404, detail="run not found")
        return detail

    @app.get("/api/runs", response_model=list[RunSummary])
    def list_runs(request: Request) -> list[RunSummary]:
        _conn: sqlite3.Connection = request.app.state.conn
        cfg: AppConfig = request.app.state.config

        run_rows = _conn.execute(
            "SELECT id, started_at, finished_at, status "
            "FROM runs WHERE status != 'running' ORDER BY id DESC"
        ).fetchall()
        if not run_rows:
            return []

        run_ids = [r["id"] for r in run_rows]
        sig_counts = get_signal_counts(_conn, run_ids)
        hit_counts = get_new_hit_counts(_conn, cfg.score_threshold, cfg.lookback_runs)

        return [
            RunSummary(
                id=r["id"],
                started_at=r["started_at"],
                finished_at=r["finished_at"],
                status=r["status"],
                n_signals=sig_counts.get(r["id"], 0),
                n_new_hits=hit_counts.get(r["id"], 0),
            )
            for r in run_rows
        ]

    @app.get("/api/runs/{run_id}", response_model=RunDetailResponse)
    def get_run(run_id: int, request: Request) -> RunDetailResponse:
        _conn: sqlite3.Connection = request.app.state.conn
        cfg: AppConfig = request.app.state.config
        detail = _build_run_detail(
            _conn, run_id, cfg.score_threshold, cfg.lookback_runs
        )
        if detail is None:
            raise HTTPException(status_code=404, detail="run not found")
        return detail

    return app
