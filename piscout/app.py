import asyncio
import ctypes
import ipaddress
import os
import sys
import threading
import json
import re
import secrets
import socket
import stat
import time
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from . import addons, clipboard, tools, updates, fleet, flasher, i18n, remote, remoteflash, scanner, transfer, vault
from .i18n import tr

STATIC = Path(__file__).parent / "static"
AGENT_PORT = 8765
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

app = FastAPI(title="piscout")

# 每次啟動產生一個隨機 token，只會嵌在我們自己的頁面裡。
# 瀏覽器裡別的網頁讀不到它，就沒辦法呼叫 /api（避免有人從網頁打到本機的服務）。
API_TOKEN = secrets.token_urlsafe(24)
MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


class LangMiddleware:
    """依 X-Lang / Accept-Language 設定這個請求的語言。
    用純 ASGI 寫，語言才會傳到後面的處理函式（BaseHTTPMiddleware 的做不到）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            h = dict(scope["headers"])
            raw = h.get(b"x-lang") or h.get(b"accept-language") or b""
            i18n.set_lang(raw.decode("latin-1"))
        await self.app(scope, receive, send)


app.add_middleware(LangMiddleware)


@app.middleware("http")
async def guard(request, call_next):
    host = (request.headers.get("host") or "").split(":")[0]
    if host not in ("127.0.0.1", "localhost"):
        return JSONResponse({"detail": "forbidden"}, status_code=403)
    if request.url.path.startswith("/api/"):
        given = request.headers.get("x-piscout-token", "")
        if not secrets.compare_digest(given, API_TOKEN):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
    return await call_next(request)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# 已經登入好、等著前端用 websocket 接上去的 SSH 連線
SESSIONS = {}
SESSION_TTL = 60


class Login(BaseModel):
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    port: int = Field(22, ge=1, le=65535)


class SessionReq(BaseModel):
    kind: str  # terminal / desktop
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    port: int = Field(22, ge=1, le=65535)


class FlashConfig(BaseModel):
    hostname: str = "raspberrypi"
    username: str = "pi"
    password: str
    wifi_ssid: str = ""
    wifi_password: str = ""
    wifi_country: str = "TW"
    timezone: str = "Asia/Taipei"
    keyboard: str = "us"


class RemoteFlashReq(BaseModel):
    risk_ack: bool = False  # 使用者已啟用進階功能並確認風險
    host: str
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    port: int = Field(22, ge=1, le=65535)
    image_url: str
    config: FlashConfig


class FlashReq(BaseModel):
    image_url: str
    disk_number: int
    disk_size: int
    verify: bool = True
    config: FlashConfig


def _check_host(host):
    """只允許操作私有網段，避免被拿來打外網。"""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise HTTPException(400, tr("host 必須是 IP"))
    if not ip.is_private:
        raise HTTPException(400, tr("只能操作區網內的位址"))
    return str(ip)


@app.get("/api/resolve")
async def api_resolve(name: str):
    """手動新增裝置：把使用者輸入的 IP 或主機名稱（例如 raspberrypi.local）變成區網 IP。"""
    name = name.strip()
    if not name or len(name) > 253:
        raise HTTPException(400, tr("請輸入 IP 或主機名稱"))
    try:
        return {"ip": _check_host(name)}
    except HTTPException:
        pass
    try:
        infos = await run_in_threadpool(socket.getaddrinfo, name, 22, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        raise HTTPException(404, tr("找不到 {name}：請確認名稱或 IP 沒有打錯，而且這台電腦和樹莓派在同一個網路。", name=name))
    return {"ip": _check_host(infos[0][4][0])}


@app.get("/")
def index():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("__PISCOUT_TOKEN__", API_TOKEN)
            .replace("__PISCOUT_VERSION__", __version__)
            .replace("__PISCOUT_DEMO__", "true" if DEMO else "false"),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/clipboard")
async def api_clipboard():
    """這台電腦剪貼簿的文字，給終端機貼上用（只有帶本機 token 的請求讀得到）。"""
    return {"text": await run_in_threadpool(clipboard.get_text)}


@app.get("/api/update")
async def api_update(channel: str = "stable", force: bool = False):
    """有沒有更新的版本（只問 GitHub 公開的 release，查不到就當沒有）。channel=pre 連預先發行版一起看。"""
    return await run_in_threadpool(lambda: updates.check(channel=channel, force=force))


class UpdateReq(BaseModel):
    version: str


@app.post("/api/update/install")
async def api_update_install(req: UpdateReq):
    """下載新版安裝程式並靜默安裝；安裝程式會關掉這個程式再重新開啟。"""
    try:
        await run_in_threadpool(updates.install, req.version)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    threading.Timer(2.0, os._exit, args=(0,)).start()   # 讓安裝程式接手
    return {"ok": True}


@app.get("/i18n-data.js")
def i18n_data():
    """把所有語言的介面翻譯交給前端（語言檔放在 static/locales/，放進去就會出現在語言選單）。"""
    data = {code: {"name": loc.get("name") or code, "ui": loc.get("ui") or {}}
            for code, loc in i18n.LOCALES.items()}
    return Response("window.PISCOUT_LOCALES = " + json.dumps(data, ensure_ascii=False) + ";",
                    media_type="application/javascript", headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------ 帳密儲存

class SavedLogin(BaseModel):
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    port: int = Field(22, ge=1, le=65535)


def _mac(key):
    key = key.lower()
    if not MAC_RE.match(key):
        raise HTTPException(400, tr("key 必須是 MAC 位址"))
    return key


# ------------------------------------------------------------ 總覽 / 批次操作

class FleetDevice(BaseModel):
    ip: str
    mac: str = ""


class FleetStatsReq(BaseModel):
    devices: list[FleetDevice]


class FleetActionReq(BaseModel):
    action: str
    devices: list[FleetDevice]


def _fleet_devices(items):
    if not items or len(items) > 64:
        raise HTTPException(400, "devices")
    out = []
    for d in items:
        out.append({"ip": _check_host(d.ip), "mac": d.mac.lower()})
    return out


@app.post("/api/fleet/stats")
async def api_fleet_stats(req: FleetStatsReq):
    devices = _fleet_devices(req.devices)
    return {"results": await run_in_threadpool(fleet.stats_many, devices)}


@app.post("/api/fleet/action")
async def api_fleet_action(req: FleetActionReq):
    if req.action not in fleet.ACTIONS:
        raise HTTPException(400, tr("不支援的操作"))
    devices = _fleet_devices(req.devices)
    return {"results": await run_in_threadpool(fleet.act_many, devices, req.action)}


@app.get("/api/vault/{key}")
def api_vault_get(key: str):
    return vault.get(_mac(key)) or {"username": "", "password": None, "key_path": None, "port": 22}


@app.put("/api/vault/{key}")
def api_vault_put(key: str, body: SavedLogin):
    vault.put(_mac(key), body.username, body.password, body.port, body.key_path)
    return {"ok": True}


@app.delete("/api/vault/{key}")
def api_vault_delete(key: str):
    vault.delete(_mac(key))
    return {"ok": True}


@app.delete("/api/vault")
def api_vault_clear():
    vault.delete(None)
    return {"ok": True}


# ------------------------------------------------------------ 掃描 / 連線

# 錄製 README 示範用：PISCOUT_DEMO=1 時回傳模擬的裝置，搭配 tools/demo_shell.py。
# 畫面上會一直顯示「DEMO」橫幅，不會被誤認成真機。
DEMO = os.environ.get("PISCOUT_DEMO") == "1"
DEMO_SCAN = {
    "network": "192.168.0.0/24",
    "devices": [
        {"ip": "127.0.0.1", "mac": "b8:27:eb:00:de:01", "hostname": "raspberrypi",
         "ssh_open": True, "is_pi": True, "hint_model": "pi4"},
        {"ip": "192.168.0.1", "mac": "18:00:00:00:00:01", "hostname": "",
         "ssh_open": False, "is_pi": False, "hint_model": None},
    ],
}


@app.get("/api/scan")
async def api_scan():
    if DEMO:
        await asyncio.sleep(2.5)
        return DEMO_SCAN
    return await run_in_threadpool(scanner.scan)


def _info(host, login):
    return _with_client(host, login, remote.get_info)


def _install(host, login):
    client = remote.connect(host, login.username, login.password, login.key_path, port=login.port)
    try:
        return remote.install_agent(client, sudo_password=login.password)
    finally:
        client.close()


@app.post("/api/devices/{host}/info")
async def api_info(host: str, login: Login):
    host = _check_host(host)
    try:
        info = await run_in_threadpool(_info, host, login)
    except remote.RemoteError as e:
        raise HTTPException(502, str(e))
    info["model_id"] = flasher.model_id(info.get("model", ""))
    return info


@app.post("/api/devices/{host}/install")
async def api_install(host: str, login: Login):
    host = _check_host(host)
    try:
        ok = await run_in_threadpool(_install, host, login)
    except remote.RemoteError as e:
        raise HTTPException(502, str(e))
    return {"installed": ok}


def _with_client(host, login, fn):
    """終端機分頁已經連著的話就直接用那條 SSH（省掉登入的時間，樹莓派上很明顯），沒有才另外連。"""
    shared = TERMS.get(host)
    transport = shared.get_transport() if shared is not None else None
    if transport is not None and transport.is_active():
        return fn(shared)
    client = remote.connect(host, login.username, login.password, login.key_path, port=login.port)
    try:
        return fn(client)
    finally:
        client.close()


@app.post("/api/devices/{host}/health")
async def api_health(host: str, login: Login):
    """新手用的健康檢查：只讀取，回傳白話的結論與建議。"""
    host = _check_host(host)
    try:
        return {"checks": await run_in_threadpool(_with_client, host, login, tools.health)}
    except remote.RemoteError as e:
        raise HTTPException(502, str(e))


class SetupReq(Login):
    action: Optional[str] = None


@app.post("/api/devices/{host}/setup")
async def api_setup(host: str, req: SetupReq):
    """一鍵快速設定。沒給 action 就回傳各項目目前的狀態；有給就執行寫死清單裡的那一項。"""
    host = _check_host(host)
    if req.action is not None and req.action not in tools.ACTIONS:
        raise HTTPException(400, tr("不支援的操作"))
    try:
        if req.action is None:
            return {"items": await run_in_threadpool(_with_client, host, req, tools.setup_status)}
        return await run_in_threadpool(
            _with_client, host, req, lambda c: tools.setup_apply(c, req.action, req.password))
    except remote.RemoteError as e:
        raise HTTPException(502, str(e))


# ------------------------------------------------------------ 擴充套件（NAS、Docker……）

@app.post("/api/devices/{host}/addons")
async def api_addons(host: str, login: Login):
    """列出擴充套件和各自的安裝狀態。"""
    host = _check_host(host)
    try:
        return await run_in_threadpool(
            _with_client, host, login, lambda c: addons.status(c, host, login.username))
    except remote.RemoteError as e:
        raise HTTPException(502, str(e))


@app.post("/api/devices/{host}/addons/{addon_id}/{op}")
async def api_addon_run(host: str, addon_id: str, op: str, login: Login):
    """開始安裝或移除，回傳工作代號，畫面再用 /api/addons/jobs/{id} 看進度。"""
    host = _check_host(host)
    if addon_id not in addons.BY_ID or op not in ("install", "remove"):
        raise HTTPException(400, tr("不支援的操作"))
    try:
        job = addons.start(host, login.model_dump(), addon_id, op)
    except remote.RemoteError as e:
        raise HTTPException(409, str(e))
    return {"job": job}


@app.get("/api/addons/jobs/{job_id}")
def api_addon_job(job_id: str, since: int = 0):
    try:
        return addons.poll(job_id, max(0, since))
    except remote.RemoteError as e:
        raise HTTPException(404, str(e))


# ------------------------------------------------------------ 終端機 / 遠端桌面

TERMS = {}
TAPS = {}
UPLOADS = {}
UPLOAD_TTL = 300


def _drop(sess):
    try:
        if sess.get("kind") == "desktop":
            remote.stop_desktop(sess["client"])
    finally:
        sess["client"].close()


def _expire_sessions():
    now = time.time()
    for token in [t for t, v in SESSIONS.items() if now - v["created"] > SESSION_TTL]:
        _drop(SESSIONS.pop(token))


def _open_session(host, req):
    client = remote.connect(host, req.username, req.password, req.key_path, port=req.port)
    try:
        port = remote.start_desktop(client) if req.kind == "desktop" else None
    except Exception:
        client.close()
        raise
    return client, port


@app.post("/api/devices/{host}/session")
async def api_session(host: str, req: SessionReq):
    host = _check_host(host)
    if req.kind not in ("terminal", "desktop"):
        raise HTTPException(400, tr("kind 不對"))
    _expire_sessions()
    try:
        client, port = await run_in_threadpool(_open_session, host, req)
    except remote.RemoteError as e:
        raise HTTPException(502, str(e))
    token = secrets.token_urlsafe(16)
    SESSIONS[token] = {
        "client": client, "kind": req.kind, "port": port, "created": time.time(), "host": host,
    }
    return {"token": token}


async def _pump(ws, chan, on_text=None, tap=None):
    """chan（paramiko channel）和 websocket 之間搬資料，任何一邊結束就收工。"""
    loop = asyncio.get_running_loop()

    def recv():
        try:
            return chan.recv(32768)
        except socket.timeout:
            return None

    async def chan_to_ws():
        if tap:
            chan.settimeout(0.4)
        while True:
            data = await loop.run_in_executor(None, recv)
            if data == b"":
                return
            if tap:
                data = tap.feed(data) if data is not None else tap.idle()
            if data:
                await ws.send_bytes(data)

    async def ws_to_chan():
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes") is not None:
                await loop.run_in_executor(None, chan.sendall, msg["bytes"])
            elif msg.get("text") is not None and on_text:
                on_text(msg["text"])

    tasks = [asyncio.ensure_future(chan_to_ws()), asyncio.ensure_future(ws_to_chan())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        chan.close()


def _take_session(token, kind):
    sess = SESSIONS.pop(token, None)
    if sess is None or sess["kind"] != kind:
        return None
    return sess


async def _accept(ws):
    # noVNC 會要求 binary 子協定
    if "binary" in ws.scope.get("subprotocols", []):
        await ws.accept(subprotocol="binary")
    else:
        await ws.accept()


@app.websocket("/ws/terminal/{token}")
async def ws_terminal(ws: WebSocket, token: str, cols: int = 80, rows: int = 24):
    sess = _take_session(token, "terminal")
    if sess is None:
        await ws.close(code=4404)
        return
    await _accept(ws)
    chan = sess["client"].invoke_shell(term="xterm-256color", width=cols, height=rows)
    TERMS[sess["host"]] = sess["client"]  # 傳檔時用它找出終端機目前的資料夾
    tap = transfer.CwdTap(chan.send)
    TAPS[sess["host"]] = tap

    def on_text(text):
        try:
            m = json.loads(text)
            if m.get("t") == "r":
                chan.resize_pty(width=int(m["c"]), height=int(m["r"]))
        except (ValueError, KeyError, TypeError):
            pass

    try:
        await _pump(ws, chan, on_text, tap)
    finally:
        if TERMS.get(sess["host"]) is sess["client"]:
            del TERMS[sess["host"]]
            TAPS.pop(sess["host"], None)
        _drop(sess)
        try:
            await ws.close()
        except RuntimeError:
            pass


@app.websocket("/ws/desktop/{token}")
async def ws_desktop(ws: WebSocket, token: str):
    sess = _take_session(token, "desktop")
    if sess is None:
        await ws.close(code=4404)
        return
    await _accept(ws)
    try:
        chan = sess["client"].get_transport().open_channel(
            "direct-tcpip", ("127.0.0.1", sess["port"]), ("127.0.0.1", 0)
        )
    except Exception:
        _drop(sess)
        await ws.close(code=1011)
        return
    try:
        await _pump(ws, chan)
    finally:
        await run_in_threadpool(_drop, sess)
        try:
            await ws.close()
        except RuntimeError:
            pass


class CompleteReq(BaseModel):
    word: str
    first: bool = False
    dirs_only: bool = False


@app.post("/api/devices/{host}/complete")
async def api_complete(host: str, req: CompleteReq):
    """終端機輸入時的補齊建議。用終端機分頁那條連線跑 compgen，只讀不寫。"""
    host = _check_host(host)
    client = TERMS.get(host)
    if client is None:
        return {"items": []}
    tap = TAPS.get(host)
    cwd = tap.cwd if tap and tap.cwd.startswith("/") else ""
    try:
        items = await run_in_threadpool(transfer.complete, client, req.word, cwd, req.first, req.dirs_only)
    except Exception:
        items = []
    return {"items": items}


# ------------------------------------------------------------ 傳檔（拖曳到視窗）

class UploadReq(BaseModel):
    mode: str  # term / desk
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    port: int = Field(22, ge=1, le=65535)


def _close_upload(u):
    try:
        u["sftp"].close()
    finally:
        u["client"].close()


def _expire_uploads():
    now = time.time()
    for token in [t for t, v in UPLOADS.items() if now - v["used"] > UPLOAD_TTL]:
        _close_upload(UPLOADS.pop(token))


def _reported_dir(sftp, host):
    """終端機用 OSC 7 回報的資料夾；必須是存在的絕對路徑，否則不採用。"""
    tap = TAPS.get(host)
    d = tap.cwd if tap else ""
    if not d.startswith("/"):
        return ""
    try:
        return d if stat.S_ISDIR(sftp.stat(d).st_mode) else ""
    except (IOError, OSError):
        return ""


def _open_upload(host, req):
    client = remote.connect(host, req.username, req.password, req.key_path, port=req.port)
    try:
        sftp = client.open_sftp()
        directory = _reported_dir(sftp, host) if req.mode == "term" else ""
        if not directory:
            directory = transfer.target_dir(client, req.mode, TERMS.get(host))
        return client, sftp, directory
    except Exception:
        client.close()
        raise


@app.post("/api/devices/{host}/upload")
async def api_upload_open(host: str, req: UploadReq):
    host = _check_host(host)
    if req.mode not in ("term", "desk"):
        raise HTTPException(400, tr("kind 不對"))
    _expire_uploads()
    try:
        client, sftp, directory = await run_in_threadpool(_open_upload, host, req)
    except remote.RemoteError as e:
        raise HTTPException(502, str(e))
    token = secrets.token_urlsafe(16)
    UPLOADS[token] = {"client": client, "sftp": sftp, "dir": directory, "used": time.time()}
    return {"token": token, "dir": directory}


def _sftp_exists(sftp, path):
    try:
        sftp.stat(path)
        return True
    except IOError:
        return False


def _open_target(u, name):
    sftp = u["sftp"]
    name = transfer.unique_name(name, lambda n: _sftp_exists(sftp, u["dir"] + "/" + n))
    final = u["dir"].rstrip("/") + "/" + name
    f = sftp.open(final + ".piscout-part", "wb")
    f.set_pipelined(True)
    return f, final


@app.post("/api/upload/{token}")
async def api_upload_file(token: str, request: Request, name: str):
    u = UPLOADS.get(token)
    if u is None:
        raise HTTPException(404, tr("沒有這個工作"))
    try:
        name = transfer.safe_name(name)
    except ValueError:
        raise HTTPException(400, tr("檔名不合法"))
    u["used"] = time.time()
    try:
        f, final = await run_in_threadpool(_open_target, u, name)
    except (IOError, OSError, ValueError) as e:
        raise HTTPException(502, tr("無法寫入 {dir}：{e}", dir=u["dir"], e=e))
    total, buf, ok = 0, bytearray(), False
    try:
        async for chunk in request.stream():
            buf += chunk
            total += len(chunk)
            if len(buf) >= 1 << 20:
                await run_in_threadpool(f.write, bytes(buf))
                buf.clear()
        if buf:
            await run_in_threadpool(f.write, bytes(buf))
        ok = True
    finally:
        await run_in_threadpool(f.close)
        sftp = u["sftp"]
        if ok:
            await run_in_threadpool(sftp.posix_rename, final + ".piscout-part", final)
        else:
            try:
                await run_in_threadpool(sftp.remove, final + ".piscout-part")
            except IOError:
                pass
    u["used"] = time.time()
    return {"path": final, "size": total}


@app.delete("/api/upload/{token}")
async def api_upload_close(token: str):
    u = UPLOADS.pop(token, None)
    if u:
        await run_in_threadpool(_close_upload, u)
    return {"ok": True}


def _fetch_stats(host):
    url = f"http://{host}:{AGENT_PORT}/stats"
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.loads(r.read())


@app.get("/api/devices/{host}/stats")
async def api_stats(host: str):
    host = _check_host(host)
    try:
        return await run_in_threadpool(_fetch_stats, host)
    except OSError:
        raise HTTPException(502, tr("agent 沒有回應"))


# ------------------------------------------------------------ 燒錄

@app.post("/api/elevate")
def api_elevate():
    """本機燒錄才需要系統管理員權限：使用者要求時，才用管理員身分重新啟動自己。"""
    if os.name != "nt":
        raise HTTPException(400, tr("燒錄功能目前只支援 Windows"))
    if flasher.is_admin():
        return {"already": True}
    exe = sys.executable
    if getattr(sys, "frozen", False):
        args = ""
    else:
        args = '"' + str(Path(__file__).resolve().parent.parent / "run_gui.py") + '"'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
    if rc <= 32:  # 使用者在 UAC 按了「否」
        raise HTTPException(400, tr("沒有取得系統管理員權限"))
    threading.Timer(1.0, lambda: os._exit(0)).start()  # 讓這個回應先送出去
    return {"ok": True}


@app.get("/api/flash/drives")
async def api_drives():
    try:
        return {
            "drives": await run_in_threadpool(flasher.list_drives),
            "admin": flasher.is_admin(),
        }
    except flasher.FlashError as e:
        raise HTTPException(500, str(e))


@app.get("/api/flash/images")
async def api_images(model: str = "pi4", purpose: str = "desktop"):
    try:
        images = await run_in_threadpool(flasher.list_images)
    except flasher.FlashError as e:
        raise HTTPException(502, str(e))
    return {
        "images": flasher.recommend(images, model, purpose),
        "models": [{"id": k, "name": v[0]} for k, v in flasher.MODELS.items()],
    }


@app.post("/api/flash/start")
async def api_flash_start(req: FlashReq):
    try:
        job_id = await run_in_threadpool(
            flasher.start_job,
            req.image_url, req.disk_number, req.disk_size,
            req.config.model_dump(), req.verify,
        )
    except flasher.FlashError as e:
        raise HTTPException(400, str(e))
    return {"job": job_id}


@app.post("/api/flash/remote/start")
async def api_flash_remote(req: RemoteFlashReq):
    if not req.risk_ack:
        raise HTTPException(400, tr("遠端重灌是進階功能，請先在「燒錄系統」頁啟用並確認風險"))
    host = _check_host(req.host)
    login = {"username": req.username, "password": req.password or None,
             "key_path": req.key_path, "port": req.port}
    try:
        job_id = await run_in_threadpool(
            remoteflash.start_job, host, login, req.image_url, req.config.model_dump()
        )
    except flasher.FlashError as e:
        raise HTTPException(400, str(e))
    return {"job": job_id}


@app.get("/api/flash/jobs/{job_id}")
def api_flash_job(job_id: str):
    try:
        return flasher.get_job(job_id)
    except flasher.FlashError as e:
        raise HTTPException(404, str(e))
