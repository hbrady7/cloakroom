from datetime import date

from lib.common import make_trade
from merge_trades import merge


def _t(id="C-aaaaaaaaaaaa", filed=date(2026, 6, 1), **kw):
    base = dict(id=id, source="congress", person="A Member", ticker="AAPL",
                side="buy", amount_low=1001, amount_high=15000,
                tx_date=date(2026, 5, 20), filed_date=filed,
                source_url="https://example.gov/1")
    base.update(kw)
    return make_trade(**base)


def test_window_filters_old_filings():
    fresh = _t(id="C-000000000001", filed=date(2026, 6, 1))
    stale = _t(id="C-000000000002", filed=date(2025, 11, 1))
    trades, invalid = merge([[fresh, stale]], "2026-01-07")
    assert [t["id"] for t in trades] == ["C-000000000001"]
    assert invalid == 0


def test_dedupes_by_id_across_sources():
    a = _t(id="C-000000000003")
    trades, _ = merge([[a], [dict(a)]], "2026-01-07")
    assert len(trades) == 1


def test_drops_schema_invalid_rows():
    bad = _t(id="C-000000000004")
    bad["side"] = "hold"  # not a valid side
    good = _t(id="C-000000000005")
    trades, invalid = merge([[bad, good]], "2026-01-07")
    assert [t["id"] for t in trades] == ["C-000000000005"]
    assert invalid == 1


def test_sorted_by_filed_then_tx_desc():
    older = _t(id="C-000000000006", filed=date(2026, 5, 1))
    newer = _t(id="C-000000000007", filed=date(2026, 6, 15))
    trades, _ = merge([[older, newer]], "2026-01-07")
    assert [t["id"] for t in trades] == ["C-000000000007", "C-000000000006"]
