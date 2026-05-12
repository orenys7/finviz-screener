import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from .config import AppConfig, Settings, load_config
from .db import connect, migrate
from .pipeline import _DEFAULT_TIMEOUT, run_once

app = typer.Typer(add_completion=False)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj)


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


@app.command()
def scan(
    config_path: Path = typer.Option(
        Path("config.yaml"), "--config", "-c", help="Path to config YAML"
    ),
    screener: Optional[str] = typer.Option(
        None, "--screener", "-s", help="Run only this screener by name"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Analyse but skip Discord notification"
    ),
    db_path: Optional[Path] = typer.Option(
        None, "--db", help="Path to SQLite state file (overrides FINVIZ_DB_PATH)"
    ),
    timeout: int = typer.Option(
        _DEFAULT_TIMEOUT, "--timeout", help="Wall-clock cap in seconds (default 900)"
    ),
) -> None:
    """Scrape Finviz, score charts via the configured LLM, notify Discord on hits."""
    _setup_logging()

    try:
        config: AppConfig = load_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}", err=True)
        raise typer.Exit(1)

    try:
        settings = Settings()
        settings.require_key_for(config.model)
    except Exception as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(1)

    resolved_db = db_path or Path(os.environ.get("FINVIZ_DB_PATH", "state.db"))

    conn = connect(resolved_db)
    migrate(conn)

    try:
        new_hits = run_once(
            config,
            conn,
            screener_filter=screener,
            dry_run=dry_run,
            webhook_url=settings.discord_webhook_url,
            timeout_seconds=timeout,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    finally:
        conn.close()

    if new_hits:
        typer.echo(
            f"{len(new_hits)} new hit(s): {', '.join(h.ticker for h in new_hits)}"
        )
    else:
        typer.echo("No new hits this run.")


@app.command()
def export(
    config_path: Path = typer.Option(
        Path("config.yaml"), "--config", "-c", help="Path to config YAML"
    ),
    db_path: Optional[Path] = typer.Option(
        None, "--db", help="Path to SQLite state file (overrides FINVIZ_DB_PATH)"
    ),
    out_dir: Path = typer.Option(
        Path("web/public/data"), "--out", "-o", help="Output directory for JSON files"
    ),
) -> None:
    """Export run history to static JSON files for the dashboard."""
    _setup_logging()

    try:
        config: AppConfig = load_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}", err=True)
        raise typer.Exit(1)

    resolved_db = db_path or Path(os.environ.get("FINVIZ_DB_PATH", "state.db"))
    conn = connect(resolved_db)
    migrate(conn)

    try:
        from .exporter import export as do_export

        do_export(
            conn,
            out_dir,
            score_threshold=config.score_threshold,
            lookback_runs=config.lookback_runs,
        )
    finally:
        conn.close()

    typer.echo(f"Exported to {out_dir}")


@app.command()
def serve(
    config_path: Path = typer.Option(
        Path("config.yaml"), "--config", "-c", help="Path to config YAML"
    ),
    db_path: Optional[Path] = typer.Option(
        None, "--db", help="Path to SQLite state file (overrides FINVIZ_DB_PATH)"
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8000, "--port", help="Port"),
) -> None:
    """Serve the REST API for local dashboard development."""
    _setup_logging()

    try:
        config: AppConfig = load_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}", err=True)
        raise typer.Exit(1)

    resolved_db = db_path or Path(os.environ.get("FINVIZ_DB_PATH", "state.db"))
    conn = connect(resolved_db)
    migrate(conn)

    import uvicorn

    from .api import create_app

    application = create_app(conn, config)
    uvicorn.run(application, host=host, port=port)
