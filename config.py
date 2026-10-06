# IST-20 configuration — single place to tune behaviour without touching logic.
# Principle: simplest to maintain, secure by default, no rewrite needed later.

UNIVERSE_SIZE = 20

# Always shown in the dashboard and reports, even outside the top N
# (CoinGecko IDs). Add more here, no code change needed.
EXTRA_IDS = ("bittensor",)  # TAO

# CoinGecko IDs treated as stablecoins / wrapped-fiat and excluded from the universe.
# Add new IDs here (e.g. "paypal-usd") — no logic change required.
STABLE_IDS = frozenset({
    "tether",           # USDT
    "usd-coin",         # USDC
    "dai",              # DAI
    "first-digital-usd",  # FDUSD
    "ethena-usde",      # USDE
    "paypal-usd",       # PYUSD
    "true-usd",         # TUSD
    "usdd",             # USDD
    "frax",             # FRAX
    "lusd",             # LUSD
    "susds",            # sUSDS
    "usds",             # USDS (Sky)
    "world-liberty-financial-usd",  # USD1
})

# Wrapped / staked / liquid-staking representations excluded for a clean L1/L2 signal.
# Set to empty frozenset() to include them.
DERIVATIVE_IDS = frozenset({
    "wrapped-bitcoin",      # WBTC
    "wrapped-steth",        # wstETH
    "staked-ether",         # stETH
    "wrapped-eeth",         # weETH
    "seth2",                # sETH
    "coinbase-wrapped-btc", # cbBTC
})

# 100-point rubric weights. Must sum to 100.
RUBRIC_WEIGHTS = {
    "tokenomics": 20,
    "traction": 20,
    "team": 15,
    "moat": 15,
    "market": 10,
    "risk_setup": 20,
}

# Verdict bands: (minimum score, rating). Evaluated top-down.
VERDICT_BANDS = (
    (80, "STRONG BUY"),
    (60, "LEAN BULLISH"),
    (40, "NEUTRAL"),
    (20, "LEAN BEARISH"),
    (0, "AVOID"),
)

# A critical red flag caps the verdict here regardless of score.
CRITICAL_FLAG_CAP = "NEUTRAL"
CRITICAL_FLAG_CAP_SCORE = 39

# Max penalty points deducted for red flags.
MAX_RED_FLAG_PENALTY = 30

# CoinGecko free API (no key needed).
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT_S = 20
MAX_RETRIES = 4
RETRY_BACKOFF_S = 5  # multiplied by attempt number

# Cache: avoids burning free-tier rate limits on re-runs.
CACHE_TTL_S = 15 * 60

# HTTP identification (polite + debuggable).
USER_AGENT = "ist20-research/1.0 (+https://github.com/affaan-m/everything-claude-code)"

# Files / dirs (relative to project root).
DATA_DIR = "data"
SNAPSHOT_DIR = "data/snapshots"
LATEST_POINTER = "data/latest.json"
REPORT_DIR = "reports"
SUMMARY_FILE = "reports/SUMMARY.md"
PROMPT_FILE = "PROMPT_V3.md"
