"""C06: a missing field treated as a negative.

baseline - AVL agent mode will handle unclear cases later

Rule-based, no LLM. Reads <data>/decisions.jsonl. Never reads labels/.
"A field is empty" is a fact; "so the candidate is weak" is a conclusion the data doesn't support.
"""
from __future__ import annotations

from pathlib import Path

from ._common import data_file, MISSING, REPO_ROOT, finding, load_jsonl

CHECK_ID = "C06"
BASELINE = True
REFS: list[str] = []


def evaluate(d: dict) -> tuple[str, str]:
    missing = d.get("fields_missing", MISSING)
    if missing is MISSING:
        return "NOT_CHECKED", "fields_missing is not recorded: can't tell if a gap was used against the candidate."
    if not missing:
        return "VERIFIED", "No missing fields."
    outcome = d.get("outcome")
    if outcome == "rejected":
        return "UNVERIFIED", (f"Rejected with missing field(s) {', '.join(missing)}. An empty field is a fact, not "
                              f"evidence about the candidate. Reason given: '{d.get('reason_text', '')}'. "
                              "Ask for the field, or decide on data that is present.")
    if outcome == "on_hold":
        return "VERIFIED", f"Missing field(s) {', '.join(missing)} routed to a human (on hold), not used as a negative."
    return "VERIFIED", f"Missing field(s) {', '.join(missing)}, but outcome '{outcome}' is not a negative."


def run(root: Path = REPO_ROOT, data: Path | None = None) -> list[dict]:
    findings = []
    for d in data_file(root, data, "decisions.jsonl"):
        verdict, detail = evaluate(d)
        head = {"UNVERIFIED": "Flag for review", "NOT_CHECKED": "Not checked"}.get(verdict, "OK")
        findings.append(finding(CHECK_ID, f"decision:{d['decision_id']}", verdict, REFS, f"{head} (baseline): {detail}"))
    return findings
