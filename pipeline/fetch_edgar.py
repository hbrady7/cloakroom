"""Source C: SEC EDGAR Form 4 insider transactions.

Scope: the tickers that appear in congressional trades (that is what the
convergence and caution signals need). For each ticker:
  data.sec.gov submissions API -> recent Form 4 accessions (+ SIC sector tags)
  -> raw Form 4 XML from the Archives -> open-market P/S transactions.

Honors SEC fair-access rules: proper User-Agent, well under 8 req/s.
Writes data/insider_transactions.json + data/tickers.json incrementally.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import date

from lib.common import (
    DATA, http_session, iso, load_json, make_trade, parse_date, polite_get,
    save_json, set_status, trade_id, utcnow_iso, window_start,
)
from lib.sectors import sic_to_sectors

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

INSIDER_DAYS = int(os.environ.get("CLOAKROOM_INSIDER_DAYS", "75"))
MAX_TICKERS = int(os.environ.get("CLOAKROOM_EDGAR_MAX_TICKERS", "250"))
MAX_FILINGS_PER_TICKER = int(os.environ.get("CLOAKROOM_EDGAR_MAX_FILINGS", "16"))


def _text(root, path: str) -> str:
    el = root.find(path)
    return (el.text or "").strip() if el is not None and el.text else ""


def parse_form4(xml_bytes: bytes) -> dict:
    """Pure parser: Form 4 XML -> owner, flags, and non-derivative P/S rows.

    Fixture-tested. Returns {ticker, owner, title, aff10b5_one,
    transactions: [{code, date, shares, price, value, acquired}]}.
    """
    root = ET.fromstring(xml_bytes)
    owners = root.findall(".//reportingOwner")
    names = [_text(o, ".//rptOwnerName") for o in owners]
    owner = names[0] if names else ""
    if len(names) > 1:
        owner += " et al."
    o0 = owners[0] if owners else root
    is_officer = _text(o0, ".//isOfficer").lower() in ("1", "true")
    is_director = _text(o0, ".//isDirector").lower() in ("1", "true")
    is_ten_pct = _text(o0, ".//isTenPercentOwner").lower() in ("1", "true")
    title = _text(o0, ".//officerTitle")
    if not title:
        title = ("Director" if is_director
                 else "10% owner" if is_ten_pct
                 else "Insider")
    aff = _text(root, ".//aff10b5One").lower() in ("1", "true")

    txs = []
    for t in root.findall(".//nonDerivativeTransaction"):
        code = _text(t, ".//transactionCode")
        if code not in ("P", "S"):
            continue
        shares = _text(t, ".//transactionShares/value")
        price = _text(t, ".//transactionPricePerShare/value")
        try:
            shares_f = float(shares)
            price_f = float(price)
        except (TypeError, ValueError):
            continue
        if shares_f <= 0 or price_f <= 0:
            continue
        txs.append({
            "code": code,
            "date": _text(t, ".//transactionDate/value"),
            "shares": shares_f,
            "price": price_f,
            "value": round(shares_f * price_f),
            "acquired": _text(t, ".//transactionAcquiredDisposedCode/value"),
        })
    return {
        "ticker": _text(root, ".//issuerTradingSymbol").upper(),
        "owner": owner.title() if owner.isupper() else owner,
        "title": title,
        "is_officer": is_officer,
        "is_director": is_director,
        "is_ten_pct": is_ten_pct,
        "aff10b5_one": aff,
        "transactions": txs,
    }


def _congress_tickers() -> list[str]:
    """Tickers with congressional activity, most recently filed first."""
    latest: dict[str, str] = {}
    for fname in ("senate_transactions.json", "house_transactions.json"):
        for t in (load_json(DATA / fname, {}) or {}).get("transactions", []):
            tick = t.get("ticker")
            if tick:
                latest[tick] = max(latest.get(tick, ""), t.get("filed_date") or "")
    return sorted(latest, key=lambda k: (latest[k], k), reverse=True)


def main() -> None:
    tickers = _congress_tickers()[:MAX_TICKERS]
    if not tickers:
        raise RuntimeError("no congressional tickers to scope EDGAR fetch")
    start = max(window_start(INSIDER_DAYS), date(2000, 1, 1))

    seen = load_json(DATA / "edgar_seen.json", {"accessions": {}}) or {"accessions": {}}
    store = load_json(DATA / "insider_transactions.json",
                      {"generated_at": None, "transactions": []}) or {}
    by_id = {t["id"]: t for t in store.get("transactions", [])}
    tickers_meta = (load_json(DATA / "tickers.json", {}) or {}).get("tickers", {})

    s = http_session(rps=5.0)
    r = polite_get(s, TICKER_MAP_URL)
    r.raise_for_status()
    cik_by_ticker = {v["ticker"].upper(): int(v["cik_str"]) for v in r.json().values()}

    new_filings = skipped = 0
    for tick in tickers:
        cik = cik_by_ticker.get(tick) or cik_by_ticker.get(tick.replace(".", "-"))
        if not cik:
            tickers_meta.setdefault(tick, {"name": None, "cik": None, "sic": None,
                                           "sic_desc": None, "sectors": []})
            continue
        try:
            sub = polite_get(s, SUBMISSIONS_URL.format(cik=cik)).json()
        except Exception as e:  # noqa: BLE001 - single-ticker failure is non-fatal
            print(f"[edgar] submissions {tick}: {e}")
            continue
        tickers_meta[tick] = {
            "name": sub.get("name"),
            "cik": cik,
            "sic": sub.get("sic"),
            "sic_desc": sub.get("sicDescription"),
            "sectors": sic_to_sectors(sub.get("sic")),
        }
        rec = sub.get("filings", {}).get("recent", {})
        forms = rec.get("form", [])
        f4 = [
            (rec["accessionNumber"][i], rec["filingDate"][i], rec["primaryDocument"][i])
            for i in range(len(forms))
            if forms[i] == "4" and (parse_date(rec["filingDate"][i]) or date.min) >= start
        ][:MAX_FILINGS_PER_TICKER]

        for acc, fdate, primary in f4:
            if acc in seen["accessions"]:
                continue
            acc_nodash = acc.replace("-", "")
            # primaryDocument is the XSL-rendered view ("xslF345X06/form4.xml");
            # the raw XML is the same basename at the accession root.
            doc = primary.split("/")[-1]
            if not doc.endswith(".xml"):
                seen["accessions"][acc] = {"status": "no_xml", "ticker": tick}
                skipped += 1
                continue
            url = ARCHIVE_URL.format(cik=cik, acc=acc_nodash, doc=doc)
            mark = {"ticker": tick, "filed": fdate, "n_tx": 0}
            try:
                resp = polite_get(s, url)
                resp.raise_for_status()
                parsed = parse_form4(resp.content)
                filed_d = parse_date(fdate)
                for i, tx in enumerate(parsed["transactions"]):
                    tx_d = parse_date(tx["date"])
                    if not tx_d:
                        continue
                    t = make_trade(
                        id=trade_id("insider", acc, i),
                        source="insider",
                        person=parsed["owner"],
                        role={"chamber": "", "party": "", "committees": []},
                        insider_title=parsed["title"],
                        ticker=tick,
                        asset_type="stock",
                        side="buy" if tx["code"] == "P" else "sell",
                        amount_low=tx["value"], amount_high=tx["value"],
                        tx_date=tx_d, filed_date=filed_d,
                        planned_10b5_1=parsed["aff10b5_one"],
                        source_url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/",
                    )
                    by_id[t["id"]] = t
                    mark["n_tx"] += 1
                mark["status"] = "parsed"
                new_filings += 1
            except Exception as e:  # noqa: BLE001 - one bad filing must not sink the run
                mark["status"] = "error"
                mark["detail"] = f"{type(e).__name__}: {e}"[:200]
            seen["accessions"][acc] = mark

    # window the store; prune seen-cache entries that fell out of the window
    keep_from = iso(window_start(INSIDER_DAYS + 30))
    txs = [t for t in by_id.values() if (t.get("filed_date") or "") >= keep_from]
    txs.sort(key=lambda t: (t["filed_date"], t["tx_date"], t["id"]), reverse=True)
    seen["accessions"] = {
        a: m for a, m in seen["accessions"].items()
        if (m.get("filed") or "9999") >= keep_from or m.get("status") != "parsed"
    }

    save_json(DATA / "insider_transactions.json",
              {"generated_at": utcnow_iso(), "transactions": txs})
    save_json(DATA / "edgar_seen.json", seen)
    save_json(DATA / "tickers.json",
              {"generated_at": utcnow_iso(), "tickers": tickers_meta})
    set_status("insider", True,
               f"tickers={len(tickers)} new_filings={new_filings}", count=len(txs))
    print(f"[edgar] wrote {len(txs)} insider transactions "
          f"({new_filings} new filings across {len(tickers)} tickers)")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("insider", main)
