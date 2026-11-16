"""Mother assumptions: dependency counting, ordering, questions, citations. No LLM, no candidate data."""
import json
import re
from datetime import date

import pytest
from conftest import ROOT

from selfune_hv import mother, report as rep
from selfune_hv.decision_chain import SEVERITY
from selfune_hv.text_mode import verify_text

TODAY = date(2026, 11, 12)
PERSON_KEYS = re.compile(r"score|rank|rating|fit|suitab", re.I)


@pytest.fixture(scope="module")
def full():
    return rep.build_report(ROOT, today=TODAY)


def _link(lid, typ, status="VERIFIED", deps=(), inherited=False):
    l = {"link_id": lid, "type": typ, "statement": f"{typ} {lid}", "status": status, "route": "human"}
    if deps:
        l["depends_on"] = list(deps)
    if inherited:
        l["inherited"] = True
    return l


def _chain(did, job, e="VERIFIED", d="VERIFIED", need="VERIFIED", r1="VERIFIED"):
    return {"chain_id": f"CH-{did}", "job_id": job, "links": [
        _link("N1", "role_need", need, inherited=True),
        _link("R1", "requirement", r1, ["N1"], inherited=True),
        _link("E1", "evidence", e, ["R1"]),
        _link("D1", "decision", d, ["E1"])]}


def _mini(chains, issues=(), questions=(), flags=()):
    return {"jobs": [{"job_id": "J1", "title": "Analyst", "requirements": [{"req_id": "J1-R1", "text": "Strong attitude"}]}],
            "tools": [{"tool_id": "T1", "name": "ScreenRank", "job_ids": ["J1"]}],
            "chains": list(chains), "job_level_issues": list(issues), "questions": list(questions), "flags": list(flags),
            "citations": {"GT-0019": {"id": "GT-0019", "label": "x", "url": "https://x", "retrieved": "2026-01-01"}}}


def _req_issue(check="C01", verdict="UNVERIFIED", refs=("GT-0019",)):
    return {"object_ref": "requirement:J1-R1", "category": "requirement", "check": check, "verdict": verdict,
            "job_ids": ["J1"], "tool_id": None, "affects_decisions": 3, "decision_ids": ["D1", "D2", "D3"],
            "ledger_refs": list(refs), "message": "vague"}


def _tool_issue(tool="T1", check="C09", verdict="ESCALATE", ids=("D1", "D2", "D3"), ref=None):
    return {"object_ref": ref or f"tool:{tool}", "category": "tool", "check": check, "verdict": verdict,
            "job_ids": ["J1"], "tool_id": tool, "affects_decisions": len(ids), "decision_ids": list(ids),
            "ledger_refs": [], "message": "m"}


def _req_q():
    return {"job_id": "J1", "ask": 'What observable result shows "Strong attitude" in this role?', "why": "w",
            "do_not_ask": "", "store_answer_in": "role_memory", "about": "requirement:J1-R1", "check": "C01",
            "applies_to": ["D1", "D2", "D3"]}


# ---------------------------------------------------------------- counting on a small graph
def test_requirement_counts_every_decision_and_link_below_it():
    r = _mini([_chain(f"D{i}", "J1", r1="UNVERIFIED") for i in (1, 2, 3)], [_req_issue()], [_req_q()])
    (m,) = mother.mother_assumptions(r)
    assert m["decisions_unblocked"] == 3
    assert m["downstream_links"] == 6            # E1 and D1 of each of 3 decisions
    assert m["checks"] == ["C01"] and m["status"] == "UNVERIFIED"
    assert m["ledger_refs"] == ["GT-0019"] and m["citations"][0]["url"] == "https://x"


def test_role_need_outweighs_requirements_below_it():
    r = _mini([_chain(f"D{i}", "J1", need="NOT_CHECKED", r1="UNVERIFIED") for i in (1, 2, 3)], [_req_issue()], [_req_q()])
    m = mother.mother_assumptions(r)
    assert m[0]["about"] == "role_need:J1" and "why does the Analyst role exist" in m[0]["question"]
    assert m[0]["downstream_links"] == 7         # R1 + E1 + D1 of 3 decisions
    assert m[1]["about"] == "requirement:J1-R1" and m[0]["decisions_unblocked"] == m[1]["decisions_unblocked"] == 3


def test_verified_and_not_checked_nodes_are_never_mother_assumptions():
    assert mother.mother_assumptions(_mini([_chain("D1", "J1", e="NOT_CHECKED", d="VERIFIED")])) == []


def test_job_level_flag_reaches_only_the_decisions_it_affects():
    r = _mini([_chain(f"D{i}", "J1") for i in (1, 2, 3)], [_tool_issue(ids=("D1", "D2"))])
    (m,) = mother.mother_assumptions(r)
    assert m["decisions_unblocked"] == 2 and m["downstream_links"] == 4
    assert "ScreenRank" in m["question"] and m["status"] == "ESCALATE"
    assert m["ledger_note"] == mother.NO_LEDGER_ROW


def test_same_question_merges_and_counts_each_decision_once():
    issues = [_tool_issue(check="C10", ids=("D1", "D2"), ref=f"tool:T1:{k}") for k in ("audit_age", "notice")]
    ms = mother.mother_assumptions(_mini([_chain(f"D{i}", "J1") for i in (1, 2)], issues))
    assert len(ms) == 1 and ms[0]["decisions_unblocked"] == 2


def test_decision_level_question_only_for_flagged_checks():
    q = {"job_id": "J1", "ask": "What data from your own process shows this vendor claim holds for this role?",
         "why": "w", "do_not_ask": "", "store_answer_in": "decision_record", "about": None, "check": "C15",
         "applies_to": ["D1", "D2"]}
    flags = [{"flag_ref": "decision:D1|C15", "verdict": "UNVERIFIED"}, {"flag_ref": "decision:D2|C15", "verdict": "VERIFIED"}]
    r = _mini([_chain("D1", "J1", e="UNVERIFIED"), _chain("D2", "J1")], questions=[q], flags=flags)
    (m,) = mother.mother_assumptions(r)
    assert m["decisions_unblocked"] == 1 and m["downstream_links"] == 1   # D1's decision link


def test_order_most_decisions_first_then_severity():
    a = _tool_issue("T1", "C09", "UNVERIFIED")
    b = _tool_issue("T2", "C11", "ESCALATE", ids=("D1",))
    c = _tool_issue("T3", "C15", "ESCALATE")
    r = _mini([_chain(f"D{i}", "J1") for i in (1, 2, 3)], [b, a, c])
    r["tools"] += [{"tool_id": "T2", "name": "B", "job_ids": ["J1"]}, {"tool_id": "T3", "name": "C", "job_ids": ["J1"]}]
    ms = mother.mother_assumptions(r)
    assert [m["about"] for m in ms] == ["tool:T3", "tool:T1", "tool:T2"]     # equal counts: ESCALATE before UNVERIFIED
    assert [m["order"] for m in ms] == [1, 2, 3]


def test_top_is_capped_at_three():
    issues = [_tool_issue(f"T{i}", ids=("D1",)) for i in range(1, 7)]
    r = _mini([_chain("D1", "J1")], issues)
    r["tools"] = [{"tool_id": f"T{i}", "name": f"Tool{i}", "job_ids": ["J1"]} for i in range(1, 7)]
    assert len(mother.mother_assumptions(r)) == 3
    assert len(mother.mother_assumptions(r, top=1)) == 1
    assert len(mother.mother_assumptions(r, top=99)) == 3


# ---------------------------------------------------------------- the real report
def test_full_report_has_one_to_three(full):
    ms = full["mother_assumptions"]
    assert 1 <= len(ms) <= 3
    assert [m["order"] for m in ms] == list(range(1, len(ms) + 1))


def test_every_question_under_25_words_and_non_empty(full):
    for m in full["mother_assumptions"]:
        assert 0 < len(m["question"].split()) < 25, m["question"]


def test_each_one_has_counts_and_a_citation_or_the_no_ledger_note(full):
    n_chains = len(full["chains"])
    for m in full["mother_assumptions"]:
        assert 1 <= m["decisions_unblocked"] <= n_chains and m["downstream_links"] >= 1
        assert m["status"] in mother.FLAGGED
        if m["ledger_refs"]:
            assert {c["id"] for c in m["citations"]} == set(m["ledger_refs"])
            assert all(r in full["citations"] for r in m["ledger_refs"])
        else:
            assert m["ledger_note"] == mother.NO_LEDGER_ROW


def test_sorted_by_decisions_then_downstream(full):
    keys = [(-m["decisions_unblocked"], -m["downstream_links"], -SEVERITY[m["status"]]) for m in full["mother_assumptions"]]
    assert keys == sorted(keys)


def test_deterministic(full):
    assert rep.build_report(ROOT, today=TODAY)["mother_assumptions"] == full["mother_assumptions"]


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def test_no_person_keys_and_no_candidate_refs(full):
    assert not re.search(r"CAND-\d{4}", json.dumps(full["mother_assumptions"]))
    assert not [k for k in _keys(full["mother_assumptions"]) if PERSON_KEYS.search(k)]


def test_html_shows_mother_assumptions_before_job_level_issues(full):
    page = rep.render_html(full)
    assert page.index("Mother assumptions") < page.index("Job-level issues")
    assert "Unblocks 80 decisions" in page
    assert not re.search(r"CAND-\d{4}", page)


def test_html_without_mother_key_still_renders(full):
    old = {k: v for k, v in full.items() if k != "mother_assumptions"}
    assert "Mother assumptions" not in rep.render_html(old)


def test_report_json_carries_mother_assumptions(full):
    from selfune_hv.loop import report_json
    assert report_json(full)["mother_assumptions"] == full["mother_assumptions"]


def test_missing_role_need_becomes_the_top_assumption(synthetic_root):
    root = synthetic_root(**{"role_memory.json": {"roles": []}})
    top = rep.build_report(root, today=TODAY)["mother_assumptions"][0]
    assert top["about"].startswith("role_need:") and "role exist" in top["question"]
    assert top["decisions_unblocked"] == 80          # J1: the biggest job


# ---------------------------------------------------------------- text mode
def test_text_mode_mother_assumptions():
    t = verify_text("Requirements:\n- Excellent attitude.\n- Minimum 5 years of experience.\n- Writes SQL, tested in a 90-minute "
                    "work sample, because reports pull from SQL.", ROOT, checks=["C01", "C02", "C03"])
    ms = t["mother_assumptions"]
    assert 1 <= len(ms) <= 3
    assert all(m["decisions_unblocked"] is None and m["downstream_links"] == 1 for m in ms)
    assert all(len(m["question"].split()) < 25 for m in ms)
    assert all(m["ledger_refs"] for m in ms)
    assert "every screening decision" in mother.unblocks_text(ms[0])


def test_text_mode_clean_post_has_none():
    t = verify_text("Requirements:\n- Writes SQL, tested in a 90-minute work sample, because reports pull from SQL.", ROOT)
    assert t["mother_assumptions"] == []


def test_text_mode_same_question_merges_lines():
    t = verify_text("Requirements:\n- Graduation year 2022 or later.\n- Applicants must be aged 21 to 30.", ROOT)
    assert len(t["mother_assumptions"]) == 1 and t["mother_assumptions"][0]["status"] == "ESCALATE"


def test_text_mode_age_line_gets_no_justify_it_question():
    t = verify_text("Requirements:\n- Applicants must be aged 21 to 30.", ROOT, checks=["C01", "C02", "C03", "C08"])
    asks = [m["question"] for m in t["mother_assumptions"]]
    assert asks and not any("help" in a and "succeed" in a for a in asks)


def test_cli_text_output_lists_mother_assumptions(tmp_path, capsys):
    from selfune_hv.cli import main
    p = tmp_path / "post.txt"
    p.write_text("Requirements:\n- Excellent attitude.\n", encoding="utf-8")
    assert main([str(p)]) == 0
    assert "Mother assumptions" in capsys.readouterr().out
