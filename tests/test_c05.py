import json
import re
import shutil
from pathlib import Path

import pytest

from selfune_hv.checks import c05_adverse_impact as c05

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def synthetic_root(tmp_path):
    """Full copy of data/synthetic and the ledger in a temp root."""
    shutil.copytree(ROOT / "data/synthetic", tmp_path / "data/synthetic")
    shutil.copytree(ROOT / "ledger", tmp_path / "ledger")
    return lambda: tmp_path


def by_ref(findings):
    return {f["object_ref"]: f for f in findings}


@pytest.fixture
def make_root(tmp_path):
    """A temp repo root with the real company and ledger and the given group counts."""
    def _make(group_counts):
        (tmp_path / "data/synthetic").mkdir(parents=True)
        (tmp_path / "ledger").mkdir()
        shutil.copy(ROOT / "data/synthetic/company.json", tmp_path / "data/synthetic/company.json")
        shutil.copy(ROOT / "ledger/hiring.jsonl", tmp_path / "ledger/hiring.jsonl")
        (tmp_path / "data/synthetic/group_counts.json").write_text(json.dumps(group_counts), encoding="utf-8")
        return tmp_path
    return _make


def test_synthetic_data_verdicts():
    f = by_ref(c05.run(ROOT))
    assert f["group_counts:J1:sex_self_reported"]["verdict"] == "UNVERIFIED"
    assert f["group_counts:J1:age_band"]["verdict"] == "UNVERIFIED"
    assert f["group_counts:J2:sex_self_reported"]["verdict"] == "VERIFIED"
    assert f["group_counts:J2:age_band"]["verdict"] == "VERIFIED"
    assert f["group_counts:J3"]["verdict"] == "NOT_CHECKED"
    assert len(f) == 5


def test_finding_shape_and_citation():
    for f in c05.run(ROOT):
        assert set(f) == {"object_ref", "check", "verdict", "ledger_refs", "message"}
        assert f["check"] == "C05"
        assert f["ledger_refs"] == ["GT-0023"]
        assert "Flag for review, not legal advice." in f["message"]
        assert "screening heuristic whose federal guideline status is changing (GT-0023)" in f["message"]
        assert "GT-0023" in f["message"] and "retrieved 2026-11-11" in f["message"]


def test_statistical_flag_wording():
    f = by_ref(c05.run(ROOT))
    assert f["group_counts:J1:sex_self_reported"]["message"].startswith(
        "Statistical flag: impact ratio 0.43 below 0.8. The four-fifths rule is a screening heuristic whose federal "
        "guideline status is changing (GT-0023); disparity still matters under discrimination law. "
        "Flag for review, not legal advice.")
    assert f["group_counts:J2:sex_self_reported"]["message"].startswith("Statistical check: impact ratio 0.89")


def test_locked_gt0023_has_no_ledger_warning():
    f = by_ref(c05.run(ROOT))["group_counts:J1:age_band"]
    assert f["verdict"] == "UNVERIFIED" and "Ledger warnings" not in f["message"]


def test_pending_ledger_row_does_not_soften_unverified(synthetic_root):
    """Hard rule 7: a pending row never causes a hard fail; UNVERIFIED is a question, not a fail."""
    root = synthetic_root()
    path = root / "ledger/hiring.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
    for r in rows:
        if r["id"] == "GT-0023":
            r["user_decision"] = "PENDING_RELOCK"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    f = by_ref(c05.run(root))["group_counts:J1:age_band"]
    assert f["verdict"] == "UNVERIFIED" and "GT-0023 is PENDING_RELOCK" in f["message"]


def test_job_without_counts_is_never_verified(make_root):
    f = by_ref(c05.run(make_root({})))
    assert {v["verdict"] for v in f.values()} == {"NOT_CHECKED"}
    assert set(f) == {"group_counts:J1", "group_counts:J2", "group_counts:J3"}


def test_ratio_exactly_four_fifths_is_verified():
    groups = {"a": {"applied": 100, "selected": 50}, "b": {"applied": 100, "selected": 40}}
    assert c05.evaluate_grouping(groups)[0] == "VERIFIED"


def test_ratio_just_below_four_fifths_is_unverified():
    groups = {"a": {"applied": 100, "selected": 50}, "b": {"applied": 100, "selected": 39}}
    assert c05.evaluate_grouping(groups)[0] == "UNVERIFIED"


def test_small_sample_note():
    small = {"a": {"applied": 29, "selected": 10}, "b": {"applied": 100, "selected": 30}}
    big = {"a": {"applied": 30, "selected": 10}, "b": {"applied": 100, "selected": 30}}
    assert "small samples weaken the 4/5 rule (GT-0023)" in c05.evaluate_grouping(small)[1]
    assert "small sample" not in c05.evaluate_grouping(big)[1]


def test_real_data_small_sample_notes():
    f = by_ref(c05.run(ROOT))
    assert "small sample" in f["group_counts:J1:age_band"]["message"]       # 40_plus applied 24
    assert "small sample" not in f["group_counts:J1:sex_self_reported"]["message"]


def test_undefined_ratio_is_not_checked():
    assert c05.evaluate_grouping({"a": {"applied": 10, "selected": 0},
                                  "b": {"applied": 10, "selected": 0}})[0] == "NOT_CHECKED"
    assert c05.evaluate_grouping({"a": {"applied": 10, "selected": 3}})[0] == "NOT_CHECKED"
    assert c05.evaluate_grouping({"a": {"applied": 0, "selected": 0},
                                  "b": {"applied": 10, "selected": 3}})[0] == "NOT_CHECKED"


def test_checks_never_reference_labels():
    """No string literal in a check points at labels/ (docstrings stating the rule are fine)."""
    literal = re.compile(r"""["'][^"'\n]*labels""")
    for src in (ROOT / "src/selfune_hv/checks").glob("*.py"):
        assert not literal.search(src.read_text(encoding="utf-8")), f"{src.name} references labels/"
