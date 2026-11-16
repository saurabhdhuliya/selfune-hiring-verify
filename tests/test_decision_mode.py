"""Decision mode: one decision's reasoning -> C06, C08, C09, C11, C15. Same rules as the full loop."""
import json
import re

import pytest
from conftest import ROOT

from selfune_hv.decision_mode import parse_fields, verify_decision
from selfune_hv.text_mode import lines_from_claims, verify_text


def v(*a, **k):
    return verify_decision(*a, root=ROOT, **k)


def verdicts(r):
    return {f["check"]: f["verdict"] for f in r["findings"]}


def test_runs_exactly_the_five_checks():
    r = v("Work sample 72/100.", "advanced", "human", "EU")
    assert [f["check"] for f in r["findings"]] == ["C06", "C08", "C09", "C11", "C15"]


def test_c06_missing_field_used_against_rejected():
    r = v("No references on file.", "rejected", "human", "other", fields_missing="references")
    assert verdicts(r)["C06"] == "UNVERIFIED"
    assert any("references" in q["ask"] for q in r["human_questions"])


def test_c06_not_checked_without_a_field_list():
    r = v("Weak answers.", "rejected", "human", "other")
    assert verdicts(r)["C06"] == "NOT_CHECKED" and "C06" in r["not_checked"]
    assert not any("applicant supply" in q["ask"] for q in r["human_questions"])


def test_c08_age_proxy_escalates_and_asks_for_job_related_reason():
    r = v("Graduation year 2012 is too early.", "rejected", "human", "NYC")
    assert verdicts(r)["C08"] == "ESCALATE" and r["status"] == "ESCALATE" and r["high_risk"]
    assert any("other than age" in q["ask"] for q in r["human_questions"])


def test_c09_emotion_inference_blocks_the_chain():
    r = v("Candidate video analysis: dominant emotion anxiety.", "rejected", "both", "other")
    assert verdicts(r)["C09"] == "ESCALATE" and r["blocked"] and r["status"] == "ESCALATE"
    assert any("replace this emotion" in q["ask"] for q in r["human_questions"])


def test_c11_only_for_eu_jobs():
    r = v("Rejected by the screening tool.", "rejected", "tool", "EU")
    assert verdicts(r)["C11"] == "ESCALATE" and r["high_risk"]
    r = v("Rejected by the screening tool.", "rejected", "tool", "NYC")
    assert verdicts(r)["C11"] == "NOT_CHECKED" and "C11" in r["not_checked"]


def test_c11_eu_without_decided_by_asks_who_decided():
    r = v("Weak answers.", "rejected", None, "EU")
    assert verdicts(r)["C11"] == "NOT_CHECKED"
    assert any("person, a tool, or both" in q["ask"] for q in r["human_questions"])


def test_c11_human_review_in_reason_passes_for_tool():
    assert verdicts(v("Tool screen, then reviewed by a human reviewer.", "rejected", "tool", "EU"))["C11"] == "VERIFIED"


def test_c15_vendor_claim_as_proof():
    r = v("The vendor AI rated low potential; vendor reports 95% accuracy.", "rejected", "human", "other")
    assert verdicts(r)["C15"] == "UNVERIFIED"
    assert any("your own process" in q["ask"] for q in r["human_questions"])


def test_clean_decision_has_no_flags():
    r = v("Work sample 72/100, above the pre-set 60.", "advanced", "human", "EU", fields_missing="")
    assert r["status"] == "VERIFIED" and r["human_questions"] == [] and r["weakest_link"] is None


def test_matches_full_loop_rules_on_same_reason():
    from selfune_hv.checks import c15_vendor_claim as c15
    reason = "Rejected: vendor AI says low potential; accuracy 95%."
    assert verdicts(v(reason, "rejected", "human", "other"))["C15"] == c15.evaluate_text(reason)[0]


def test_every_question_under_25_words_and_no_person_language():
    r = v("Graduation year 2012. Vendor AI accuracy 95%. Emotion: anxiety on video.", "rejected", "tool", "EU",
          fields_missing="references, salary expectation")
    assert r["human_questions"]
    assert all(len(q["ask"].split()) < 25 for q in r["human_questions"])
    assert not re.search(r"\b(hire|rank|score)\b", json.dumps(r["human_questions"]), re.I)


def test_ledger_citations_for_flagged_checks():
    r = v("Graduation year 2012.", "rejected", "human", "NYC")
    assert {"GT-0027", "GT-0024"} <= set(r["citations"])
    assert all(c["url"].startswith("http") for c in r["citations"].values())


def test_bad_outcome_rejected():
    with pytest.raises(ValueError):
        v("x", "hired", "human", "EU")


def test_parse_fields():
    assert parse_fields("References, salary expectation\nportfolio url") == ["references", "salary_expectation", "portfolio_url"]
    assert parse_fields("") == [] and parse_fields(None) == []


# ---------------------------------------------------------------- text mode options used by the Space
def test_text_mode_check_filter():
    t = verify_text("Requirements:\n- Excellent attitude.\n- Applicants must be aged 21 to 30.", ROOT, checks=["C01"])
    assert t["checks"] == ["C01"]
    assert {f["check"] for it in t["items"] for f in it["findings"]} == {"C01"}


def test_text_mode_claims_replace_line_splitting():
    claims = ["We need someone with 5 years of experience.", "The office has a dog."]
    t = verify_text("ignored", ROOT, claims=claims, checks=["C01", "C02", "C03"])
    assert [it["text"] for it in t["items"]] == [claims[0]]     # only the requirement-like claim has a check to run
    assert lines_from_claims(["", "  ", "Go."])[0]["text"] == "Go."
