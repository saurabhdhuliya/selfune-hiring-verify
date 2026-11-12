"""Run the verification loop on data/synthetic and write out/report.json and out/report.html. No LLM.

Usage: py scripts/run_loop.py
Never reads labels/ (scoring is scripts/score.py's job).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator  # noqa: E402

from selfune_hv import outcome_log  # noqa: E402
from selfune_hv.report import build_report, chains_for_schema, render_html  # noqa: E402

LOG = ROOT / "out/outcome_log.jsonl"


def make_run_id(report: dict) -> str:
    """RUN-<UTC time>-<hash of the flags>: unique per run, and the hash shows when two runs flagged the same things."""
    digest = hashlib.sha256(json.dumps(sorted(f["flag_ref"] + f["verdict"] for f in report["flags"])).encode()).hexdigest()
    return f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{digest[:8]}"


def main() -> int:
    report = build_report(ROOT)
    report = {"run_id": make_run_id(report), **report}
    with open(ROOT / "schemas/decision_chain.schema.json", encoding="utf-8") as f:
        validator = Draft202012Validator(json.load(f))
    bad = [(c["chain_id"], e.message) for c in chains_for_schema(report) for e in validator.iter_errors(c)]
    if bad:
        for cid, msg in bad[:20]:
            print(f"schema error {cid}: {msg}")
        return 1
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    with open(out / "report.json", "w", encoding="utf-8") as f:
        json.dump({**report, "chains": chains_for_schema(report)}, f, indent=2, ensure_ascii=False)
    entries = outcome_log.read(LOG)
    history = outcome_log.latest(entries, per_run=False) if entries else None   # last action per flag, any run
    with open(out / "report.html", "w", encoding="utf-8") as f:
        f.write(render_html(report, history))
    s = report["summary"]
    print(f"Run {report['run_id']}: {len(report['flags'])} flags.")
    print(f"{s['chains']} chains, all valid against the schema.")
    print(f"Job-level issues:   {s['job_level_issues']} (" + ", ".join(
        f"{k} {v}" for k, v in sorted(s["job_level_issues_by_verdict"].items())) + ")")
    print("Chains by status:  ", ", ".join(f"{k} {v}" for k, v in sorted(s["chains_by_status"].items())))
    print("Findings by verdict:", ", ".join(f"{k} {v}" for k, v in sorted(s["findings_by_verdict"].items())))
    print(f"Chains stopped by C09: {s['blocked_chains']}. Human questions (deduplicated): {s['human_questions']}.")
    print(f"Ledger warnings: {len(report['ledger_warnings'])}.")
    print("Wrote out/report.json and out/report.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
