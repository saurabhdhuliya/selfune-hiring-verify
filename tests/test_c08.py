import pytest
from conftest import ROOT, by_ref

from selfune_hv.checks import c08_age_proxy as c08


def test_synthetic_tools_and_decisions():
    f = by_ref(c08.run(ROOT))
    assert f["tool:T9:age_rule"]["verdict"] == "ESCALATE"
    assert "tool:T9:rules" not in f
    assert f["tool:T10:rules"]["verdict"] == "VERIFIED"
    assert f["decision:D0152"]["verdict"] == "ESCALATE"
    assert f["decision:D0153"]["verdict"] == "VERIFIED"
    assert f["decision:D0156"]["verdict"] == "VERIFIED"
    # D0152 is the only decision in the synthetic set with an age term.
    assert [k for k, v in f.items() if k.startswith("decision:") and v["verdict"] != "VERIFIED"] == ["decision:D0152"]


@pytest.mark.parametrize("text", [
    "auto-reject if graduation_year < 1995",
    "Graduation year 1991",
    "reject if age > 50",
    "Candidates aged 55 or older",
    "date of birth before 1970",
    "DOB required",
    "birth year after 1990",
    "year of birth",
    "more than 20 years since graduation",
])
def test_age_terms_detected(text):
    assert c08.age_terms(text)


@pytest.mark.parametrize("text", [
    "Auto-rejected by AgeSmart Filter",
    "Rejected at screen stage",
    "Managed a team; average handle time 4 min",
    "Minimum 5 years of experience",
    "Agency placement",
])
def test_no_false_positives(text):
    assert c08.age_terms(text) == []


def test_legal_message_and_citation():
    f = by_ref(c08.run(ROOT))
    for key in ("tool:T9:age_rule", "decision:D0152"):
        assert "flag for review, not legal advice" in f[key]["message"]
        assert "GT-0027" in f[key]["message"] and "retrieved 2026-11-11" in f[key]["message"]
        assert f[key]["ledger_refs"] == ["GT-0027", "GT-0024"]


def test_custom_tool_and_decision(synthetic_root):
    tools = [{"tool_id": "TX", "job_ids": ["J1"], "rules": ["reject if years since graduation > 25"]},
             {"tool_id": "TY", "job_ids": ["J1"], "rules": ["reject if typing speed < 40 wpm"]}]
    decisions = [{"decision_id": "DX", "reason_text": "Too old: date of birth 1960."},
                 {"decision_id": "DY", "reason_text": "Scored 41/100 on the knowledge test."}]
    f = by_ref(c08.run(synthetic_root(**{"tools.json": tools, "decisions.jsonl": decisions})))
    assert f["tool:TX:age_rule"]["verdict"] == "ESCALATE"
    assert f["tool:TY:rules"]["verdict"] == "VERIFIED"
    assert f["decision:DX"]["verdict"] == "ESCALATE"
    assert f["decision:DY"]["verdict"] == "VERIFIED"
