"""C12: Illinois (HB 3773). Every tool on a job that declares "IL" needs a notice and a disparate-effect review.

Reads data/synthetic/company.json, tools.json and ledger/hiring.jsonl. Never reads labels/.
"""
from __future__ import annotations

from pathlib import Path

from ._common import LEGAL, MISSING, REPO_ROOT, Sources, finding, jobs_in, load_json, tools_for

CHECK_ID = "C12"
REFS = ["GT-0031"]
FIELDS = {"il_notice_sent": "Illinois notice", "il_disparate_effect_review": "disparate-effect review"}


def evaluate_tool(tool: dict) -> tuple[str, str]:
    values = {f: tool.get(f, MISSING) for f in FIELDS}
    null = [FIELDS[f] for f, v in values.items() if v is None]
    absent = [FIELDS[f] for f, v in values.items() if v is MISSING]
    mode = tool.get("decision_mode", "not stated")
    if null:
        return "ESCALATE", f"No {' and no '.join(null)} recorded (decision_mode '{mode}')."
    if absent:
        return "NOT_CHECKED", f"{' and '.join(absent).capitalize()} not stated in the input: not a pass."
    return "VERIFIED", (f"Notice {values['il_notice_sent']}; disparate-effect review: "
                        f"{values['il_disparate_effect_review']}.")


def run(root: Path = REPO_ROOT) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    il_jobs = jobs_in(load_json(root / "data/synthetic/company.json"), "IL")
    findings = []
    for tool in tools_for(load_json(root / "data/synthetic/tools.json"), il_jobs):
        verdict, detail = evaluate_tool(tool)
        verdict = src.soften(verdict, REFS)
        head = "Illinois not checked" if verdict == "NOT_CHECKED" else "Illinois"
        findings.append(finding(CHECK_ID, f"tool:{tool['tool_id']}:illinois", verdict, REFS,
                                f"{head}: {LEGAL}. {detail}{cite}"))
    return findings
