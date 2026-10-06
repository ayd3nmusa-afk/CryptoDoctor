"""IST-20 Desktop — live charts, rise probability %, risks.

Run:  python app.py   (or double-click IST-20 Desktop.bat)
Needs: requests, matplotlib (see requirements.txt).

Layout: left = coin list (ranked, color-coded), right = chart +
probability gauge + drivers + risks. Refresh button re-fetches.
All network wrapped — offline shows cached snapshot, never crashes.
"""
import os
import sys
import threading
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)  # config paths are relative; works from any launch dir

import requests
import tkinter as tk
from tkinter import ttk

import config
from run import _mechanical_inputs, with_extras
from src import coingecko, news, probability, scoring

try:
    from ist20_analysis.provider import CoinGeckoProvider
    from ist20_analysis.quick_panel import QuickAnalysisPanel
    HAS_ANALYSIS = True
except Exception as _exc:  # folder missing/broken: app still runs, no button
    print(f"Quick Analysis unavailable: {_exc}", file=sys.stderr)
    HAS_ANALYSIS = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_CHART = True
except Exception:
    HAS_CHART = False

BG, PANEL, TEXT, MUTED = "#0f1420", "#182032", "#e8edf5", "#8b95a9"
GREEN, RED, AMBER = "#22c55e", "#ef4444", "#f59e0b"

# Thread-safe UI queue: background threads post callbacks here; the Tk
# main loop drains them via _pump. This keeps refresh() working whether
# the caller runs mainloop() (real app) or pumps update() manually.
import queue as _queue


# Chart timeframes: label -> (days of CoinGecko history, candle minutes).
# CoinGecko serves 5-minute points for 1 day and hourly points for 2-90 days;
# candles are built from those price samples (wicks can be a bit shorter
# than exchange candles).
CANDLE_TFS = {"15m": (1, 15), "4h": (14, 240)}


def _fetch_prices(cid, days):
    resp = requests.get(
        f"{config.COINGECKO_BASE}/coins/{cid}/market_chart",
        params={"vs_currency": "usd", "days": days},
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json().get("prices", [])


def _to_candles(pairs, minutes):
    """[[ts_ms, price], ...] -> [(bucket_ts_ms, open, high, low, close)]."""
    step = minutes * 60 * 1000
    buckets = {}
    for ts, price in pairs:
        k = int(ts // step)
        b = buckets.get(k)
        if b is None:
            buckets[k] = [price, price, price, price]
        else:
            b[1] = max(b[1], price)
            b[2] = min(b[2], price)
            b[3] = price
    return [(k * step, *v) for k, v in sorted(buckets.items())]


def _label_color(label):
    return (GREEN if label == "LIKELY UP"
            else RED if label == "LIKELY DOWN" else AMBER)


def _fmt_price(p):
    return f"{p:,.2f}" if p >= 1 else f"{p:.4f}" if p >= 0.01 else f"{p:.8f}"


def _verdict_color(rating):
    return {"STRONG BUY": GREEN, "LEAN BULLISH": GREEN, "NEUTRAL": AMBER,
            "LEAN BEARISH": RED, "AVOID": RED}.get(rating, MUTED)


def _load_data(status_cb, use_cache=True):
    """Fetch snapshot + news + charts. Returns list of enriched rows.

    Rate-limit safe: a 429 (or any fetch failure) falls back to the cached
    snapshot instead of raising — the window always opens with data.
    """
    def _safe_status(text):
        try:
            status_cb(text)
        except Exception:
            pass

    try:
        raw = coingecko.get_top_markets(per_page=100, use_cache=use_cache)
    except Exception:
        return _load_data_offline(_safe_status)
    universe = coingecko.filter_universe(raw, config.UNIVERSE_SIZE)
    universe = with_extras(universe, raw)
    snap = coingecko.build_snapshot(universe)
    coingecko.save_snapshot(snap, config.SNAPSHOT_DIR, config.LATEST_POINTER)
    as_of = snap["as_of_utc"]
    rows = []
    for coin in universe:
        cid = coin.get("id")
        try:
            risk = news.check_coin(cid, coin.get("name"), coin.get("symbol"))
        except Exception:
            risk = {"hits": [], "hit_count": 0, "news_penalty": 0,
                    "news_critical": False}
        try:
            days, bucket, label, ttl = probability.CHART_RANGES["7d"]
            chart = coingecko.get_market_chart(cid, days=days,
                                               use_cache=use_cache, ttl_s=ttl)
            raw_pairs = (chart or {}).get("prices", [])
            spark = probability.bucketize(raw_pairs, bucket)
            charts = {"7d": spark}
        except Exception:
            spark, charts = [], {}
        pct, label, drivers = probability.rise_probability(
            coin, spark, risk, range_label="7-day")
        rating, final = scoring.rate(_mechanical_inputs(coin, risk))
        risks = probability.build_risks(
            coin, risk, scoring.unlock_pressure_90d(coin))
        rows.append({"coin": coin, "spark": spark, "charts": charts,
                     "range": "7d", "pct": pct, "label": label,
                     "drivers": drivers, "rating": rating, "final": final,
                     "risks": risks, "risk": risk})
    rows.sort(key=lambda r: r["pct"], reverse=True)
    return rows, as_of


def _load_data_offline(status_cb):
    """Fallback path: cached snapshot only, no network at all."""
    snap = coingecko.load_latest(config.LATEST_POINTER)
    if snap is None:
        raise RuntimeError("Offline and no cached snapshot available.")
    try:
        status_cb("Offline — showing cached snapshot")
    except Exception:
        pass
    rows = []
    for coin in snap["coins"]:
        cid = coin.get("id")
        risk = {"hits": [], "hit_count": 0, "news_penalty": 0,
                "news_critical": False, "offline": True}
        spark = []
        try:
            chart = coingecko.get_market_chart(cid, use_cache=True)
            spark = probability.extract_prices(chart)
        except Exception:
            pass
        pct, label, drivers = probability.rise_probability(coin, spark, risk)
        drivers = ["OFFLINE — cached prices; news gate skipped"] + drivers
        rating, final = scoring.rate(_mechanical_inputs(coin, risk))
        risks = probability.build_risks(
            coin, risk, scoring.unlock_pressure_90d(coin))
        rows.append({"coin": coin, "spark": spark, "pct": pct, "label": label,
                     "drivers": drivers, "rating": rating, "final": final,
                     "risks": risks, "risk": risk})
    rows.sort(key=lambda r: r["pct"], reverse=True)
    return rows, snap["as_of_utc"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IST-20 — Top 20 ex-stablecoins + extras (live)")
        self.geometry("1180x720")
        self.configure(bg=BG)
        self.rows, self.as_of = [], ""
        self._ui_queue = _queue.Queue()
        self._busy = False
        self._candles = {}
        self._draw_token = 0
        self.tf = tk.StringVar(value="7D")
        self._build()
        self._pump()
        self.refresh(fresh=False)

    def _pump(self):
        """Drain thread-posted UI callbacks — runs inside the Tk main loop."""
        try:
            while True:
                callback = self._ui_queue.get_nowait()
                try:
                    callback()
                except Exception as exc:  # one bad callback must not kill the pump
                    print(f"UI callback failed: {exc}", file=sys.stderr)
        except _queue.Empty:
            pass
        self.after(100, self._pump)

    def _post(self, callback):
        """Thread-safe: background threads schedule UI work through here."""
        self._ui_queue.put(callback)

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="IST-20 DASHBOARD", fg=TEXT, bg=BG,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        self.status = tk.Label(top, text="loading…", fg=MUTED, bg=BG,
                               font=("Segoe UI", 10))
        self.status.pack(side="left", padx=12)
        self.refresh_btn = tk.Button(
            top, text="Refresh", command=lambda: self.refresh(True),
            bg=PANEL, fg=TEXT, relief="flat", padx=12, pady=4,
            cursor="hand2")
        self.refresh_btn.pack(side="right")
        if HAS_ANALYSIS:
            tk.Button(
                top, text="Quick Analysis", command=self._open_analysis,
                bg=PANEL, fg=TEXT, relief="flat", padx=12, pady=4,
                cursor="hand2").pack(side="right", padx=(0, 8))
        tk.Label(top, text="Not financial advice", fg=MUTED, bg=BG,
                 font=("Segoe UI", 9, "italic")).pack(side="right", padx=10)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=6)

        left = tk.Frame(body, bg=PANEL, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        tk.Label(left, text="TOP 20 + EXTRAS (by rise %)", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(pady=(8, 2))
        self.coin_list = tk.Listbox(left, bg=PANEL, fg=TEXT, relief="flat",
                                    font=("Consolas", 11), activestyle="none",
                                    highlightthickness=0)
        self.coin_list.pack(fill="both", expand=True, padx=8, pady=4)
        self.coin_list.bind("<<ListboxSelect>>", lambda _e: self._show())

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        head = tk.Frame(right, bg=PANEL)
        head.pack(fill="x", pady=(0, 8))
        self.name = tk.Label(head, text="—", fg=TEXT, bg=PANEL,
                             font=("Segoe UI", 15, "bold"))
        self.name.pack(side="left", padx=12, pady=8)
        self.price = tk.Label(head, text="", fg=MUTED, bg=PANEL,
                              font=("Segoe UI", 12))
        self.price.pack(side="left")
        self.badge = tk.Label(head, text="", bg=PANEL, fg="white",
                              font=("Segoe UI", 11, "bold"), padx=10)
        self.badge.pack(side="right", padx=12)

        chart_box = tk.Frame(right, bg=PANEL)
        chart_box.pack(fill="both", expand=True, pady=(0, 8))
        bar = tk.Frame(chart_box, bg=PANEL)
        bar.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(bar, text="LIVE CHART", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        for tf in ("4h", "15m", "7D"):  # packed right-to-left
            tk.Radiobutton(bar, text=tf, value=tf, variable=self.tf,
                           indicatoron=0, command=self._show_chart,
                           bg=PANEL, fg=TEXT, selectcolor="#2a3550",
                           activebackground="#2a3550", activeforeground=TEXT,
                           relief="flat", bd=0, padx=10, pady=2,
                           cursor="hand2").pack(side="right", padx=2)
        self.chart_host = tk.Frame(chart_box, bg=PANEL)
        self.chart_host.pack(fill="both", expand=True, padx=8, pady=8)

        bottom = tk.Frame(right, bg=BG)
        bottom.pack(fill="x")
        prob_box = tk.Frame(bottom, bg=PANEL, width=380)
        prob_box.pack(side="left", fill="y", padx=(0, 8))
        prob_box.pack_propagate(False)
        tk.Label(prob_box, text="RISE PROBABILITY", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12,
                                                     pady=(8, 0))
        self.pct = tk.Label(prob_box, text="—", fg=GREEN, bg=PANEL,
                            font=("Segoe UI", 34, "bold"))
        self.pct.pack(anchor="w", padx=12)
        self.drivers = tk.Label(prob_box, text="", fg=TEXT, bg=PANEL,
                                font=("Segoe UI", 9), justify="left",
                                wraplength=340)
        self.drivers.pack(anchor="w", padx=12, pady=(0, 8))

        risk_box = tk.Frame(bottom, bg=PANEL)
        risk_box.pack(side="left", fill="both", expand=True)
        tk.Label(risk_box, text="RISKS", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12,
                                                     pady=(8, 0))
        self.risk_list = tk.Label(risk_box, text="", fg=TEXT, bg=PANEL,
                                  font=("Segoe UI", 10), justify="left",
                                  anchor="nw", wraplength=640)
        self.risk_list.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def _open_analysis(self):
        """Open (or bring to front) the Quick Analysis window."""
        win = getattr(self, "_analysis_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            win.focus_force()
            return
        if getattr(self, "_analysis_provider", None) is None:
            self._analysis_provider = CoinGeckoProvider()
        win = tk.Toplevel(self)
        win.title("IST-20 — Quick Analysis")
        win.geometry("1100x720")
        win.configure(bg=BG)
        QuickAnalysisPanel(win, self._analysis_provider).pack(
            fill="both", expand=True)
        self._analysis_win = win

    def refresh(self, fresh):
        if self._busy:
            return
        self._busy = True
        self.refresh_btn.config(state="disabled")
        self.status.config(text="fetching live data… (can take a minute)")

        def _work():
            try:
                rows, as_of = _load_data(lambda t: self._post(
                    lambda: self.status.config(text=t)),
                    use_cache=not fresh)
                self._post(lambda: self._done(rows, as_of, None))
            except Exception as exc:
                msg = str(exc)  # `exc` is unbound once this block ends
                self._post(lambda: self._done([], "", msg))

        threading.Thread(target=_work, daemon=True).start()

    def _done(self, rows, as_of, error):
        self._busy = False
        self.refresh_btn.config(state="normal")
        self._candles.clear()
        if error:
            self.status.config(text=f"Error: {error}")
            return
        self.rows, self.as_of = rows, as_of
        self.status.config(text=f"as of {as_of} UTC - {len(rows)} coins")
        self.coin_list.delete(0, "end")
        for r in rows:
            c = r["coin"]
            sym = str(c.get("symbol", "?")).upper()
            self.coin_list.insert(
                "end",
                f"{r['pct']:5.1f}%  {sym:<7} {str(c.get('name', '?'))[:18]}")
            self.coin_list.itemconfig("end", fg=_label_color(r["label"]))
        if rows:
            self.coin_list.selection_set(0)
            self._show()

    def _show(self):
        sel = self.coin_list.curselection()
        if not sel or not self.rows:
            return
        r = self.rows[sel[0]]
        c = r["coin"]
        self.name.config(
            text=f"{c.get('name')} ({str(c.get('symbol', '')).upper()})")
        try:
            price = float(c.get("current_price") or 0)
            chg = float(c.get("price_change_percentage_24h") or 0)
            self.price.config(
                text=f"${_fmt_price(price)}  ({chg:+.1f}% 24h)  -  "
                     f"research {r['final']}/100 {r['rating']}")
        except (TypeError, ValueError):
            self.price.config(text="")
        color = _label_color(r["label"])
        self.badge.config(text=f" {r['pct']:.1f}% {r['label']} ", bg=color)
        self.pct.config(text=f"{r['pct']:.1f}%", fg=color)
        self.drivers.config(text="\n".join(f"- {d}" for d in r["drivers"]))
        sev_icon = {"HIGH": "[!!]", "MED": "[!]", "LOW": "[ok]"}
        self.risk_list.config(text="\n".join(
            f"{sev_icon.get(s, '-')} [{s}] {t}" for s, t in r["risks"]))
        self._show_chart()

    def _message(self, text):
        for w in self.chart_host.winfo_children():
            w.destroy()
        tk.Label(self.chart_host, text=text, fg=MUTED, bg=PANEL).pack(pady=40)

    def _show_chart(self):
        sel = self.coin_list.curselection()
        if not sel or not self.rows:
            return
        r = self.rows[sel[0]]
        tf = self.tf.get()
        self._draw_token += 1
        token = self._draw_token
        if tf == "7D":
            self._draw(r)
            return
        cid = r["coin"].get("id")
        cached = self._candles.get((cid, tf))
        if cached:
            self._draw_candles(r, cached, tf)
            return
        self._message("loading candles…")
        days, minutes = CANDLE_TFS[tf]

        def _work():
            try:
                candles = _to_candles(_fetch_prices(cid, days), minutes)
            except Exception:
                candles = None

            def _apply():
                if token != self._draw_token:
                    return  # user already switched coin or timeframe
                if not candles:
                    self._message("candles unavailable (rate limit or "
                                  "offline) - try again in a minute")
                    return
                self._candles[(cid, tf)] = candles
                self._draw_candles(r, candles, tf)
            self._post(_apply)

        threading.Thread(target=_work, daemon=True).start()

    def _draw_candles(self, r, candles, tf):
        if not HAS_CHART:
            self._message("chart unavailable (matplotlib missing)")
            return
        for w in self.chart_host.winfo_children():
            w.destroy()
        fig = Figure(figsize=(7, 2.6), dpi=100, facecolor=PANEL)
        ax = fig.add_subplot(111, facecolor=PANEL)
        for x, (_t, o, hi, lo, c) in enumerate(candles):
            col = GREEN if c >= o else RED
            ax.vlines(x, lo, hi, color=col, linewidth=1)
            body = abs(c - o) or (hi - lo) * 0.02 or hi * 1e-4
            ax.bar(x, body, bottom=min(o, c), width=0.7, color=col)
        n = len(candles)
        idx = list(range(0, n, max(1, n // 6)))
        ax.set_xticks(idx)
        ax.set_xticklabels([
            datetime.fromtimestamp(candles[i][0] / 1000, tz=timezone.utc)
            .strftime("%d %b %H:%M") for i in idx])
        ax.set_xlim(-1, n)
        ax.tick_params(colors=MUTED, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#2a3550")
        span = "last 24h" if tf == "15m" else "last 14 days"
        ax.set_title(f"{r['coin'].get('name')} - {tf} candles, {span} "
                     f"(USD, UTC)", color=MUTED, fontsize=9)
        fig.tight_layout()
        FigureCanvasTkAgg(fig, master=self.chart_host).get_tk_widget().pack(
            fill="both", expand=True)

    def _draw(self, r):
        for w in self.chart_host.winfo_children():
            w.destroy()
        spark = r["spark"]
        c = r["coin"]
        if not HAS_CHART or len(spark) < 3:
            tk.Label(self.chart_host, text="chart unavailable (offline?)",
                     fg=MUTED, bg=PANEL).pack(pady=40)
            return
        color = GREEN if spark[-1] >= spark[0] else RED
        fig = Figure(figsize=(7, 2.6), dpi=100, facecolor=PANEL)
        ax = fig.add_subplot(111, facecolor=PANEL)
        ax.plot(spark, color=color, linewidth=1.8)
        ax.fill_between(range(len(spark)), spark, alpha=0.15, color=color)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_xticks([0, len(spark) - 1])
        ax.set_xticklabels(["7d ago", "now"])
        for spine in ax.spines.values():
            spine.set_color("#2a3550")
        ax.set_title(f"{c.get('name')} - 7d (USD)", color=MUTED, fontsize=9)
        fig.tight_layout()
        FigureCanvasTkAgg(fig, master=self.chart_host).get_tk_widget().pack(
            fill="both", expand=True)


if __name__ == "__main__":
    App().mainloop()
