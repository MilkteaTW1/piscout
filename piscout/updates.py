"""檢查 GitHub 上有沒有比目前更新的版本。

只問一次公開的 "latest release" 資訊（不帶帳號、不上傳任何資料），結果快取幾個小時；
連不上、被擋或格式不對都安靜略過，不影響程式。設環境變數 PISCOUT_NO_UPDATE_CHECK=1 可以完全關掉。
"""
import json
import os
import hashlib
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from . import __version__
from .i18n import tr

REPO = "MilkteaTW1/piscout"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
API_ALL = f"https://api.github.com/repos/{REPO}/releases?per_page=15"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
TTL = 6 * 3600
TIMEOUT = 6

_lock = threading.Lock()
_cache = {}   # channel -> {"at": 時間, "data": tag}


def parse(version):
    """'v0.1.8' -> (0, 1, 8)；看不懂就回 None。"""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", str(version or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def disabled():
    return os.environ.get("PISCOUT_NO_UPDATE_CHECK", "") not in ("", "0")


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"piscout/{__version__}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read(2_000_000).decode("utf-8"))


def _fetch(channel="stable"):
    """stable：只看正式版（GitHub 的 latest）；pre：連預先發行版一起看，取版本最高的那個。"""
    if channel != "pre":
        return _get(API)
    rels = [r for r in _get(API_ALL) if not r.get("draft") and parse(r.get("tag_name"))]
    return max(rels, key=lambda r: parse(r["tag_name"]), default={})


def check(fetch=_fetch, now=time.time, channel="stable", force=False):
    """回傳 {current, latest, newer, url, channel}；查不到時 latest 是 None、newer 是 False。"""
    channel = "pre" if channel == "pre" else "stable"
    out = {"current": __version__, "latest": None, "newer": False, "url": RELEASES_URL, "channel": channel}
    if disabled():
        return out
    with _lock:
        c = _cache.get(channel)
        if force or c is None or now() - c["at"] > TTL:
            try:
                rel = fetch(channel) if fetch is _fetch else fetch()
                tag = str(rel.get("tag_name") or "")
                c = {"at": now(), "data": tag if parse(tag) else ""}
            except Exception:
                c = {"at": now(), "data": ""}
            _cache[channel] = c
        tag = c["data"]
    if tag:
        out["latest"] = tag.lstrip("v")
        out["newer"] = parse(tag) > (parse(__version__) or (0, 0, 0))
    return out


DOWNLOAD = f"https://github.com/{REPO}/releases/download/v{{v}}/piscout-setup.exe"


def _download(url, dest, limit=300_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": f"piscout/{__version__}"})
    h, size = hashlib.sha256(), 0
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError("too large")
            h.update(chunk)
            f.write(chunk)
    return h.hexdigest()


def install(version, launch=subprocess.Popen, download=_download):
    """下載新版安裝程式、核對 SHA256，靜默安裝（會關掉並重開這個程式）。失敗丟 RuntimeError（訊息可直接顯示）。"""
    if not parse(version):
        raise RuntimeError(tr("版本格式不正確"))
    if not getattr(sys, "frozen", False) and download is _download:
        raise RuntimeError(tr("從原始碼執行時不能自動更新，請用 git pull"))
    url = DOWNLOAD.format(v=version.lstrip("v"))
    folder = tempfile.mkdtemp(prefix="piscout-update-")
    exe = os.path.join(folder, "piscout-setup.exe")
    try:
        got = download(url, exe)
    except Exception as e:
        raise RuntimeError(tr("下載更新失敗：{e}", e=e))
    try:
        req = urllib.request.Request(url + ".sha256", headers={"User-Agent": f"piscout/{__version__}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            want = r.read(1000).decode("ascii", "ignore").split()[0].lower()
    except Exception:
        want = ""
    if not want or want != got:
        raise RuntimeError(tr("更新檔驗證失敗，已取消"))
    launch([exe, "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS", "/update=1"],
           close_fds=True)
