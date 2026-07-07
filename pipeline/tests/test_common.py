from datetime import date

from lib.common import clean_ticker, make_trade, parse_band, parse_date, trade_id


class TestParseBand:
    def test_standard_band(self):
        assert parse_band("$1,001 - $15,000") == (1001, 15000)

    def test_band_split_across_lines_rejoined(self):
        assert parse_band("$15,001 - $50,000") == (15001, 50000)

    def test_million_band(self):
        assert parse_band("$1,000,001 - $5,000,000") == (1000001, 5000000)

    def test_over_band(self):
        assert parse_band("Over $50,000,000") == (50000001, 100000000)

    def test_plus_band(self):
        assert parse_band("$50,000,001 +") == (50000001, 100000002)

    def test_garbage(self):
        assert parse_band("Unknown") == (0, 0)
        assert parse_band(None) == (0, 0)
        assert parse_band("") == (0, 0)


class TestCleanTicker:
    def test_plain(self):
        assert clean_ticker("AAPL") == "AAPL"
        assert clean_ticker(" nvda ") == "NVDA"

    def test_class_shares(self):
        assert clean_ticker("BRK.B") == "BRK.B"
        assert clean_ticker("BF-B") == "BF-B"

    def test_rejects_placeholders(self):
        for bad in ("--", "N/A", "", None, "-"):
            assert clean_ticker(bad) is None

    def test_rejects_non_tickers(self):
        assert clean_ticker("this is not a ticker") is None


class TestDates:
    def test_us_format(self):
        assert parse_date("02/26/2025") == date(2025, 2, 26)

    def test_iso_format(self):
        assert parse_date("2026-06-15") == date(2026, 6, 15)

    def test_garbage(self):
        assert parse_date("not a date") is None


class TestTradeBuilding:
    def test_id_is_deterministic_and_prefixed(self):
        a = trade_id("congress", "senate", "X", "AAPL", "2026-01-01", "buy", 1001, 0)
        b = trade_id("congress", "senate", "X", "AAPL", "2026-01-01", "buy", 1001, 0)
        c = trade_id("congress", "senate", "X", "AAPL", "2026-01-01", "buy", 1001, 1)
        assert a == b and a != c
        assert a.startswith("C-") and len(a) == 14
        assert trade_id("insider", "acc", 0).startswith("I-")

    def test_lag_days_never_negative(self):
        t = make_trade(id="C-x", source="congress", person="A", ticker="T",
                       side="buy", tx_date=date(2026, 2, 1), filed_date=date(2026, 1, 1))
        assert t["lag_days"] == 0

    def test_lag_days(self):
        t = make_trade(id="C-x", source="congress", person="A", ticker="T",
                       side="buy", tx_date=date(2026, 1, 1), filed_date=date(2026, 2, 15))
        assert t["lag_days"] == 45
        assert t["tx_date"] == "2026-01-01" and t["filed_date"] == "2026-02-15"
