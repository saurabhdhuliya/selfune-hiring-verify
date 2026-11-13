import json
import re
from datetime import date

import pytest
from conftest import ROOT, by_ref

from selfune_hv import text_mode as tm
from selfune_hv.checks import (c01_undefined_trait as c01, c02_years_proxy as c02, c03_no_reason as c03,
                               c09_emotion_inference as c09, c15_vendor_claim as c15)
from selfune_hv.checks._common import Sources
from selfune_hv.role_memory import RoleMemory

TODAY = date(2026, 11, 13)
POSTS = ROOT / "examples/job_posts"


def run_post(name):
    return tm.verify_text((POSTS / name).read_text(encoding="utf-8"), ROOT, today=TODAY)


def flagged(report):
    return {it["link_id"]: sorted((f["check"], f["verdict"]) for f in it["findings"]) for it in report["items"]}


# ---------------------------------------------------------------- the 5 sample posts
def test_clean_post_is_verified():
    r = run_post("1_clean_data_analyst.txt")
    assert r["status"] == "VERIFIED" and r["weakest_link"] is None and r["human_questions"] == []
    assert r["summary"]["requirement_lines"] == 2
    assert all(not it["findings"] for it in r["items"])


def test_vague_post_flags_undefined_traits():
    r = run_post("2_vague_support_rep.txt")
    f = flagged(r)
    assert f["R1"] == [("C01", "UNVERIFIED"), ("C03", "UNVERIFIED")]
    assert f["R2"] == [("C01", "UNVERIFIED"), ("C03", "UNVERIFIED")]
    assert r["status"] == "UNVERIFIED" and r["weakest_link"] == "R1"
    assert len(r["human_questions"]) == 2                         # one per line: C01 covers C03
    assert all("personality, attitude or 'fit'" in q["do_not_ask"] for q in r["human_questions"])
    assert all(q["store_answer_in"] == "role_memory" for q in r["human_questions"])


def test_years_post_flags_years_as_proxy():
    r = run_post("3_years_backend.txt")
    f = flagged(r)
    assert ("C02", "UNVERIFIED") in f["R1"] and ("C02", "UNVERIFIED") in f["R2"]
    assert f["R3"] == []                                          # reason stated, no years
    asks = [q["ask"] for q in r["human_questions"]]
    assert any("5 years" in a for a in asks) and any("3+ years" in a for a in asks)


def test_age_post_escalates_and_asks_only_the_age_question():
    r = run_post("4_age_proxy_ops.txt")
    f = flagged(r)
    assert ("C08", "ESCALATE") in f["R1"] and ("C08", "ESCALATE") in f["R2"]
    assert r["status"] == "ESCALATE" and r["high_risk"] is True and r["blocked"] is False
    assert [q["ask"] for q in r["human_questions"]] == [
        "What job-related reason, other than age or graduation year, supports this?"]
    assert r["human_questions"][0]["do_not_ask"] == "Don't ask the applicant's age or graduation year."


def test_ai_summary_is_blocked_and_flags_vendor_claim():
    r = run_post("5_ai_screening_summary.txt")
    f = flagged(r)
    assert f["E2"] == [("C09", "ESCALATE")] and f["E3"] == [("C15", "UNVERIFIED")]
    assert r["status"] == "ESCALATE" and r["blocked"] is True and r["weakest_link"] == "E2"
    e2 = next(it for it in r["items"] if it["link_id"] == "E2")
    assert "EU AI Act prohibits inferring emotions from biometric data" in e2["findings"][0]["message"]  # video input


def test_weakest_link_is_most_severe_not_first():
    text = ("Requirements:\n- Minimum 5 years of experience.\n"
            "- Excellent attitude and a great culture fit.\n- Applicants must be aged 21 to 30.\n")
    r = tm.verify_text(text, ROOT, today=TODAY)
    status = {it["link_id"]: it["status"] for it in r["items"]}
    assert status == {"R1": "UNVERIFIED", "R2": "UNVERIFIED", "R3": "ESCALATE"}
    assert r["status"] == "ESCALATE" and r["weakest_link"] == "R3"


@pytest.mark.parametrize("name", sorted(p.name for p in POSTS.glob("*.txt")))
def test_every_post_questions_short_with_do_not_ask(name):
    r = run_post(name)
    for q in r["human_questions"]:
        assert len(q["ask"].split()) < 25 and q["do_not_ask"] and q["why"]
    assert len({q["ask"] for q in r["human_questions"]}) == len(r["human_questions"])


@pytest.mark.parametrize("name", sorted(p.name for p in POSTS.glob("*.txt")))
def test_every_post_cites_and_never_judges_a_person(name):
    r = run_post(name)
    blob = json.dumps(r)
    assert not re.search(r"CAND-\d{4}|\bhire\b|reject this candidate|best candidate|\bscore[ds]?\b\"\s*:", blob, re.I)
    for it in r["items"]:
        for f in it["findings"]:
            for ref in f["ledger_refs"]:
                c = r["citations"][ref]
                assert c["url"] and c["retrieved"] and c["label"]
    assert r["footer"] == "Verifies process, not people. Not legal advice."


# ---------------------------------------------------------------- same verdicts as the main loop
def _main_loop_findings():
    return {(f["object_ref"], f["check"]): f["verdict"]
            for mod in (c01, c02, c03) for f in (mod.run(ROOT, today=TODAY) if mod is c01 else mod.run(ROOT))}


def test_requirement_verdicts_match_main_loop():
    main = _main_loop_findings()
    company = json.loads((ROOT / "data/synthetic/company.json").read_text(encoding="utf-8"))
    rm = json.loads((ROOT / "data/synthetic/role_memory.json").read_text(encoding="utf-8"))
    src = Sources(ROOT, sorted({r for rs in tm.REFS.values() for r in rs}))
    memory = RoleMemory(rm, TODAY)
    compared = 0
    for job in company["jobs"]:
        for req in job["requirements"]:
            got = {f["check"]: f["verdict"] for f in
                   tm.check_line(req["text"], "requirement", src, memory, job["job_id"], job["title"])}
            for chk in ("C01", "C02", "C03"):
                assert got[chk] == main[(f"requirement:{req['req_id']}", chk)], (req["req_id"], chk)
                compared += 1
    assert compared == 48


def test_ai_text_verdicts_match_main_loop():
    main = {(f["object_ref"], f["check"]): f["verdict"] for mod in (c09, c15) for f in mod.run(ROOT)}
    src = Sources(ROOT, sorted({r for rs in tm.REFS.values() for r in rs}))
    memory = RoleMemory({"roles": []}, TODAY)
    for line in (ROOT / "data/synthetic/ai_text.jsonl").read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        got = {f["check"]: f["verdict"] for f in tm.check_line(t["text"], "statement", src, memory)}
        assert got["C09"] == main[(f"ai_text:{t['text_id']}", "C09")], t["text_id"]
        assert got["C15"] == main[(f"ai_text:{t['text_id']}", "C15")], t["text_id"]


# ---------------------------------------------------------------- splitting and edge cases
def test_split_lines_sections_bullets_sentences():
    text = ("Title (fictional)\n\nRequirements:\n- Python, because we use it.\n* SQL\n\nWe offer lunch. "
            "Remote friendly.\n\nNice to have:\n1. Go\n")
    lines = tm.split_lines(text)
    assert [(l["kind"], l["text"]) for l in lines] == [
        ("statement", "Title (fictional)"), ("requirement", "Python, because we use it."), ("requirement", "SQL"),
        ("statement", "We offer lunch."), ("statement", "Remote friendly."), ("requirement", "Go")]
    assert [l["text"] for l in tm.split_lines("Skills:\n- R\n- C#\n- ---\n")] == ["R", "C#"]


def test_empty_text_is_not_checked():
    r = tm.verify_text("   \n\n", ROOT)
    assert r["status"] == "NOT_CHECKED" and r["items"] == []


def test_readable_format():
    out = tm.format_text(run_post("5_ai_screening_summary.txt"))
    assert "Status: ESCALATE" in out and "BLOCKED by C09" in out
    assert "Avoid: Don't ask the candidate how they felt" in out
    assert "GT-0008 · " in out and out.rstrip().endswith("Verifies process, not people. Not legal advice.")


def test_new_modules_never_reference_labels():
    literal = re.compile(r"""["'][^"'\n]*labels""")
    for name in ("text_mode.py", "cli.py", "mcp_server.py", "loop.py", "paths.py"):
        assert not literal.search((ROOT / "src/selfune_hv" / name).read_text(encoding="utf-8")), name
