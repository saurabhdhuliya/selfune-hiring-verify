"""C01: undefined trait in a requirement or AI-written text.

baseline - AVL agent mode will handle unclear cases later

Rule-based, no LLM. Looks up role memory first: an ACTIVE definition verifies the trait without
asking anyone. Otherwise a vague trait word with no number, threshold or test gets one question.
Reads <data>/company.json, role_memory.json, ai_text.jsonl and ledger/hiring.jsonl.
Never reads labels/.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from selfune_hv.role_memory import RoleMemory

from ._common import data_file, REPO_ROOT, Sources, finding, load_json, load_jsonl

CHECK_ID = "C01"
BASELINE = True
REFS = ["GT-0019", "GT-0021"]

TRAIT_WORDS = ["strong", "excellent", "exceptional", "great", "good", "amazing", "rockstar", "ninja",
               "team player", "culture fit", "attitude", "energy", "drive", "attention to detail", "proficient"]
_TRAIT = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in TRAIT_WORDS) + r")\b", re.I)
# A number, a threshold or a test makes the requirement checkable.
_MEASURED = re.compile(r"\d|\b(?:test(?:ed|s)?|measured|score[ds]?|exercise|work sample|threshold|"
                       r"at least|at most|minimum|maximum|benchmark|rubric)\b", re.I)


def trait_words(text: str) -> list[str]:
    seen = []
    for m in _TRAIT.finditer(text):
        w = m.group(0).lower()
        if w not in seen:
            seen.append(w)
    return seen


def _question(text: str, words: list[str], role_title: str) -> str:
    text = text.rstrip(". ")
    q = RoleMemory.question_for(text, role_title)
    if len(q.split()) >= 25:   # long requirement: ask about the vague words only
        q = RoleMemory.question_for(" ".join(words), role_title)
    return q


def evaluate(text: str, role_id: str, role_title: str, memory: RoleMemory) -> tuple[str, str, dict]:
    """Return (verdict, detail, extra fields for the finding)."""
    look = memory.lookup(role_id, text)
    if look.status == "FOUND":
        # Anything vague left once the defined term is removed is still undefined.
        rest = re.sub(re.escape(look.matched_term), " ", text, flags=re.I)
        left = [w for w in trait_words(rest) if not _MEASURED.search(rest)]
        if not left:
            t = look.trait
            return ("VERIFIED", f"Defined in role memory {t['trait_id']} ('{look.matched_term}'): "
                    f"{t['definition']} Measured by {t.get('measured_by', 'n/a')}.", {"trait_ref": t["trait_id"]})
        words = left
        status_note = f"Role memory {look.trait['trait_id']} covers '{look.matched_term}' but not: {', '.join(words)}."
    else:
        words = trait_words(text)
        if not words or _MEASURED.search(text):
            return "VERIFIED", "No undefined trait word, or the requirement has a number, threshold or test.", {}
        status_note = {"STALE": f"Role memory definition for '{look.matched_term}' is stale (review date passed).",
                       "RETIRED": f"Role memory definition for '{look.matched_term}' is retired.",
                       "MISSING": "No role memory definition."}[look.status]
    q = _question(text, words, role_title)
    detail = f"Undefined trait ({', '.join(words)}) with no number, threshold or test. {status_note} Ask once per role: {q}"
    extra = {"question": q}
    if look.trait:
        extra["trait_ref"] = look.trait["trait_id"]
    return "UNVERIFIED", detail, extra


def run(root: Path = REPO_ROOT, today: date | None = None, data: Path | None = None) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    company = data_file(root, data, "company.json")
    memory = RoleMemory(data_file(root, data, "role_memory.json"), today)
    titles = {j["job_id"]: j["title"] for j in company["jobs"]}

    def make(ref: str, text: str, job_id: str) -> dict:
        verdict, detail, extra = evaluate(text, job_id, titles.get(job_id, job_id), memory)
        verdict = src.soften(verdict, REFS)
        head = "Flag for review" if verdict == "UNVERIFIED" else "OK"
        return {**finding(CHECK_ID, ref, verdict, REFS, f"{head} (baseline): {detail}{cite}"), **extra}

    findings = [make(f"requirement:{r['req_id']}", r["text"], j["job_id"])
                for j in company["jobs"] for r in j.get("requirements", [])]
    findings += [make(f"ai_text:{t['text_id']}", t.get("text", ""), t.get("job_id"))
                 for t in data_file(root, data, "ai_text.jsonl")]
    return findings
