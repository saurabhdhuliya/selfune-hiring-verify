"""Shared helpers for code checks. Not a check itself (no CHECK_ID)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from selfune_hv import ledger

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGAL = "flag for review, not legal advice"


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


DEFAULT_DATA = "data/synthetic"
REQUIRED_FILES = ("company.json", "decisions.jsonl")
# Optional input files and what a missing one means: nothing to check (checks report NOT_CHECKED where it matters).
OPTIONAL_FILES = {"tools.json": [], "group_counts.json": {}, "tool_probes.jsonl": [], "ai_text.jsonl": [],
                  "policy_statements.jsonl": [], "role_memory.json": {"roles": []}}


def data_dir(root: Path, data: Path | str | None = None) -> Path:
    """The data folder: `data` if given (a company's own folder), else <root>/data/synthetic."""
    return Path(data) if data else Path(root) / DEFAULT_DATA


def data_file(root: Path, data: Path | str | None, name: str):
    """Load one input file from the data folder. Missing optional files are empty; missing required ones raise."""
    path = data_dir(root, data) / name
    if not path.exists():
        if name in OPTIONAL_FILES:
            return json.loads(json.dumps(OPTIONAL_FILES[name]))
        raise FileNotFoundError(f"{path} is required (see docs/schema.md)")
    return load_jsonl(path) if name.endswith(".jsonl") else load_json(path)


class Sources:
    """Ledger rows a check relies on: citation text, warnings, and whether every row is soft."""

    def __init__(self, root: Path, ids: list[str]):
        rows = ledger.load(str(Path(root) / "ledger/hiring.jsonl"))
        self.rows = {i: rows[i] for i in ids}

    def cite(self, ids: list[str]) -> str:
        parts = [ledger.cite(self.rows[i]) for i in ids]
        warns = [w for i in ids for w in ledger.row_warnings(self.rows[i])]
        text = " Source: " + "; ".join(parts) + "."
        if warns:
            text += " Ledger warnings: " + " ".join(warns)
        return text

    def soft(self, ids: list[str]) -> bool:
        """True when every cited row is contested or not locked: hard rule 7, warn only."""
        return all(self.rows[i]["use_as"] == "warn_only" or self.rows[i]["user_decision"] != "LOCKED"
                   for i in ids)

    def soften(self, verdict: str, ids: list[str]) -> str:
        """Hard rule 7: contested or pending rows never cause a hard fail.

        Only hard fails (CONTRADICTED, ESCALATE) drop to WARN. UNVERIFIED stays: it is not a fail but a
        question for a human, and a pending row is a reason to ask, not to stay quiet.
        """
        if verdict in ("CONTRADICTED", "ESCALATE") and self.soft(ids):
            return "WARN"
        return verdict


def finding(check: str, object_ref: str, verdict: str, ledger_refs: list[str], message: str) -> dict:
    return {"object_ref": object_ref, "check": check, "verdict": verdict,
            "ledger_refs": list(ledger_refs), "message": message}


MISSING = object()


def jobs_in(company: dict, code: str) -> set[str]:
    """Job IDs whose declared jurisdiction includes `code` (e.g. "EU", "IL", "IN", "NYC")."""
    return {j["job_id"] for j in company["jobs"] if code in (j.get("jurisdiction") or [])}


def tools_for(tools: list[dict], job_ids: set[str]) -> list[dict]:
    """Tools used on at least one of the given jobs."""
    return [t for t in tools if job_ids.intersection(t.get("job_ids") or [])]


def parse_date(value) -> date | None:
    """ISO date or None if missing/unparseable."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
