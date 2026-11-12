import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def synthetic_root(tmp_path):
    """Temp repo root with a copy of data/synthetic and the ledger; override files by name.

    synthetic_root(**{"tools.json": [...], "decisions.jsonl": [...]})
    A .jsonl override is a list of dicts; anything else is written as JSON.
    """
    calls = iter(range(10_000))

    def _make(**overrides):
        root = tmp_path / f"root{next(calls)}"   # fresh root per call, so a test can build several
        shutil.copytree(ROOT / "data/synthetic", root / "data/synthetic")
        shutil.copytree(ROOT / "ledger", root / "ledger")
        for name, data in overrides.items():
            path = root / "data/synthetic" / name
            if name.endswith(".jsonl"):
                text = "".join(json.dumps(r) + "\n" for r in data)
            else:
                text = json.dumps(data)
            path.write_text(text, encoding="utf-8")
        return root
    return _make


def by_ref(findings):
    return {f["object_ref"]: f for f in findings}
