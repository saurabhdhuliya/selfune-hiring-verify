import json
import re
from datetime import date

import pytest
from conftest import ROOT
from jsonschema import Draft202012Validator

from selfune_hv import report as rep

TODAY = date(2026, 11, 12)
BANNED_PHRASES = re.compile(r"\bhire\b|\bhired\b|reject this candidate|hire this candidate|best candidate|"
                            r"top candidate|recommend(?:ed)? (?:hiring|rejecting)|\branked?\b|\bshortlist", re.I)
PERSON_KEYS = re.compile(r"score|rank|rating|fit|suitab", re.I)


@pytest.fixture(scope="module")
def report():
    return rep.build_report(ROOT, today=TODAY)


@pytest.fixture(scope="module")
def page(report):
    return rep.render_html(report)


def _keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k
            yield from _keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _keys(v, f"{path}[{i}]")


def test_every_chain_valid_against_schema(report):
    schema = json.loads((ROOT / "schemas/decision_chain.schema.json").read_text(encoding="utf-8"))
    v = Draft202012Validator(schema)
    chains = rep.chains_for_schema(report)
    assert len(chains) == 200
    for c in chains:
        assert not list(v.iter_errors(c)), c["chain_id"]


def test_html_never_shows_a_candidate_reference(page):
    assert not re.search(r"CAND-\d{4}", page)


def test_candidate_ref_only_in_its_own_field(report):
    """In report.json a candidate_ref appears only as a chain's candidate_ref, never next to a score or verdict text."""
    for c in report["chains"]:
        rest = json.dumps({k: v for k, v in c.items() if k != "candidate_ref"})
        assert not re.search(r"CAND-\d{4}", rest), c["chain_id"]
    others = json.dumps({k: v for k, v in report.items() if k != "chains"})
    assert not re.search(r"CAND-\d{4}", others)


def test_no_score_or_rank_fields_anywhere(report):
    bad = [p for p, k in _keys(report) if PERSON_KEYS.search(k)]
    assert bad == []


def test_no_hire_or_reject_language(report, page):
    # Employer-written reason texts are quoted as data; the report's own words must never judge a person.
    assert not BANNED_PHRASES.search(page)
    generated = json.dumps({k: report[k] for k in ("summary", "questions", "ledger_warnings")})
    assert not BANNED_PHRASES.search(generated)


def test_every_question_under_25_words(report):
    asks = [q["ask"] for q in report["questions"]]
    asks += [q["ask"] for c in report["chains"] for q in c.get("human_questions", [])]
    assert asks
    for a in asks:
        assert len(a.split()) < 25, a


def test_questions_deduplicated(report):
    seen = [(q["job_id"], q["ask"]) for q in report["questions"]]
    assert len(seen) == len(set(seen))
    reqs = [q["about"] for q in report["questions"] if q["about"]]
    assert len(reqs) == len(set(reqs)), "more than one question for the same requirement"


def test_one_question_per_trait_per_role(report):
    j3 = [q for q in report["questions"] if q["about"] == "requirement:J3-R1"]
    assert len(j3) == 1 and j3[0]["store_answer_in"] == "role_memory"
    assert len(j3[0]["applies_to"]) == 50   # every J3 decision, asked once


def test_high_risk_chains(report):
    chains = {c["chain_id"]: c for c in report["chains"]}
    assert chains["CH-D0082"]["chain_status"] == "ESCALATE"   # decided by tool, GDPR Art 22
    assert chains["CH-D0152"]["chain_status"] == "ESCALATE"   # age proxy
    assert chains["CH-D0004"]["chain_status"] != "ESCALATE"


def test_c06_evidence_link_uses_erd_split(report):
    e1 = next(l for l in {c["chain_id"]: c for c in report["chains"]}["CH-D0001"]["links"] if l["link_id"] == "E1")
    assert e1["status"] == "UNVERIFIED"
    assert e1["observed_confidence"] == "High" and e1["inference_confidence"] == "Low"
    assert e1["fields_missing"] == ["references"] and len(e1["alternative_explanations"]) >= 2


def test_flags_show_ledger_id_url_and_date(report, page):
    for f in report["job_and_tool_findings"]:
        if f["verdict"] == "VERIFIED":
            continue
        for r in f["ledger_refs"]:
            c = report["citations"][r]
            assert r in page and c["url"] in page and f"retrieved {c['retrieved']}" in page


def test_footer(page):
    assert "Verifies process, not people. Not legal advice." in page


def test_ledger_warning_for_pending_row(report):
    ids = {w["id"] for w in report["ledger_warnings"]}
    assert "GT-0009" in ids


def test_missing_role_need_is_not_checked(synthetic_root):
    rm = json.loads((ROOT / "data/synthetic/role_memory.json").read_text(encoding="utf-8"))
    rm["roles"] = [r for r in rm["roles"] if r["role_id"] != "J1"]
    r = rep.build_report(synthetic_root(**{"role_memory.json": rm}), today=TODAY)
    j1 = [c for c in r["chains"] if c["job_id"] == "J1"]
    assert all(next(l for l in c["links"] if l["link_id"] == "N1")["status"] == "NOT_CHECKED" for c in j1)
    assert any("why does the Customer Support Specialist role exist" in q["ask"] for q in r["questions"])


def test_report_code_never_references_labels():
    literal = re.compile(r"""["'][^"'\n]*labels""")
    for p in (ROOT / "src/selfune_hv/report.py", ROOT / "scripts/run_loop.py"):
        assert not literal.search(p.read_text(encoding="utf-8")), p.name
