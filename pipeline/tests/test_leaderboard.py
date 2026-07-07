from datetime import date

from lib.common import make_trade, trade_id
from leaderboard import build_leaderboard

PRICES = {
    "SPY": [["2026-06-01", 100.0], ["2026-06-02", 100.0], ["2026-06-30", 102.0]],
    "WIN": [["2026-06-01", 10.0], ["2026-06-02", 10.0], ["2026-06-30", 12.0]],
    "LOSE": [["2026-06-01", 10.0], ["2026-06-02", 10.0], ["2026-06-30", 9.0]],
}


def trade(person, ticker, side="buy", filed=date(2026, 6, 1), n=0):
    return make_trade(
        id=trade_id("congress", person, ticker, side, n),
        source="congress", person=person,
        role={"chamber": "house", "party": "X", "committees": []},
        ticker=ticker, asset_type="stock", side=side,
        amount_low=1001, amount_high=15000,
        tx_date=filed, filed_date=filed, source_url="")


def five(person, ticker, side="buy"):
    return [trade(person, ticker, side=side, n=i) for i in range(5)]


def test_buy_excess_is_return_minus_spy():
    rows = build_leaderboard(five("A One", "WIN"), PRICES, [])
    assert len(rows) == 1
    # WIN +20%, SPY +2% -> excess 18% on every scored trade
    assert abs(rows[0]["avg_excess"] - 0.18) < 1e-6
    assert rows[0]["trades_scored"] == 5
    assert rows[0]["win_rate"] == 1.0


def test_sell_gets_credit_for_dodging_underperformance():
    rows = build_leaderboard(five("B Two", "LOSE", side="sell"), PRICES, [])
    # LOSE -10% vs SPY +2% -> selling scored +12%
    assert abs(rows[0]["avg_excess"] - 0.12) < 1e-6


def test_min_trades_gate():
    rows = build_leaderboard([trade("C Three", "WIN")], PRICES, [])
    assert rows == []


def test_missing_price_series_is_skipped_not_fatal():
    trades = five("D Four", "WIN") + [trade("D Four", "NOPRICE", n=9)]
    rows = build_leaderboard(trades, PRICES, [])
    assert rows[0]["trades_scored"] == 5
