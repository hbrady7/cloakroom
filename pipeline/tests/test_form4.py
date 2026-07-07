"""Exact-value assertions against real SEC Form 4 XML (committed fixtures)."""
from pathlib import Path

from fetch_edgar import parse_form4

FIXTURES = Path(__file__).parent / "fixtures"


def test_open_market_buys_parse_exactly():
    """AUBN Form 4 (acc 0001193125-26-295042, filed 2026-07-02):
    SVP Shannon O'Donnell, two open-market purchases, not 10b5-1."""
    parsed = parse_form4((FIXTURES / "form4_open_market_buy.xml").read_bytes())
    assert parsed["ticker"] == "AUBN"
    assert parsed["owner"] == "O'Donnell Shannon"
    assert parsed["title"] == "Senior Vice President"
    assert parsed["is_officer"] is True
    assert parsed["is_director"] is False
    assert parsed["aff10b5_one"] is False

    assert len(parsed["transactions"]) == 2
    t1, t2 = parsed["transactions"]
    assert (t1["code"], t1["date"], t1["shares"], t1["price"], t1["value"]) == \
        ("P", "2026-07-02", 16.0, 26.9, 430)
    assert (t2["code"], t2["date"], t2["shares"], t2["price"], t2["value"]) == \
        ("P", "2026-07-02", 11.0, 26.01, 286)
    assert t1["acquired"] == "A"


def test_non_open_market_codes_are_excluded():
    """AAPL Form 4 (SVP option exercise): codes M and F only - none of them
    are open-market transactions, so no P/S rows come out."""
    parsed = parse_form4((FIXTURES / "form4_no_open_market.xml").read_bytes())
    assert parsed["ticker"] == "AAPL"
    assert parsed["owner"] == "Newstead Jennifer"
    assert parsed["title"] == "SVP, GC and Secretary"
    assert parsed["transactions"] == []
