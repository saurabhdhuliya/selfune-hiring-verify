"""C04: weak selection method. Holistic combination, or an unstructured interview as the only interview.

Reads <data>/company.json and ledger/hiring.jsonl. Never reads labels/.
"""
from __future__ import annotations

from pathlib import Path

from ._common import data_file, REPO_ROOT, Sources, finding, load_json

CHECK_ID = "C04"
REFS = ["GT-0006", "GT-0007", "GT-0033"]


def evaluate_method(method: dict | None) -> tuple[str, str]:
    if not method or not method.get("stages") or not method.get("combine"):
        return "NOT_CHECKED", "Selection stages or combination rule missing: not a pass."
    stages = [str(s) for s in method["stages"]]
    combine = str(method["combine"]).strip().lower()
    interviews = [s for s in stages if "interview" in s.lower()]
    problems = []
    if combine == "holistic":
        problems.append("results are combined holistically (judgment), which loses validity against "
                        "mechanical combination (GT-0033)")
    if interviews and all("unstructured" in s.lower() for s in interviews):
        problems.append("the only interview is unstructured; structured interviews rank highest (GT-0006, GT-0007)")
    detail = f"Stages: {', '.join(stages)}; combine: {method['combine']}."
    if problems:
        return "UNVERIFIED", "Weak selection method: " + "; ".join(problems) + ". " + detail
    return "VERIFIED", detail


def run(root: Path = REPO_ROOT, data: Path | None = None) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    findings = []
    for job in data_file(root, data, "company.json")["jobs"]:
        verdict, detail = evaluate_method(job.get("selection_method"))
        verdict = src.soften(verdict, REFS)
        head = "Not checked" if verdict == "NOT_CHECKED" else "Flag for review" if verdict != "VERIFIED" else "OK"
        findings.append(finding(CHECK_ID, f"job:{job['job_id']}:selection_method", verdict, REFS,
                                f"{head}: {detail}{src.cite(REFS)}"))
    return findings
