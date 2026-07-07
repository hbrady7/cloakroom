"""Signal engine unit tests on synthetic fixtures. No network, no wall clock.

Signal mechanics are tested through the pure per-ticker scorers
(score_ticker / caution_ticker); ranking, caps, and universe rules through
run_engine.
"""
from datetime import date

from lib.common import make_trade, trade_id
from score import (
    BROAD_ETFS, _prep, caution_ticker, decay, run_engine, score_ticker,
    size_factor,
)

AS_OF = date(2026, 7, 1)


def c_buy(person, ticker, tx, lo=15001, hi=50000, asset_type="stock", n=0, side="buy"):
    return make_trade(
        id=trade_id("congress", person, ticker, tx, side, n),
        source="congress", person=person,
        role={"chamber": "house", "party": "X", "committees": []},
        ticker=ticker, asset_type=asset_type, side=side,
        amount_low=lo, amount_high=hi,
        tx_date=tx, filed_date=tx, source_url="https://example.gov")


def i_trade(person, ticker, tx, side="buy", value=100000, planned=False, n=0):
    return make_trade(
        id=trade_id("insider", person, ticker, tx, side, n),
        source="insider", person=person, insider_title="CEO",
        ticker=ticker, asset_type="stock", side=side,
        amount_low=value, amount_high=value,
        tx_date=tx, filed_date=tx, planned_10b5_1=planned,
        source_url="https://sec.gov")


def sig(trades, ticker, person_sectors=None, ticker_sectors=None):
    """Score a single ticker through the pure per-ticker scorer."""
    return score_ticker(ticker, _prep(trades), AS_OF,
                        person_sectors or {}, ticker_sectors or [])


def caution(trades, ticker, person_sectors=None, ticker_sectors=None):
    return caution_ticker(ticker, _prep(trades), AS_OF,
                          person_sectors or {}, ticker_sectors or [])


def members(*specs):
    return [{"name": n, "first": n.split()[0], "last": n.split()[-1],
             "chamber": "house", "party": "X", "state": "ZZ",
             "committees": [], "sectors": list(s)} for n, s in specs]


class TestClusterSignal:
    def test_three_buyers_in_window_fire(self):
        trades = [c_buy(p, "NVDA", date(2026, 6, d)) for p, d in
                  [("A One", 10), ("B Two", 20), ("C Three", 28)]]
        c = sig(trades, "NVDA")
        assert c["signals"]["cluster"]["fired"] is True
        assert c["signals"]["cluster"]["distinct_buyers"] == 3

    def test_two_buyers_do_not_fire(self):
        trades = [c_buy("A One", "NVDA", date(2026, 6, 10)),
                  c_buy("B Two", "NVDA", date(2026, 6, 20))]
        assert sig(trades, "NVDA")["signals"]["cluster"]["fired"] is False

    def test_three_buyers_spread_beyond_window_do_not_fire(self):
        trades = [c_buy("A One", "NVDA", date(2026, 2, 1)),
                  c_buy("B Two", "NVDA", date(2026, 4, 1)),
                  c_buy("C Three", "NVDA", date(2026, 6, 1))]
        assert sig(trades, "NVDA")["signals"]["cluster"]["fired"] is False

    def test_same_person_thrice_is_not_a_cluster(self):
        trades = [c_buy("A One", "NVDA", date(2026, 6, d), n=d) for d in (10, 15, 20)]
        assert sig(trades, "NVDA")["signals"]["cluster"]["fired"] is False


class TestConvergenceSignal:
    def base(self):
        return [c_buy("A One", "LMT", date(2026, 6, 15))]

    def test_two_insider_buyers_within_45d_fire(self):
        trades = self.base() + [i_trade("Ceo Person", "LMT", date(2026, 6, 1)),
                                i_trade("Cfo Person", "LMT", date(2026, 6, 20))]
        c = sig(trades, "LMT")
        assert c["signals"]["convergence"]["fired"] is True
        assert c["signals"]["convergence"]["insider_buyers"] == ["Ceo Person", "Cfo Person"]

    def test_planned_10b5_1_buys_do_not_count(self):
        trades = self.base() + [
            i_trade("Ceo Person", "LMT", date(2026, 6, 1), planned=True),
            i_trade("Cfo Person", "LMT", date(2026, 6, 20), planned=True)]
        assert sig(trades, "LMT")["signals"]["convergence"]["fired"] is False

    def test_single_insider_does_not_fire(self):
        trades = self.base() + [i_trade("Ceo Person", "LMT", date(2026, 6, 1))]
        assert sig(trades, "LMT")["signals"]["convergence"]["fired"] is False

    def test_insiders_outside_45d_do_not_fire(self):
        trades = self.base() + [i_trade("Ceo Person", "LMT", date(2026, 4, 1)),
                                i_trade("Cfo Person", "LMT", date(2026, 4, 10))]
        assert sig(trades, "LMT")["signals"]["convergence"]["fired"] is False

    def test_convergence_outranks_lone_cluster(self):
        conv = self.base() + [i_trade("Ceo Person", "LMT", date(2026, 6, 10)),
                              i_trade("Cfo Person", "LMT", date(2026, 6, 20))]
        clus = [c_buy(p, "NVDA", date(2026, 6, d), lo=1001, hi=15000) for p, d in
                [("A One", 10), ("B Two", 20), ("C Three", 28)]]
        out = run_engine(conv + clus, [], {}, AS_OF)
        assert out["candidates"][0]["ticker"] == "LMT"


class TestCommitteeAndOptions:
    def test_committee_alignment_fires_on_sector_overlap(self):
        trades = [c_buy("A One", "LMT", date(2026, 6, 15))]
        c = sig(trades, "LMT", person_sectors={"A One": ["defense"]},
                ticker_sectors=["defense", "aerospace"])
        assert c["signals"]["committee"]["fired"] is True
        assert c["signals"]["committee"]["aligned_buyers"] == ["A One"]

    def test_no_overlap_no_fire(self):
        trades = [c_buy("A One", "LMT", date(2026, 6, 15))]
        c = sig(trades, "LMT", person_sectors={"A One": ["ag"]},
                ticker_sectors=["defense"])
        assert c["signals"]["committee"]["fired"] is False

    def test_option_position_boosts_score(self):
        plain = sig([c_buy("A One", "INTC", date(2026, 6, 15))], "INTC")
        opt = sig([c_buy("A One", "INTC", date(2026, 6, 15), asset_type="option",
                         lo=1000001, hi=5000000)], "INTC")
        assert opt["signals"]["options"]["fired"] is True
        assert opt["score"] > plain["score"]


class TestDecayAndDeterminism:
    def test_decay_halves_every_14_days(self):
        assert decay(AS_OF, AS_OF) == 1.0
        assert abs(decay(AS_OF, date(2026, 6, 17)) - 0.5) < 1e-9
        assert decay(AS_OF, date(2026, 5, 18)) < 0.15

    def test_size_factor_log_scale(self):
        assert size_factor(1000, 1000) == 1.0
        assert abs(size_factor(100000, 100000) - 3.0) < 1e-9

    def test_fresh_signal_beats_stale_identical_signal(self):
        fresh = [c_buy(p, "AAA", date(2026, 6, d)) for p, d in
                 [("A One", 20), ("B Two", 25), ("C Three", 28)]]
        stale = [c_buy(p, "BBB", date(2026, 3, d)) for p, d in
                 [("A One", 20), ("B Two", 25), ("C Three", 28)]]
        assert sig(fresh, "AAA")["score"] > sig(stale, "BBB")["score"]

    def test_engine_is_deterministic(self):
        trades = [c_buy(p, "NVDA", date(2026, 6, d)) for p, d in
                  [("A One", 10), ("B Two", 20), ("C Three", 28)]]
        assert run_engine(trades, [], {}, AS_OF) == run_engine(trades, [], {}, AS_OF)

    def test_every_evidence_id_references_an_input_trade(self):
        trades = ([c_buy(p, "LMT", date(2026, 6, d)) for p, d in
                   [("A One", 10), ("B Two", 20), ("C Three", 28)]] +
                  [i_trade("Ceo Person", "LMT", date(2026, 6, 10)),
                   i_trade("Cfo Person", "LMT", date(2026, 6, 20))])
        ids = {t["id"] for t in trades}
        out = run_engine(trades, [], {}, AS_OF)
        assert out["candidates"], "expected LMT to be a candidate"
        for c in out["candidates"] + out["caution"]:
            for e in c["evidence"]:
                assert e["id"] in ids


class TestCautionList:
    def test_sell_cluster_flags(self):
        trades = [c_buy(p, "TSLA", date(2026, 6, d), side="sell") for p, d in
                  [("A One", 10), ("B Two", 15), ("C Three", 20)]]
        w = caution(trades, "TSLA")
        assert w is not None
        assert w["signals"]["sell_cluster"]["fired"] is True

    def test_insider_distribution_two_officers(self):
        trades = [i_trade("Ceo Person", "MSTR", date(2026, 6, 10), side="sell"),
                  i_trade("Cfo Person", "MSTR", date(2026, 6, 15), side="sell")]
        w = caution(trades, "MSTR")
        assert w is not None
        assert w["signals"]["insider_distribution"]["fired"] is True

    def test_planned_sales_are_half_weighted(self):
        trades = [i_trade("Ceo Person", "MSTR", date(2026, 6, 10), side="sell", planned=True),
                  i_trade("Cfo Person", "MSTR", date(2026, 6, 15), side="sell", planned=True)]
        assert caution(trades, "MSTR") is None  # weight 1.0 < 2.0 threshold

    def test_caution_feeds_engine_output(self):
        trades = [c_buy(p, "TSLA", date(2026, 6, d), side="sell") for p, d in
                  [("A One", 10), ("B Two", 15), ("C Three", 20)]]
        out = run_engine(trades, [], {}, AS_OF)
        assert [w["ticker"] for w in out["caution"]] == ["TSLA"]


class TestUniverseRules:
    def test_broad_etfs_never_become_candidates(self):
        assert "SPY" in BROAD_ETFS
        trades = [c_buy(p, "SPY", date(2026, 6, d), asset_type="etf") for p, d in
                  [("A One", 10), ("B Two", 20), ("C Three", 28)]]
        out = run_engine(trades, [], {}, AS_OF)
        assert not any(c["ticker"] == "SPY" for c in out["candidates"])

    def test_top15_cap_and_ordering(self):
        trades = []
        for i in range(20):
            tick = f"T{i:02d}"
            trades += [c_buy(p, tick, date(2026, 6, 10 + j), lo=1001 * (i + 1),
                             hi=15000 * (i + 1))
                       for j, p in enumerate(["A One", "B Two", "C Three"])]
        out = run_engine(trades, [], {}, AS_OF)
        assert len(out["candidates"]) == 15
        scores = [c["score"] for c in out["candidates"]]
        assert scores == sorted(scores, reverse=True)
