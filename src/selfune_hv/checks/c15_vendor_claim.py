"""C15: a vendor or tool claim used as proof for an outcome.

baseline - AVL agent mode will handle unclear cases later

Rule-based, no LLM. Reads <data>/decisions.jsonl, ai_text.jsonl, tools.json and
ledger/hiring.jsonl. Never reads labels/.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._common import data_file, REPO_ROOT, Sources, finding, load_json, load_jsonl

CHECK_ID = "C15"
BASELINE = True
REFS = ["GT-0015", "GT-0017"]

CLAIM = re.compile(r"\bvendor\b|\baccuracy\b|\bmeasures\b|\bproves?\b|\bindustry data\b", re.I)
# Text that marks the claim as a claim, not evidence.
LABELLED = re.compile(r"\bnot (?:independently )?validated\b|\bunvalidated\b|\bnot used as (?:decision )?evidence\b|"
                      r"\bnot (?:used|relied on) (?:for|in) (?:the )?decision\b|\bclaim only\b", re.I)


def evaluate_text(text: str) -> tuple[str, str]:
    cues = sorted({m.group(0).lower() for m in CLAIM.finditer(text)})
    if not cues:
        return "VERIFIED", "No vendor or tool claim cited."
    if LABELLED.search(text):
        return "VERIFIED", f"Vendor claim ({', '.join(cues)}) is labelled as unvalidated / not used as evidence."
    return "UNVERIFIED", (f"Vendor or tool claim ({', '.join(cues)}) used as grounds: '{text}'. A vendor's claim "
                          "is context, not proof. Ask for the employer's own validation data.")


def run(root: Path = REPO_ROOT, data: Path | None = None) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)

    def make(ref: str, verdict: str, detail: str) -> dict:
        verdict = src.soften(verdict, REFS)
        head = "Flag for review" if verdict == "UNVERIFIED" else "OK"
        return finding(CHECK_ID, ref, verdict, REFS, f"{head} (baseline): {detail}{cite}")

    texts = [(f"decision:{d['decision_id']}", d.get("reason_text", ""))
             for d in data_file(root, data, "decisions.jsonl")]
    texts += [(f"ai_text:{t['text_id']}", t.get("text", ""))
              for t in data_file(root, data, "ai_text.jsonl")]
    results = [(ref, text, *evaluate_text(text)) for ref, text in texts]
    findings = [make(ref, verdict, detail) for ref, _, verdict, detail in results]

    # Tools with vendor claims: flagged only if a flagged text names the tool.
    for tool in data_file(root, data, "tools.json"):
        if not tool.get("vendor_claims"):
            continue
        name = tool.get("name", "")
        used = [ref for ref, text, v, _ in results
                if v == "UNVERIFIED" and name and re.search(rf"\b{re.escape(name)}\b", text, re.I)]
        if used:
            verdict, detail = "UNVERIFIED", f"Vendor claim for {name} used as grounds in {', '.join(used)}."
        else:
            verdict, detail = "VERIFIED", (f"Vendor claim for {name} is listed but no text uses it as grounds "
                                           "(matched by tool name only).")
        findings.append(make(f"tool:{tool['tool_id']}:vendor_claim", verdict, detail))
    return findings
