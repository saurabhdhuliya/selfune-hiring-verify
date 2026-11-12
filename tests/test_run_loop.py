"""run_loop.py --data: a company's own folder in the same format as data/synthetic."""
import json
import subprocess
import sys

import pytest
from conftest import ROOT

from selfune_hv import report as rep
from selfune_hv.checks._common import data_file

LOOP = [sys.executable, str(ROOT / "scripts/run_loop.py")]
COMPANY = {"employer_id": "EMP-T", "employer_name": "Test Co (fictional)",
           "jobs": [{"job_id": "J1", "title": "Data Analyst", "jurisdiction": ["EU"],
                     "selection_method": {"stages": ["work sample", "structured interview"], "combine": "mechanical"},
                     "requirements": [{"req_id": "J1-R1", "text": "Strong SQL skills."},
                                      {"req_id": "J1-R2", "text": "Minimum 5 years of analytics experience."}]}]}
DECISIONS = [
    {"decision_id": "D0001", "candidate_ref": "CAND-0001", "job_id": "J1", "stage": "screen", "outcome": "rejected",
     "reason_text": "Auto-rejected by the screening tool.", "fields_present": ["skills"], "fields_missing": [],
     "decision_date": "2026-11-01", "decided_by": "tool"},
    {"decision_id": "D0002", "candidate_ref": "CAND-0002", "job_id": "J1", "stage": "screen", "outcome": "advanced",
     "reason_text": "Work sample 82/100, above pre-set 60.", "fields_present": ["skills"], "fields_missing": [],
     "decision_date": "2026-11-01", "decided_by": "human"},
]


def write_folder(path, company=COMPANY, decisions=DECISIONS, **extra):
    path.mkdir(parents=True, exist_ok=True)
    (path / "company.json").write_text(json.dumps(company), encoding="utf-8")
    (path / "decisions.jsonl").write_text("".join(json.dumps(d) + "\n" for d in decisions), encoding="utf-8")
    for name, content in extra.items():
        (path / name).write_text(content, encoding="utf-8")
    return path


def run(*args):
    return subprocess.run(LOOP + list(args), capture_output=True, text=True)


def test_minimal_company_folder(tmp_path):
    data = write_folder(tmp_path / "acme")
    out = tmp_path / "out"
    r = run("--data", str(data), "--out", str(out))
    assert r.returncode == 0, r.stderr
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["employer"] == "Test Co (fictional)" and report["summary"]["chains"] == 2
    flags = {f["flag_ref"]: f["verdict"] for f in report["flags"]}
    assert flags["group_counts:J1|C05"] == "NOT_CHECKED"          # no group_counts.json: never a pass
    assert flags["requirement:J1-R1|C01"] == "UNVERIFIED"         # no role memory: vague trait asks
    assert flags["requirement:J1-R2|C02"] == "UNVERIFIED"
    assert flags["decision:D0001|C11"] == "ESCALATE"              # EU job, decided by tool
    assert not any(ref.startswith("tool:") for ref in flags)      # no tools.json
    chains = {c["chain_id"]: c for c in report["chains"]}
    assert chains["CH-D0001"]["chain_status"] == "ESCALATE"
    assert (out / "report.html").exists()


def test_synthetic_report_unchanged_by_explicit_default():
    a = rep.build_report(ROOT)
    b = rep.build_report(ROOT, data_folder=ROOT / "data/synthetic")
    assert a["summary"] == b["summary"] and a["flags"] == b["flags"]


@pytest.mark.parametrize("setup,message", [
    (lambda p: p / "nope", "is not a folder"),
    (lambda p: write_folder(p / "x") and (p / "x" / "decisions.jsonl").unlink() or p / "x", "missing required file"),
    (lambda p: write_folder(p / "y", decisions=[{**DECISIONS[0], "candidate_ref": "Jane Smith"}]), "decisions.jsonl D0001"),
    (lambda p: write_folder(p / "z", company={"employer_id": "E", "jobs": []}), "non-empty 'jobs'"),
])
def test_bad_input_writes_nothing(tmp_path, setup, message):
    data = setup(tmp_path)
    out = tmp_path / "out"
    r = run("--data", str(data), "--out", str(out))
    assert r.returncode == 1 and message in r.stderr
    assert not out.exists()


def test_optional_and_required_files(tmp_path):
    data = write_folder(tmp_path / "d")
    assert data_file(ROOT, data, "tools.json") == []
    assert data_file(ROOT, data, "group_counts.json") == {}
    assert data_file(ROOT, data, "role_memory.json") == {"roles": []}
    (data / "company.json").unlink()
    with pytest.raises(FileNotFoundError, match="docs/schema.md"):
        data_file(ROOT, data, "company.json")


def test_company_data_folders_are_git_ignored():
    for path, ignored in [("data/real/acme/company.json", True), ("data/acme/decisions.jsonl", True),
                          ("data/synthetic/company.json", False), ("data/c9_corpus/c9_inputs.jsonl", False)]:
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
        assert (r.returncode == 0) is ignored, path


def test_checks_never_hardcode_the_synthetic_folder():
    for p in (ROOT / "src/selfune_hv/checks").glob("c*.py"):
        assert "data/synthetic" not in p.read_text(encoding="utf-8"), p.name
