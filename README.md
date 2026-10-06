# IST-20 — Top 20 (ex-stablecoins) Token Research Program

Windows PC program. Two ways to use it:

## Option A — Desktop dashboard (recommended)

Double-click **`IST-20 Desktop.bat`** — a window opens:

- **Left:** 20 coins ranked by rise probability % (click any coin)
- **7-day live chart** per coin (green up / red down)
- **Rise probability %** — heuristic gauge (24h momentum + 7d trend +
  supply solidity + daily-news penalty) with plain-English drivers
- **Risks panel** — HIGH/MED/LOW with headlines, unlock pressure, volatility
- **Refresh button** — re-fetches live; loads in background; works offline
  from cache

The % is a heuristic gauge, not a prediction model — the driver bullets
show its work. Research scores (100-pt rubric) shown per coin.

## Option B — Reports (CLI)

1. Double-click **`run.bat`** — installs deps, refreshes everything.
2. Read `reports/SUMMARY.md` (ranked table) + `reports/<coin>.md`.
3. Paste a report + `PROMPT_V3.md` into an AI with web access to fill
   the qualitative sections (team, moat, lawsuits — marked N/A).

## Update (it's updateable)

- **Daily refresh:** run `run.bat` again (or `python run.py`). Universe
  re-fetched, snapshots versioned in `data/snapshots/`, `data/latest.json`
  points at the newest, reports overwritten in place. No duplicates.
- **Re-score without network:** `python run.py --no-fetch`
- **Skip news (faster):** `python run.py --no-news`
- **One coin (saves rate limits):** `python run.py --coin bitcoin`

## Tuning (no code changes)

All in `config.py`: `UNIVERSE_SIZE`, `STABLE_IDS` / `DERIVATIVE_IDS`
denylists, `RUBRIC_WEIGHTS`, `VERDICT_BANDS`, `CACHE_TTL_S`.

## Daily-news risk gate

Before scoring, each coin is scanned against CoinDesk / Cointelegraph /
Decrypt RSS. Adverse hits add to the red-flag penalty (capped); critical
keywords (rug, fraud, bankrupt, depeg...) cap the verdict at NEUTRAL.
Cache: 6h. Offline/feeds down -> scan degrades to zero penalty, never
crashes the run.

## Tests

`python -m unittest discover -s tests -v` (stdlib only, HTTP mocked).

## Disclaimer

Research tooling, not financial advice. Mechanical scores only;
validate before any decision.
