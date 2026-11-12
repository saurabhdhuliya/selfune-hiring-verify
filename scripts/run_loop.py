"""Run the verification loop on data/synthetic and write out/report.json and out/report.html. No LLM.

Usage: py scripts/run_loop.py
Never reads labels/ (scoring is scripts/score.py's job).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator  # noqa: E402

from selfune_hv.report import build_report, chains_for_schema, render_html  # noqa: E402


def main() -> int:
    report = build_report(ROOT)
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
    with open(out / "report.html", "w", encoding="utf-8") as f:
        f.write(render_html(report))
    s = report["summary"]
    print(f"{s['chains']} chains, all valid against the schema.")
    print("Chains by status:  ", ", ".join(f"{k} {v}" for k, v in sorted(s["chains_by_status"].items())))
    print("Findings by verdict:", ", ".join(f"{k} {v}" for k, v in sorted(s["findings_by_verdict"].items())))
    print(f"Blocked chains: {s['blocked_chains']}. Human questions (deduplicated): {s['human_questions']}.")
    print(f"Ledger warnings: {len(report['ledger_warnings'])}.")
    print("Wrote out/report.json and out/report.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
