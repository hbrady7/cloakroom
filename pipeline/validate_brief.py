"""Validate a Claude-produced brief: JSON Schema + grounding cross-checks.

Beyond the schema, enforce that the brief only references reality:
  - every evidence_id must exist in data/trades.json
  - every pick/caution/skipped ticker must be an engine candidate or caution
  - the date must equal the engine's as_of

Usage: validate_brief.py <brief.json>   (exit 0 valid / 1 invalid,
errors on stderr - the retry prompt appends them verbatim)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from lib.common import DATA, load_json

PIPELINE = Path(__file__).resolve().parent


WRAPPER_KEYS = ("status", "model", "generated_at")  # added by run_brief for the site


def validate(brief: dict, cand: dict | None = None,
             trades: list[dict] | None = None) -> list[str]:
    brief = {k: v for k, v in brief.items() if k not in WRAPPER_KEYS}
    errors: list[str] = []
    schema = json.loads((PIPELINE / "brief_schema.json").read_text())
    for e in Draft202012Validator(schema).iter_errors(brief):
        path = "$" + "".join(f"[{p!r}]" for p in e.absolute_path)
        errors.append(f"schema: {path}: {e.message[:200]}")
    if errors:
        return errors  # structural problems first; grounding checks need shape

    if cand is None:
        cand = load_json(DATA / "candidates.json", {}) or {}
    if trades is None:
        trades = (load_json(DATA / "trades.json", {}) or {}).get("trades", [])
    known_ids = {t["id"] for t in trades}
    long_tickers = {c["ticker"] for c in cand.get("candidates", [])}
    caution_tickers = {c["ticker"] for c in cand.get("caution", [])}
    allowed = long_tickers | caution_tickers

    if brief.get("date") != cand.get("as_of"):
        errors.append(f"grounding: date {brief.get('date')!r} != engine as_of {cand.get('as_of')!r}")

    for i, p in enumerate(brief.get("picks", [])):
        if p["ticker"] not in allowed:
            errors.append(f"grounding: picks[{i}].ticker {p['ticker']!r} is not an engine candidate")
        for eid in p.get("evidence_ids", []):
            if eid not in known_ids:
                errors.append(f"grounding: picks[{i}] cites unknown evidence id {eid!r}")
    for i, c in enumerate(brief.get("caution_list", [])):
        if c["ticker"] not in allowed:
            errors.append(f"grounding: caution_list[{i}].ticker {c['ticker']!r} is not an engine entry")
        for eid in c.get("evidence_ids", []):
            if eid not in known_ids:
                errors.append(f"grounding: caution_list[{i}] cites unknown evidence id {eid!r}")
    for i, s in enumerate(brief.get("skipped", [])):
        if s["ticker"] not in allowed:
            errors.append(f"grounding: skipped[{i}].ticker {s['ticker']!r} is not an engine entry")

    picked = [p["ticker"] for p in brief.get("picks", [])]
    if len(picked) != len(set(picked)):
        errors.append("grounding: duplicate tickers in picks")
    accounted = set(picked) | {s["ticker"] for s in brief.get("skipped", [])}
    missing = long_tickers - accounted
    if missing:
        errors.append(f"grounding: candidates neither picked nor skipped: {sorted(missing)}")
    return errors


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: validate_brief.py <brief.json>", file=sys.stderr)
        sys.exit(2)
    try:
        brief = json.loads(Path(sys.argv[1]).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"unreadable: {e}", file=sys.stderr)
        sys.exit(1)
    if brief.get("status") == "engine_only":
        print("engine_only fallback brief - valid by definition")
        sys.exit(0)
    errors = validate(brief)
    for e in errors:
        print(e, file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
