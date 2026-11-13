"""Run the verification loop and write report.json and report.html. No LLM.

Usage:
  py scripts/run_loop.py                                  # the synthetic data in data/synthetic
  py scripts/run_loop.py --data data/real/acme            # a company's own folder (format: docs/schema.md)
  py scripts/run_loop.py --data <folder> --out <folder>   # write the report somewhere else (default out/)

Relative paths are relative to the repo. Real data folders under data/ are git-ignored.
After `pip install .`, `selfune-verify --data <folder>` does the same from anywhere.
Never reads labels/ (scoring is scripts/score.py's job).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from selfune_hv.checks._common import DEFAULT_DATA  # noqa: E402
from selfune_hv.loop import run_folder, summary_lines, write_outputs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=DEFAULT_DATA, help=f"input folder (default {DEFAULT_DATA})")
    ap.add_argument("--out", default="out", help="output folder for report.json, report.html (default out)")
    a = ap.parse_args(argv)
    data = Path(a.data) if Path(a.data).is_absolute() else ROOT / a.data
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    report, errs = run_folder(ROOT, data)
    if errs:
        print("Input problems, nothing written:", file=sys.stderr)
        for e in errs[:30]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    write_outputs(report, out)
    print("\n".join(summary_lines(report, data, out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
