import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import AppConfig
from .db import connect, migrate
from .exporter import _build_run_detail
from .models import LatestRunResponse, RunDetailResponse, RunSummary

_conn: sqlite3.Connection | None = None
_config: AppConfig | None = None


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("DB not initialised")
    return _conn


def _get_config() -> AppConfig:
    if _config is None:
        raise RuntimeError("Config not initialised")
    return _config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(conn: sqlite3.Connection, config: AppConfig) -> FastAPI:
    global _conn, _config
    _conn = conn
    _config = config

    app = FastAPI(title="finviz-screener", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/api/latest", response_model=LatestRunResponse)
    def get_latest() -> LatestRunResponse:
        from .db import get_finished_run_ids

        ids = get_finished_run_ids(_get_conn())
        if not ids:
            raise HTTPException(status_code=404, detail="no finished runs")
        cfg = _get_config()
        detail = _build_run_detail(
            _get_conn(), ids[0], cfg.score_threshold, cfg.lookback_runs
        )
        if detail is None:
            raise HTTPException(status_code=404, detail="run not found")
        return detail

    @app.get("/api/runs", response_model=list[RunSummary])
    def list_runs() -> list[RunSummary]:
        from .db import get_finished_run_ids

        cfg = _get_config()
        ids = get_finished_run_ids(_get_conn())
        summaries: list[RunSummary] = []
        for run_id in ids:
            detail = _build_run_detail(
                _get_conn(), run_id, cfg.score_threshold, cfg.lookback_runs
            )
            if detail is not None:
                summaries.append(detail.run)
        return summaries

    @app.get("/api/runs/{run_id}", response_model=RunDetailResponse)
    def get_run(run_id: int) -> RunDetailResponse:
        cfg = _get_config()
        detail = _build_run_detail(
            _get_conn(), run_id, cfg.score_threshold, cfg.lookback_runs
        )
        if detail is None:
            raise HTTPException(status_code=404, detail="run not found")
        return detail

    return app
