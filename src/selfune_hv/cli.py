"""`selfune-verify`: one command for text mode or the full loop. No LLM.

  selfune-verify job_post.txt            readable report for a job post or AI hiring summary
  selfune-verify job_post.txt --json     the same report as JSON
  cat post.txt | selfune-verify -        read the text from stdin
  selfune-verify --data data/real/acme   full loop on a company folder (docs/schema.md); writes out/report.html

Verifies process, not people. Not legal advice.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from selfune_hv.loop import report_json, run_folder, summary_lines, write_outputs
from selfune_hv.paths import resource_root
from selfune_hv.text_mode import format_text, verify_text


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(prog="selfune-verify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="text file to verify, or - for stdin")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the readable report")
    ap.add_argument("--data", help="run the full loop on this data folder instead of a text file")
    ap.add_argument("--out", default="out", help="output folder for the full loop (default ./out)")
    a = ap.parse_args(argv)

    if bool(a.file) == bool(a.data):
        ap.error("give either a text file (or - for stdin) or --data <folder>")
    try:
        root = resource_root()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2

    if a.data:
        data, out = Path(a.data).resolve(), Path(a.out).resolve()
        report, errs = run_folder(root, data)
        if errs:
            print("Input problems, nothing written:", file=sys.stderr)
            for e in errs[:30]:
                print(f"  - {e}", file=sys.stderr)
            return 1
        write_outputs(report, out)
        if a.json:
            print(json.dumps(report_json(report), indent=2, ensure_ascii=False))
        else:
            print("\n".join(summary_lines(report, data, out)))
        return 0

    if a.file == "-":
        text = sys.stdin.read()
    else:
        p = Path(a.file)
        if not p.is_file():
            print(f"No such file: {p}", file=sys.stderr)
            return 1
        text = p.read_text(encoding="utf-8")
    report = verify_text(text, root)
    print(json.dumps(report, indent=2, ensure_ascii=False) if a.json else format_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
