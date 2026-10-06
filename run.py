"""IST-20 runner. Updateable: every run refreshes the universe.

Usage:
    python run.py                 # full refresh (fetch + news + score)
    python run.py --no-fetch      # re-score cached snapshot (no network)
    python run.py --no-news       # skip daily-news scan (faster)
    python run.py --coin bitcoin  # single-coin refresh (saves rate limits)

Pipeline: fetch -> filter stables -> snapshot -> NEWS SCAN -> score.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src import coingecko, news, report, scoring


def with_extras(universe, raw):
    """Append config.EXTRA_IDS (e.g. Bittensor/TAO) when outside the top N."""
    have = {c.get("id") for c in universe}
    missing = [i for i in config.EXTRA_IDS if i not in have]
    if not missing:
        return universe
    by_id = {c.get("id"): c for c in raw}
    out = list(universe)
    still = []
    for cid in missing:
        if cid in by_id:
            out.append(by_id[cid])
        else:
            still.append(cid)
    if still:  # not in the top-100 list: ask CoinGecko for them directly
        try:
            import requests
            resp = requests.get(
                f"{config.COINGECKO_BASE}/coins/markets",
                params={"vs_currency": "usd", "ids": ",".join(still),
                        "price_change_percentage": "1h,24h,7d"},
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            out.extend(resp.json())
        except Exception:
            pass  # extras are best-effort; never break the main run
    return out


def _mechanical_inputs(coin, risk):
    """Baseline from live quant. Qualitative parts default to neutral
    midpoints — never invented highs. News penalty feeds the deduction."""
    circulating = coin.get("circulating_supply") or 0
    total = coin.get("total_supply") or coin.get("max_supply") or 0
    ratio = (circulating / total) if total else 0.5
    tokenomics = round(config.RUBRIC_WEIGHTS["tokenomics"] *
                       max(0.0, min(1.0, ratio)), 2)
    change = coin.get("price_change_percentage_24h") or 0
    momentum = max(0.0, min(1.0, 0.5 + float(change) / 20.0))
    risk_setup = round(config.RUBRIC_WEIGHTS["risk_setup"] * momentum, 2)
    return {"tokenomics": tokenomics, "traction": 10.0, "team": 7.5,
            "moat": 7.5, "market": 5.0, "risk_setup": risk_setup,
            "red_flag_penalty": risk.get("news_penalty", 0),
            "critical_flag": bool(risk.get("news_critical", False))}


def _scan_news(coins, no_news):
    """DAILY-NEWS risk gate. Runs BEFORE scoring. Returns {coin_id: risk}."""
    if no_news:
        print("Skipping daily-news scan (--no-news).")
        return {c.get("id"): {"hits": [], "hit_count": 0, "news_penalty": 0,
                              "news_critical": False, "skipped": True}
                for c in coins}
    print("Scanning daily news (risk gate before scoring)...")
    news_cache = os.path.join(config.DATA_DIR, ".cache")
    os.makedirs(news_cache, exist_ok=True)
    cache_file = news.cache_path(news_cache)
    cached = None
    if news.is_fresh(cache_file):
        with open(cache_file, encoding="utf-8") as fh:
            cached = json.load(fh)
        print("  using fresh news cache (<6h).")
    risks = {}
    for coin in coins:
        cid = coin.get("id")
        if cached and cid in cached:
            risks[cid] = cached[cid]
            continue
        risks[cid] = news.check_coin(cid, coin.get("name"),
                                     coin.get("symbol")) or {
            "coin": cid, "hits": [], "hit_count": 0,
            "news_penalty": 0, "news_critical": False}
        if risks[cid].get("news_critical"):
            print(f"  !! {cid}: CRITICAL news flag")
    with open(cache_file, "w", encoding="utf-8") as fh:
        json.dump(risks, fh, indent=2)
    flagged = sum(1 for r in risks.values() if r["hit_count"])
    print(f"  {flagged}/{len(coins)} coins with adverse news hits.")
    return risks


def run(args):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)
    os.makedirs(config.REPORT_DIR, exist_ok=True)

    if args.no_fetch:
        snapshot = coingecko.load_latest(config.LATEST_POINTER)
        if snapshot is None:
            print("No cached snapshot. Run without --no-fetch first.")
            return 1
        print(f"Re-scoring cached snapshot ({snapshot['as_of_utc']}).")
    else:
        raw = coingecko.get_top_markets(per_page=100)
        universe = coingecko.filter_universe(raw, config.UNIVERSE_SIZE)
        universe = with_extras(universe, raw)
        snapshot = coingecko.build_snapshot(universe)
        coingecko.save_snapshot(snapshot, config.SNAPSHOT_DIR,
                                config.LATEST_POINTER)
        print(f"Fetched {len(universe)} coins @ {snapshot['as_of_utc']}.")

    coins = snapshot["coins"]
    if args.coin:
        coins = [c for c in coins if c.get("id") == args.coin] or coins[:1]

    risks = _scan_news(coins, args.no_news)

    rows = []
    for coin in coins:
        cid = coin.get("id")
        risk = risks.get(cid, {"news_penalty": 0, "news_critical": False,
                               "hits": [], "hit_count": 0})
        rating, final = scoring.rate(_mechanical_inputs(coin, risk))
        md = report.render_token_report(coin, rating, final,
                                        snapshot["as_of_utc"], news=risk)
        with open(os.path.join(config.REPORT_DIR, f"{cid}.md"),
                  "w", encoding="utf-8") as fh:
            fh.write(md)
        top_risk = (risk["hits"][0]["title"][:80] if risk.get("hits")
                    else "N/A (needs AI pass)")
        rows.append({"id": cid, "name": coin.get("name", cid),
                     "current_price": coin.get("current_price"),
                     "market_cap": coin.get("market_cap"), "final": final,
                     "rating": rating, "top_risk": top_risk})

    with open(config.SUMMARY_FILE, "w", encoding="utf-8") as fh:
        fh.write(report.render_summary(rows, snapshot["as_of_utc"]))
    print(f"Wrote {len(rows)} reports + SUMMARY.md @ {snapshot['as_of_utc']}.")
    print("Next: paste reports/*.md + PROMPT_V3.md into an AI with web "
          "access to fill qualitative sections.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="IST-20 top-20 researcher")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--no-news", action="store_true")
    parser.add_argument("--coin", default=None)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
