"""C10: NYC Local Law 144 on tools used for NYC jobs: scope, bias audit age, candidate notice.

Reads data/synthetic/company.json, data/synthetic/tools.json and ledger/hiring.jsonl.
Never reads labels/.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from ._common import LEGAL, REPO_ROOT, Sources, finding, load_json, parse_date

CHECK_ID = "C10"
IN_SCOPE_MODES = {"alone", "weighted_most", "overrides_human"}
MAX_AUDIT_AGE_DAYS = 365
MIN_NOTICE_BUSINESS_DAYS = 10
SCOPE_REFS = ["GT-0038", "GT-0002"]
AUDIT_REFS = ["GT-0036"]
NOTICE_REFS = ["GT-0037"]
ALL_REFS = SCOPE_REFS + AUDIT_REFS + NOTICE_REFS

_MISSING = object()


def business_days_between(start: date, end: date) -> int:
    """Mon-Fri days strictly between start and end. Public holidays are not excluded."""
    n, d = 0, start + timedelta(days=1)
    while d < end:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


def check_scope(tool: dict) -> tuple[str, str, bool | None]:
    """Return (verdict, detail, in_scope). in_scope is None when it can't be decided."""
    mode = tool.get("decision_mode")
    if mode is None:
        return "NOT_CHECKED", "decision_mode is missing, so scope can't be decided.", None
    in_scope = mode in IN_SCOPE_MODES
    actual = "in scope" if in_scope else "not in scope"
    claim = tool.get("employer_scope_claim")
    if claim is None:
        return "NOT_CHECKED", f"No employer scope claim given; decision_mode '{mode}' makes it {actual}.", in_scope
    claim_norm = " ".join(str(claim).lower().split())
    if claim_norm == "not in scope" and in_scope:
        return ("ESCALATE", f"Employer says 'not in scope', but decision_mode '{mode}' puts it in scope "
                "whatever the employer claims.", in_scope)
    if claim_norm == "in scope" and not in_scope:
        return ("VERIFIED", f"Employer treats it as in scope; decision_mode '{mode}' alone would not. "
                "Stricter than required.", in_scope)
    return "VERIFIED", f"Employer claim '{claim}' matches decision_mode '{mode}'.", in_scope


def check_audit(tool: dict) -> tuple[str, str]:
    audit = tool.get("last_bias_audit_date", _MISSING)
    if audit is _MISSING:
        return "NOT_CHECKED", "last_bias_audit_date is absent from the input: not a pass."
    if audit is None:
        return "ESCALATE", "No bias audit recorded for an in-scope tool."
    audit_d, use_d = parse_date(audit), parse_date(tool.get("first_use_date"))
    if audit_d is None or use_d is None:
        return "NOT_CHECKED", "Audit date or first use date is missing or not a valid date."
    age = (use_d - audit_d).days
    if age < 0:
        return "ESCALATE", f"Bias audit {audit} is dated after first use {tool['first_use_date']}."
    if age > MAX_AUDIT_AGE_DAYS:
        return "ESCALATE", (f"Bias audit {audit} was {age} days before first use {tool['first_use_date']}, "
                            f"more than {MAX_AUDIT_AGE_DAYS}.")
    return "VERIFIED", f"Bias audit {audit} was {age} days before first use {tool['first_use_date']}."


def check_notice(tool: dict) -> tuple[str, str]:
    notice = tool.get("notice_sent_date", _MISSING)
    if notice is _MISSING:
        return "NOT_CHECKED", "notice_sent_date is absent from the input: not a pass."
    if notice is None:
        return "ESCALATE", "No candidate notice recorded for an in-scope tool."
    notice_d, use_d = parse_date(notice), parse_date(tool.get("first_use_date"))
    if notice_d is None or use_d is None:
        return "NOT_CHECKED", "Notice date or first use date is missing or not a valid date."
    days = business_days_between(notice_d, use_d)
    detail = (f"Notice {notice} to first use {tool['first_use_date']}: {days} business days strictly between "
              "(Mon-Fri; public holidays not excluded)")
    if days < MIN_NOTICE_BUSINESS_DAYS:
        return "ESCALATE", f"{detail}, under {MIN_NOTICE_BUSINESS_DAYS}."
    return "VERIFIED", f"{detail}."


def run(root: Path = REPO_ROOT) -> list[dict]:
    root = Path(root)
    src = Sources(root, ALL_REFS)
    company = load_json(root / "data/synthetic/company.json")
    nyc_jobs = {j["job_id"] for j in company["jobs"] if "NYC" in (j.get("jurisdiction") or [])}

    def make(tid: str, aspect: str, verdict: str, detail: str, refs: list[str]) -> dict:
        verdict = src.soften(verdict, refs)
        head = "NYC LL144 not checked" if verdict == "NOT_CHECKED" else "NYC LL144"
        return finding(CHECK_ID, f"tool:{tid}:{aspect}", verdict, refs,
                       f"{head} ({aspect}): {LEGAL}. {detail}{src.cite(refs)}")

    findings = []
    for tool in load_json(root / "data/synthetic/tools.json"):
        if not nyc_jobs.intersection(tool.get("job_ids") or []):
            continue
        tid = tool["tool_id"]
        verdict, detail, in_scope = check_scope(tool)
        findings.append(make(tid, "scope", verdict, detail, SCOPE_REFS))
        if in_scope:
            findings.append(make(tid, "audit_age", *check_audit(tool), AUDIT_REFS))
            findings.append(make(tid, "notice", *check_notice(tool), NOTICE_REFS))
    return findings
