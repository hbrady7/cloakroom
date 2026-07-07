"""Merge senate + house + insider intermediates into data/trades.json.

Each intermediate is last-good on its own (a failed fetcher leaves its old
file untouched), so this step is a pure, always-safe combine: validate,
window to the rolling 180 days by filed_date, dedupe by id, sort.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator

from lib.common import (
    DATA, WINDOW_DAYS, iso, load_json, save_json, set_status, utcnow_iso,
    window_start,
)

TRADE_SCHEMA = {
    "type": "object",
    "required": ["id", "source", "person", "role", "ticker", "asset_type", "side",
                 "amount_low", "amount_high", "tx_date", "filed_date", "lag_days",
                 "planned_10b5_1", "source_url"],
    "properties": {
        "id": {"type": "string", "minLength": 3},
        "source": {"enum": ["congress", "insider"]},
        "person": {"type": "string", "minLength": 1},
        "role": {
            "type": "object",
            "required": ["chamber", "party", "committees"],
            "properties": {
                "chamber": {"enum": ["senate", "house", ""]},
                "party": {"type": "string"},
                "committees": {"type": "array", "items": {"type": "string"}},
            },
        },
        "insider_title": {"type": "string"},
        "ticker": {"type": "string", "minLength": 1},
        "asset_type": {"enum": ["stock", "option", "etf", "other"]},
        "side": {"enum": ["buy", "sell"]},
        "amount_low": {"type": "number", "minimum": 0},
        "amount_high": {"type": "number", "minimum": 0},
        "tx_date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "filed_date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "lag_days": {"type": "integer", "minimum": 0},
        "option_detail": {"type": ["string", "null"]},
        "planned_10b5_1": {"type": "boolean"},
        "source_url": {"type": "string"},
    },
}
_validator = Draft202012Validator(TRADE_SCHEMA)

SOURCES = ["senate_transactions.json", "house_transactions.json",
           "insider_transactions.json"]


def merge(parts: list[list[dict]], start_iso: str) -> tuple[list[dict], int]:
    by_id: dict[str, dict] = {}
    invalid = 0
    for part in parts:
        for t in part or []:
            if not isinstance(t, dict) or (t.get("filed_date") or "") < start_iso:
                continue
            if next(_validator.iter_errors(t), None) is not None:
                invalid += 1
                continue
            by_id[t["id"]] = t
    trades = sorted(by_id.values(),
                    key=lambda t: (t["filed_date"], t["tx_date"], t["id"]),
                    reverse=True)
    return trades, invalid


def main() -> None:
    parts = [(load_json(DATA / f, {}) or {}).get("transactions", []) for f in SOURCES]
    trades, invalid = merge(parts, iso(window_start()))
    if invalid:
        print(f"[merge] dropped {invalid} schema-invalid rows")
    save_json(DATA / "trades.json", {
        "generated_at": utcnow_iso(),
        "window_days": WINDOW_DAYS,
        "trades": trades,
    })
    n_c = sum(1 for t in trades if t["source"] == "congress")
    n_i = len(trades) - n_c
    set_status("merge", True, f"congress={n_c} insider={n_i}", count=len(trades))
    print(f"[merge] wrote {len(trades)} trades ({n_c} congress, {n_i} insider)")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("merge", main)
