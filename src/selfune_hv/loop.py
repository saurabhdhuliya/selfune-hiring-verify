"""The full verification loop on a data folder: check input, build the report, write report.json and report.html.

Used by scripts/run_loop.py, the `selfune-verify --data` command and the MCP server. No LLM. Never reads labels/.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from selfune_hv import outcome_log
from selfune_hv.checks._common import REQUIRED_FILES, data_file
from selfune_hv.report import build_report, chains_for_schema, render_html


def make_run_id(report: dict) -> str:
    """RUN-<UTC time>-<hash of the flags>: unique per run, and the hash shows when two runs flagged the same things."""
    digest = hashlib.sha256(json.dumps(sorted(f["flag_ref"] + f["verdict"] for f in report["flags"])).encode()).hexdigest()
    return f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{digest[:8]}"


def check_input(root: Path, data: Path) -> list[str]:
    """Problems with a data folder before any check runs: missing required files, bad decision records."""
    if not data.is_dir():
        return [f"{data} is not a folder"]
    errs = [f"missing required file {data / n} (see docs/schema.md)" for n in REQUIRED_FILES if not (data / n).exists()]
    if errs:
        return errs
    with open(root / "schemas/decision.schema.json", encoding="utf-8") as f:
        v = Draft202012Validator(json.load(f))
    for d in data_file(root, data, "decisions.jsonl"):
        errs += [f"decisions.jsonl {d.get('decision_id', '?')}: {e.message}" for e in v.iter_errors(d)]
    jobs = data_file(root, data, "company.json").get("jobs")
    if not isinstance(jobs, list) or not jobs:
        errs.append("company.json needs a non-empty 'jobs' list")
    return errs


def run_folder(root: Path, data: Path) -> tuple[dict | None, list[str]]:
    """Build the full-loop report for a data folder. Returns (report, problems); report is None if any problem."""
    errs = check_input(root, data)
    if errs:
        return None, errs
    report = build_report(root, data_folder=data)
    report = {"run_id": make_run_id(report), **report}
    with open(root / "schemas/decision_chain.schema.json", encoding="utf-8") as f:
        validator = Draft202012Validator(json.load(f))
    bad = [f"schema error {c['chain_id']}: {e.message}" for c in chains_for_schema(report) for e in validator.iter_errors(c)]
    return (None, bad) if bad else (report, [])


def report_json(report: dict) -> dict:
    """The report as written to report.json (chains without report-only helper fields)."""
    return {**report, "chains": chains_for_schema(report)}


def write_outputs(report: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "report.json", "w", encoding="utf-8") as f:
        json.dump(report_json(report), f, indent=2, ensure_ascii=False)
    entries = outcome_log.read(out / "outcome_log.jsonl")
    history = outcome_log.latest(entries, per_run=False) if entries else None   # last action per flag, any run
    with open(out / "report.html", "w", encoding="utf-8") as f:
        f.write(render_html(report, history))


def summary_lines(report: dict, data: Path, out: Path) -> list[str]:
    s = report["summary"]
    return [
        f"Data: {data}",
        f"Run {report['run_id']}: {len(report['flags'])} flags.",
        f"{s['chains']} chains, all valid against the schema.",
        f"Job-level issues:   {s['job_level_issues']} (" + ", ".join(
            f"{k} {v}" for k, v in sorted(s["job_level_issues_by_verdict"].items())) + ")",
        "Chains by status:   " + ", ".join(f"{k} {v}" for k, v in sorted(s["chains_by_status"].items())),
        "Findings by verdict: " + ", ".join(f"{k} {v}" for k, v in sorted(s["findings_by_verdict"].items())),
        f"Chains stopped by C09: {s['blocked_chains']}. Human questions (deduplicated): {s['human_questions']}.",
        f"Ledger warnings: {len(report['ledger_warnings'])}.",
        f"Wrote {out / 'report.json'} and {out / 'report.html'}",
    ]
