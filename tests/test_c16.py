"""C16 unvalidated product claims, plus the 2026-11-25 fixes to C01, C02 and C03.

Cases come from a live test on a real Indian sales job post and four hiring-tool websites (wording kept,
company names removed).
"""
from datetime import date

import pytest
from conftest import ROOT

from selfune_hv import text_mode as tm
from selfune_hv.checks import (c01_undefined_trait as c01, c02_years_proxy as c02, c03_no_reason as c03,
                               c16_unvalidated_claim as c16)

TODAY = date(2026, 11, 25)


def kinds(text):
    return c16.evaluate_text(text)[1] if c16.evaluate_text(text)[0] == "UNVERIFIED" else []


# ---------------------------------------------------------------- C16 planted
@pytest.mark.parametrize("text,kind", [
    ("Relationship Manager: 92% match.", "score"),
    ("Adrian 96% Top fit, shortlisted.", "score"),
    ("Assessment Complete: 72% Overall score.", "score"),
    ("AI video interviews assess voice, video and text across behavioural and technical dimensions, then rank "
     "every candidate.", "signal"),
    ("Connecting workers with 200+ verified employers across 500+ cities.", "verified"),
    ("Our AI makes hiring bias-free.", "bias_free"),
    ("We remove human bias from screening.", "bias_free"),
    ("Our model predicts top performers before the interview.", "predicts"),
    ("Feedback collection happens without a recruiter in the loop.", "no_human"),
    ("AI agents screen end-to-end, so your recruiters only touch what's ready to close.", "no_human"),
    ("Candidates below the cut-off are auto-rejected.", "no_human"),
])
def test_c16_flags_unvalidated_claims(text, kind):
    assert kinds(text)[0] == kind


# ---------------------------------------------------------------- C16 clean
@pytest.mark.parametrize("text", [
    "Answers 40 chat tickets per shift with an average customer rating of 4.5 or higher.",
    "30% of manual recruiter effort eliminated.",
    "Writes SQL that answers a weekly business question.",
    "The match score was validated against 12 months of performance data and has a published bias audit.",
    "Shortlists are reviewed by a recruiter before anyone is rejected; scores are not used to reject.",
    "Recruiter-led hiring and AI-assisted recruitment workflows.",
])
def test_c16_leaves_clean_or_supported_text(text):
    assert c16.evaluate_text(text)[0] == "VERIFIED"


def test_voice_video_question_comes_before_score_question():
    text = ("AI video interviews run on the candidate's schedule, assessing voice, video and text across behavioural "
            "and technical dimensions, then rank every candidate, with the evidence attached.")
    assert c16.kinds(text)[:2] == ["signal", "score"]


def test_c16_in_text_mode_gives_mother_question_and_citations():
    r = tm.verify_text("Relationship Manager: 92% match.\nAdrian 96% Top fit, shortlisted.", ROOT, today=TODAY)
    assert r["status"] == "UNVERIFIED"
    assert r["mother_assumptions"][0]["question"] == c16.QUESTIONS["score"]
    assert set(r["citations"]) >= {"GT-0006", "GT-0007"}
    assert "C16" in r["checks"]


# ---------------------------------------------------------------- fixes to C01-C03
def test_age_rule_is_not_a_years_of_experience_count():
    assert c02.years_counts("Age below 30 years") == []
    assert c02.years_counts("Candidates under 25 years of age") == []
    assert c02.years_counts("3-5 years of experience in B2B sales") == ["3-5 years"]


def test_age_line_gets_only_the_age_question():
    r = tm.verify_text("Requirements:\n- Age below 30 years", ROOT, today=TODAY)
    checks = {f["check"] for f in r["items"][0]["findings"]}
    assert "C02" not in checks and "C08" in checks


@pytest.mark.parametrize("word", ["reputed", "premier", "prestigious", "go-getter", "self-starter", "presentable"])
def test_common_vague_words_are_undefined_traits(word):
    assert word in c01.trait_words(f"Graduate from a {word} college")


def test_measurable_outcome_counts_as_its_own_reason():
    assert c03.stated_reason("Achieve monthly target of 15 lakh revenue") == "measurable outcome of the role"
    assert c03.stated_reason("Close 10 enterprise deals a quarter") == "measurable outcome of the role"
    assert c03.stated_reason("Must have own two-wheeler") is None
    assert c03.stated_reason("Manage stakeholders") is None          # no number: not measurable


def test_indian_sales_post_end_to_end():
    post = ("Sales Executive - Bengaluru\nRequirements:\n- 3-5 years of experience in B2B sales\n"
            "- Excellent communication skills in English and Hindi\n- Go-getter attitude and a self-starter\n"
            "- Age below 30 years\n- Graduate from a reputed college\n- Must have own two-wheeler\n"
            "- Achieve monthly target of 15 lakh revenue")
    r = tm.verify_text(post, ROOT, today=TODAY)
    by_text = {it["text"]: {f["check"] for f in it["findings"]} for it in r["items"]}
    assert r["mother_assumptions"][0]["question"].startswith("What job-related reason, other than age")
    assert "C01" in by_text["Graduate from a reputed college"]
    assert by_text["Achieve monthly target of 15 lakh revenue"] == set()
    assert "C02" not in by_text["Age below 30 years"]
