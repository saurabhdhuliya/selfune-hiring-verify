"""The MCP server (skipped when the mcp package is not installed)."""
import asyncio
import json
import os
import subprocess
import sys

import pytest
from conftest import ROOT

POST = ROOT / "examples/job_posts/5_ai_screening_summary.txt"
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}

mcp = pytest.importorskip("mcp")


def test_mcp_tools_registered():
    from selfune_hv import mcp_server
    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    assert names == {"verify_text", "verify_folder", "ledger_row"}


def test_mcp_tool_functions():
    from selfune_hv import mcp_server
    r = mcp_server.verify_text(POST.read_text(encoding="utf-8"))
    assert r["status"] == "ESCALATE" and r["blocked"] is True
    row = mcp_server.ledger_row("gt-0008")
    assert row["ok"] and row["id"] == "GT-0008" and "biometric" in row["claim"] and "caveats" in row
    assert mcp_server.ledger_row("GT-9999")["ok"] is False
    folder = mcp_server.verify_folder(str(ROOT / "data/synthetic"))
    assert folder["ok"] and folder["summary"]["chains"] == 200
    assert mcp_server.verify_folder(str(ROOT / "nope"))["ok"] is False


def test_mcp_stdio_handshake():
    """Start the server like an MCP client does and call a tool over stdio JSON-RPC."""
    p = subprocess.Popen([sys.executable, "-m", "selfune_hv.mcp_server"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=ENV)

    def send(m):
        p.stdin.write(json.dumps(m) + "\n")
        p.stdin.flush()

    def recv(i):
        while True:
            line = p.stdout.readline()
            assert line, p.stderr.read()
            m = json.loads(line)
            if m.get("id") == i:
                return m
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
        assert recv(1)["result"]["serverInfo"]["name"] == "selfune-hiring-verify"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "ledger_row", "arguments": {"id": "GT-0023"}}})
        res = recv(2)["result"]
        data = res.get("structuredContent") or json.loads(res["content"][0]["text"])
        data = data.get("result", data)
        assert data["id"] == "GT-0023" and data["status"] == "VERIFIED_SECONDARY"
    finally:
        p.stdin.close()
        p.terminate()
        p.wait(timeout=10)
