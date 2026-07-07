"""Deterministic signal engine: data/trades.json -> data/candidates.json.

Pure functions, no network, no LLM, no wall clock: everything derives from
the input JSON plus an as_of date taken from the data itself (max filed_date),
so the same inputs always produce byte-identical output.

Signals and weights (see /methodology on the site):
  convergence   0-35  congress buys + >=2 distinct non-10b5-1 insider buyers, 45d
  cluster       0-30  >=3 distinct members buying the same ticker in any 30d window
  committee     0-20  buyers sit on committees overseeing the ticker's sector
  options       0-15  a disclosed congressional option position = leveraged conviction
  size          0-10  log-scale on band midpoints
All components are multiplied by exponential staleness decay on information
age (as_of - tx_date, half-life 14 days) before summing; the sum is capped
at 100.

Caution list mirrors the negative side: sell clusters and insider
distribution (multiple officer sales), 10b5-1 sales half-weighted.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from lib.common import DATA, load_json, parse_date, save_json, set_status, utcnow_iso

HALF_LIFE_DAYS = 14.0
CLUSTER_WINDOW_DAYS = 30
CONVERGENCE_WINDOW_DAYS = 45
TOP_CANDIDATES = 15
TOP_CAUTION = 5
MAX_EVIDENCE = 24

# broad-market index ETFs make meaningless "picks"; sector ETFs stay eligible
BROAD_ETFS = {"SPY", "VOO", "VTI", "IVV", "QQQ", "QQQM", "DIA", "IWM", "AGG",
              "BND", "SCHD", "VYM", "VUG", "VTV", "VEA", "VWO", "EFA", "VXUS",
              "SPLG", "RSP", "VIG", "VOOG", "IEFA", "IEMG", "BSV", "TLT"}


def decay(as_of: date, tx: date | None) -> float:
    """Exponential staleness decay on information age."""
    if not tx:
        return 0.0
    age = max(0, (as_of - tx).days)
    return 0.5 ** (age / HALF_LIFE_DAYS)


def size_factor(amount_low: float, amount_high: float) -> float:
    """Log-scale factor on the band midpoint: $1k->1, $100k->3, $10M->5."""
    mid = max(1000.0, (float(amount_low) + float(amount_high)) / 2.0)
    return 1.0 + math.log10(mid / 1000.0)


def best_cluster(txs: list[dict], window_days: int = CLUSTER_WINDOW_DAYS) -> list[dict]:
    """Largest set of trades by distinct persons inside one sliding window."""
    dated = sorted((t for t in txs if t.get("_tx")), key=lambda t: t["_tx"])
    best: list[dict] = []
    for i, anchor in enumerate(dated):
        end = anchor["_tx"] + timedelta(days=window_days)
        span = [t for t in dated[i:] if t["_tx"] <= end]
        if len({t["person"] for t in span}) > len({t["person"] for t in best}):
            best = span
    return best


def _prep(trades: list[dict]) -> list[dict]:
    out = []
    for t in trades:
        t = dict(t)
        t["_tx"] = parse_date(t.get("tx_date"))
        t["_filed"] = parse_date(t.get("filed_date"))
        out.append(t)
    return out


def _member_sectors(members: list[dict]) -> dict[str, list[str]]:
    return {m["name"]: m.get("sectors", []) for m in members}


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def score_ticker(ticker: str, txs: list[dict], as_of: date,
                 person_sectors: dict[str, list[str]],
                 ticker_sectors: list[str]) -> dict | None:
    """Score one ticker's long case. Returns None if there is nothing to score."""
    c_buys = [t for t in txs if t["source"] == "congress" and t["side"] == "buy"
              and t["asset_type"] in ("stock", "option", "etf")]
    if not c_buys:
        return None
    i_buys = [t for t in txs if t["source"] == "insider" and t["side"] == "buy"
              and not t.get("planned_10b5_1")]

    signals: dict[str, dict] = {}
    evidence: list[dict] = []

    # --- cluster buys (0-30)
    cluster = best_cluster(c_buys)
    buyers = {t["person"] for t in cluster}
    pts = 0.0
    if len(buyers) >= 3:
        base = 18.0 + min(12.0, (len(buyers) - 3) * 4.0)
        pts = base * _mean([decay(as_of, t["_tx"]) for t in cluster])
        evidence += [{"id": t["id"], "signal": "cluster"} for t in cluster]
    signals["cluster"] = {"fired": len(buyers) >= 3, "points": round(pts, 1),
                          "distinct_buyers": len(buyers)}
    total = pts

    # --- committee alignment (0-20)
    aligned = [t for t in c_buys
               if set(person_sectors.get(t["person"], [])) & set(ticker_sectors)]
    aligned_people = {t["person"] for t in aligned}
    pts = 0.0
    if aligned:
        base = 12.0 if len(aligned_people) == 1 else 20.0
        pts = base * max(decay(as_of, t["_tx"]) for t in aligned)
        evidence += [{"id": t["id"], "signal": "committee"} for t in aligned]
    signals["committee"] = {"fired": bool(aligned), "points": round(pts, 1),
                            "aligned_buyers": sorted(aligned_people),
                            "sectors": ticker_sectors}
    total += pts

    # --- convergence: the CCS concept (0-35)
    conv_insiders: dict[str, dict] = {}
    for ib in i_buys:
        if not ib["_tx"]:
            continue
        near = any(cb["_tx"] and abs((ib["_tx"] - cb["_tx"]).days) <= CONVERGENCE_WINDOW_DAYS
                   for cb in c_buys)
        if near:
            prev = conv_insiders.get(ib["person"])
            if not prev or ib["_tx"] > prev["_tx"]:
                conv_insiders[ib["person"]] = ib
    pts = 0.0
    if len(conv_insiders) >= 2:
        ins = list(conv_insiders.values())
        value = sum(t["amount_low"] for t in ins)
        base = 25.0 + min(6.0, (len(ins) - 2) * 3.0) + min(4.0, math.log10(max(value, 1)) - 3)
        pts = max(0.0, base) * max(decay(as_of, t["_tx"]) for t in ins)
        evidence += [{"id": t["id"], "signal": "convergence"} for t in ins]
        evidence += [{"id": t["id"], "signal": "convergence"} for t in c_buys[:4]]
    signals["convergence"] = {"fired": len(conv_insiders) >= 2, "points": round(pts, 1),
                              "insider_buyers": sorted(conv_insiders)}
    total += pts

    # --- options conviction (0-15)
    opts = [t for t in c_buys if t["asset_type"] == "option"]
    pts = 0.0
    if opts:
        big = any((t["amount_low"] + t["amount_high"]) / 2 >= 250_000 for t in opts)
        base = 10.0 + (5.0 if big else 0.0)
        pts = base * max(decay(as_of, t["_tx"]) for t in opts)
        evidence += [{"id": t["id"], "signal": "options"} for t in opts]
    signals["options"] = {"fired": bool(opts), "points": round(pts, 1),
                          "count": len(opts)}
    total += pts

    # --- size weighting (0-10)
    sf = max(size_factor(t["amount_low"], t["amount_high"]) for t in c_buys)
    biggest = max(c_buys, key=lambda t: size_factor(t["amount_low"], t["amount_high"]))
    pts = min(10.0, max(0.0, (sf - 1.0) * 2.5)) * decay(as_of, biggest["_tx"])
    if pts > 1:
        evidence.append({"id": biggest["id"], "signal": "size"})
    signals["size"] = {"fired": pts > 1, "points": round(pts, 1),
                       "max_band_mid": int((biggest["amount_low"] + biggest["amount_high"]) / 2)}
    total += pts

    seen: set[tuple[str, str]] = set()
    ev = [e for e in evidence
          if (e["id"], e["signal"]) not in seen and not seen.add((e["id"], e["signal"]))]
    return {
        "ticker": ticker,
        "score": round(min(100.0, total), 1),
        "signals": signals,
        "evidence": ev[:MAX_EVIDENCE],
        "stats": {
            "congress_buys": len(c_buys),
            "distinct_buyers": len({t["person"] for t in c_buys}),
            "insider_open_market_buys": len(i_buys),
            "options_positions": len(opts),
        },
    }


def caution_ticker(ticker: str, txs: list[dict], as_of: date,
                   person_sectors: dict[str, list[str]],
                   ticker_sectors: list[str]) -> dict | None:
    c_sells = [t for t in txs if t["source"] == "congress" and t["side"] == "sell"]
    i_sells = [t for t in txs if t["source"] == "insider" and t["side"] == "sell"]
    if not c_sells and not i_sells:
        return None

    signals: dict[str, dict] = {}
    evidence: list[dict] = []
    total = 0.0

    cluster = best_cluster(c_sells)
    sellers = {t["person"] for t in cluster}
    pts = 0.0
    if len(sellers) >= 3:
        base = 24.0 + min(12.0, (len(sellers) - 3) * 4.0)
        pts = base * _mean([decay(as_of, t["_tx"]) for t in cluster])
        evidence += [{"id": t["id"], "signal": "sell_cluster"} for t in cluster]
    signals["sell_cluster"] = {"fired": len(sellers) >= 3, "points": round(pts, 1),
                               "distinct_sellers": len(sellers)}
    total += pts

    # insider distribution: officer sales; 10b5-1 plans half-weighted
    officers: dict[str, float] = {}
    officer_txs = []
    for t in i_sells:
        w = 0.5 if t.get("planned_10b5_1") else 1.0
        officers[t["person"]] = max(officers.get(t["person"], 0), w)
        officer_txs.append(t)
    weight = sum(officers.values())
    pts = 0.0
    if weight >= 2.0:
        recent = [t for t in officer_txs if t["_tx"]]
        base = 24.0 + min(12.0, (weight - 2.0) * 4.0)
        pts = base * (max(decay(as_of, t["_tx"]) for t in recent) if recent else 0)
        evidence += [{"id": t["id"], "signal": "insider_distribution"} for t in officer_txs]
    signals["insider_distribution"] = {"fired": weight >= 2.0, "points": round(pts, 1),
                                       "distinct_sellers": len(officers),
                                       "weighted_sellers": round(weight, 1)}
    total += pts

    aligned = [t for t in c_sells
               if set(person_sectors.get(t["person"], [])) & set(ticker_sectors)]
    pts = 0.0
    if aligned and (signals["sell_cluster"]["fired"] or signals["insider_distribution"]["fired"]):
        pts = 10.0 * max(decay(as_of, t["_tx"]) for t in aligned)
        evidence += [{"id": t["id"], "signal": "committee_sell"} for t in aligned]
    signals["committee_sell"] = {"fired": pts > 0, "points": round(pts, 1)}
    total += pts

    if total < 8:  # not worth flagging
        return None
    seen = set()
    ev = [e for e in evidence if not (e["id"] in seen or seen.add(e["id"]))]
    return {
        "ticker": ticker,
        "score": round(min(100.0, total), 1),
        "signals": signals,
        "evidence": ev[:MAX_EVIDENCE],
        "stats": {"congress_sells": len(c_sells),
                  "insider_sells": len(i_sells)},
    }


def run_engine(trades: list[dict], members: list[dict],
               tickers_meta: dict[str, dict], as_of: date) -> dict:
    txs = _prep(trades)
    person_sectors = _member_sectors(members)
    by_ticker: dict[str, list[dict]] = {}
    for t in txs:
        if t.get("ticker"):
            by_ticker.setdefault(t["ticker"], []).append(t)

    candidates, caution = [], []
    for ticker in sorted(by_ticker):
        t_sectors = (tickers_meta.get(ticker) or {}).get("sectors", []) or []
        name = (tickers_meta.get(ticker) or {}).get("name")
        if ticker not in BROAD_ETFS:
            c = score_ticker(ticker, by_ticker[ticker], as_of, person_sectors, t_sectors)
            if c and c["score"] >= 3:
                c["name"] = name
                c["sectors"] = t_sectors
                candidates.append(c)
        w = caution_ticker(ticker, by_ticker[ticker], as_of, person_sectors, t_sectors)
        if w:
            w["name"] = name
            w["sectors"] = t_sectors
            caution.append(w)

    candidates.sort(key=lambda c: (-c["score"], c["ticker"]))
    caution.sort(key=lambda c: (-c["score"], c["ticker"]))
    return {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "candidates": candidates[:TOP_CANDIDATES],
        "caution": caution[:TOP_CAUTION],
        "universe": len(by_ticker),
    }


def main() -> None:
    trades = (load_json(DATA / "trades.json", {}) or {}).get("trades", [])
    members = (load_json(DATA / "members.json", {}) or {}).get("members", [])
    tickers_meta = (load_json(DATA / "tickers.json", {}) or {}).get("tickers", {})
    if not trades:
        raise RuntimeError("no trades to score")
    as_of = max(d for d in (parse_date(t.get("filed_date")) for t in trades) if d)
    result = run_engine(trades, members, tickers_meta, as_of)
    result["generated_at"] = utcnow_iso()
    save_json(DATA / "candidates.json", result)
    set_status("score", True,
               f"as_of={result['as_of']} universe={result['universe']}",
               count=len(result["candidates"]))
    print(f"[score] {len(result['candidates'])} candidates, "
          f"{len(result['caution'])} caution (universe {result['universe']}, "
          f"as_of {result['as_of']})")
    for c in result["candidates"][:5]:
        fired = [k for k, v in c["signals"].items() if v["fired"]]
        print(f"  {c['ticker']:<6} {c['score']:>5}  {'+'.join(fired)}")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("score", main)
