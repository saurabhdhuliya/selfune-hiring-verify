"""Log what a person did with a flag, or summarise the log. No LLM.

Examples:
  py scripts/log_outcome.py --flag "tool:T1:audit_age|C10" --seen-by "HR lead" --decided-by "HR lead" \
      --action fixed --note "New audit ordered" --outcome-date 2026-11-20
  py scripts/log_outcome.py --flag "requirement:J1-R5|C03" --seen-by "Recruiter" --decided-by "Head of Support" \
      --action overridden --reason "Typing speed is a contractual minimum set by the client for every agent"
  py scripts/log_outcome.py --summary

Accepts only flags from the current run (out/report.json, written by scripts/run_loop.py).
The log (out/outcome_log.jsonl) is append-only and stays local.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from selfune_hv import outcome_log as ol  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", action="store_true", help="print counts by action and check, and override rates")
    ap.add_argument("--flag", help='flag_ref as "object_ref|check", e.g. "tool:T1:audit_age|C10"')
    ap.add_argument("--seen-by", help="role that saw the flag (never a name)")
    ap.add_argument("--decided-by", help="role that decided what to do (never a name)")
    ap.add_argument("--action", choices=ol.ACTIONS)
    ap.add_argument("--reason", default="", help=f"required for overridden, at least {ol.MIN_OVERRIDE_WORDS} words")
    ap.add_argument("--note", default="", help="what happened")
    ap.add_argument("--outcome-date", default="", help="YYYY-MM-DD")
    ap.add_argument("--report", default=str(ROOT / "out/report.json"))
    ap.add_argument("--log", default=str(ROOT / "out/outcome_log.jsonl"))
    a = ap.parse_args(argv)

    if a.summary:
        entries = ol.read(Path(a.log))
        if not entries:
            print(f"No outcome log at {a.log}.")
            return 0
        print(ol.format_summary(ol.summary(entries)))
        return 0

    missing = [n for n, v in (("--flag", a.flag), ("--seen-by", a.seen_by), ("--decided-by", a.decided_by),
                              ("--action", a.action)) if not v]
    if missing:
        ap.error(f"missing {', '.join(missing)}")
    report_path = Path(a.report)
    if not report_path.exists():
        print(f"No report at {report_path}. Run scripts/run_loop.py first.", file=sys.stderr)
        return 1
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    entry = ol.make_entry(report, a.flag, a.seen_by, a.decided_by, a.action, a.reason, a.note, a.outcome_date)
    errs = ol.append(Path(a.log), entry, report)
    if errs:
        print("Not logged:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"Logged: {entry['flag_ref']} -> {entry['action']} (run {entry['run_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
