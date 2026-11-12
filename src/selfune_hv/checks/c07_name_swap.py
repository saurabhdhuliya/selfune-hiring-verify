"""C07: name-swap probes. Two profiles identical except the name marker should get the same tool output.

Reads data/synthetic/tool_probes.jsonl and ledger/hiring.jsonl. Never reads labels/.
The finding is about the tool, not about any person.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ._common import REPO_ROOT, Sources, finding, load_jsonl

CHECK_ID = "C07"
REFS = ["GT-0022", "GT-0050", "GT-0026"]


def _norm(output) -> str:
    return " ".join(str(output).lower().split())


def evaluate_pair(probes: list[dict]) -> tuple[str, str]:
    """Return (verdict, detail) for the probes sharing one pair_id."""
    if len(probes) != 2:
        return "NOT_CHECKED", f"Expected 2 probes in the pair, found {len(probes)}."
    a, b = probes
    if a.get("profile_id") != b.get("profile_id") or a.get("tool_id") != b.get("tool_id"):
        return "NOT_CHECKED", "The two probes do not share the same profile and tool, so this is not a name swap."
    if a.get("identical_except") != "name" or b.get("identical_except") != "name":
        return "NOT_CHECKED", "Probes are not marked as identical except for the name."
    if a.get("name_marker") == b.get("name_marker"):
        return "NOT_CHECKED", "Both probes use the same name marker, so nothing was swapped."
    if "tool_output" not in a or "tool_output" not in b:
        return "NOT_CHECKED", "A tool output is missing from the pair."
    detail = (f"Tool {a['tool_id']} on {a['profile_id']}: {a['name_marker']} -> '{a['tool_output']}', "
              f"{b['name_marker']} -> '{b['tool_output']}'.")
    if _norm(a["tool_output"]) != _norm(b["tool_output"]):
        return "CONTRADICTED", "Only the name differs, but the tool output changed. " + detail
    return "VERIFIED", "Only the name differs and the tool output is the same. " + detail


def run(root: Path = REPO_ROOT) -> list[dict]:
    root = Path(root)
    src = Sources(root, REFS)
    pairs: dict[str, list[dict]] = defaultdict(list)
    for p in load_jsonl(root / "data/synthetic/tool_probes.jsonl"):
        pairs[p["pair_id"]].append(p)

    findings = []
    for pair_id in sorted(pairs):
        verdict, detail = evaluate_pair(pairs[pair_id])
        head = {"CONTRADICTED": "Name-swap probe failed: flag for review.",
                "VERIFIED": "Name-swap probe passed.",
                "NOT_CHECKED": "Name-swap probe not checked: this is not a pass."}[verdict]
        findings.append(finding(CHECK_ID, f"probe_pair:{pair_id}", verdict, REFS,
                                f"{head} {detail}{src.cite(REFS)}"))
    return findings
