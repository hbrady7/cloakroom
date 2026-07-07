"""Exact-value assertions against a real eFD PTR page (committed fixture)."""
from pathlib import Path

from fetch_senate import parse_efd_ptr_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_peters_att_purchase():
    """eFD PTR 40fbe259-f282-4982-a53f-1c7278d041cd (Gary Peters, filed
    2026-06-30): single self purchase of AT&T."""
    rows = parse_efd_ptr_html((FIXTURES / "efd_ptr.html").read_text())
    assert len(rows) == 1
    r = rows[0]
    assert r["tx_date"] == "06/29/2026"
    assert r["owner"] == "Self"
    assert r["ticker"] == "T"
    assert r["asset_name"] == "AT&T Inc."
    assert r["asset_type"] == "Stock"
    assert r["type"] == "Purchase"
    assert r["amount"] == "$1,001 - $15,000"
