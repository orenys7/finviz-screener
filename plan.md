# Finviz Momentum Screener — Plan

## 1. Goal

A scheduled Python job that, every X hours on weekdays:

1. Scrapes one or more Finviz screener URLs (momentum filters).
2. For each ticker, downloads the chart and asks Claude to score it for
   momentum (1–10 + one-line rationale).
3. Stores every result in a SQLite history.
4. Detects tickers that are **newly** above the score threshold (not flagged in
   the prior N runs).
5. Posts the new hits to a Discord webhook.

Out of scope for v1: order execution, broker integration, backtesting
(left as Phase 10+ extensions). A read-only web dashboard is included
as Phase 9 (static SPA on GitHub Pages, regenerated each scan run).

## 2. Tech stack

| Concern           | Choice                          | Why                                                                                |
|-------------------|---------------------------------|------------------------------------------------------------------------------------|
| Language          | Python 3.11+                    | Finance/quant ecosystem; room to grow beyond LLM-only scoring.                     |
| Package manager   | `uv` + `pyproject.toml`         | Fast, lockfile, modern.                                                            |
| Scraping          | `playwright` (sync API)         | Finviz needs a real browser; sync API is simpler for a CLI batch.                  |
| HTTP              | `httpx`                         | Chart download + Discord webhook.                                                  |
| LLM               | `anthropic` (Claude API)        | Vision + structured output; **prompt caching** on the static prompt prefix.        |
| LLM model         | `claude-sonnet-4-6` (default)   | Best cost/perf for per-ticker chart scoring. Opus 4.7 as opt-in for higher quality.|
| Validation        | `pydantic` v2                   | Config, Claude response parsing, DB row shapes.                                    |
| Settings          | `pydantic-settings`             | `.env` + YAML loader.                                                              |
| DB                | stdlib `sqlite3`                | Tiny state, no extra dep.                                                          |
| CLI               | `typer`                         | `scan`, `--screener`, `--dry-run`.                                                 |
| Logging           | stdlib `logging` (JSON handler) | Readable in GH Actions logs.                                                       |
| Scheduling        | GitHub Actions cron             | Free, no infra.                                                                    |
| State persistence | `state.db` committed by CI      | Simplest reliable option in GH Actions.                                            |
| Tests             | `pytest` + in-memory SQLite     | Fast, no fixtures on disk.                                                         |
| Dev API server    | `fastapi` + `uvicorn`           | Local-only; serves JSON shapes the SPA also consumes statically in prod.           |
| Frontend          | Vite + Svelte + TypeScript      | Tiny bundle, no SSR, fits a 2–3 view read-only dashboard.                          |
| Dashboard hosting | GitHub Pages (`gh-pages` branch)| Free, static. CI builds the SPA and exports SQLite → JSON each scan run.           |

## 3. Architecture

```
GitHub Actions cron (every X hrs, Mon–Fri)
        │
        ▼
   python -m finviz_screener scan
        │
        ├─► scraper.py  : Playwright → list[Ticker]   per screener
        ├─► charts.py   : httpx      → PNG bytes      per ticker
        ├─► analyzer.py : Claude     → Score+Reason   per ticker  (cached prefix)
        ├─► db.py       : sqlite     → insert run + signals
        ├─► diff.py     :             → list[NewHit]
        ├─► notify.py   : Discord    → post if hits > 0
        └─► exporter.py : sqlite     → web/public/data/*.json
        │
        ▼
   git commit state.db ([skip ci])
        │
        ▼
   build SPA + publish to gh-pages branch (web/dist + data/)
```

### Dashboard data flow

The SPA never talks to a server in production. After each scan run, the
exporter writes a small set of JSON files (latest run, runs index, per-run
detail) into `web/public/data/`. The same JSON shapes are also exposed by a
local FastAPI dev server (`api.py`) so the SPA can be developed against a
live `state.db` without rebuilding. Both code paths share the pydantic
response models.

A run = one `runs` row + N `signals` rows. Everything else is derived by
queries, so any run is fully reproducible.

### LLM call shape (prompt caching)

The analyzer prompt is identical for every ticker; only the chart image
changes. So we structure each call as:

- **System** (cached, `cache_control: ephemeral`): role + scoring rubric +
  output JSON schema. ~1–2k tokens of stable instructions.
- **User** (per call): the chart image + a one-line "score this ticker:
  {TICKER}" line.

With cache hits, every ticker after the first in a run pays only the image +
tiny user-text cost on input.

## 4. Project layout

```
finviz-screener/
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── README.md
├── plan.md
├── config.yaml                  # screener filters, thresholds, lookback
├── state.db                     # committed by CI
├── src/finviz_screener/
│   ├── __init__.py
│   ├── __main__.py              # `python -m finviz_screener`
│   ├── cli.py                   # typer entry
│   ├── config.py                # pydantic-settings + yaml loader
│   ├── models.py                # Signal, RunRow, NewHit, AnalysisResponse
│   ├── scraper.py               # Playwright → tickers
│   ├── charts.py                # httpx → chart PNG bytes
│   ├── analyzer.py              # Claude call + cached prompt prefix
│   ├── db.py                    # schema migration + queries
│   ├── diff.py                  # find_new_hits()
│   ├── notify.py                # Discord webhook
│   ├── pipeline.py              # orchestrates one run
│   ├── exporter.py              # state.db → web/public/data/*.json
│   └── api.py                   # FastAPI dev server (not used in prod)
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/data/             # generated; gitignored except .gitkeep
│   └── src/
│       ├── main.ts
│       ├── App.svelte
│       ├── lib/api.ts           # fetch wrappers + TS types
│       └── routes/
│           ├── LatestRun.svelte
│           ├── RunsList.svelte
│           └── RunDetail.svelte
├── tests/
│   ├── test_diff.py
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_exporter.py
│   └── fixtures/
└── .github/workflows/
    ├── scan.yml
    └── pages.yml                # build SPA + deploy to gh-pages
```

## 5. Data model (SQLite)

```sql
CREATE TABLE runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT    NOT NULL,    -- ISO8601 UTC
    finished_at TEXT,
    status      TEXT    NOT NULL     -- 'ok' | 'partial' | 'failed'
);

CREATE TABLE signals (
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    ticker      TEXT    NOT NULL,
    screener    TEXT    NOT NULL,
    score       INTEGER NOT NULL,    -- 1..10
    analysis    TEXT    NOT NULL,
    PRIMARY KEY (run_id, ticker, screener)
);

CREATE INDEX idx_signals_ticker_score ON signals(ticker, score);
```

**"New hit"** = `score >= threshold` in the current run AND the same ticker
did not have `score >= threshold` in the previous `lookback_runs` runs.

## 6. Config shape

```yaml
# config.yaml
model: claude-sonnet-4-6      # or claude-opus-4-7
score_threshold: 8
lookback_runs: 6              # ~24h at one run every 4h
screeners:
  - name: high-short-midcap
    url: https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_curvol_o2000,sh_float_u100,sh_outstanding_u100,sh_relvol_o1,sh_short_o20
  - name: breakouts
    url: https://finviz.com/screener.ashx?...
```

Secrets via `.env` / GH Actions secrets:

- `ANTHROPIC_API_KEY`
- `DISCORD_WEBHOOK_URL`

## 7. Task breakdown

Each task is a small, reviewable unit (~15–60 min). Phases are sequential;
tasks within a phase can sometimes parallelize.

### Phase 0 — Scaffold

- [ ] **0.1** `pyproject.toml` via `uv init`; declare runtime deps:
      `playwright`, `httpx`, `anthropic`, `pydantic`, `pydantic-settings`,
      `pyyaml`, `typer`. Dev deps: `pytest`, `ruff`.
- [ ] **0.2** `.gitignore`: `.venv/`, `__pycache__/`, `.env`, `charts/`,
      `*.db-journal`.
- [ ] **0.3** `.env.example` with `ANTHROPIC_API_KEY=` and
      `DISCORD_WEBHOOK_URL=`.
- [ ] **0.4** `README.md` skeleton: install, run locally, configure.
- [ ] **0.5** Empty `src/finviz_screener/` package + `__main__.py` that prints
      version (sanity check the entry point).

### Phase 1 — Config & models

- [ ] **1.1** `config.yaml` with two example screeners and defaults.
- [ ] **1.2** `config.py`: `Settings` (env via pydantic-settings) +
      `AppConfig` (loaded from YAML). `load_config(path) -> AppConfig`.
- [ ] **1.3** `models.py`: `Signal`, `RunRow`, `NewHit`, `AnalysisResponse`
      (pydantic).
- [ ] **1.4** `tests/test_config.py`: loads a fixture YAML, asserts shape.

### Phase 2 — Scraper

- [ ] **2.1** `scraper.py::fetch_tickers(url: str) -> list[str]` using
      Playwright sync API; selector `tr.styled-row a.tab-link`.
- [ ] **2.2** Headless Chromium with realistic UA + 60s nav timeout.
- [ ] **2.3** Retry + exponential backoff on 429 / nav timeout (max 3 tries).
- [ ] **2.4** Manual smoke test: print tickers for one screener URL.

### Phase 3 — Charts & analyzer (Claude)

- [ ] **3.1** `charts.py::download_chart(ticker) -> bytes` via httpx
      (`https://charts2.finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l`).
- [ ] **3.2** Design the cached system prompt: role, momentum scoring rubric
      (breakout vs base, volume surge, MA stacking 20/50/200, RS, gap
      behavior), strict JSON output schema (`{"score": int, "analysis": str}`).
- [ ] **3.3** `analyzer.py::analyze(ticker, png_bytes, model) ->
      AnalysisResponse` — Anthropic Messages API with image content block;
      `cache_control={"type": "ephemeral"}` on the system prompt; parse +
      validate via pydantic; raise on parse failure.
- [ ] **3.4** Per-ticker timeout (e.g., 30s); retry once on transient 5xx /
      overloaded.
- [ ] **3.5** Log cache hit ratio per run (from response usage) so we can
      confirm caching is working.

### Phase 4 — Persistence

- [ ] **4.1** `db.py::connect(path) -> sqlite3.Connection` with WAL +
      foreign keys on.
- [ ] **4.2** `db.py::migrate(conn)` — idempotent CREATE TABLE / INDEX.
- [ ] **4.3** `db.py::insert_run(conn) -> run_id`;
      `mark_run_finished(conn, run_id, status)`.
- [ ] **4.4** `db.py::insert_signals(conn, run_id, signals)` batch insert.
- [ ] **4.5** `diff.py::find_new_hits(conn, run_id, threshold, lookback) ->
      list[NewHit]` — pure SQL.
- [ ] **4.6** `tests/test_diff.py`: in-memory sqlite, fixture history,
      assert new-hit detection for edge cases (first run, ticker just
      cooled off, ticker repeats).

### Phase 5 — Notifications

- [ ] **5.1** `notify.py::post_discord(hits, webhook_url)` — formatted
      message: ticker, score, one-line analysis, Finviz link, chart link.
- [ ] **5.2** No-op (log only) when `hits` is empty.
- [ ] **5.3** Surface webhook 4xx/5xx as a logged error but don't fail
      the run (state is already persisted).

### Phase 6 — Orchestration & CLI

- [ ] **6.1** `pipeline.py::run_once(config, conn)` — loops screeners,
      collects signals, writes them, computes diff, calls notify.
- [ ] **6.2** `cli.py`: `scan` command; flags `--config`,
      `--screener NAME` (filter to one), `--dry-run` (skip Discord),
      `--db PATH`.
- [ ] **6.3** Wire `__main__.py` to `cli.app()`.

### Phase 7 — CI / scheduling

- [ ] **7.1** `.github/workflows/scan.yml`: cron `0 13,17,21 * * 1-5`
      (UTC; market-hour-ish), `workflow_dispatch`, `setup-python@v5`,
      `uv sync`, `playwright install --with-deps chromium`.
- [ ] **7.2** Step: `python -m finviz_screener scan`. Env:
      `ANTHROPIC_API_KEY`, `DISCORD_WEBHOOK_URL` from secrets.
- [ ] **7.3** Step: commit `state.db` back with message
      `chore: run @ <ts> [skip ci]` using `actions/checkout@v4` with
      `persist-credentials: true`.
- [ ] **7.4** Document required secrets in `README.md`.

### Phase 8 — Hardening & polish

- [ ] **8.1** Total run wall-clock cap (e.g., 15 min) — fail cleanly
      rather than time out.
- [ ] **8.2** Concurrency guard: GH Actions `concurrency:` block so two
      runs can't race the `state.db` commit.
- [ ] **8.3** Structured JSON log lines; log a run summary at end
      (tickers scanned, new hits, cache hit ratio, wall-clock).
- [ ] **8.4** `ruff` + `pytest` in a separate `ci.yml` workflow on PRs.
- [ ] **8.5** README: how to add a screener, tune `score_threshold` /
      `lookback_runs`, inspect `state.db` with `sqlite3` CLI.

### Phase 9 — Web dashboard (static SPA on GitHub Pages)

Read-only dashboard regenerated from `state.db` each scan run. Two views
in v1: **latest run** (ticker / score / analysis) and **runs list → run
detail**. The SPA is deployed statically; a local FastAPI server is
included for development only.

- [ ] **9.1** Add deps: runtime `fastapi`, `uvicorn` (dev extra). Decide
      JSON shapes up front and codify them as pydantic response models in
      `models.py` (`LatestRunResponse`, `RunSummary`, `RunDetailResponse`).
      Keep them flat and SPA-friendly — no nested `runs[].signals[]`.
- [ ] **9.2** `exporter.py::export(conn, out_dir)` — writes:
      - `data/latest.json` → most recent finished run + its signals
      - `data/runs.json` → list of `RunSummary` (id, started_at, status,
        n_signals, n_new_hits) ordered newest first
      - `data/runs/<id>.json` → `RunDetailResponse` per run
      Idempotent; overwrite-in-place; emits a `data/manifest.json` with
      `{generated_at, latest_run_id}` so the SPA can show staleness.
- [ ] **9.3** `tests/test_exporter.py` — in-memory sqlite + fixture
      history; assert files written, JSON shapes round-trip through the
      pydantic models, `runs/<id>.json` matches `runs.json` summary.
- [ ] **9.4** `api.py` — FastAPI app with three endpoints
      (`/api/latest`, `/api/runs`, `/api/runs/{id}`) that wrap the same
      query helpers as `exporter.py`. CORS allow `localhost:5173` for
      Vite dev. No write endpoints, ever.
- [ ] **9.5** CLI: `python -m finviz_screener export --out web/public`
      and `python -m finviz_screener serve --port 8000` subcommands.
- [ ] **9.6** Scaffold `web/` via Vite (`svelte-ts` template). Add a
      `npm run check` (svelte-check) and `npm run build` script.
- [ ] **9.7** `web/src/lib/api.ts` — typed fetchers. In dev (when
      `import.meta.env.DEV`) hit `http://localhost:8000/api/...`; in prod
      fetch `./data/...json` relative to the page. Shared TS types
      generated by hand from the pydantic models (small surface — fine
      without codegen for v1).
- [ ] **9.8** `LatestRun.svelte` — table of `{ticker, screener, score,
      analysis}` for the most recent run; sortable by score (default
      desc); ticker links to its Finviz quote page; small header shows
      run timestamp + age. Highlight rows where `score >= threshold`.
- [ ] **9.9** `RunsList.svelte` — table of runs (id, started_at, status,
      n_signals, n_new_hits), newest first; row click → run detail.
- [ ] **9.10** `RunDetail.svelte` — header (run metadata), signals
      table (same columns as Latest), and a "new hits" badge column.
- [ ] **9.11** Routing — hash router (e.g., `svelte-spa-router`) so the
      site works under a non-root path on GitHub Pages without rewrites.
      Three routes: `#/`, `#/runs`, `#/runs/:id`.
- [ ] **9.12** Styling — Tailwind via `@tailwindcss/vite` (or a single
      hand-written CSS file if Tailwind feels heavy). Dark mode optional.
- [ ] **9.13** Empty/loading/error states — show "no runs yet" if
      `runs.json` is empty; surface fetch failures with a retry button.
- [ ] **9.14** Pipeline hook — after `mark_run_finished(..., 'ok')`,
      `pipeline.py` calls `exporter.export(conn, "web/public")`. Failures
      in export are logged but do not fail the run (state is durable).
- [ ] **9.15** `.github/workflows/pages.yml` — triggered by push to
      `master` (after `scan.yml` commits `state.db`). Steps:
      `uv sync` → `python -m finviz_screener export --out web/public` →
      `cd web && npm ci && npm run build` → `actions/upload-pages-artifact`
      → `actions/deploy-pages`. Use the official Pages action, not a
      `gh-pages` branch push, to avoid polluting history.
- [ ] **9.16** `scan.yml` concurrency group must serialize with
      `pages.yml` (or chain via `workflow_run`) so a deploy never reads
      `state.db` mid-commit.
- [ ] **9.17** README: add "Dashboard" section — local dev (`npm run
      dev` + `serve` subcommand), live URL once Pages is configured,
      data freshness guarantees.

### Phase 10+ — Future (not in v1)

- Score-over-time per ticker (inline matplotlib chart in notify message,
  and a per-ticker view in the dashboard).
- Dashboard filters (screener, min score, lookback window).
- Blend Claude score with rule-based features (volume z-score, RS rank).
- Backtest harness (`vectorbt`) over `signals` history.
- Replace `state.db`-in-repo with Turso/Supabase once history > ~10 MB.

## 8. Open questions

- Cron cadence: every 4h on weekdays, or tighter near the open/close?
- Score threshold default (8?) — calibrate after the first week of data.
- Should the same ticker re-alert across screeners, or dedupe per run?
- Sonnet 4.6 by default vs Opus 4.7 — start cheap, upgrade if scores look noisy?
- Dashboard: commit generated `web/public/data/*.json` to `master`, or
  regenerate them only inside the Pages workflow? Latter keeps the repo
  small; former makes the SPA trivially testable from a fresh clone.
