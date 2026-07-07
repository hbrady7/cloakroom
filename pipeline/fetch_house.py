"""Source B: House trades from the official Clerk disclosure system.

(House Stock Watcher is dead - its S3 bucket 403s - so we build from source.)

1. Download the annual financial-disclosure index ZIP(s) from
   disclosures-clerk.house.gov; the TSV inside lists every filing with DocID.
2. FilingType == "P" rows are Periodic Transaction Reports.
3. Fetch each new PTR PDF and parse transactions with pdfplumber.
   E-filed PTRs have a text layer; paper/scanned ones do not and are recorded
   as "no_text" in data/house_seen.json so they are never re-fetched.

Writes data/house_transactions.json incrementally (unified trade schema).
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from datetime import date

import pdfplumber

from lib.common import (
    DATA, clean_ticker, http_session, iso, load_json, make_trade, parse_band,
    parse_date, polite_get, save_json, set_status, trade_id, utcnow_iso,
    window_start,
)
from lib.names import MemberIndex

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc}.pdf"
MAX_NEW_DOCS = int(os.environ.get("CLOAKROOM_HOUSE_MAX_NEW_DOCS", "150"))

# A transaction row's first visual line: [owner] [asset words...] TYPE date date $band-start
ANCHOR_RE = re.compile(
    r"^(?:(?P<owner>SP|DC|JT)\s+)?"
    r"(?P<asset>.*?)\s*"
    r"(?P<type>P|S|E|S \(partial\))\s+"
    r"(?P<tx>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<notif>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amt>\$[\d,]+(?:\s*-\s*(?:\$[\d,]+)?)?|\$[\d,]+\s*\+?)\s*$"
)
# Row metadata lines render with small-caps labels mangled to bare capitals,
# e.g. "F S : New" (Filing Status), "S O : Schwab" (Subholding Of),
# "D : Purchased 10 call options ..." (Description). Values keep normal text.
META_RE = re.compile(r"^(?P<label>[A-Z][A-Z\s]{0,24}?)\s*:\s*(?P<value>.*)$")
TICKER_IN_ASSET_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)")
CLASS_TAG_RE = re.compile(r"\[([A-Z]{2})\]")
STOP_RE = re.compile(r"^(\*\s*For the complete list|Digitally Signed|I\s+V\s+D|C\s+S\s*$)")

NOT_TICKERS = {"NYSE", "NASDAQ", "OTC", "USD", "IRA", "LLC", "LP", "ETF", "N/A", "US"}
TAG_TO_TYPE = {"ST": "stock", "OP": "option", "EF": "etf", "ET": "etf"}
SIDE_MAP = {"P": "buy", "S": "sell", "S (partial)": "sell"}


def parse_index(tsv_text: str) -> list[dict]:
    """Parse the {year}FD.txt tab-separated filing index."""
    rows = []
    lines = tsv_text.splitlines()
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        prefix, last, first, suffix, ftype, statedst, year, fdate, docid = parts[:9]
        rows.append({
            "last": last.strip(), "first": first.strip(), "suffix": suffix.strip(),
            "filing_type": ftype.strip(), "state_district": statedst.strip(),
            "year": year.strip(), "filed": parse_date(fdate.strip()),
            "doc_id": docid.strip(),
        })
    return rows


def _finish_row(row: dict, cont_lines: list[str]) -> dict:
    """Fold continuation lines (asset wrap, band high, ticker, class tag,
    option description) into an anchored row."""
    asset_extra, band_extra, desc = [], "", []
    for line in cont_lines:
        meta = META_RE.match(line)
        if meta:
            label = re.sub(r"\s+", "", meta.group("label"))
            if label.startswith("D"):  # "Description:"
                desc.append(meta.group("value").strip())
            continue
        if not band_extra and row["amount"].rstrip().endswith("-"):
            m = re.search(r"\$[\d,]+", line)
            if m:
                band_extra = m.group(0)
        asset_extra.append(line)

    asset_text = " ".join([row["asset"]] + asset_extra)
    tickers = [t for t in TICKER_IN_ASSET_RE.findall(asset_text) if t not in NOT_TICKERS]
    tags = CLASS_TAG_RE.findall(asset_text)
    # strip ticker/tag noise out of the display name
    name = TICKER_IN_ASSET_RE.sub("", asset_text)
    name = CLASS_TAG_RE.sub("", name)
    name = re.sub(r"\$[\d,]+\s*$", "", name)  # stray band-high fragment
    row["asset"] = re.sub(r"\s{2,}", " ", name).strip(" -–")
    row["ticker"] = tickers[-1] if tickers else None
    row["tag"] = tags[0] if tags else None
    if band_extra:
        row["amount"] = f"{row['amount']} {band_extra}"
    row["description"] = " ".join(desc) or None
    return row


def parse_ptr_text(text: str) -> list[dict]:
    """Pure parser: extracted PTR text -> raw transaction dicts.

    Returns [{owner, asset, ticker, tag, type, tx_date, notif_date, amount,
    description}]. Fixture-tested against real filings.
    """
    # small-caps label glyphs come out of pdfplumber as NUL bytes
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text or "")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows: list[dict] = []
    current: dict | None = None
    cont: list[str] = []
    for line in lines:
        if STOP_RE.match(line):
            break
        m = ANCHOR_RE.match(line)
        if m:
            if current:
                rows.append(_finish_row(current, cont))
            current = {
                "owner": m.group("owner") or "",
                "asset": m.group("asset").strip(),
                "type": m.group("type"),
                "tx_date": m.group("tx"),
                "notif_date": m.group("notif"),
                "amount": m.group("amt").strip(),
            }
            cont = []
        elif current:
            cont.append(line)
    if current:
        rows.append(_finish_row(current, cont))
    return rows


def extract_pdf_text(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def trades_from_ptr(raw_rows: list[dict], person: str, filed: date, role: dict,
                    doc_id: str, url: str) -> list[dict]:
    out = []
    for i, r in enumerate(raw_rows):
        side = SIDE_MAP.get(r["type"])
        ticker = clean_ticker(r.get("ticker"))
        tx = parse_date(r.get("tx_date"))
        if not side or not tx:
            continue
        tag = r.get("tag")
        desc = r.get("description") or ""
        if tag:
            atype = TAG_TO_TYPE.get(tag, "other")
        else:
            atype = "stock" if ticker else "other"
        if "option" in desc.lower() or atype == "option":
            atype = "option"
        if not ticker:
            continue  # unscoreable without a ticker (T-bills, funds, munis)
        lo, hi = parse_band(r.get("amount"))
        detail = None
        if atype == "option":
            detail = desc or r.get("asset") or None
        out.append(make_trade(
            id=trade_id("congress", "house", person, ticker, iso(tx), side, lo, doc_id, i),
            source="congress", person=person, role=role,
            ticker=ticker, asset_type=atype, side=side,
            amount_low=lo, amount_high=hi,
            tx_date=tx, filed_date=filed, option_detail=detail, source_url=url,
        ))
    return out


def main() -> None:
    start = window_start()
    idx = MemberIndex((load_json(DATA / "members.json", {}) or {}).get("members", []))
    seen = load_json(DATA / "house_seen.json", {"docs": {}}) or {"docs": {}}
    store = load_json(DATA / "house_transactions.json",
                      {"generated_at": None, "transactions": []}) or {}
    by_id = {t["id"]: t for t in store.get("transactions", [])}

    s = http_session(rps=1.4)
    years = sorted({start.year, window_start(0).year})
    ptrs: list[dict] = []
    for year in years:
        r = polite_get(s, INDEX_URL.format(year=year), timeout=(10, 120))
        if r.status_code != 200:
            print(f"[house] index {year} -> HTTP {r.status_code}, skipping year")
            continue
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            txt_name = next(n for n in z.namelist() if n.endswith(".txt"))
            rows = parse_index(z.read(txt_name).decode("utf-8", "replace"))
        ptrs.extend([x for x in rows
                     if x["filing_type"] == "P" and x["filed"] and x["filed"] >= start])
    if not ptrs:
        raise RuntimeError("no PTR filings found in any index")

    new = [p for p in ptrs if p["doc_id"] not in seen["docs"]]
    new.sort(key=lambda p: (p["filed"], p["doc_id"]), reverse=True)
    print(f"[house] {len(ptrs)} PTRs in window, {len(new)} new (cap {MAX_NEW_DOCS})")

    parsed = no_text = errors = 0
    for p in new[:MAX_NEW_DOCS]:
        doc, year = p["doc_id"], p["year"]
        url = PDF_URL.format(year=year, doc=doc)
        person = f"{p['first']} {p['last']}".strip()
        mark = {"filed": iso(p["filed"]), "member": person, "n_tx": 0}
        try:
            r = polite_get(s, url)
            if r.status_code != 200:
                mark["status"] = f"http_{r.status_code}"
                seen["docs"][doc] = mark
                continue
            text = extract_pdf_text(r.content)
            if len(text.strip()) < 50:
                mark["status"] = "no_text"  # scanned paper filing
                no_text += 1
                seen["docs"][doc] = mark
                continue
            m = idx.match(person, "house")
            role = {"chamber": "house",
                    "party": (m or {}).get("party", ""),
                    "committees": [c["name"] for c in (m or {}).get("committees", [])]}
            trades = trades_from_ptr(parse_ptr_text(text), person, p["filed"], role, doc, url)
            for t in trades:
                by_id[t["id"]] = t
            mark["status"] = "parsed"
            mark["n_tx"] = len(trades)
            parsed += 1
        except Exception as e:  # noqa: BLE001 - one bad PDF must not sink the run
            mark["status"] = "error"
            mark["detail"] = f"{type(e).__name__}: {e}"[:200]
            errors += 1
        seen["docs"][doc] = mark

    # window the store (keep a little slack past the merge window)
    keep_from = iso(window_start(220))
    txs = [t for t in by_id.values() if (t.get("filed_date") or "") >= keep_from]
    txs.sort(key=lambda t: (t["filed_date"], t["tx_date"], t["id"]), reverse=True)

    save_json(DATA / "house_transactions.json",
              {"generated_at": utcnow_iso(), "transactions": txs})
    save_json(DATA / "house_seen.json", seen)
    set_status("house", True,
               f"parsed={parsed} no_text={no_text} errors={errors}", count=len(txs))
    print(f"[house] wrote {len(txs)} transactions "
          f"(parsed {parsed} new docs, {no_text} scanned, {errors} errors)")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("house", main)
