"""C09: emotion or personality inference about candidates. Blocks the chain (hard rule 1).

Reads data/synthetic/tools.json, data/synthetic/ai_text.jsonl, data/c9_corpus/c9_inputs.jsonl
and ledger/hiring.jsonl. Never reads labels/. Never labels a person: it only flags the tool or text.
"""
from __future__ import annotations

from pathlib import Path

from selfune_hv.emotion_terms import has_inference_cue, mentions_banned_construct

from ._common import LEGAL, MISSING, REPO_ROOT, Sources, finding, load_json, load_jsonl

CHECK_ID = "C09"
REFS = ["GT-0008"]
CORPUS = "data/c9_corpus/c9_inputs.jsonl"


def evaluate_tool(tool: dict) -> tuple[str, str]:
    infers = tool.get("infers_emotion", MISSING)
    outputs = str(tool.get("what_it_outputs") or "")
    if infers is True:
        return "ESCALATE", f"Tool declares it infers emotion. Outputs: '{outputs}'."
    if mentions_banned_construct(outputs):
        return "ESCALATE", f"Tool output names an emotion or personality construct: '{outputs}'."
    if isinstance(infers, str) and infers.strip().lower() == "unknown":
        return "UNVERIFIED", "Employer does not know whether the tool infers emotion: ask the employer or vendor."
    if infers is MISSING or infers is None:
        return "NOT_CHECKED", "infers_emotion is not stated, so emotion inference can't be ruled out: not a pass."
    return "VERIFIED", f"No emotion inference declared and none named in outputs ('{outputs}')."


def evaluate_text(text: str) -> tuple[str, str]:
    """ESCALATE only when the text shows the system inferring; emotion words alone are allowed."""
    if has_inference_cue(text):
        return "ESCALATE", "Text infers a candidate's emotion or personality."
    if mentions_banned_construct(text):
        return "VERIFIED", "Emotion words describe the task, behaviour or someone else's account, not an inference about the candidate."
    return "VERIFIED", "No emotion or personality inference."


def _msg(verdict: str, detail: str, cite: str, what: str = "text") -> str:
    """`what` is "tool" or "text". A finding never says "Blocked": only a chain that uses the tool/text is blocked."""
    if verdict == "ESCALATE":
        return f"Would block any decision chain that uses this {what}: {LEGAL}. {detail}{cite}"
    if verdict == "UNVERIFIED":
        return f"Ask a human: {LEGAL}. {detail}{cite}"
    if verdict == "NOT_CHECKED":
        return f"Not checked: {detail}{cite}"
    return f"{detail}{cite}"


def run(root: Path = REPO_ROOT) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    findings = []
    for tool in load_json(root / "data/synthetic/tools.json"):
        verdict, detail = evaluate_tool(tool)
        verdict = src.soften(verdict, REFS)
        findings.append(finding(CHECK_ID, f"tool:{tool['tool_id']}", verdict, REFS, _msg(verdict, detail, cite, "tool")))
    for t in load_jsonl(root / "data/synthetic/ai_text.jsonl"):
        verdict, detail = evaluate_text(t.get("text", ""))
        verdict = src.soften(verdict, REFS)
        findings.append(finding(CHECK_ID, f"ai_text:{t['text_id']}", verdict, REFS, _msg(verdict, detail, cite)))
    return findings


def run_corpus(root: Path = REPO_ROOT) -> list[dict]:
    """The C9 detector corpus. object_ref is "c9_corpus:<c9_id>"."""
    root = Path(root)
    src = Sources(root, REFS)
    cite = src.cite(REFS)
    findings = []
    for t in load_jsonl(root / CORPUS):
        verdict, detail = evaluate_text(t.get("text", ""))
        verdict = src.soften(verdict, REFS)
        findings.append(finding(CHECK_ID, f"c9_corpus:{t['c9_id']}", verdict, REFS, _msg(verdict, detail, cite)))
    return findings
