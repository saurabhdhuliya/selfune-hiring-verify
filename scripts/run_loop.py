"""Run the verification loop and write report.json and report.html. No LLM.

Usage:
  py scripts/run_loop.py                                  # the synthetic data in data/synthetic
  py scripts/run_loop.py --data data/real/acme            # a company's own folder (format: docs/schema.md)
  py scripts/run_loop.py --data <folder> --out <folder>   # write the report somewhere else (default out/)

Real data folders under data/ are git-ignored (only data/synthetic and data/c9_corpus are tracked).
Never reads labels/ (scoring is scripts/score.py's job).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator  # noqa: E402

from selfune_hv import outcome_log  # noqa: E402
from selfune_hv.checks._common import DEFAULT_DATA, REQUIRED_FILES, data_file  # noqa: E402
from selfune_hv.report import build_report, chains_for_schema, render_html  # noqa: E402


def make_run_id(report: dict) -> str:
    """RUN-<UTC time>-<hash of the flags>: unique per run, and the hash shows when two runs flagged the same things."""
    digest = hashlib.sha256(json.dumps(sorted(f["flag_ref"] + f["verdict"] for f in report["flags"])).encode()).hexdigest()
    return f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{digest[:8]}"


def check_input(data: Path) -> list[str]:
    """Problems with a data folder before any check runs: missing required files, bad decision records."""
    if not data.is_dir():
        return [f"{data} is not a folder"]
    errs = [f"missing required file {data / n} (see docs/schema.md)" for n in REQUIRED_FILES if not (data / n).exists()]
    if errs:
        return errs
    with open(ROOT / "schemas/decision.schema.json", encoding="utf-8") as f:
        v = Draft202012Validator(json.load(f))
    for d in data_file(ROOT, data, "decisions.jsonl"):
        errs += [f"decisions.jsonl {d.get('decision_id', '?')}: {e.message}" for e in v.iter_errors(d)]
    jobs = data_file(ROOT, data, "company.json").get("jobs")
    if not isinstance(jobs, list) or not jobs:
        errs.append("company.json needs a non-empty 'jobs' list")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=DEFAULT_DATA, help=f"input folder (default {DEFAULT_DATA})")
    ap.add_argument("--out", default="out", help="output folder for report.json, report.html (default out)")
    a = ap.parse_args(argv)
    data = Path(a.data) if Path(a.data).is_absolute() else ROOT / a.data
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out

    errs = check_input(data)
    if errs:
        print("Input problems, nothing written:", file=sys.stderr)
        for e in errs[:30]:
            print(f"  - {e}", file=sys.stderr)
        return 1

    report = build_report(ROOT, data_folder=data)
    report = {"run_id": make_run_id(report), **report}
    with open(ROOT / "schemas/decision_chain.schema.json", encoding="utf-8") as f:
        validator = Draft202012Validator(json.load(f))
    bad = [(c["chain_id"], e.message) for c in chains_for_schema(report) for e in validator.iter_errors(c)]
    if bad:
        for cid, msg in bad[:20]:
            print(f"schema error {cid}: {msg}")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "report.json", "w", encoding="utf-8") as f:
        json.dump({**report, "chains": chains_for_schema(report)}, f, indent=2, ensure_ascii=False)
    entries = outcome_log.read(out / "outcome_log.jsonl")
    history = outcome_log.latest(entries, per_run=False) if entries else None   # last action per flag, any run
    with open(out / "report.html", "w", encoding="utf-8") as f:
        f.write(render_html(report, history))
    s = report["summary"]
    print(f"Data: {data}")
    print(f"Run {report['run_id']}: {len(report['flags'])} flags.")
    print(f"{s['chains']} chains, all valid against the schema.")
    print(f"Job-level issues:   {s['job_level_issues']} (" + ", ".join(
        f"{k} {v}" for k, v in sorted(s["job_level_issues_by_verdict"].items())) + ")")
    print("Chains by status:  ", ", ".join(f"{k} {v}" for k, v in sorted(s["chains_by_status"].items())))
    print("Findings by verdict:", ", ".join(f"{k} {v}" for k, v in sorted(s["findings_by_verdict"].items())))
    print(f"Chains stopped by C09: {s['blocked_chains']}. Human questions (deduplicated): {s['human_questions']}.")
    print(f"Ledger warnings: {len(report['ledger_warnings'])}.")
    print(f"Wrote {out / 'report.json'} and {out / 'report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
