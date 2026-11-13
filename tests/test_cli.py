"""The selfune-verify command."""
import json
import os
import subprocess
import sys

import pytest
from conftest import ROOT

from selfune_hv.paths import resource_root

POST = ROOT / "examples/job_posts/5_ai_screening_summary.txt"
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}


def cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-m", "selfune_hv.cli", *args], capture_output=True, text=True,
                          encoding="utf-8", env=ENV, input=stdin)


def test_mcp_command_without_extra_explains_install():
    """Core install has no mcp: the server command must say how to get it, not crash."""
    import importlib.util
    if importlib.util.find_spec("mcp") is not None:
        pytest.skip("mcp is installed here; this checks the core install without the [mcp] extra")
    r = subprocess.run([sys.executable, "-m", "selfune_hv.mcp_server"], capture_output=True, text=True,
                       encoding="utf-8", env=ENV, timeout=60)
    assert r.returncode == 1 and 'pip install ".[mcp]"' in r.stderr
    from selfune_hv import mcp_server                        # the tool functions still work without the SDK
    assert mcp_server.server is None and mcp_server.ledger_row("GT-0023")["ok"]


def test_resource_root_is_repo_when_running_from_source():
    assert resource_root() == ROOT


def test_cli_readable_report():
    r = cli(str(POST))
    assert r.returncode == 0, r.stderr
    assert "Status: ESCALATE" in r.stdout and "Questions for you (2)" in r.stdout


def test_cli_json_and_stdin():
    r = cli("--json", "-", stdin=POST.read_text(encoding="utf-8"))
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert rep["mode"] == "text" and rep["blocked"] is True


def test_cli_full_loop(tmp_path):
    r = cli("--data", str(ROOT / "data/synthetic"), "--out", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "200 chains" in r.stdout and (tmp_path / "report.html").exists()


@pytest.mark.parametrize("args,code", [((), 2), ((str(POST), "--data", "x"), 2), (("missing.txt",), 1)])
def test_cli_usage_errors(args, code):
    assert cli(*args).returncode == code
