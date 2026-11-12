"""C11: GDPR Article 22, solely automated decisions. EU jobs only.

Reads <data>/company.json, tools.json, decisions.jsonl and ledger/hiring.jsonl. Never reads labels/.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._common import (data_file, LEGAL, MISSING, REPO_ROOT, Sources, finding, jobs_in, load_json, load_jsonl,
                      tools_for)

CHECK_ID = "C11"
REFS = ["GT-0048", "GT-0049"]

_HUMAN_REVIEW = re.compile(r"human review|reviewed by (?:a )?human|human reviewer|manual(?:ly)? review", re.I)
_NEGATED = re.compile(r"\b(?:no|without|not|never)\b[^.;]{0,25}(?:human review|reviewed by (?:a )?human|"
                      r"human reviewer|manual(?:ly)? review)", re.I)


def reason_shows_human_review(reason: str) -> bool:
    """True if the reason says a human reviewed it. 'No human review' does not count."""
    return bool(_HUMAN_REVIEW.search(reason)) and not _NEGATED.search(reason)


def evaluate_tool(tool: dict) -> tuple[str, str]:
    mode = tool.get("decision_mode")
    if mode is None:
        return "NOT_CHECKED", "decision_mode is missing: can't tell if the tool decides alone."
    if mode != "alone":
        return "VERIFIED", f"decision_mode '{mode}': the tool does not decide alone."
    hr, lb = tool.get("human_review", MISSING), tool.get("lawful_basis", MISSING)
    gaps = []
    if hr is False:
        gaps.append("no human review")
    if lb is None:
        gaps.append("no lawful basis recorded")
    if gaps:
        return "ESCALATE", f"Tool decides alone with {' and '.join(gaps)}."
    if hr is MISSING or lb is MISSING:
        return "NOT_CHECKED", "Tool decides alone, but human_review or lawful_basis is not stated."
    return "VERIFIED", f"Tool decides alone, with human review and lawful basis '{lb}'."


def evaluate_decision(d: dict) -> tuple[str, str]:
    by = d.get("decided_by")
    if by is None:
        return "NOT_CHECKED", "decided_by is missing: can't tell if the decision was solely automated."
    reason = d.get("reason_text", "")
    if by == "tool" and not reason_shows_human_review(reason):
        return "ESCALATE", f"Decided by a tool with no human review in the stated reason: '{reason}'."
    return "VERIFIED", f"decided_by '{by}'."


def run(root: Path = REPO_ROOT, data: Path | None = None) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    eu_jobs = jobs_in(data_file(root, data, "company.json"), "EU")

    def make(ref: str, verdict: str, detail: str) -> dict:
        verdict = src.soften(verdict, REFS)
        head = "GDPR Art 22 not checked" if verdict == "NOT_CHECKED" else "GDPR Art 22"
        return finding(CHECK_ID, ref, verdict, REFS, f"{head}: {LEGAL}. {detail}{cite}")

    findings = [make(f"tool:{t['tool_id']}", *evaluate_tool(t))
                for t in tools_for(data_file(root, data, "tools.json"), eu_jobs)]
    findings += [make(f"decision:{d['decision_id']}", *evaluate_decision(d))
                 for d in data_file(root, data, "decisions.jsonl") if d.get("job_id") in eu_jobs]
    return findings
