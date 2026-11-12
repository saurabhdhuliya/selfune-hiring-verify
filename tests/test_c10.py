from datetime import date

from conftest import ROOT, by_ref

from selfune_hv.checks import c10_nyc_ll144 as c10


def nyc_tool(**fields):
    base = {"tool_id": "TX", "job_ids": ["J1"], "decision_mode": "weighted_most",
            "employer_scope_claim": "in scope", "last_bias_audit_date": "2026-03-01",
            "notice_sent_date": "2026-09-01", "first_use_date": "2026-09-20"}
    base.update(fields)
    return base


def run_with(synthetic_root, *tools):
    return by_ref(c10.run(synthetic_root(**{"tools.json": list(tools)})))


def test_synthetic_tools():
    f = by_ref(c10.run(ROOT))
    assert f["tool:T1:audit_age"]["verdict"] == "ESCALATE"
    assert f["tool:T1:notice"]["verdict"] == "ESCALATE"
    assert f["tool:T3:scope"]["verdict"] == "ESCALATE"
    assert f["tool:T4:audit_age"]["verdict"] == "VERIFIED"
    assert f["tool:T4:notice"]["verdict"] == "VERIFIED"
    assert f["tool:T2:scope"]["verdict"] == "VERIFIED"
    assert f["tool:T13:audit_age"]["verdict"] == "NOT_CHECKED"


def test_only_nyc_tools():
    tools = {k.split(":")[1] for k in by_ref(c10.run(ROOT))}
    assert tools == {"T1", "T2", "T3", "T4", "T13"}


def test_out_of_scope_tool_gets_no_audit_or_notice_finding():
    f = by_ref(c10.run(ROOT))
    assert "tool:T2:audit_age" not in f and "tool:T2:notice" not in f


def test_business_days_strictly_between():
    assert c10.business_days_between(date(2026, 9, 1), date(2026, 9, 20)) == 13   # T4
    assert c10.business_days_between(date(2026, 10, 26), date(2026, 11, 2)) == 4   # T1
    assert c10.business_days_between(date(2026, 11, 2), date(2026, 11, 3)) == 0
    assert c10.business_days_between(date(2026, 11, 3), date(2026, 11, 2)) == 0


def test_scope_claim_overridden_by_decision_mode(synthetic_root):
    for mode in ("alone", "weighted_most", "overrides_human"):
        f = run_with(synthetic_root, nyc_tool(decision_mode=mode, employer_scope_claim="not in scope"))
        assert f["tool:TX:scope"]["verdict"] == "ESCALATE"
    f = run_with(synthetic_root, nyc_tool(decision_mode="advisory", employer_scope_claim="not in scope"))
    assert f["tool:TX:scope"]["verdict"] == "VERIFIED"
    assert "tool:TX:audit_age" not in f


def test_audit_age_boundaries(synthetic_root):
    ok = run_with(synthetic_root, nyc_tool(last_bias_audit_date="2025-09-20", first_use_date="2026-09-20"))
    assert ok["tool:TX:audit_age"]["verdict"] == "VERIFIED"   # exactly 365 days


def test_audit_age_over_one_year(synthetic_root):
    f = run_with(synthetic_root, nyc_tool(last_bias_audit_date="2025-09-19", first_use_date="2026-09-20"))
    assert f["tool:TX:audit_age"]["verdict"] == "ESCALATE"    # 366 days


def test_audit_null_absent_and_after_use(synthetic_root):
    assert run_with(synthetic_root, nyc_tool(last_bias_audit_date=None))["tool:TX:audit_age"]["verdict"] == "ESCALATE"
    t = nyc_tool()
    del t["last_bias_audit_date"]
    assert run_with(synthetic_root, t)["tool:TX:audit_age"]["verdict"] == "NOT_CHECKED"


def test_audit_dated_after_first_use_escalates(synthetic_root):
    f = run_with(synthetic_root, nyc_tool(last_bias_audit_date="2026-10-01"))
    assert f["tool:TX:audit_age"]["verdict"] == "ESCALATE"


def test_notice_null_absent_and_threshold(synthetic_root):
    assert run_with(synthetic_root, nyc_tool(notice_sent_date=None))["tool:TX:notice"]["verdict"] == "ESCALATE"
    t = nyc_tool()
    del t["notice_sent_date"]
    assert run_with(synthetic_root, t)["tool:TX:notice"]["verdict"] == "NOT_CHECKED"
    # Mon 2026-09-07 -> Mon 2026-09-21: 9 business days strictly between; Fri 2026-09-04 -> 10.
    assert run_with(synthetic_root, nyc_tool(notice_sent_date="2026-09-07", first_use_date="2026-09-21",
                                             last_bias_audit_date="2026-03-01"))["tool:TX:notice"]["verdict"] == "ESCALATE"
    assert run_with(synthetic_root, nyc_tool(notice_sent_date="2026-09-04", first_use_date="2026-09-21",
                                             last_bias_audit_date="2026-03-01"))["tool:TX:notice"]["verdict"] == "VERIFIED"


def test_non_nyc_tool_ignored(synthetic_root):
    f = run_with(synthetic_root, nyc_tool(tool_id="TE", job_ids=["J2"]))
    assert f == {}


def test_legal_message_and_citations():
    f = by_ref(c10.run(ROOT))
    assert f["tool:T3:scope"]["ledger_refs"] == ["GT-0038", "GT-0002"]
    assert "retrieved 2026-10-29" in f["tool:T3:scope"]["message"]          # GT-0002
    assert f["tool:T1:audit_age"]["ledger_refs"] == ["GT-0036"]
    assert f["tool:T1:notice"]["ledger_refs"] == ["GT-0037"]
    for v in f.values():
        assert "flag for review, not legal advice" in v["message"]
        assert "retrieved 2026-11-11" in v["message"] or "retrieved 2026-10-29" in v["message"]
