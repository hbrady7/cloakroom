"""Assemble pipeline/brief_input.txt: analyst prompt + grounded dossier.

The dossier is everything the model is allowed to know: the engine's
candidates/caution lists, the full evidence trade records they reference,
and 30/90-day price context (including SPY for the regime note). Nothing
else goes in; the validator enforces that nothing else comes out.
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.common import DATA, load_json

PIPELINE = Path(__file__).resolve().parent
OUT = PIPELINE / "brief_input.txt"


def price_context(series: list[list]) -> dict | None:
    """Last close, 5d/30d change, 90d high/low - computed, not estimated."""
    if not series:
        return None
    closes = [float(r[1]) for r in series]
    dates = [r[0] for r in series]
    last = closes[-1]

    def pct(n_back: int) -> float | None:
        if len(closes) <= n_back:
            return None
        prev = closes[-1 - n_back]
        return round((last / prev - 1.0) * 100, 2) if prev else None

    win90 = closes[-63:]  # ~90 calendar days of trading sessions
    return {
        "last_close": last,
        "last_date": dates[-1],
        "chg_5d_pct": pct(5),
        "chg_30d_pct": pct(21),
        "high_90d": max(win90),
        "low_90d": min(win90),
    }


def build_payload() -> dict:
    cand = load_json(DATA / "candidates.json", {}) or {}
    trades = (load_json(DATA / "trades.json", {}) or {}).get("trades", [])
    prices = (load_json(DATA / "prices.json", {}) or {}).get("series", {})
    by_id = {t["id"]: t for t in trades}

    wanted: set[str] = set()
    tickers: set[str] = {"SPY"}
    for entry in (cand.get("candidates") or []) + (cand.get("caution") or []):
        tickers.add(entry["ticker"])
        for e in entry.get("evidence", []):
            wanted.add(e["id"])

    evidence_trades = [by_id[i] for i in sorted(wanted) if i in by_id]
    ctx = {t: price_context(prices.get(t, [])) for t in sorted(tickers)}
    return {
        "as_of": cand.get("as_of"),
        "engine": {
            "candidates": cand.get("candidates", []),
            "caution": cand.get("caution", []),
        },
        "evidence_trades": evidence_trades,
        "price_context": {t: c for t, c in ctx.items() if c},
    }


def main() -> None:
    payload = build_payload()
    if not payload["engine"]["candidates"]:
        raise RuntimeError("no candidates - run score.py first")
    prompt = (PIPELINE / "brief_prompt.md").read_text()
    OUT.write_text(prompt + "\n=== INPUT ===\n" +
                   json.dumps(payload, indent=1, ensure_ascii=False))
    n_ev = len(payload["evidence_trades"])
    print(f"[brief-input] {len(payload['engine']['candidates'])} candidates, "
          f"{n_ev} evidence trades, {len(payload['price_context'])} price series "
          f"-> {OUT.name} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
