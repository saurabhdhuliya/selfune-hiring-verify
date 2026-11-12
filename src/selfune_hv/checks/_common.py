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
        if verdict in ("UNVERIFIED", "CONTRADICTED", "ESCALATE") and self.soft(ids):
            return "WARN"
        return verdict


def finding(check: str, object_ref: str, verdict: str, ledger_refs: list[str], message: str) -> dict:
    return {"object_ref": object_ref, "check": check, "verdict": verdict,
            "ledger_refs": list(ledger_refs), "message": message}


def parse_date(value) -> date | None:
    """ISO date or None if missing/unparseable."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
