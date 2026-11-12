import pytest
from conftest import ROOT, by_ref

from selfune_hv.checks import c11_gdpr_art22 as c11


def test_synthetic():
    f = by_ref(c11.run(ROOT))
    assert f["tool:T5"]["verdict"] == "ESCALATE"
    assert f["tool:T7"]["verdict"] == "VERIFIED"
    assert f["tool:T8"]["verdict"] == "VERIFIED"
    assert f["decision:D0082"]["verdict"] == "ESCALATE"
    assert f["decision:D0084"]["verdict"] == "VERIFIED"
    assert f["decision:D0085"]["verdict"] == "NOT_CHECKED"


def test_eu_jobs_only():
    f = by_ref(c11.run(ROOT))
    assert {k for k in f if k.startswith("tool:")} == {"tool:T5", "tool:T6", "tool:T7", "tool:T8"}
    assert "tool:T9" not in f   # J3 tool decides alone, but J3 is not EU


@pytest.mark.parametrize("reason,expected", [
    ("Auto-rejected: score 64 below 70. No human review.", False),
    ("Rejected without human review.", False),
    ("Rejected after human review of the score.", True),
    ("Score below cut-off; reviewed by a human recruiter.", True),
])
def test_reason_human_review(reason, expected):
    assert c11.reason_shows_human_review(reason) is expected


def test_tool_rules():
    assert c11.evaluate_tool({"decision_mode": "alone", "human_review": True, "lawful_basis": None})[0] == "ESCALATE"
    assert c11.evaluate_tool({"decision_mode": "alone", "human_review": False, "lawful_basis": "consent"})[0] == "ESCALATE"
    assert c11.evaluate_tool({"decision_mode": "alone", "human_review": True, "lawful_basis": "consent"})[0] == "VERIFIED"
    assert c11.evaluate_tool({"decision_mode": "alone"})[0] == "NOT_CHECKED"
    assert c11.evaluate_tool({"decision_mode": "advisory", "human_review": False})[0] == "VERIFIED"


def test_decision_rules():
    assert c11.evaluate_decision({"decided_by": "tool", "reason_text": "Auto-rejected."})[0] == "ESCALATE"
    assert c11.evaluate_decision({"decided_by": "tool", "reason_text": "Tool flag, then human review."})[0] == "VERIFIED"
    assert c11.evaluate_decision({"decided_by": "both", "reason_text": "x"})[0] == "VERIFIED"
    assert c11.evaluate_decision({"reason_text": "x"})[0] == "NOT_CHECKED"


def test_message_and_citation():
    for f in c11.run(ROOT):
        assert "flag for review, not legal advice" in f["message"]
        assert "retrieved 2026-11-11" in f["message"]
        assert f["ledger_refs"] == ["GT-0048", "GT-0049"]
