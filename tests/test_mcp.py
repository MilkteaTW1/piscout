

from piscout import mcp


def test_list_and_tools():
    r = mcp.handle({"id": 1, "method": "tools/list"})
    assert [t["name"] for t in r["tools"]] == ["pi_list", "pi_run", "pi_health"]


def test_run_trims_and_reports(monkeypatch):
    monkeypatch.setattr(mcp, "_client", lambda host: object())
    monkeypatch.setattr(mcp.remote, "run", lambda c, cmd, timeout: (0, "x" * 10000, ""))
    r = mcp.handle({"id": 2, "method": "tools/call",
                    "params": {"name": "pi_run", "arguments": {"host": "192.168.1.5", "cmd": "ls"}}})
    assert not r["isError"] and len(r["content"][0]["text"]) < 3100


def test_public_address_refused():
    r = mcp.handle({"id": 3, "method": "tools/call",
                    "params": {"name": "pi_run", "arguments": {"host": "8.8.8.8", "cmd": "id"}}})
    assert r["isError"] and "private" in r["content"][0]["text"]
