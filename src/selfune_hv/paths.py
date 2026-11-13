"""Where the ledger and schemas live, whether running from the repo or after `pip install .`.

Order:
1. SELFUNE_HV_HOME, if set (a folder with ledger/hiring.jsonl and schemas/).
2. The repo checkout this package sits in (source tree or `pip install -e .`).
3. The copy installed by `pip install .` under <prefix>/share/selfune-hiring-verify/.
"""
from __future__ import annotations

import os
import sysconfig
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SHARE_NAME = "selfune-hiring-verify"


def _has_resources(p: Path) -> bool:
    return (p / "ledger/hiring.jsonl").is_file() and (p / "schemas/decision_chain.schema.json").is_file()


def resource_root() -> Path:
    candidates = []
    if os.environ.get("SELFUNE_HV_HOME"):
        candidates.append(Path(os.environ["SELFUNE_HV_HOME"]))
    candidates.append(PACKAGE_DIR.parents[1])                                   # repo: src/selfune_hv -> repo
    for scheme_key in ("data",):
        candidates.append(Path(sysconfig.get_path(scheme_key)) / "share" / SHARE_NAME)
    for c in candidates:
        if _has_resources(c):
            return c
    raise FileNotFoundError("Selfune ledger and schemas not found. Set SELFUNE_HV_HOME to a folder that contains "
                            "ledger/hiring.jsonl and schemas/, or reinstall with `pip install .`.")
