"""C02: a years-of-experience count used as a proxy for ability.

baseline - AVL agent mode will handle unclear cases later

Rule-based, no LLM. Reads data/synthetic/company.json and ledger/hiring.jsonl. Never reads labels/.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._common import REPO_ROOT, Sources, finding, load_json

CHECK_ID = "C02"
BASELINE = True
REFS = ["GT-0019"]

_NUM = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty)"
# "5 years", "3+ years", "5-7 years", "five yrs"; not "years old" or "years since" (age: C08).
YEARS = re.compile(rf"\b{_NUM}(?:\s*(?:-|to)\s*{_NUM})?\s*\+?\s*(?:years?|yrs?)\b(?!\s+(?:old|of age|since))", re.I)


def years_counts(text: str) -> list[str]:
    return [m.group(0) for m in YEARS.finditer(text)]


def run(root: Path = REPO_ROOT) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    findings = []
    for job in load_json(root / "data/synthetic/company.json")["jobs"]:
        for r in job.get("requirements", []):
            hits = years_counts(r["text"])
            if hits:
                verdict = src.soften("UNVERIFIED", REFS)
                msg = (f"Flag for review (baseline): years count ({', '.join(hits)}) used as a proxy for ability. "
                       f"Ask what the years should show, and test that directly.{cite}")
            else:
                verdict, msg = "VERIFIED", f"OK (baseline): no years-of-experience count.{cite}"
            findings.append(finding(CHECK_ID, f"requirement:{r['req_id']}", verdict, REFS, msg))
    return findings
