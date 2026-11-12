"""Load the locked ledger and report rows that cannot be used as proof."""
from __future__ import annotations

import json
from datetime import date


def load(path: str = "ledger/hiring.jsonl") -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        return {r["id"]: r for r in (json.loads(l) for l in f if l.strip())}


def row_warnings(row: dict, today: date | None = None) -> list[str]:
    today = today or date.today()
    w = []
    if date.fromisoformat(row["recheck_by"]) < today:
        w.append(f"{row['id']} expired on {row['recheck_by']}: re-check before relying on it.")
    if row["user_decision"] != "LOCKED":
        w.append(f"{row['id']} is {row['user_decision']}: a human has not locked this version.")
    if row["use_as"] == "warn_only":
        w.append(f"{row['id']} is CONTESTED: warning only, never a hard fail.")
    if row["use_as"] == "context_only":
        w.append(f"{row['id']}: {row['display_label']}.")
    return w


def cite(row: dict) -> str:
    """How every flag cites a row: ID, label, source URL, retrieved date. Not legal advice."""
    ev = row["evidence"]
    return f"{row['id']} ({row['display_label']}; {ev['url']}; retrieved {ev['retrieved']})"
