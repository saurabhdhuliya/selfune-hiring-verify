"""C05: four-fifths (4/5) rule on selection rates, per job and per grouping.

Flags for review only. This is not a legal finding (README hard rule 6).
Reads <data>/group_counts.json, <data>/company.json and ledger/hiring.jsonl.
Never reads labels/.
"""
from __future__ import annotations

import json
from pathlib import Path

from selfune_hv import ledger

from ._common import data_file

CHECK_ID = "C05"
LEDGER_ID = "GT-0023"
THRESHOLD = 0.8
SMALL_SAMPLE = 30

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _finding(object_ref: str, verdict: str, message: str) -> dict:
    return {
        "object_ref": object_ref,
        "check": CHECK_ID,
        "verdict": verdict,
        "ledger_refs": [LEDGER_ID],
        "message": message,
    }


def impact_ratio(groups: dict[str, dict]) -> float | None:
    """Lowest selection rate / highest, or None when undefined."""
    rates = [c["selected"] / c["applied"] for c in groups.values() if c.get("applied", 0) > 0]
    if len(rates) < 2 or max(rates) == 0:
        return None
    return min(rates) / max(rates)


def evaluate_grouping(groups: dict[str, dict]) -> tuple[str, str]:
    """Return (verdict, detail) for one grouping, e.g. {"women": {"applied": 40, "selected": 6}, ...}."""
    rates = {g: c["selected"] / c["applied"] for g, c in groups.items() if c.get("applied", 0) > 0}
    if len(rates) < 2:
        return "NOT_CHECKED", "Fewer than two groups with applicants: no rate comparison possible."
    hi = max(rates.values())
    if hi == 0:
        return "NOT_CHECKED", "No group had anyone selected: the impact ratio is undefined."
    lo_group = min(rates, key=rates.get)
    hi_group = max(rates, key=rates.get)
    ratio = rates[lo_group] / hi
    rate_txt = ", ".join(f"{g} {c['selected']}/{c['applied']} = {rates[g]:.3f}"
                         for g, c in groups.items() if g in rates)
    detail = f"Selection rates: {rate_txt}. Impact ratio {lo_group}/{hi_group} = {ratio:.2f}"
    if ratio < THRESHOLD:
        verdict = "UNVERIFIED"
        detail += f", below {THRESHOLD}."
    else:
        verdict = "VERIFIED"
        detail += f", at or above {THRESHOLD}."
    small = [g for g, c in groups.items() if c.get("applied", 0) < SMALL_SAMPLE]
    if small:
        detail += (f" Note: small sample ({', '.join(small)} under {SMALL_SAMPLE} applicants); "
                   f"small samples weaken the 4/5 rule ({LEDGER_ID}).")
    return verdict, detail


def run(root: Path = REPO_ROOT, data: Path | None = None) -> list[dict]:
    root = Path(root)
    counts = data_file(root, data, "group_counts.json")
    company = data_file(root, data, "company.json")
    row = ledger.load(str(root / "ledger/hiring.jsonl"))[LEDGER_ID]
    citation = ledger.cite(row)
    warnings = ledger.row_warnings(row)
    # The verdict is a code result (the ratio); GT-0023 is cited for context. UNVERIFIED is never a hard
    # fail (hard rule 7), so a pending GT-0023 shows up as a ledger warning in the message, not a softer verdict.
    heuristic = ("The four-fifths rule is a screening heuristic whose federal guideline status is changing "
                 f"({LEDGER_ID}); disparity still matters under discrimination law. Flag for review, not legal advice.")

    def message(verdict: str, detail: str, ratio: float | None = None) -> str:
        if verdict == "UNVERIFIED":
            head = f"Statistical flag: impact ratio {ratio:.2f} below {THRESHOLD}. {heuristic}"
        elif verdict == "VERIFIED":
            head = (f"Statistical check: impact ratio {ratio:.2f} at or above {THRESHOLD}; this does not rule out "
                    f"discrimination. {heuristic}")
        else:
            head = f"Not checked: this is not a pass. {heuristic}"
        tail = f" Source: {citation}."
        if warnings:
            tail += " Ledger warnings: " + " ".join(warnings)
        return f"{head} {detail}{tail}"

    findings = []
    for job in company["jobs"]:
        job_id = job["job_id"]
        groupings = counts.get(job_id) or {}
        if not groupings:
            findings.append(_finding(
                f"group_counts:{job_id}", "NOT_CHECKED",
                message("NOT_CHECKED", f"No group counts provided for {job_id}; this is not a pass.")))
            continue
        for grouping, groups in groupings.items():
            verdict, detail = evaluate_grouping(groups)
            findings.append(_finding(f"group_counts:{job_id}:{grouping}", verdict,
                                     message(verdict, detail, impact_ratio(groups))))
    return findings
