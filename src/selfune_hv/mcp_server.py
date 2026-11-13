"""MCP server: lets Claude or any MCP agent call the Selfune Hiring Verification Loop. No LLM inside.

Tools:
  verify_text(text)   -> text-mode report (C01, C02, C03, C08, C09, C15) for a job post or AI hiring summary
  verify_folder(path) -> full-loop report for a data folder in the docs/schema.md format (read-only: writes nothing)
  ledger_row(id)      -> one ledger row with its status, caveats and any warnings

Run: `selfune-verify-mcp` (stdio). Needs the optional extra: pip install ".[mcp]".
Uses the official Python MCP SDK: MCPServer in mcp 2.x, FastMCP in mcp 1.x.
Verifies process, not people. Not legal advice.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:                                                    # mcp 2.x: FastMCP was renamed MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:
    try:                                                # mcp 1.x
        from mcp.server.fastmcp import FastMCP as _Server
    except ImportError:                                 # core install without the [mcp] extra
        _Server = None

from selfune_hv import ledger as ledger_mod
from selfune_hv.loop import report_json, run_folder
from selfune_hv.paths import resource_root
from selfune_hv.text_mode import verify_text as _verify_text

INSTRUCTIONS = (
    "Selfune Hiring Verification Loop. It checks whether a hiring process is sound: requirement wording, "
    "selection method, legal flags and evidence. It never scores, ranks, accepts or rejects people, and its "
    "output is not legal advice. Relay verdicts as flags for a human to review, with their ledger citations. "
    "Ask the human questions as written and respect each question's do_not_ask."
)

MISSING_MCP = ('selfune-verify-mcp needs the MCP SDK, which is an optional extra. Install it with:\n'
               '  pip install ".[mcp]"        (from the repo)\n'
               'The rest of the package (selfune-verify) works without it.')


def verify_text(text: str) -> dict:
    """Verify a job post or AI hiring summary given as plain text.

    Runs C01 undefined trait, C02 years as proxy, C03 no stated reason, C08 age or age proxy,
    C09 emotion/personality inference and C15 vendor claim as proof. Returns per-line verdicts,
    the overall status, the weakest link, questions for a human (with do_not_ask) and citations.
    """
    return _verify_text(text, resource_root())


def verify_folder(path: str) -> dict:
    """Run the full verification loop on a data folder (company.json, decisions.jsonl, optional tools.json, ...).

    Read-only: nothing is written. Returns the full report (job-level issues, decision chains, questions,
    ledger warnings), or {"ok": false, "problems": [...]} if the folder is not in the expected format.
    """
    report, errs = run_folder(resource_root(), Path(path).expanduser().resolve())
    if errs:
        return {"ok": False, "problems": errs[:50]}
    return {"ok": True, **report_json(report)}


def ledger_row(id: str) -> dict:
    """Return one ledger row (e.g. "GT-0023"): claim, status, display label, caveats, source and date, and warnings.

    Use it to explain a citation. A row records what a source says and how well it was checked; it is not legal advice.
    """
    rows = ledger_mod.load(str(resource_root() / "ledger/hiring.jsonl"))
    row = rows.get(id.strip().upper())
    if row is None:
        return {"ok": False, "error": f"No ledger row {id!r}. IDs look like GT-0001 to GT-{len(rows):04d}."}
    return {"ok": True, **row, "warnings": ledger_mod.row_warnings(row)}


TOOLS = (verify_text, verify_folder, ledger_row)

# Register the tools only when the SDK is installed; the functions above work either way.
server = _Server("selfune-hiring-verify", instructions=INSTRUCTIONS) if _Server else None
if server is not None:
    for _tool in TOOLS:
        server.tool()(_tool)


def main() -> None:
    if server is None:
        print(MISSING_MCP, file=sys.stderr)
        sys.exit(1)
    server.run()


if __name__ == "__main__":
    main()
