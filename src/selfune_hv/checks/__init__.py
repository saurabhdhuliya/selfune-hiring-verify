"""Code checks C01-C15. No LLM.

Each check module defines:
    CHECK_ID: str                      e.g. "C05"
    run(root: Path) -> list[dict]      findings for the repo/data rooted at `root`

A finding is {object_ref, check, verdict, ledger_refs, message}.
Checks read only data/, ledger/ and schemas/. They must never read labels/.
"""
