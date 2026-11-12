"""C14: India DPDP. Tools on jobs that declare "IN" need a consent notice and a stated retention period.

Reads <data>/company.json, tools.json and ledger/hiring.jsonl. Never reads labels/.
"""
from __future__ import annotations

from pathlib import Path

from ._common import data_file, LEGAL, MISSING, REPO_ROOT, Sources, finding, jobs_in, load_json, tools_for

CHECK_ID = "C14"
REFS = ["GT-0030"]
TIMING = ("Per the ledger, core DPDP duties apply 18 months after the Rules were notified in "
          "mid-November 2025; check whether they apply yet.")


def check_consent(tool: dict) -> tuple[str, str]:
    v = tool.get("consent_notice", MISSING)
    if v is MISSING:
        return "NOT_CHECKED", "consent_notice is not stated in the input: not a pass."
    if v is None or (isinstance(v, str) and not v.strip()):
        return "ESCALATE", "No consent notice recorded."
    return "VERIFIED", f"Consent notice {v}."


def check_retention(tool: dict) -> tuple[str, str]:
    v = tool.get("retention_days", MISSING)
    if v is MISSING:
        return "NOT_CHECKED", "retention_days is not stated in the input: not a pass."
    if v is None or (isinstance(v, str) and v.strip().lower() == "indefinite"):
        return "ESCALATE", f"Retention is {'not stated' if v is None else 'indefinite'}."
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        return "UNVERIFIED", f"Retention '{v}' is not a stated number of days: ask the employer."
    return "VERIFIED", f"Retention {v} days."


def run(root: Path = REPO_ROOT, data: Path | None = None) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    in_jobs = jobs_in(data_file(root, data, "company.json"), "IN")
    findings = []
    for tool in tools_for(data_file(root, data, "tools.json"), in_jobs):
        tid = tool["tool_id"]
        results = {"consent": check_consent(tool), "retention": check_retention(tool)}
        if all(v == "VERIFIED" for v, _ in results.values()):
            detail = " ".join(d for _, d in results.values())
            findings.append(finding(CHECK_ID, f"tool:{tid}:dpdp", "VERIFIED", REFS,
                                    f"India DPDP: {LEGAL}. {detail} {TIMING}{cite}"))
            continue
        for aspect, (verdict, detail) in results.items():
            if verdict == "VERIFIED":
                continue
            verdict = src.soften(verdict, REFS)
            head = "India DPDP not checked" if verdict == "NOT_CHECKED" else "India DPDP"
            findings.append(finding(CHECK_ID, f"tool:{tid}:{aspect}", verdict, REFS,
                                    f"{head} ({aspect}): {LEGAL}. {detail} {TIMING}{cite}"))
    return findings
