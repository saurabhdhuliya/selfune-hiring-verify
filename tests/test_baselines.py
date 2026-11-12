"""Tests for the rule-based baselines C01, C02, C03, C06, C15."""
from datetime import date

import pytest
from conftest import ROOT, by_ref

from selfune_hv.checks import c01_undefined_trait as c01
from selfune_hv.checks import c02_years_proxy as c02
from selfune_hv.checks import c03_no_reason as c03
from selfune_hv.checks import c06_missing_field as c06
from selfune_hv.checks import c15_vendor_claim as c15
from selfune_hv.role_memory import RoleMemory

TODAY = date(2026, 11, 12)
BASELINES = [c01, c02, c03, c06, c15]


@pytest.mark.parametrize("mod", BASELINES)
def test_marked_as_baseline(mod):
    assert mod.BASELINE is True
    assert "baseline - AVL agent mode will handle unclear cases later" in mod.__doc__


# ---------------------------------------------------------------- C01
def test_c01_synthetic():
    f = by_ref(c01.run(ROOT, today=TODAY))
    for ref in ("requirement:J1-R1", "requirement:J1-R4", "requirement:J2-R5", "requirement:J3-R1", "ai_text:AT01"):
        assert f[ref]["verdict"] == "UNVERIFIED", ref
    for ref in ("requirement:J1-R2", "requirement:J3-R2", "ai_text:AT02"):
        assert f[ref]["verdict"] == "VERIFIED", ref
    assert f["requirement:J2-R1"]["verdict"] == "VERIFIED"
    assert f["requirement:J2-R1"]["trait_ref"] == "TR-J2-PY"
    assert f["requirement:J2-R2"]["trait_ref"] == "TR-J2-PROD"


def test_c01_stale_definition_asks_again():
    f = by_ref(c01.run(ROOT, today=TODAY))["requirement:J3-R1"]
    assert "stale" in f["message"] and f["trait_ref"] == "TR-J3-DETAIL"


def test_c01_questions_under_25_words():
    for f in c01.run(ROOT, today=TODAY):
        if f["verdict"] == "UNVERIFIED":
            assert 0 < len(f["question"].split()) < 25


def test_c01_long_requirement_question_still_short():
    long_text = ("Strong ability to coordinate many teams across several regions while keeping every stakeholder "
                 "informed about progress, risks, dependencies and changes on a weekly basis")
    memory = RoleMemory({"roles": []}, TODAY)
    v, _, extra = c01.evaluate(long_text, "JX", "Programme Manager", memory)
    assert v == "UNVERIFIED" and len(extra["question"].split()) < 25


@pytest.mark.parametrize("text", [
    "Strong communication: scores 4 of 5 on the structured interview rubric.",
    "Good written English, tested in the work sample.",
    "Resolves at least 85% of tickets in 24 hours.",
])
def test_c01_measured_trait_is_verified(text):
    v, _, _ = c01.evaluate(text, "JX", "Role", RoleMemory({"roles": []}, TODAY))
    assert v == "VERIFIED"


def test_c01_found_but_extra_vague_word_is_unverified():
    memory = RoleMemory.load(str(ROOT / "data/synthetic/role_memory.json"), TODAY)
    v, _, extra = c01.evaluate("Strong Python skills and a great team player.", "J2", "Backend Engineer", memory)
    assert v == "UNVERIFIED" and extra["trait_ref"] == "TR-J2-PY"


def test_c01_word_boundaries():
    assert c01.trait_words("Response time drives renewals; goods in transit.") == []


# ---------------------------------------------------------------- C02
def test_c02_synthetic():
    f = by_ref(c02.run(ROOT))
    for r in ("J1-R3", "J2-R3", "J3-R3"):
        assert f[f"requirement:{r}"]["verdict"] == "UNVERIFIED"
    for r in ("J2-R4", "J3-R6"):
        assert f[f"requirement:{r}"]["verdict"] == "VERIFIED"


@pytest.mark.parametrize("text,hit", [
    ("Minimum 5 years of support experience.", True),
    ("3+ years of Go.", True),
    ("5-7 years in operations.", True),
    ("Five years managing a team.", True),
    ("Has used SQL to answer a business question.", False),
    ("Candidates 18 years old or over.", False),   # age, not experience: C08's job
    ("Resolves 85% of tickets within 24 hours.", False),
])
def test_c02_years_pattern(text, hit):
    assert bool(c02.years_counts(text)) is hit


# ---------------------------------------------------------------- C03
def test_c03_synthetic():
    f = by_ref(c03.run(ROOT))
    for r in ("J1-R5", "J3-R4", "J3-R5"):
        assert f[f"requirement:{r}"]["verdict"] == "UNVERIFIED"
    for r in ("J1-R2", "J2-R4", "J3-R2"):
        assert f[f"requirement:{r}"]["verdict"] == "VERIFIED"


@pytest.mark.parametrize("text,has_reason", [
    ("Python skills, because the backend is Python.", True),
    ("SQL, so that reports can be self-served.", True),
    ("Forklift licence, required by state law.", True),
    ("Spanish, to support LATAM customers.", True),
    ("Typing speed of 60 words per minute.", False),
    ("Has contributed to open-source projects.", False),   # "to" here is not a purpose clause
])
def test_c03_reason_detection(text, has_reason):
    assert (c03.stated_reason(text) is not None) is has_reason


# ---------------------------------------------------------------- C06
def test_c06_synthetic():
    f = by_ref(c06.run(ROOT))
    for d in ("D0001", "D0002", "D0081", "D0151"):
        assert f[f"decision:{d}"]["verdict"] == "UNVERIFIED"
    for d in ("D0004", "D0083", "D0153", "D0154"):
        assert f[f"decision:{d}"]["verdict"] == "VERIFIED"


def test_c06_rules():
    assert c06.evaluate({"fields_missing": ["x"], "outcome": "rejected"})[0] == "UNVERIFIED"
    assert c06.evaluate({"fields_missing": ["x"], "outcome": "on_hold"})[0] == "VERIFIED"
    assert c06.evaluate({"fields_missing": ["x"], "outcome": "advanced"})[0] == "VERIFIED"
    assert c06.evaluate({"fields_missing": [], "outcome": "rejected"})[0] == "VERIFIED"
    assert c06.evaluate({"outcome": "rejected"})[0] == "NOT_CHECKED"


# ---------------------------------------------------------------- C15
def test_c15_synthetic():
    f = by_ref(c15.run(ROOT))
    for ref in ("decision:D0003", "decision:D0155", "ai_text:AT03"):
        assert f[ref]["verdict"] == "UNVERIFIED"
    assert f["ai_text:AT04"]["verdict"] == "VERIFIED"
    assert f["tool:T8:vendor_claim"]["verdict"] == "VERIFIED"


@pytest.mark.parametrize("text,expected", [
    ("Rejected: vendor reports 95% accuracy.", "UNVERIFIED"),
    ("The detector proves the candidate cheated.", "UNVERIFIED"),
    ("Industry data shows 40% exaggerate.", "UNVERIFIED"),
    ("Vendor states it measures grit. Not independently validated; not used as decision evidence.", "VERIFIED"),
    ("Work sample 44/100, below pre-set 60.", "VERIFIED"),
])
def test_c15_text_rules(text, expected):
    assert c15.evaluate_text(text)[0] == expected


def test_c15_tool_flagged_when_named_in_flagged_text(synthetic_root):
    decisions = [{"decision_id": "DX", "reason_text": "Rejected: vendor says SheetTest measures critical thinking."}]
    tools = [{"tool_id": "TZ", "job_ids": ["J3"], "name": "SheetTest", "vendor_claims": ["Measures critical thinking."]}]
    f = by_ref(c15.run(synthetic_root(**{"decisions.jsonl": decisions, "tools.json": tools})))
    assert f["tool:TZ:vendor_claim"]["verdict"] == "UNVERIFIED"
