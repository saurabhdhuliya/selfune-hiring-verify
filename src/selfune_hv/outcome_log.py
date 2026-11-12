"""Outcome log: what people did with each flag. Append-only JSONL, kept local (out/ is git-ignored). No LLM.

One entry per action on a flag. Roles only, never names. Free text may not contain candidate refs,
emails or phone numbers. The log is how we learn which checks people disagree with (override rate).
Never reads labels/.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ACTIONS = ("accepted", "overridden", "fixed", "deferred")
MIN_OVERRIDE_WORDS = 10
FIELDS = ("logged_at", "run_id", "flag_ref", "verdict_shown", "seen_by_role", "decided_by_role", "action",
          "override_reason", "outcome_note", "outcome_date")
FREE_TEXT = ("seen_by_role", "decided_by_role", "override_reason", "outcome_note")

CAND = re.compile(r"CAND-\d+", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_CANDIDATE = re.compile(r"\+?\(?\d[\d\s().-]{6,}\d")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# A role names a function. "HR lead", "Hiring manager", "Interview panel" pass; "Jane Smith" does not.
ROLE_WORDS = re.compile(
    r"\b(?:hr|people|talent|recruit\w*|hiring|lead|head|manager|director|officer|partner|panel|committee|team|"
    r"engineer\w*|analyst|admin\w*|coordinator|specialist|counsel|legal|compliance|dpo|ops|operations|owner|"
    r"founder|ceo|cto|cfo|coo|vp|chief|interviewer|reviewer|auditor|supervisor|executive)\b", re.I)


def has_phone(text: str) -> bool:
    for m in _PHONE_CANDIDATE.finditer(text):
        s = m.group(0).strip()
        rest = _ISO_DATE.sub("", s)
        if sum(c.isdigit() for c in rest) >= 9:
            return True
    return False


def pii_problems(field: str, text: str) -> list[str]:
    out = []
    if CAND.search(text):
        out.append(f"{field} contains a candidate reference (CAND-...); describe the process, not the person")
    if EMAIL.search(text):
        out.append(f"{field} contains an email address")
    if has_phone(text):
        out.append(f"{field} contains a phone number")
    return out


def flag_ref(object_ref: str, check: str) -> str:
    return f"{object_ref}|{check}"


def run_flags(report: dict) -> dict[str, str]:
    """flag_ref -> verdict for every flag shown in this run."""
    return {f["flag_ref"]: f["verdict"] for f in report.get("flags", [])}


def validate(entry: dict, report: dict) -> list[str]:
    """Return a list of problems; empty means the entry can be logged."""
    errs = []
    unknown = set(entry) - set(FIELDS)
    if unknown:
        errs.append(f"unknown field(s): {', '.join(sorted(unknown))}")
    for f in ("run_id", "flag_ref", "seen_by_role", "decided_by_role", "action"):
        if not str(entry.get(f) or "").strip():
            errs.append(f"{f} is required")
    if entry.get("run_id") and entry["run_id"] != report.get("run_id"):
        errs.append(f"run_id {entry['run_id']} is not the current run ({report.get('run_id')})")
    flags = run_flags(report)
    ref = entry.get("flag_ref")
    if ref and ref not in flags:
        errs.append(f"flag_ref {ref!r} is not a flag in run {report.get('run_id')}")
    elif ref and entry.get("verdict_shown") and entry["verdict_shown"] != flags[ref]:
        errs.append(f"verdict_shown {entry['verdict_shown']} does not match the report ({flags[ref]})")
    if entry.get("action") and entry["action"] not in ACTIONS:
        errs.append(f"action must be one of {', '.join(ACTIONS)}")
    reason = str(entry.get("override_reason") or "").strip()
    if entry.get("action") == "overridden" and len(reason.split()) < MIN_OVERRIDE_WORDS:
        errs.append(f"override_reason is required for an override and needs at least {MIN_OVERRIDE_WORDS} words")
    for f in ("seen_by_role", "decided_by_role"):
        v = str(entry.get(f) or "").strip()
        if v and not ROLE_WORDS.search(v):
            errs.append(f"{f} {v!r} must name a role (e.g. 'HR lead', 'Hiring manager'), never a person")
    if entry.get("outcome_date"):
        try:
            date.fromisoformat(entry["outcome_date"])
        except (TypeError, ValueError):
            errs.append("outcome_date must be an ISO date (YYYY-MM-DD)")
    for f in FREE_TEXT:
        if entry.get(f):
            errs += pii_problems(f, str(entry[f]))
    return errs


def make_entry(report: dict, flag: str, seen_by: str, decided_by: str, action: str,
               override_reason: str = "", outcome_note: str = "", outcome_date: str = "",
               now: datetime | None = None) -> dict:
    """Build an entry; run_id and verdict_shown come from the report."""
    e = {"logged_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
         "run_id": report.get("run_id"), "flag_ref": flag, "verdict_shown": run_flags(report).get(flag),
         "seen_by_role": seen_by, "decided_by_role": decided_by, "action": action}
    for k, v in (("override_reason", override_reason), ("outcome_note", outcome_note), ("outcome_date", outcome_date)):
        if v:
            e[k] = v
    return e


def append(path: Path, entry: dict, report: dict) -> list[str]:
    """Validate and append. Returns problems; nothing is written if there are any. Never rewrites the file."""
    errs = validate(entry, report)
    if errs:
        return errs
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return []


def read(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def latest(entries: list[dict], per_run: bool = True) -> dict:
    """Latest entry per flag (per run_id and flag_ref by default). File order is time order (append-only)."""
    out = {}
    for e in entries:
        out[(e["run_id"], e["flag_ref"]) if per_run else e["flag_ref"]] = e
    return out


def check_of(ref: str) -> str:
    return ref.rsplit("|", 1)[-1]


def summary(entries: list[dict]) -> dict:
    """Counts by action and by check, and override rate per check.

    Each flag counts once per run, using its latest action, so 'deferred' then 'fixed' counts as fixed.
    """
    final = list(latest(entries).values())
    by_check: dict[str, Counter] = defaultdict(Counter)
    for e in final:
        by_check[check_of(e["flag_ref"])][e["action"]] += 1
    rates = {c: {"overridden": n["overridden"], "total": sum(n.values()),
                 "override_rate": round(n["overridden"] / sum(n.values()), 3)} for c, n in by_check.items()}
    return {"entries": len(entries), "flags_with_action": len(final),
            "by_action": dict(Counter(e["action"] for e in final)),
            "by_check": {c: dict(n) for c, n in sorted(by_check.items())},
            "override_rate": dict(sorted(rates.items(), key=lambda kv: (-kv[1]["override_rate"], kv[0])))}


def format_summary(s: dict) -> str:
    lines = [f"{s['entries']} log entries; {s['flags_with_action']} flags with an action "
             "(latest action per flag per run).", "", "By action:"]
    lines += [f"  {a:<11} {s['by_action'].get(a, 0)}" for a in ACTIONS]
    lines += ["", "By check:      " + "  ".join(f"{a:>10}" for a in ACTIONS)]
    for c, n in s["by_check"].items():
        lines.append(f"  {c:<12} " + "  ".join(f"{n.get(a, 0):>10}" for a in ACTIONS))
    lines += ["", "Override rate per check (high = people disagree with this check):"]
    for c, r in s["override_rate"].items():
        lines.append(f"  {c:<5} {r['override_rate']:>6.0%}  ({r['overridden']} of {r['total']})")
    return "\n".join(lines)
