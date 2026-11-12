import json

from conftest import ROOT, by_ref

from selfune_hv import ledger
from selfune_hv.checks import c13_timing as c13


def _set_row(root, rid, **fields):
    path = root / "ledger/hiring.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    for r in rows:
        if r["id"] == rid:
            r.update(fields)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_locked_row_normal_rules():
    f = by_ref(c13.run(ROOT))
    assert f["policy:PS01"]["verdict"] == "CONTRADICTED"   # 2 August 2026 vs locked 2 December 2027
    assert f["policy:PS02"]["verdict"] == "VERIFIED"       # matches
    assert "differs from the ledger date" in f["policy:PS01"]["message"]
    assert "matches the ledger date" in f["policy:PS02"]["message"]


def test_message_states_ledger_date_and_citation():
    for f in c13.run(ROOT):
        assert "2 December 2027" in f["message"]
        assert "GT-0009 is LOCKED" in f["message"]
        assert "retrieved 2026-11-12" in f["message"]
        assert "flag for review, not legal advice" in f["message"]


def test_contested_row_is_warn_only(synthetic_root):
    root = synthetic_root()
    _set_row(root, "GT-0009", status="CONTESTED", use_as="warn_only")
    f = by_ref(c13.run(root))
    assert {v["verdict"] for v in f.values()} == {"WARN"}
    assert "GT-0009 is CONTESTED: warning only." in f["policy:PS01"]["message"]


def test_pending_row_softens_contradiction(synthetic_root):
    root = synthetic_root()
    _set_row(root, "GT-0009", user_decision="PENDING_RELOCK")
    f = by_ref(c13.run(root))
    assert f["policy:PS01"]["verdict"] == "WARN" and "awaits a human re-lock" in f["policy:PS01"]["message"]
    assert f["policy:PS02"]["verdict"] == "VERIFIED"


def test_statement_without_date_is_unverified(synthetic_root):
    root = synthetic_root(**{"policy_statements.jsonl": [
        {"stmt_id": "X1", "job_id": "J2", "text": "EU AI Act high-risk duties apply to our screening tool soon."}]})
    assert by_ref(c13.run(root))["policy:X1"]["verdict"] == "UNVERIFIED"


def test_hardcoded_dates_still_in_ledger():
    rows = ledger.load(str(ROOT / "ledger/hiring.jsonl"))
    for ref, _, _, date_text in c13.TOPICS.values():
        assert date_text in rows[ref]["claim"]


def test_jurisdiction_gated(synthetic_root):
    statements = [
        {"stmt_id": "X1", "job_id": "J2", "text": "EU AI Act high-risk duties start 1 January 2025."},
        {"stmt_id": "X2", "job_id": "J1", "text": "EU AI Act high-risk duties start 1 January 2025."},   # J1 is NYC
        {"stmt_id": "X3", "job_id": "J2", "text": "Colorado rules start 1 January 2027."},              # J2 not CO
        {"stmt_id": "X4", "text": "Colorado rules start 1 January 2027."},                              # no job: checked
        {"stmt_id": "X5", "job_id": "J2", "text": "We review all tools yearly."},
    ]
    f = by_ref(c13.run(synthetic_root(**{"policy_statements.jsonl": statements})))
    assert set(f) == {"policy:X1", "policy:X4"}
    assert f["policy:X1"]["verdict"] == "CONTRADICTED"
    assert f["policy:X4"]["verdict"] == "VERIFIED" and f["policy:X4"]["ledger_refs"] == ["GT-0025"]
