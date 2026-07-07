"""Source D: EOD price history for every traded ticker + SPY.

Primary: stooq.com free CSV endpoint. Stooq sometimes fronts a JavaScript
anti-bot challenge (headless clients get HTML instead of CSV); after a few
consecutive non-CSV responses we trip a circuit breaker and finish the rest
of the list with yfinance in batches. Tickers that fail everywhere keep
their last-good committed series.

Writes data/prices.json: {"series": {"SPY": [["2026-01-02", 589.31], ...]}}.
"""
from __future__ import annotations

import io
import os
import time

from lib.common import (
    DATA, http_session, iso, load_json, polite_get, save_json, set_status,
    utcnow_iso, window_start,
)

HISTORY_DAYS = int(os.environ.get("CLOAKROOM_PRICE_DAYS", "120"))
# calendar-day fetch span that comfortably covers HISTORY_DAYS trading days
SPAN_DAYS = int(HISTORY_DAYS * 1.55) + 14
MAX_TICKERS = int(os.environ.get("CLOAKROOM_PRICE_MAX_TICKERS", "500"))
STOOQ_URL = "https://stooq.com/q/d/l/?s={sym}&d1={d1}&d2={d2}&i=d"


def parse_stooq_csv(text: str) -> list[list] | None:
    """CSV -> [[iso_date, close], ...]; None when the response is not CSV
    (bot challenge, 'Exceeded the daily hits limit', 'No data')."""
    if not text or text.lstrip().startswith("<"):
        return None
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines or not lines[0].lower().startswith("date,"):
        return None
    out = []
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) < 5:
            continue
        try:
            out.append([parts[0], round(float(parts[4]), 4)])
        except ValueError:
            continue
    return out or None


def fetch_stooq(s, ticker: str, d1: str, d2: str) -> list[list] | None:
    sym = ticker.lower().replace(".", "-") + ".us"
    r = polite_get(s, STOOQ_URL.format(sym=sym, d1=d1, d2=d2), timeout=(10, 30))
    if r.status_code != 200:
        return None
    return parse_stooq_csv(r.text)


def fetch_yfinance(tickers: list[str], start_iso: str) -> dict[str, list[list]]:
    import pandas as pd  # noqa: F401 - yfinance returns DataFrames
    import yfinance as yf

    out: dict[str, list[list]] = {}
    for i in range(0, len(tickers), 50):
        chunk = tickers[i:i + 50]
        try:
            df = yf.download(chunk, start=start_iso, interval="1d",
                             group_by="ticker", auto_adjust=True,
                             progress=False, threads=True)
        except Exception as e:  # noqa: BLE001 - a bad chunk should not sink the rest
            print(f"[prices] yfinance chunk failed: {e}")
            continue
        if df is None or df.empty:
            continue
        for t in chunk:
            try:
                closes = df[t]["Close"] if len(chunk) > 1 else df["Close"]
            except KeyError:
                continue
            closes = closes.dropna()
            if closes.empty:
                continue
            out[t] = [[d.strftime("%Y-%m-%d"), round(float(v), 4)]
                      for d, v in closes.items()]
        time.sleep(1.0)
    return out


def main() -> None:
    trades = (load_json(DATA / "trades.json", {}) or {}).get("trades", [])
    latest: dict[str, str] = {}
    for t in trades:
        if t.get("ticker"):
            latest[t["ticker"]] = max(latest.get(t["ticker"], ""), t.get("filed_date") or "")
    # cap by disclosure recency, not alphabet, so the freshest names keep coverage
    tickers = sorted(latest, key=lambda k: (latest[k], k), reverse=True)
    if len(tickers) > MAX_TICKERS:
        print(f"[prices] capping {len(tickers)} tickers to {MAX_TICKERS} by recency")
        tickers = tickers[:MAX_TICKERS]
    tickers = ["SPY"] + [t for t in tickers if t != "SPY"]

    old = (load_json(DATA / "prices.json", {}) or {}).get("series", {})
    start = window_start(SPAN_DAYS)
    d1, d2 = start.strftime("%Y%m%d"), window_start(0).strftime("%Y%m%d")

    series: dict[str, list[list]] = {}
    misses: list[str] = []
    s = http_session(rps=3.0)
    stooq_dead = 0
    for t in tickers:
        if stooq_dead >= 3:
            misses.append(t)
            continue
        got = fetch_stooq(s, t, d1, d2)
        if got:
            series[t] = got
            stooq_dead = 0
        else:
            misses.append(t)
            stooq_dead += 1
    if stooq_dead >= 3:
        print(f"[prices] stooq circuit-breaker tripped; {len(misses)} tickers -> yfinance")

    if misses:
        series.update(fetch_yfinance(misses, iso(start)))

    kept_old = 0
    for t in tickers:
        if t not in series and t in old:
            series[t] = old[t]
            kept_old += 1

    if "SPY" not in series or len(series) < max(1, len(tickers) // 4):
        raise RuntimeError(
            f"price coverage too thin ({len(series)}/{len(tickers)}) - keeping last-good")

    n_stooq = len(series) - kept_old - len([t for t in misses if t in series])
    save_json(DATA / "prices.json", {
        "generated_at": utcnow_iso(),
        "history_days": HISTORY_DAYS,
        "series": {t: series[t] for t in sorted(series)},
    })
    set_status("prices", True,
               f"stooq={max(n_stooq, 0)} yf={len([t for t in misses if t in series])} "
               f"cached={kept_old} missing={len(tickers) - len(series)}",
               count=len(series))
    print(f"[prices] wrote {len(series)}/{len(tickers)} series ({kept_old} from cache)")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("prices", main)
