"""Per-member performance vs SPY -> data/leaderboard.json.

For every congressional stock/ETF trade with price coverage: entry = first
close ON OR AFTER filed_date (the first day the public could have acted on
the disclosure), exit = latest close. A buy scores the ticker's excess
return over SPY across that span; a sell scores the negative (credit for
exiting what then underperformed). Members need >= MIN_TRADES scored trades
to qualify.
"""
from __future__ import annotations

import bisect
import os

from lib.common import DATA, load_json, save_json, set_status, utcnow_iso

MIN_TRADES = int(os.environ.get("CLOAKROOM_LEADERBOARD_MIN_TRADES", "5"))


class Series:
    def __init__(self, rows: list[list]):
        self.dates = [r[0] for r in rows]
        self.closes = [float(r[1]) for r in rows]

    def at_or_after(self, iso_date: str) -> tuple[str, float] | None:
        i = bisect.bisect_left(self.dates, iso_date)
        if i >= len(self.dates):
            return None
        return self.dates[i], self.closes[i]

    def last(self) -> tuple[str, float] | None:
        return (self.dates[-1], self.closes[-1]) if self.dates else None


def trade_excess(trade: dict, series: dict[str, Series]) -> dict | None:
    tick = trade.get("ticker")
    if trade["source"] != "congress" or trade["asset_type"] not in ("stock", "etf"):
        return None
    ts, spy = series.get(tick), series.get("SPY")
    if not ts or not spy:
        return None
    entry = ts.at_or_after(trade["filed_date"])
    entry_spy = spy.at_or_after(trade["filed_date"])
    exit_, exit_spy = ts.last(), spy.last()
    if not entry or not entry_spy or not exit_ or exit_[0] <= entry[0]:
        return None
    ret = exit_[1] / entry[1] - 1.0
    spy_ret = exit_spy[1] / entry_spy[1] - 1.0
    excess = (ret - spy_ret) if trade["side"] == "buy" else (spy_ret - ret)
    return {"id": trade["id"], "ticker": tick, "side": trade["side"],
            "filed_date": trade["filed_date"], "entry_date": entry[0],
            "return": round(ret, 4), "spy_return": round(spy_ret, 4),
            "excess": round(excess, 4)}


def build_leaderboard(trades: list[dict], prices: dict[str, list[list]],
                      members: list[dict]) -> list[dict]:
    series = {t: Series(rows) for t, rows in prices.items()}
    meta = {m["name"]: m for m in members}
    by_person: dict[str, list[dict]] = {}
    for t in trades:
        scored = trade_excess(t, series)
        if scored:
            by_person.setdefault(t["person"], []).append(scored | {
                "party": t["role"].get("party", ""),
                "chamber": t["role"].get("chamber", ""),
            })

    rows = []
    for person, scored in by_person.items():
        if len(scored) < MIN_TRADES:
            continue
        excesses = [s["excess"] for s in scored]
        avg = sum(excesses) / len(excesses)
        best = max(scored, key=lambda s: s["excess"])
        worst = min(scored, key=lambda s: s["excess"])
        m = meta.get(person, {})
        rows.append({
            "person": person,
            "party": scored[0]["party"] or m.get("party", ""),
            "chamber": scored[0]["chamber"] or m.get("chamber", ""),
            "state": m.get("state", ""),
            "trades_scored": len(scored),
            "avg_excess": round(avg, 4),
            "win_rate": round(sum(1 for e in excesses if e > 0) / len(excesses), 3),
            "best": {"ticker": best["ticker"], "side": best["side"], "excess": best["excess"]},
            "worst": {"ticker": worst["ticker"], "side": worst["side"], "excess": worst["excess"]},
        })
    rows.sort(key=lambda r: (-r["avg_excess"], r["person"]))
    return rows


def main() -> None:
    trades = (load_json(DATA / "trades.json", {}) or {}).get("trades", [])
    prices = (load_json(DATA / "prices.json", {}) or {}).get("series", {})
    members = (load_json(DATA / "members.json", {}) or {}).get("members", [])
    if not trades or "SPY" not in prices:
        raise RuntimeError("need trades + SPY prices for the leaderboard")
    rows = build_leaderboard(trades, prices, members)
    save_json(DATA / "leaderboard.json", {
        "generated_at": utcnow_iso(),
        "min_trades": MIN_TRADES,
        "members": rows,
    })
    set_status("leaderboard", True, f"min_trades={MIN_TRADES}", count=len(rows))
    print(f"[leaderboard] {len(rows)} qualifying members")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("leaderboard", main)
