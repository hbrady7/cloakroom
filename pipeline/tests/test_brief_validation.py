"""The brief validator is the grounding enforcement layer - test it hard."""
import copy

from validate_brief import validate

CAND = {
    "as_of": "2026-07-01",
    "candidates": [{"ticker": "LMT"}, {"ticker": "NVDA"}],
    "caution": [{"ticker": "TSLA"}],
}
TRADES = [{"id": "C-1a2b3c4d5e6f"}, {"id": "I-9f8e7d6c5b4a"}]

VALID = {
    "date": "2026-07-01",
    "regime_note": "SPY rose over the last 30 days per price context.",
    "picks": [{
        "ticker": "LMT",
        "direction": "long",
        "conviction": "medium",
        "thesis": "Three members bought within a month while two insiders added stock.",
        "evidence_ids": ["C-1a2b3c4d5e6f", "I-9f8e7d6c5b4a"],
        "key_risks": ["Disclosure lag means entries may be stale."],
        "invalidation": "Cluster members file sales.",
        "expression": {"simple": "common shares",
                       "defined_risk_note": None},
    }],
    "caution_list": [{"ticker": "TSLA", "reason": "Sell cluster of three members.",
                      "evidence_ids": ["C-1a2b3c4d5e6f"]}],
    "skipped": [{"ticker": "NVDA", "reason": "Single stale filer only."}],
}


def check(brief):
    return validate(brief, cand=CAND, trades=TRADES)


def test_valid_brief_passes():
    assert check(VALID) == []


def test_unknown_evidence_id_rejected():
    b = copy.deepcopy(VALID)
    b["picks"][0]["evidence_ids"] = ["C-000000000000"]
    assert any("unknown evidence id" in e for e in check(b))


def test_hallucinated_ticker_rejected():
    b = copy.deepcopy(VALID)
    b["picks"][0]["ticker"] = "GME"
    assert any("not an engine candidate" in e for e in check(b))


def test_wrong_date_rejected():
    b = copy.deepcopy(VALID)
    b["date"] = "2026-06-30"
    assert any("as_of" in e for e in check(b))


def test_unaccounted_candidate_rejected():
    b = copy.deepcopy(VALID)
    b["skipped"] = []  # NVDA now neither picked nor skipped
    assert any("neither picked nor skipped" in e for e in check(b))


def test_schema_rejects_prose_extras_and_bad_enums():
    b = copy.deepcopy(VALID)
    b["picks"][0]["direction"] = "short"
    assert any(e.startswith("schema:") for e in check(b))

    b2 = copy.deepcopy(VALID)
    b2["commentary"] = "extra field"
    assert any(e.startswith("schema:") for e in check(b2))


def test_missing_evidence_ids_rejected_by_schema():
    b = copy.deepcopy(VALID)
    b["picks"][0]["evidence_ids"] = []
    assert any(e.startswith("schema:") for e in check(b))
