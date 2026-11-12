"""C03: requirement with no stated reason (why it serves the role).

baseline - AVL agent mode will handle unclear cases later

Rule-based, no LLM. Reads data/synthetic/company.json and ledger/hiring.jsonl. Never reads labels/.
Only checks that a reason is stated, not that the reason is true.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._common import REPO_ROOT, Sources, finding, load_json

CHECK_ID = "C03"
BASELINE = True
REFS = ["GT-0020"]

# "to" counts only as a purpose clause ("in order to", "so as to", ", to keep ..."), not "contributed to".
REASON = re.compile(r"\bbecause\b|\bso that\b|\brequired by\b|\bin order to\b|\bso as to\b|,\s*to\s+[a-z]+", re.I)


def stated_reason(text: str) -> str | None:
    m = REASON.search(text)
    return m.group(0).strip(" ,") if m else None


def run(root: Path = REPO_ROOT) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    findings = []
    for job in load_json(root / "data/synthetic/company.json")["jobs"]:
        for r in job.get("requirements", []):
            cue = stated_reason(r["text"])
            if cue:
                verdict, msg = "VERIFIED", f"OK (baseline): reason stated ('{cue}'); its truth is not checked here.{cite}"
            else:
                verdict = src.soften("UNVERIFIED", REFS)
                msg = (f"Flag for review (baseline): no stated reason why '{r['text']}' serves the role. "
                       f"Ask how it predicts success in this role.{cite}")
            findings.append(finding(CHECK_ID, f"requirement:{r['req_id']}", verdict, REFS, msg))
    return findings
