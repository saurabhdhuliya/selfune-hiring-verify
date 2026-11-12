from conftest import ROOT, by_ref

from selfune_hv.checks import c14_india_dpdp as c14


def test_synthetic():
    f = by_ref(c14.run(ROOT))
    assert f["tool:T9:consent"]["verdict"] == "ESCALATE"
    assert f["tool:T9:retention"]["verdict"] == "ESCALATE"
    assert "tool:T9:dpdp" not in f
    assert f["tool:T10:dpdp"]["verdict"] == "VERIFIED"
    assert f["tool:T11:dpdp"]["verdict"] == "VERIFIED"
    assert {k.split(":")[1] for k in f} == {"T9", "T10", "T11"}   # IN jobs only


def test_retention_rules():
    assert c14.check_retention({"retention_days": "indefinite"})[0] == "ESCALATE"
    assert c14.check_retention({"retention_days": "Indefinite "})[0] == "ESCALATE"
    assert c14.check_retention({"retention_days": None})[0] == "ESCALATE"
    assert c14.check_retention({})[0] == "NOT_CHECKED"
    assert c14.check_retention({"retention_days": 180})[0] == "VERIFIED"
    assert c14.check_retention({"retention_days": "until role filled"})[0] == "UNVERIFIED"
    assert c14.check_retention({"retention_days": 0})[0] == "UNVERIFIED"


def test_consent_rules():
    assert c14.check_consent({"consent_notice": None})[0] == "ESCALATE"
    assert c14.check_consent({})[0] == "NOT_CHECKED"
    assert c14.check_consent({"consent_notice": "2026-08-01"})[0] == "VERIFIED"


def test_one_gap_reports_only_that_aspect(synthetic_root):
    tools = [{"tool_id": "TX", "job_ids": ["J3"], "consent_notice": "2026-08-01", "retention_days": "indefinite"}]
    f = by_ref(c14.run(synthetic_root(**{"tools.json": tools})))
    assert set(f) == {"tool:TX:retention"}


def test_message_has_timing_caveat_and_citation():
    for f in c14.run(ROOT):
        assert "flag for review, not legal advice" in f["message"]
        assert "18 months" in f["message"]
        assert "GT-0030" in f["message"] and "retrieved 2026-11-11" in f["message"]
