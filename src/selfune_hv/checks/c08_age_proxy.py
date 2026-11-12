"""C08: age or age proxy in tool rules or decision reasons.

Reads data/synthetic/tools.json, data/synthetic/decisions.jsonl and ledger/hiring.jsonl.
Never reads labels/.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._common import LEGAL, REPO_ROOT, Sources, finding, load_json, load_jsonl

CHECK_ID = "C08"
REFS = ["GT-0027", "GT-0024"]

# Word-bounded so "stage", "manage" or "AgeSmart" don't match "age".
AGE_TERMS = re.compile(
    r"\bage[ds]?\b"
    r"|\bdate of birth\b|\bdob\b"
    r"|\bbirth ?year\b|\byear of birth\b"
    r"|\bgraduation ?year\b|\byear of graduation\b"
    r"|\byears? since (?:graduation|graduating|graduated)\b"
)


def age_terms(text: str) -> list[str]:
    """Age or age-proxy terms in text. Underscores and hyphens count as spaces (graduation_year)."""
    norm = re.sub(r"[_\-]", " ", str(text).lower())
    return sorted({m.group(0) for m in AGE_TERMS.finditer(norm)})


def run(root: Path = REPO_ROOT) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    findings = []

    for tool in load_json(root / "data/synthetic/tools.json"):
        tid = tool["tool_id"]
        rules = tool.get("rules") or []
        hits = [(r, age_terms(r)) for r in rules]
        hits = [(r, t) for r, t in hits if t]
        if hits:
            shown = "; ".join(f"'{r}' ({', '.join(t)})" for r, t in hits)
            verdict = src.soften("ESCALATE", REFS)
            findings.append(finding(CHECK_ID, f"tool:{tid}:age_rule", verdict, REFS,
                                    f"Age or age-proxy rule in tool {tid}: {LEGAL}. Rule: {shown}.{cite}"))
        else:
            basis = f"{len(rules)} rule(s) listed" if rules else "no rules listed"
            findings.append(finding(CHECK_ID, f"tool:{tid}:rules", "VERIFIED", REFS,
                                    f"No age or age-proxy rule in tool {tid} ({basis}).{cite}"))

    for d in load_jsonl(root / "data/synthetic/decisions.jsonl"):
        did = d["decision_id"]
        terms = age_terms(d.get("reason_text", ""))
        if terms:
            verdict = src.soften("ESCALATE", REFS)
            msg = (f"Decision reason uses an age or age proxy ({', '.join(terms)}): {LEGAL}. "
                   f"Reason: '{d['reason_text']}'.{cite}")
        else:
            verdict, msg = "VERIFIED", f"No age or age-proxy term in the stated reason.{cite}"
        findings.append(finding(CHECK_ID, f"decision:{did}", verdict, REFS, msg))
    return findings
