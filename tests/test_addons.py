import re
import time

import pytest

from piscout import addons, remote


def test_catalog_is_well_formed():
    ids = [a["id"] for a in addons.CATALOG]
    assert len(ids) == len(set(ids))
    for a in addons.CATALOG:
        assert re.fullmatch(r"[a-z0-9_]+", a["id"])
        for key in ("title", "desc", "steps", "ports", "check", "install", "remove", "after"):
            assert a.get(key), (a["id"], key)
        assert "curl" not in a["install"] and "wget" not in a["install"], "add-ons must be apt-only"
        a["after"].format(ip="1.2.3.4", user="pi")


def test_script_quotes_user_and_password():
    spec = {"install": "echo hi"}
    s = addons._script(spec, "install", "pi", "pa'ss $(rm -rf /)")
    assert "PI_PW='pa'\"'\"'ss $(rm -rf /)'" in s
    assert s.startswith("set -e\n") and s.endswith("echo hi\n")


class FakeClient:
    def __init__(self, out):
        self.out = out


def test_status_parses_items(monkeypatch):
    out = "apt=1\n" + "".join(f"{a['id']}={0 if a['id'] == 'docker' else 1}\n" for a in addons.CATALOG)
    monkeypatch.setattr(remote, "_run_script", lambda c, s, timeout: (0, out, ""))
    r = addons.status(object(), "10.0.0.5", "pi")
    assert r["apt"] is True
    assert {i["id"]: i["installed"] for i in r["items"]}["docker"] is True
    assert [i["installed"] for i in r["items"] if i["id"] == "nas"] == [False]
    nas = next(i for i in r["items"] if i["id"] == "nas")
    assert "10.0.0.5" in nas["after"] and "pi" in nas["after"]


def test_status_without_apt(monkeypatch):
    monkeypatch.setattr(remote, "_run_script", lambda c, s, timeout: (0, "apt=0\n", ""))
    assert addons.status(object(), "10.0.0.5", "pi")["apt"] is False


def test_start_refusals():
    with pytest.raises(remote.RemoteError):
        addons.start("h", {"username": "pi", "password": "x"}, "nope", "install")
    with pytest.raises(remote.RemoteError):
        addons.start("h", {"username": "pi", "password": "x"}, "docker", "format")
    with pytest.raises(remote.RemoteError):  # NAS needs the password for the Samba account
        addons.start("h", {"username": "pi", "password": ""}, "nas", "install")


def test_one_job_per_host_and_poll(monkeypatch):
    def fake_worker(job, host, login, spec, op):
        addons._job_text(job, "hello\r\nworld")
        time.sleep(0.2)
        with addons._lock:
            job["state"] = "ok"
            job["finished"] = time.time()

    monkeypatch.setattr(addons, "_worker", fake_worker)
    login = {"username": "pi", "password": "x"}
    job = addons.start("busy-host", login, "docker", "install")
    with pytest.raises(remote.RemoteError):
        addons.start("busy-host", login, "fail2ban", "install")
    other = addons.start("other-host", login, "fail2ban", "install")
    for _ in range(50):
        if addons.poll(job)["state"] != "running":
            break
        time.sleep(0.05)
    r = addons.poll(job)
    assert r["state"] == "ok" and r["text"] == "hello\nworld"
    assert addons.poll(job, since=6)["text"] == "world"
    assert addons.poll(other) is not None
    with pytest.raises(remote.RemoteError):
        addons.poll("missing")


def test_explain_known_failures():
    assert "sudo" in addons._explain("sudo: a password is required", 1)
    assert "apt" in addons._explain("E: Could not get lock /var/lib/dpkg/lock", 100)
    assert "100" in addons._explain("boom", 100)
