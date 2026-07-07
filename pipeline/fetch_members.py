"""Source E: member metadata from unitedstates/congress-legislators.

Writes data/members.json: party, state, chamber, committee assignments
(thomas_id + name) and the sector tags those committees oversee.
"""
from __future__ import annotations

from datetime import timedelta

import yaml

from lib.common import (
    DATA, http_session, polite_get, save_json, set_status, today, utcnow_iso,
)
from lib.sectors import committee_sectors

BASE = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main"


def _today_iso() -> str:
    return today().strftime("%Y-%m-%d")


def _load_yaml(session, name: str):
    r = polite_get(session, f"{BASE}/{name}")
    r.raise_for_status()
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    return yaml.load(r.text, Loader=loader)


def recent_departures(historical, cutoff_iso: str) -> list[dict]:
    """Members who left recently can still have in-window disclosures
    (e.g. a senator resigning mid-term). Committees are left empty - they
    no longer sit on any - but party/state attribution stays correct."""
    out = []
    for leg in historical or []:
        terms = leg.get("terms") or []
        if not terms or (terms[-1].get("end") or "") < cutoff_iso:
            continue
        out.append(leg)
    return out


def build_members(legislators, committees, membership) -> list[dict]:
    comm_names = {}
    for c in committees or []:
        if c.get("thomas_id"):
            comm_names[c["thomas_id"]] = c.get("name", c["thomas_id"])

    # committee membership is keyed by thomas_id; 4-char keys are full
    # committees, longer keys (e.g. HSAG14) are subcommittees - skip those.
    by_bioguide: dict[str, list[str]] = {}
    for cid, roster in (membership or {}).items():
        if len(cid) != 4:
            continue
        for seat in roster or []:
            bid = seat.get("bioguide")
            if bid:
                by_bioguide.setdefault(bid, []).append(cid)

    members = []
    for leg in legislators or []:
        terms = leg.get("terms") or []
        if not terms:
            continue
        term = terms[-1]
        chamber = {"sen": "senate", "rep": "house"}.get(term.get("type"), "")
        if not chamber:
            continue
        bid = (leg.get("id") or {}).get("bioguide", "")
        name = leg.get("name") or {}
        cids = sorted(by_bioguide.get(bid, []))
        former = bool(term.get("end") and term["end"] < _today_iso())
        members.append({
            "bioguide": bid,
            "former": former,
            "name": name.get("official_full") or f"{name.get('first', '')} {name.get('last', '')}".strip(),
            "first": name.get("first", ""),
            "last": name.get("last", ""),
            "nickname": name.get("nickname", ""),
            "chamber": chamber,
            "party": term.get("party", ""),
            "state": term.get("state", ""),
            "district": term.get("district") if chamber == "house" else None,
            "committees": [{"id": c, "name": comm_names.get(c, c)} for c in cids],
            "sectors": committee_sectors(cids),
        })
    members.sort(key=lambda m: (m["chamber"], m["last"], m["first"]))
    return members


def main() -> None:
    s = http_session(rps=2.0)
    legislators = _load_yaml(s, "legislators-current.yaml")
    committees = _load_yaml(s, "committees-current.yaml")
    membership = _load_yaml(s, "committee-membership-current.yaml")
    historical = _load_yaml(s, "legislators-historical.yaml")
    cutoff = (today() - timedelta(days=400)).strftime("%Y-%m-%d")
    legislators = list(legislators or []) + recent_departures(historical, cutoff)
    members = build_members(legislators, committees, membership)
    if len(members) < 400:
        raise RuntimeError(f"only {len(members)} members parsed - refusing to overwrite")
    save_json(DATA / "members.json", {"generated_at": utcnow_iso(), "members": members})
    set_status("members", True, "congress-legislators", count=len(members))
    print(f"[members] wrote {len(members)} members")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("members", main)
