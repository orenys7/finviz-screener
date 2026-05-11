# finviz-screener

Scheduled momentum stock screener. Scrapes Finviz, scores charts with Claude, and posts new high-score tickers to Discord.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Install

```bash
uv sync
uv run playwright install chromium
cp .env.example .env   # fill in ANTHROPIC_API_KEY and DISCORD_WEBHOOK_URL
```

## Run

```bash
uv run python -m finviz_screener scan
uv run python -m finviz_screener scan --dry-run        # skip Discord
uv run python -m finviz_screener scan --screener NAME  # single screener
```

## Configure

### Adding a screener

Add an entry under `screeners:` in `config.yaml`. Each entry needs a `name` (used in Discord messages and `--screener` filter) and a `url` (the full Finviz screener URL):

```yaml
screeners:
  - name: my-filter
    url: "https://finviz.com/screener.ashx?v=111&f=cap_midover,ta_highlow52w_nh"
```

Build the URL using Finviz's screener UI, then copy it from the browser's address bar.

### Tuning thresholds

| Setting | Default | Effect |
|---|---|---|
| `score_threshold` | `8` | Minimum Claude score (1–10) to count as a hit. Lower = more alerts, higher = fewer but stronger signals. |
| `lookback_runs` | `6` | Number of past runs to check before calling a ticker "new". At 3 runs/day this covers ~2 days. |

### Inspecting the database

```bash
# Open the database
sqlite3 state.db

-- Last 10 runs
SELECT id, started_at, status, finished_at FROM runs ORDER BY id DESC LIMIT 10;

-- Signals from the latest run
SELECT ticker, screener, score, analysis
FROM signals WHERE run_id = (SELECT MAX(id) FROM runs)
ORDER BY score DESC;

-- All-time high scorers
SELECT ticker, MAX(score) as best, COUNT(*) as appearances
FROM signals GROUP BY ticker ORDER BY best DESC LIMIT 20;
```

## Secrets

Set these as environment variables locally (`.env`) or as GitHub Actions repository secrets for CI.

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key (Claude) |
| `DISCORD_WEBHOOK_URL` | No | Discord incoming webhook URL — omit to skip notifications |

To add secrets in GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

## Scheduled runs (GitHub Actions)

The workflow at `.github/workflows/scan.yml` runs automatically at **13:00, 17:00, and 21:00 UTC on weekdays** (Mon–Fri), covering pre-open, mid-session, and after-close windows in US Eastern time.

You can also trigger a run manually from the **Actions** tab using **Run workflow**.

After each scan the workflow commits `state.db` back to `master` with a `[skip ci]` message so history accumulates without triggering another scan.
