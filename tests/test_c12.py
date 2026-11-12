from conftest import ROOT, by_ref

from selfune_hv.checks import c12_illinois as c12


def test_synthetic():
    f = by_ref(c12.run(ROOT))
    assert f["tool:T9:illinois"]["verdict"] == "ESCALATE"
    assert f["tool:T10:illinois"]["verdict"] == "VERIFIED"
    assert f["tool:T11:illinois"]["verdict"] == "NOT_CHECKED"   # IL fields absent
    assert {k.split(":")[1] for k in f} == {"T9", "T10", "T11"}  # IL jobs only


def test_rules():
    both = {"il_notice_sent": "2026-08-01", "il_disparate_effect_review": "2026-07-15"}
    assert c12.evaluate_tool(both)[0] == "VERIFIED"
    assert c12.evaluate_tool({**both, "il_notice_sent": None})[0] == "ESCALATE"
    assert c12.evaluate_tool({**both, "il_disparate_effect_review": None})[0] == "ESCALATE"
    assert c12.evaluate_tool({"il_notice_sent": "2026-08-01"})[0] == "NOT_CHECKED"
    assert c12.evaluate_tool({"il_notice_sent": None})[0] == "ESCALATE"   # a null beats an absent field


def test_non_il_job_ignored(synthetic_root):
    tools = [{"tool_id": "TX", "job_ids": ["J2"], "il_notice_sent": None, "il_disparate_effect_review": None}]
    assert c12.run(synthetic_root(**{"tools.json": tools})) == []


def test_message_and_citation():
    for f in c12.run(ROOT):
        assert "flag for review, not legal advice" in f["message"]
        assert "GT-0031" in f["message"] and "retrieved 2026-11-11" in f["message"]
