from conftest import ROOT, by_ref

from selfune_hv import ledger
from selfune_hv.checks import c13_timing as c13


def test_synthetic_statements_warn():
    f = by_ref(c13.run(ROOT))
    assert f["policy:PS01"]["verdict"] == "WARN"
    assert f["policy:PS02"]["verdict"] == "WARN"
    assert "differs from the ledger date" in f["policy:PS01"]["message"]
    assert "matches the ledger date" in f["policy:PS02"]["message"]


def test_message_states_ledger_date_and_relock():
    for f in c13.run(ROOT):
        assert "2 December 2027" in f["message"]
        assert "awaits a human re-lock" in f["message"]
        assert "retrieved 2026-11-12" in f["message"]
        assert "flag for review, not legal advice" in f["message"]


def test_hardcoded_dates_still_in_ledger():
    rows = ledger.load(str(ROOT / "ledger/hiring.jsonl"))
    for ref, _, _, date_text in c13.TOPICS.values():
        assert date_text in rows[ref]["claim"]


def test_never_fails_and_jurisdiction_gated(synthetic_root):
    statements = [
        {"stmt_id": "X1", "job_id": "J2", "text": "EU AI Act high-risk duties start 1 January 2025."},
        {"stmt_id": "X2", "job_id": "J1", "text": "EU AI Act high-risk duties start 1 January 2025."},   # J1 is NYC
        {"stmt_id": "X3", "job_id": "J2", "text": "Colorado rules start 1 January 2027."},              # J2 not CO
        {"stmt_id": "X4", "text": "Colorado rules start 1 January 2027."},                              # no job: checked
        {"stmt_id": "X5", "job_id": "J2", "text": "We review all tools yearly."},
    ]
    f = by_ref(c13.run(synthetic_root(**{"policy_statements.jsonl": statements})))
    assert set(f) == {"policy:X1", "policy:X4"}
    assert {v["verdict"] for v in f.values()} == {"WARN"}
    assert f["policy:X4"]["ledger_refs"] == ["GT-0025"]
