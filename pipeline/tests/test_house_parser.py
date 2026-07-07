"""Exact-value assertions against real House PTR PDFs (committed fixtures)."""
from pathlib import Path

from fetch_house import extract_pdf_text, parse_ptr_text

FIXTURES = Path(__file__).parent / "fixtures"


def parse_fixture(name: str):
    return parse_ptr_text(extract_pdf_text((FIXTURES / name).read_bytes()))


def test_webster_rexr_sale():
    """Filing 20034562: Hon. Daniel Webster (FL11), filed 06/01/2026."""
    rows = parse_fixture("ptr_20034562.pdf")
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "REXR"
    assert r["asset"] == "Rexford Industrial Realty, Inc. Common Stock"
    assert r["type"] == "S"
    assert r["tx_date"] == "02/26/2025"
    assert r["notif_date"] == "03/01/2025"
    assert r["amount"] == "$15,001 - $50,000"
    assert r["tag"] == "ST"


def test_pelosi_option_purchases():
    """Filing 20034836: Hon. Nancy Pelosi (CA11), filed 06/23/2026.
    Two spouse call-option buys with Description lines - the options-conviction
    path. Both descriptions are identical in the source document."""
    rows = parse_fixture("ptr_20034836.pdf")
    assert len(rows) == 2

    intc, uber = rows
    assert intc["owner"] == "SP"
    assert intc["ticker"] == "INTC"
    assert intc["asset"] == "Intel Corporation - Common Stock"
    assert intc["type"] == "P"
    assert intc["tx_date"] == "05/29/2026"
    assert intc["notif_date"] == "05/29/2026"
    assert intc["amount"] == "$1,000,001 - $5,000,000"
    assert intc["tag"] == "OP"
    assert intc["description"] == ("Purchased 200 call options with a strike "
                                   "price of $50 and an expiration date of 3/19/27.")

    assert uber["ticker"] == "UBER"
    assert uber["asset"] == "Uber Technologies, Inc. Common Stock"
    assert uber["tag"] == "OP"
    assert uber["amount"] == "$500,001 - $1,000,000"
    assert uber["description"] == intc["description"]


def test_yakym_treasury_purchase():
    """Filing 20034298: Hon. Rudy C. Yakym III (IN02), filed 04/06/2026."""
    rows = parse_fixture("ptr_20034298.pdf")
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] is None  # treasury bill - no ticker
    assert r["asset"] == "Treasury Bill (3-Month, Matures 7/9/2026)"
    assert r["type"] == "P"
    assert r["tx_date"] == "04/06/2026"
    assert r["amount"] == "$15,001 - $50,000"
    assert r["tag"] == "GS"
