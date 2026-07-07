"""Source A: Senate trades.

Primary: Senate Stock Watcher aggregate JSON (per spec). As of mid-2026 that
project is dead (last data Dec 2020), so when the aggregate yields zero
in-window rows we fall through to scraping efdsearch.senate.gov directly -
the official Senate eFD system. Set CLOAKROOM_DISABLE_EFD=1 to keep the
scraper off entirely.

Writes data/senate_transactions.json (unified trade schema).
"""
from __future__ import annotations

import os
import re

from bs4 import BeautifulSoup

from lib.common import (
    DATA, clean_ticker, http_session, iso, load_json, make_trade, parse_band,
    parse_date, polite_get, polite_post, save_json, set_status, today,
    trade_id, utcnow_iso, window_start,
)
from lib.names import MemberIndex

AGGREGATE_URL = ("https://raw.githubusercontent.com/timothycarambat/"
                 "senate-stock-watcher-data/master/aggregate/all_transactions.json")
EFD = "https://efdsearch.senate.gov"
MAX_REPORTS = int(os.environ.get("CLOAKROOM_SENATE_MAX_REPORTS", "400"))

SIDE_MAP = {
    "purchase": "buy",
    "sale (full)": "sell",
    "sale (partial)": "sell",
    "sale": "sell",
}


def _asset_type(label: str, description: str = "") -> str:
    t = (label or "").lower()
    if "option" in t or "option" in (description or "").lower():
        return "option"
    if "exchange traded" in t or t == "etf":
        return "etf"
    if t == "stock" or "stock" in t and "non-public" not in t:
        return "stock"
    return "other"


def _member_role(idx: MemberIndex | None, name: str) -> dict:
    m = idx.match(name, "senate") if idx else None
    if not m:
        return {"chamber": "senate", "party": "", "committees": []}
    return {
        "chamber": "senate",
        "party": m.get("party", ""),
        "committees": [c["name"] for c in m.get("committees", [])],
    }


def rows_from_aggregate(raw_rows: list[dict], idx: MemberIndex | None, start) -> list[dict]:
    """Parse Senate Stock Watcher aggregate rows (no disclosure_date field is
    published, so filed_date falls back to tx_date - acceptable because this
    source only matters if it ever comes back to life)."""
    out = []
    for i, r in enumerate(raw_rows or []):
        side = SIDE_MAP.get(str(r.get("type", "")).lower())
        ticker = clean_ticker(r.get("ticker"))
        tx = parse_date(r.get("transaction_date"))
        filed = parse_date(r.get("disclosure_date")) or tx
        if not side or not ticker or not tx or filed < start:
            continue
        lo, hi = parse_band(r.get("amount"))
        atype = _asset_type(r.get("asset_type", ""), r.get("asset_description", ""))
        detail = None
        if atype == "option":
            detail = " ".join(x for x in [r.get("asset_description"), r.get("comment")]
                              if x and x not in ("--",)) or None
        person = str(r.get("senator", "")).strip()
        out.append(make_trade(
            id=trade_id("congress", "senate", person, ticker, iso(tx), side, lo, i),
            source="congress", person=person, role=_member_role(idx, person),
            ticker=ticker, asset_type=atype, side=side, amount_low=lo, amount_high=hi,
            tx_date=tx, filed_date=filed, option_detail=detail,
            source_url=r.get("ptr_link", ""),
        ))
    return out


# ------------------------------------------------------------------ eFD scraper

def efd_session():
    s = http_session(rps=0.8)
    polite_get(s, f"{EFD}/search/")
    csrf = s.cookies.get("csrftoken", "")
    r = polite_post(s, f"{EFD}/search/home/",
                    data={"prohibition_agreement": "1", "csrfmiddlewaretoken": csrf},
                    headers={"Referer": f"{EFD}/search/home/"})
    r.raise_for_status()
    return s


def efd_report_list(s, start, end) -> list[dict]:
    """Paginated DataTables endpoint: PTR filings by senators in the window."""
    reports, offset = [], 0
    while offset < MAX_REPORTS * 2:
        csrf = s.cookies.get("csrftoken", "")
        payload = {
            "start": str(offset), "length": "100",
            "report_types": "[11]", "filer_types": "[1]",
            "submitted_start_date": start.strftime("%m/%d/%Y") + " 00:00:00",
            "submitted_end_date": end.strftime("%m/%d/%Y") + " 23:59:59",
            "candidate_state": "", "senator_state": "", "office_id": "",
            "first_name": "", "last_name": "",
            "csrfmiddlewaretoken": csrf,
        }
        r = polite_post(s, f"{EFD}/search/report/data/", data=payload,
                        headers={"Referer": f"{EFD}/search/", "X-CSRFToken": csrf})
        r.raise_for_status()
        rows = r.json().get("data", [])
        for row in rows:
            m = re.search(r'href="(/search/view/(ptr|paper)/[^"]+)"', row[3] or "")
            if not m:
                continue
            reports.append({
                "first": re.sub(r"<[^>]+>", "", row[0] or "").strip(),
                "last": re.sub(r"<[^>]+>", "", row[1] or "").strip(),
                "href": m.group(1),
                "kind": m.group(2),
                "filed": parse_date((row[4] or "").strip()),
            })
        if len(rows) < 100:
            break
        offset += 100
    return reports


def parse_efd_ptr_html(html: str) -> list[dict]:
    """Parse one eFD electronic PTR page into raw transaction dicts."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for tr in soup.select("table tbody tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 8:
            continue
        # columns: #, tx date, owner, ticker, asset name, asset type, type, amount[, comment]
        out.append({
            "tx_date": cells[1], "owner": cells[2], "ticker": cells[3],
            "asset_name": cells[4], "asset_type": cells[5], "type": cells[6],
            "amount": cells[7], "comment": cells[8] if len(cells) > 8 else "",
        })
    return out


def trades_from_efd(reports: list[dict], fetch_html, idx: MemberIndex | None, start) -> tuple[list[dict], int]:
    trades, papers = [], 0
    for rep in reports[:MAX_REPORTS]:
        if not rep["filed"] or rep["filed"] < start:
            continue
        if rep["kind"] == "paper":
            papers += 1
            continue
        person = f"{rep['first'].title()} {rep['last'].title()}".strip()
        url = EFD + rep["href"]
        html = fetch_html(url)
        if not html:
            continue
        role = _member_role(idx, person)
        for i, raw in enumerate(parse_efd_ptr_html(html)):
            side = SIDE_MAP.get(str(raw.get("type", "")).lower())
            ticker = clean_ticker(raw.get("ticker"))
            tx = parse_date(raw.get("tx_date"))
            if not side or not ticker or not tx:
                continue
            lo, hi = parse_band(raw.get("amount"))
            atype = _asset_type(raw.get("asset_type", ""), raw.get("asset_name", ""))
            detail = None
            if atype == "option":
                bits = [raw.get("asset_name", ""), raw.get("comment", "")]
                detail = " — ".join(b for b in bits if b and b != "--") or None
            trades.append(make_trade(
                id=trade_id("congress", "senate", person, ticker, iso(tx), side, lo, rep["href"], i),
                source="congress", person=person, role=role,
                ticker=ticker, asset_type=atype, side=side,
                amount_low=lo, amount_high=hi,
                tx_date=tx, filed_date=rep["filed"], option_detail=detail,
                source_url=url,
            ))
    return trades, papers


def main() -> None:
    start = window_start()
    idx = MemberIndex((load_json(DATA / "members.json", {}) or {}).get("members", []))

    trades: list[dict] = []
    mode = "aggregate"
    s = http_session(rps=2.0)
    try:
        r = polite_get(s, AGGREGATE_URL, timeout=(10, 120))
        r.raise_for_status()
        trades = rows_from_aggregate(r.json(), idx, start)
    except Exception as e:  # noqa: BLE001 - fall through to eFD
        print(f"[senate] aggregate fetch failed: {e}")

    if not trades and os.environ.get("CLOAKROOM_DISABLE_EFD") != "1":
        mode = "efd"
        es = efd_session()
        reports = efd_report_list(es, start, today())
        print(f"[senate] eFD: {len(reports)} PTR filings in window")

        def fetch_html(url: str) -> str | None:
            try:
                resp = polite_get(es, url)
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001 - skip one report, keep going
                print(f"[senate] skip {url}: {exc}")
                return None

        trades, papers = trades_from_efd(reports, fetch_html, idx, start)
        print(f"[senate] parsed {len(trades)} transactions ({papers} paper filings skipped)")

    if not trades:
        raise RuntimeError("no senate transactions from any source")

    trades.sort(key=lambda t: (t["filed_date"], t["tx_date"], t["id"]), reverse=True)
    save_json(DATA / "senate_transactions.json",
              {"generated_at": utcnow_iso(), "mode": mode, "transactions": trades})
    set_status("senate", True, f"mode={mode}", count=len(trades))
    print(f"[senate] wrote {len(trades)} transactions (mode={mode})")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("senate", main)
