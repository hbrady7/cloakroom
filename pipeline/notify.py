"""Optional push notification: top-3 picks one-liner to ntfy.sh/<NTFY_TOPIC>.

Free push to any phone with the ntfy app subscribed to the topic. Skips
silently when NTFY_TOPIC is unset; never fails the pipeline.
"""
from __future__ import annotations

import os
import sys

import requests

from lib.common import DATA, USER_AGENT, load_json


def build_line() -> str | None:
    brief = load_json(DATA / "brief-latest.json", {}) or {}
    if brief.get("status") == "ok" and brief.get("picks"):
        parts = [f"{p['ticker']} {p['direction']} ({p['conviction']})"
                 for p in brief["picks"][:3]]
        return f"{brief.get('date', '')}: " + " · ".join(parts)
    cand = (load_json(DATA / "candidates.json", {}) or {})
    top = (cand.get("candidates") or [])[:3]
    if not top:
        return None
    parts = [f"{c['ticker']} {c['score']}" for c in top]
    return f"{cand.get('as_of', '')} (engine only): " + " · ".join(parts)


def main() -> None:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("[notify] NTFY_TOPIC unset - skipping")
        return
    line = build_line()
    if not line:
        print("[notify] nothing to send")
        return
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=line.encode("utf-8"),
            headers={
                "Title": "CLOAKROOM daily brief",
                "Tags": "classical_building,chart_with_upwards_trend",
                "User-Agent": USER_AGENT,
            },
            timeout=15,
        )
        print(f"[notify] sent: {line}")
    except requests.RequestException as e:
        print(f"[notify] failed (non-fatal): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
