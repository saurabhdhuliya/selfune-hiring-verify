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
    assert chains["CH-D0004"]["chain_status"] == "VERIFIED"


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


def _chain(report, cid):
    return next(c for c in report["chains"] if c["chain_id"] == cid)


def test_inherited_links_marked(report):
    for c in report["chains"]:
        for l in c["links"]:
            if l["type"] in ("role_need", "requirement"):
                assert l["inherited"] is True and l["note"].startswith("inherited from job")
            else:
                assert "inherited" not in l


def test_roll_up_ignores_inherited_links(report):
    # J1 requirements are flagged, but a decision with clean evidence and decision links is VERIFIED.
    c = _chain(report, "CH-D0004")
    assert any(l["status"] != "VERIFIED" for l in c["links"] if l.get("inherited"))
    assert c["chain_status"] == "VERIFIED" and c["weakest_link"] is None


def test_chain_status_from_own_links_only(report):
    assert _chain(report, "CH-D0001")["chain_status"] == "UNVERIFIED"   # C06
    assert _chain(report, "CH-D0001")["weakest_link"] == "E1"
    assert _chain(report, "CH-D0003")["chain_status"] == "UNVERIFIED"   # C15
    assert _chain(report, "CH-D0085")["chain_status"] == "NOT_CHECKED"  # decided_by missing
    assert _chain(report, "CH-D0085")["weakest_link"] == "D1"
    for c in report["chains"]:
        assert c["weakest_link"] in (None, "E1", "D1")


def test_chain_questions_are_decision_level_only(report):
    for c in report["chains"]:
        assert all(q["link_id"] in ("E1", "D1") for q in c.get("human_questions", []))
    assert sum(1 for q in report["questions"] if q["store_answer_in"] == "role_memory") == 10


def test_roll_up_unit():
    from selfune_hv.decision_chain import Link, roll_up
    links = [Link("N1", "role_need", "n", "VERIFIED", "role_memory", inherited=True),
             Link("R1", "requirement", "r", "UNVERIFIED", "human", inherited=True),
             Link("E1", "evidence", "e", "VERIFIED", "code"),
             Link("D1", "decision", "d", "WARN", "code")]
    assert roll_up(links) == ("WARN", "D1")
    assert roll_up([Link("R1", "requirement", "r", "UNVERIFIED", "human")] + links[2:]) == ("UNVERIFIED", "R1")
    assert roll_up(links[:2], high_risk=True) == ("ESCALATE", "R1")   # all inherited: fall back to all links


def test_job_level_issues(report):
    issues = report["job_level_issues"]
    assert report["summary"]["job_level_issues"] == len(issues) > 0
    assert all(i["verdict"] != "VERIFIED" and not i["object_ref"].startswith("decision:") for i in issues)
    by = {(i["object_ref"], i["check"]): i for i in issues}
    assert by[("requirement:J1-R1", "C01")]["affects_decisions"] == 80
    assert by[("job:J3:selection_method", "C04")]["affects_decisions"] == 50
    assert by[("tool:T6", "C09")]["affects_decisions"] == 70
    assert by[("group_counts:J1:age_band", "C05")]["category"] == "group counts"
    assert {i["category"] for i in issues} >= {"requirement", "selection method", "tool", "group counts"}


def test_job_level_block_above_decision_chains(page):
    assert 0 < page.index("Job-level issues") < page.index("Decision chains by verdict")
    assert "affects 80 decisions" in page


def _with_tools_used(synthetic_root, mapping):
    ds = [json.loads(l) for l in (ROOT / "data/synthetic/decisions.jsonl").read_text(encoding="utf-8").splitlines() if l]
    for d in ds:
        if d["decision_id"] in mapping:
            d["tools_used"] = mapping[d["decision_id"]]
    return rep.build_report(synthetic_root(**{"decisions.jsonl": ds}), today=TODAY)


def test_c09_blocks_only_when_tool_in_tools_used(synthetic_root):
    r = _with_tools_used(synthetic_root, {"D0084": ["T6", "T8"], "D0086": ["T8"], "D0087": ["T11"]})
    blocked = _chain(r, "CH-D0084")
    assert blocked["blocked"] is True and blocked["chain_status"] == "ESCALATE" and blocked["weakest_link"] == "E1"
    assert _chain(r, "CH-D0086")["blocked"] is False                       # T8 is not C09-flagged
    assert _chain(r, "CH-D0087")["chain_status"] == "UNVERIFIED"            # T11 infers_emotion unknown: ask
    assert _chain(r, "CH-D0088")["blocked"] is False                       # no tools_used: job-level only
    assert sum(c["blocked"] for c in r["chains"]) == 1
    t6 = next(i for i in r["job_level_issues"] if i["object_ref"] == "tool:T6" and i["check"] == "C09")
    assert t6["affects_decisions"] == 68   # 70 J2 decisions minus D0086 and D0087, which list tools without T6


def test_decisions_valid_against_decision_schema():
    schema = json.loads((ROOT / "schemas/decision.schema.json").read_text(encoding="utf-8"))
    v = Draft202012Validator(schema)
    for line in (ROOT / "data/synthetic/decisions.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            assert not list(v.iter_errors(json.loads(line)))
    assert not list(v.iter_errors({**json.loads(line), "tools_used": ["T1", "T4"]}))
    assert list(v.iter_errors({**json.loads(line), "tools_used": ["ScreenRank"]}))


def test_report_code_never_references_labels():
    literal = re.compile(r"""["'][^"'\n]*labels""")
    for p in (ROOT / "src/selfune_hv/report.py", ROOT / "scripts/run_loop.py"):
        assert not literal.search(p.read_text(encoding="utf-8")), p.name
