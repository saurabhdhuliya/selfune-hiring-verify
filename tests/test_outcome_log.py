import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from conftest import ROOT

from selfune_hv import outcome_log as ol
from selfune_hv import report as rep

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
REPORT = {"run_id": "RUN-TEST-1", "flags": [
    {"flag_ref": "tool:T1:audit_age|C10", "verdict": "ESCALATE"},
    {"flag_ref": "requirement:J1-R5|C03", "verdict": "UNVERIFIED"},
    {"flag_ref": "decision:D0001|C06", "verdict": "UNVERIFIED"},
    {"flag_ref": "requirement:J1-R1|C01", "verdict": "UNVERIFIED"},
]}
REASON = "Typing speed is a contractual minimum the client sets for every agent on this account"


def entry(**kw):
    base = dict(flag="tool:T1:audit_age|C10", seen_by="HR lead", decided_by="HR lead", action="fixed",
                outcome_note="New audit ordered")
    base.update(kw)
    return ol.make_entry(REPORT, base.pop("flag"), base.pop("seen_by"), base.pop("decided_by"), base.pop("action"),
                         base.pop("override_reason", ""), base.pop("outcome_note", ""), base.pop("outcome_date", ""), NOW)


# ---------------------------------------------------------------- validation
def test_valid_entry_and_autofill():
    e = entry()
    assert ol.validate(e, REPORT) == []
    assert e["run_id"] == "RUN-TEST-1" and e["verdict_shown"] == "ESCALATE"
    assert e["logged_at"] == "2026-11-12T10:00:00+00:00"


def test_flag_must_exist_in_run():
    errs = ol.validate(entry(flag="tool:T99:audit_age|C10"), REPORT)
    assert any("not a flag in run" in e for e in errs)


def test_run_id_must_match():
    e = entry()
    e["run_id"] = "RUN-OLD"
    assert any("not the current run" in x for x in ol.validate(e, REPORT))


def test_verdict_shown_must_match():
    e = entry()
    e["verdict_shown"] = "VERIFIED"
    assert any("does not match" in x for x in ol.validate(e, REPORT))


def test_action_must_be_known():
    assert any("action must be one of" in x for x in ol.validate(entry(action="ignored"), REPORT))


def test_override_needs_reason_of_10_words():
    flag = "requirement:J1-R5|C03"
    assert any("override_reason" in x for x in ol.validate(entry(flag=flag, action="overridden"), REPORT))
    short = entry(flag=flag, action="overridden", override_reason="Client requires it for all agents")
    assert any("at least 10 words" in x for x in ol.validate(short, REPORT))
    assert ol.validate(entry(flag=flag, action="overridden", override_reason=REASON), REPORT) == []


@pytest.mark.parametrize("field,text,problem", [
    ("outcome_note", "Asked CAND-0001 for references", "candidate reference"),
    ("outcome_note", "Emailed jane.doe@example.com about it", "email"),
    ("outcome_note", "Called +44 20 7946 0958 to confirm", "phone"),
    ("outcome_note", "Call 555-123-4567", "phone"),
    ("override_reason", "We spoke to cand-0042 and they said the reference form was broken on mobile", "candidate reference"),
])
def test_rejects_personal_data(field, text, problem):
    kw = {field: text}
    if field == "override_reason":
        kw["action"] = "overridden"
    assert any(problem in x for x in ol.validate(entry(**kw), REPORT))


@pytest.mark.parametrize("text", [
    "Audit dated 2026-03-01, new one booked for 2026-12-01",
    "Ticket 4521 opened; 85% threshold kept",
    "Re-run on 2026-11-20 after vendor update v2.3.1",
])
def test_dates_and_small_numbers_are_not_phones(text):
    assert ol.validate(entry(outcome_note=text), REPORT) == []


@pytest.mark.parametrize("role,ok", [
    ("HR lead", True), ("Hiring manager", True), ("Head of Support", True), ("Recruiter", True),
    ("Interview panel", True), ("Jane Smith", False), ("Saurabh", False), ("", False),
])
def test_roles_not_names(role, ok):
    errs = ol.validate(entry(seen_by=role, decided_by=role), REPORT)
    assert (errs == []) is ok, errs


def test_outcome_date_must_be_iso():
    assert any("ISO date" in x for x in ol.validate(entry(outcome_date="20/11/2026"), REPORT))


def test_unknown_fields_rejected():
    e = entry()
    e["candidate_ref"] = "CAND-0001"
    assert any("unknown field" in x for x in ol.validate(e, REPORT))


# ---------------------------------------------------------------- append-only file
def test_append_never_rewrites_and_rejects_bad(tmp_path):
    log = tmp_path / "outcome_log.jsonl"
    assert ol.append(log, entry(), REPORT) == []
    first = log.read_text(encoding="utf-8")
    assert ol.append(log, entry(outcome_note="Asked CAND-0001"), REPORT)       # rejected, nothing written
    assert log.read_text(encoding="utf-8") == first
    assert ol.append(log, entry(action="deferred"), REPORT) == []
    text = log.read_text(encoding="utf-8")
    assert text.startswith(first) and len(ol.read(log)) == 2


# ---------------------------------------------------------------- summary
def test_summary_counts_and_override_rate():
    entries = [
        entry(flag="tool:T1:audit_age|C10", action="deferred"),
        entry(flag="tool:T1:audit_age|C10", action="fixed"),                         # latest wins: fixed
        entry(flag="requirement:J1-R5|C03", action="overridden", override_reason=REASON),
        entry(flag="requirement:J1-R1|C01", action="accepted"),
        entry(flag="decision:D0001|C06", action="fixed"),
    ]
    s = ol.summary(entries)
    assert s["entries"] == 5 and s["flags_with_action"] == 4
    assert s["by_action"] == {"fixed": 2, "overridden": 1, "accepted": 1}
    assert s["by_check"]["C10"] == {"fixed": 1}
    assert s["override_rate"]["C03"] == {"overridden": 1, "total": 1, "override_rate": 1.0}
    assert s["override_rate"]["C10"]["override_rate"] == 0.0
    assert list(s["override_rate"])[0] == "C03"                                     # highest first
    text = ol.format_summary(s)
    assert "C03" in text and "100%" in text


def test_summary_counts_each_run_separately():
    e1 = entry(action="fixed")
    e2 = dict(e1, run_id="RUN-TEST-2")
    assert ol.summary([e1, e2])["flags_with_action"] == 2


# ---------------------------------------------------------------- report integration
def test_report_lists_flags_for_the_log():
    r = rep.build_report(ROOT)
    refs = {f["flag_ref"] for f in r["flags"]}
    assert "tool:T1:audit_age|C10" in refs and "decision:D0001|C06" in refs
    assert all(f["verdict"] != "VERIFIED" for f in r["flags"])


def test_html_flag_history_column():
    r = rep.build_report(ROOT)
    assert "Flag history" not in rep.render_html(r)
    hist = {"tool:T1:audit_age|C10": {**entry(), "outcome_date": "2026-11-20"}}
    page = rep.render_html(r, hist)
    assert "Flag history" in page and "fixed<div class='muted'>HR lead · 2026-11-20</div>" in page


def test_cli_logs_and_summarises(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(REPORT), encoding="utf-8")
    log = tmp_path / "log.jsonl"
    cli = [sys.executable, str(ROOT / "scripts/log_outcome.py"), "--report", str(report), "--log", str(log)]
    ok = subprocess.run(cli + ["--flag", "tool:T1:audit_age|C10", "--seen-by", "HR lead", "--decided-by", "HR lead",
                               "--action", "fixed", "--note", "New audit ordered"], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    bad = subprocess.run(cli + ["--flag", "requirement:J1-R5|C03", "--seen-by", "Recruiter", "--decided-by", "HR lead",
                                "--action", "overridden", "--reason", "too short"], capture_output=True, text=True)
    assert bad.returncode == 1 and "at least 10 words" in bad.stderr
    summ = subprocess.run(cli + ["--summary"], capture_output=True, text=True)
    assert summ.returncode == 0 and "C10" in summ.stdout and len(ol.read(log)) == 1


def test_outcome_code_never_references_labels():
    import re
    literal = re.compile(r"""["'][^"'\n]*labels""")
    for p in (ROOT / "src/selfune_hv/outcome_log.py", ROOT / "scripts/log_outcome.py"):
        assert not literal.search(p.read_text(encoding="utf-8")), p.name
