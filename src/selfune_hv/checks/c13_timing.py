"""C13: dates in policy statements about the EU AI Act high-risk duties or the Colorado AI law.

Reads <data>/company.json, policy_statements.jsonl and ledger/hiring.jsonl. Never reads labels/.
- Row CONTESTED (or warn_only): every finding is WARN.
- Otherwise: the statement's date matches the ledger date -> VERIFIED; differs -> CONTRADICTED;
  no date -> UNVERIFIED. A pending row turns CONTRADICTED into WARN (hard rule 7).
"""
from __future__ import annotations

import re
from pathlib import Path

from ._common import data_file, LEGAL, REPO_ROOT, Sources, finding, jobs_in, load_json, load_jsonl

CHECK_ID = "C13"

# topic -> (ledger row, jurisdiction code the job must declare, how to spot it, the key date in that row)
TOPICS = {
    "EU AI Act high-risk": ("GT-0009", "EU",
                            re.compile(r"\b(?:EU|AI Act)\b.*\bhigh[- ]risk\b|\bhigh[- ]risk\b.*\b(?:EU|AI Act)\b", re.I),
                            "2 December 2027"),
    "Colorado AI law": ("GT-0025", "CO", re.compile(r"\bColorado\b", re.I), "1 January 2027"),
}
_DATE = re.compile(r"\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|"
                   r"November|December) \d{4}\b")


def run(root: Path = REPO_ROOT, data: Path | None = None) -> list[dict]:
    root = Path(root)
    company = data_file(root, data, "company.json")
    refs_all = [t[0] for t in TOPICS.values()]
    src = Sources(root, refs_all)
    findings = []
    for s in data_file(root, data, "policy_statements.jsonl"):
        text = s.get("text", "")
        for topic, (ref, code, pattern, ledger_date) in TOPICS.items():
            if not pattern.search(text):
                continue
            job = s.get("job_id")
            if job is not None and job not in jobs_in(company, code):
                continue   # only for jurisdictions the job declares
            row = src.rows[ref]
            if ledger_date not in row["claim"]:
                ledger_note = f"The ledger text for {ref} no longer contains {ledger_date}: re-read the row."
            else:
                ledger_note = f"The ledger date for {topic} is {ledger_date} ({ref})."
            stated = _DATE.findall(text)
            if not stated:
                verdict, compare = "UNVERIFIED", "The statement gives no date to compare: ask which date it relies on."
            elif ledger_date in stated:
                verdict, compare = "VERIFIED", f"The statement's date ({', '.join(stated)}) matches the ledger date."
            else:
                verdict, compare = "CONTRADICTED", f"The statement's date ({', '.join(stated)}) differs from the ledger date."
            contested = row.get("status") == "CONTESTED" or row.get("use_as") == "warn_only"
            if contested:
                verdict, status = "WARN", f"{ref} is CONTESTED: warning only."
            else:
                softened = src.soften(verdict, [ref])
                status = (f"{ref} is {row['user_decision']}: it awaits a human re-lock, so this is a warning only."
                          if softened != verdict else f"{ref} is {row['user_decision']}.")
                verdict = softened
            head = "Timing check" if verdict == "VERIFIED" else "Timing flag"
            msg = f"{head}, {topic}: {LEGAL}. {ledger_note} {compare} {status}{src.cite([ref])}"
            findings.append(finding(CHECK_ID, f"policy:{s['stmt_id']}", verdict, [ref], msg))
    return findings
