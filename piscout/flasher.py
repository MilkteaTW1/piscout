"""把 Raspberry Pi OS 燒進 SD 卡，並寫入開機設定（SSH、帳號、Wi-Fi…）。

目前只支援 Windows。流程：
  下載 .img.xz -> 清掉磁碟 -> 解壓縮並直接寫入實體磁碟 -> 讀回校驗
  -> 掛載 boot 分割區 -> 寫入 user-data / custom.toml
"""
import ctypes
import hashlib
import json
import lzma
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from .i18n import get_lang, set_lang, tr

OS_LIST_URL = "https://downloads.raspberrypi.org/os_list_imagingutility_v4.json"
SECTOR = 512
CHUNK = 4 * 1024 * 1024
MAX_DISK_BYTES = 512 * 10**9  # 超過這個大小的磁碟不列出來，避免誤選外接硬碟
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,62}$")
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
TIMEZONE_RE = re.compile(r"^[A-Za-z_]+(/[A-Za-z0-9_+-]+)*$")


class FlashError(Exception):
    pass


def keep_awake(on):
    """燒錄期間禁止 Windows 進入睡眠（設定是以執行緒為單位，開始與結束都要在同一個執行緒呼叫）。"""
    if os.name != "nt":
        return
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        )
    except OSError:
        pass


# ---------------------------------------------------------------- 映像清單

def _flatten(items, out, in_pi_group):
    for o in items:
        if "subitems" in o:
            _flatten(o["subitems"], out, o["name"].startswith("Raspberry Pi OS"))
            continue
        is_pi = in_pi_group or o["name"].startswith("Raspberry Pi OS")
        if not (is_pi and o.get("url") and o.get("extract_sha256") and o.get("extract_size")):
            continue
        if o.get("init_format") not in ("cloudinit-rpi", "systemd"):
            continue
        out.append(
            {
                "name": o["name"],
                "url": o["url"],
                "sha256": o["extract_sha256"],
                "size": int(o["extract_size"]),
                "download_size": int(o.get("image_download_size") or 0),
                "release_date": o.get("release_date", ""),
                "init_format": o["init_format"],
                "devices": o.get("devices") or [],
            }
        )


def list_images():
    req = urllib.request.Request(OS_LIST_URL, headers={"User-Agent": "piscout"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
    except (OSError, ValueError) as e:
        raise FlashError(tr("抓不到系統清單，網路有通嗎？（{e}）", e=e))
    out = []
    _flatten(data.get("os_list", []), out, False)
    return out


OFFICIAL_HOSTS = ("raspberrypi.com", "raspberrypi.org")


def find_image(url):
    # 只接受官方清單裡的網址，而且網域必須是樹莓派官方的
    host = urllib.parse.urlparse(url).hostname or ""
    if not any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS):
        raise FlashError(tr("只能下載樹莓派官方網站的映像"))
    for img in list_images():
        if img["url"] == url:
            return img
    raise FlashError(tr("找不到這個系統映像"))


# ---------------------------------------------------------------- 磁碟

def _ps(script, timeout=90):
    return subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script,
        ],
        capture_output=True, text=True, encoding="utf-8",
        timeout=timeout, creationflags=NO_WINDOW,
    )


def list_drives():
    """列出可移除磁碟，並判斷卡上有沒有樹莓派系統。

    status: blank（完全空白）/ pi_os（看得到 cmdline.txt 或 config.txt）/ other
    """
    if os.name != "nt":
        raise FlashError(tr("燒錄功能目前只支援 Windows"))
    script = (
        "Get-Disk | Where-Object { $_.BusType -in 'USB','SD','MMC' "
        "-and -not $_.IsSystem -and -not $_.IsBoot -and $_.Size -gt 0 } "
        "| ForEach-Object { "
        "$n = $_.Number; "
        "$parts = @(Get-Partition -DiskNumber $n -ErrorAction SilentlyContinue); "
        "$pi = $false; "
        "foreach ($p in $parts) { if ($p.DriveLetter) { "
        "$r = \"$($p.DriveLetter):\\\"; "
        "if ((Test-Path ($r + 'cmdline.txt')) -or (Test-Path ($r + 'config.txt'))) { $pi = $true } } }; "
        "[pscustomobject]@{ Number = $n; FriendlyName = $_.FriendlyName; "
        "Size = $_.Size; BusType = [string]$_.BusType; Parts = $parts.Count; IsPi = $pi } "
        "} | ConvertTo-Json -Compress"
    )
    r = _ps(script)
    if r.returncode != 0:
        raise FlashError(tr("讀取磁碟失敗：{err}", err=r.stderr.strip()))
    text = r.stdout.strip()
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    out = []
    for d in data:
        if int(d["Size"]) > MAX_DISK_BYTES:
            continue
        if d.get("IsPi"):
            status = "pi_os"
        elif int(d.get("Parts") or 0) == 0:
            status = "blank"
        else:
            status = "other"
        out.append(
            {
                "number": int(d["Number"]),
                "name": (d.get("FriendlyName") or "").strip(),
                "size": int(d["Size"]),
                "bus": str(d.get("BusType", "")),
                "status": status,
            }
        )
    return out


# 型號 -> 官方清單裡的 devices 標籤
MODELS = {
    "pi5": ("Raspberry Pi 5 / 500 / CM5", "pi5-64bit"),
    "pi4": ("Raspberry Pi 4 / 400 / CM4", "pi4-64bit"),
    "pi3": ("Raspberry Pi 3 / Zero 2 W", "pi3-64bit"),
    "pi2": ("Raspberry Pi 2", "pi2-32bit"),
    "pi1": ("Raspberry Pi 1 / Zero / Zero W", "pi1-32bit"),
}


def model_id(text):
    """把 /proc/device-tree/model 的字串轉成 MODELS 的 id，認不出來回傳 None。"""
    t = text or ""
    if re.search(r"Pi 5|Pi 500|Compute Module 5", t, re.I):
        return "pi5"
    if re.search(r"Pi 4|Pi 400|Compute Module 4", t, re.I):
        return "pi4"
    if re.search(r"Pi 3|Zero 2", t, re.I):
        return "pi3"
    if re.search(r"Pi 2", t, re.I):
        return "pi2"
    if re.search(r"Zero|Pi Model|Pi 1|Pi Compute Module", t, re.I):
        return "pi1"
    return None


def recommend(images, model, purpose="desktop"):
    """依型號和用途挑出最適合的映像，回傳加了 supported / recommended / reason 的清單。"""
    if model not in MODELS:
        model = "pi4"
    label, tag = MODELS[model]
    is64 = tag.endswith("64bit")
    want_lite = purpose == "lite"

    want = ("Raspberry Pi OS Lite (64-bit)" if want_lite else "Raspberry Pi OS (64-bit)")         if is64 else         ("Raspberry Pi OS Lite (32-bit)" if want_lite else "Raspberry Pi OS (32-bit)")

    if want_lite:
        reason = tr("精簡版：沒有桌面，佔空間小、開機快，只能用終端機操作。")
    else:
        reason = tr("官方預設的完整桌面版，可以用終端機，也可以遠端操作桌面。")
    if is64:
        reason += " " + tr("{label} 支援 64 位元，官方建議用 64 位元版。", label=label)
    else:
        reason += " " + tr("{label} 只支援 32 位元版。", label=label)
    if model in ("pi3", "pi1") and not want_lite:
        reason += " " + tr("這款記憶體偏少，如果覺得卡，可以改選精簡版。")

    out = []
    for im in images:
        supported = tag in im["devices"]
        rec = supported and im["name"] == want
        out.append({**im, "supported": supported, "recommended": rec,
                    "reason": reason if rec else ""})
    out.sort(key=lambda i: (not i["recommended"], not i["supported"], i["name"]))
    return out


def is_admin():
    if os.name != "nt":
        return os.geteuid() == 0
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


# ---------------------------------------------------------------- 下載 / 寫入

def _download(url, dest, progress):
    if dest.exists():
        progress("download", 1, 1)
        return
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "piscout"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                b = r.read(256 * 1024)
                if not b:
                    break
                f.write(b)
                done += len(b)
                progress("download", done, total)
    except OSError as e:
        raise FlashError(tr("下載失敗：{e}", e=e))
    part.replace(dest)


def _decompressed(path):
    dec = lzma.LZMADecompressor()
    with open(path, "rb") as f:
        while True:
            raw = f.read(1 << 20)
            if not raw:
                break
            data = dec.decompress(raw)
            if data:
                yield data


def _write_all(f, data):
    view = memoryview(data)
    while view:
        n = f.write(view)
        view = view[n:]


def write_image(src, target, sha256, size, progress, verify=True):
    """把 src(.img.xz) 解壓縮後寫到 target（磁碟或檔案），回傳寫入的位元組數。"""
    h = hashlib.sha256()
    buf = bytearray()
    total = 0
    sums = []  # 每個 CHUNK 的校驗碼，讀回時用來指出壞在哪裡
    head = None  # 第一個 CHUNK（含分割表）留到最後才寫，避免寫到一半 Windows 就去掛載新磁碟區
    try:
        with open(target, "r+b", buffering=0) as out:
            def put(block, last=False):
                nonlocal head
                sums.append(hashlib.sha256(block).digest())
                if head is None and len(sums) == 1:
                    head = block
                    out.seek(len(block))
                else:
                    _write_all(out, block + b"\0" * (-len(block) % SECTOR) if last else block)

            for data in _decompressed(src):
                h.update(data)
                total += len(data)
                buf += data
                while len(buf) >= CHUNK:
                    put(bytes(buf[:CHUNK]))
                    del buf[:CHUNK]
                    progress("write", total - len(buf), size)
            if buf:
                put(bytes(buf), last=True)
            progress("write", total, size)
            if head is not None:
                out.seek(0)
                _write_all(out, head + b"\0" * (-len(head) % SECTOR))
            os.fsync(out.fileno())
    except lzma.LZMAError as e:
        raise FlashError(tr("映像檔損毀：{e}", e=e))
    except PermissionError:
        raise FlashError(tr("沒有寫入磁碟的權限，請用系統管理員身分執行"))
    except OSError as e:
        raise FlashError(tr("寫入磁碟失敗：{e}", e=e))

    if total != size or h.hexdigest() != sha256:
        raise FlashError(tr("下載的映像檔校驗碼不符，已放棄。請刪掉快取後重試"))

    if verify:
        left = total
        index = 0
        with open(target, "rb", buffering=0) as f:
            while left > 0:
                want = min(CHUNK, left)
                for attempt in (1, 2):  # 讀不一致時重讀一次，排除一次性的讀取錯誤
                    f.seek(index * CHUNK)
                    block = f.read(-(-want // SECTOR) * SECTOR)
                    if hashlib.sha256(block[:want]).digest() == sums[index]:
                        break
                else:
                    raise FlashError(tr("寫入後讀回校驗失敗（約在 {mb} MB 處），這張 SD 卡或讀卡機可能有問題，請換一張卡或換個 USB 孔再試",
                                        mb=index * CHUNK // (1024 * 1024)))
                left -= want
                index += 1
                progress("verify", total - left, total)
    return total


# ---------------------------------------------------------------- 開機設定

def validate_config(cfg):
    if not HOSTNAME_RE.match(cfg["hostname"]):
        raise FlashError(tr("主機名稱只能用英文、數字和 -"))
    if not USERNAME_RE.match(cfg["username"]):
        raise FlashError(tr("使用者名稱只能用小寫英文、數字、_ 和 -"))
    if not cfg["password"] or "\n" in cfg["password"]:
        raise FlashError(tr("請設定密碼"))
    if not TIMEZONE_RE.match(cfg["timezone"]):
        raise FlashError(tr("時區格式不對，例如 Asia/Taipei"))
    if not re.match(r"^[a-z]{2}$", cfg["keyboard"]):
        raise FlashError(tr("鍵盤配置請填兩個小寫字母，例如 us"))
    ssid, wpass = cfg["wifi_ssid"], cfg["wifi_password"]
    if ssid:
        if len(ssid.encode()) > 32:
            raise FlashError(tr("Wi-Fi 名稱太長"))
        if wpass and not 8 <= len(wpass) <= 63:
            raise FlashError(tr("Wi-Fi 密碼要 8 到 63 個字元"))
        if not re.match(r"^[A-Z]{2}$", cfg["wifi_country"]):
            raise FlashError(tr("Wi-Fi 國碼請填兩個大寫字母，例如 TW"))


def _q(s):
    # JSON 字串同時也是合法的 YAML / TOML 字串
    return json.dumps(s, ensure_ascii=False)


def make_config(init_format, cfg):
    """回傳 {檔名: 內容}，要寫進 boot 分割區根目錄。"""
    from passlib.hash import sha512_crypt

    hashed = sha512_crypt.hash(cfg["password"])
    wifi = bool(cfg["wifi_ssid"])
    files = {}

    if init_format == "cloudinit-rpi":
        files["user-data"] = "\n".join(
            [
                "#cloud-config",
                f"hostname: {cfg['hostname']}",
                "manage_etc_hosts: true",
                "packages:",
                "- avahi-daemon",
                "users:",
                f"- name: {cfg['username']}",
                "  groups: users,adm,dialout,audio,netdev,video,plugdev,cdrom,games,input,gpio,spi,i2c,render,sudo",
                "  shell: /bin/bash",
                "  lock_passwd: false",
                f"  passwd: {_q(hashed)}",
                "enable_ssh: true",
                "ssh_pwauth: true",
                f"timezone: {cfg['timezone']}",
                "keyboard:",
                "  model: pc105",
                f"  layout: {_q(cfg['keyboard'])}",
                "",
            ]
        )
        if wifi:
            lines = [
                "network:",
                "  version: 2",
                "  wifis:",
                "    renderer: networkd",
                "    wlan0:",
                "      dhcp4: true",
                "      optional: true",
                f"      regulatory-domain: {cfg['wifi_country']}",
                "      access-points:",
                f"        {_q(cfg['wifi_ssid'])}:",
            ]
            if cfg["wifi_password"]:
                lines.append(f"          password: {_q(cfg['wifi_password'])}")
            else:
                lines[-1] += " {}"
            files["network-config"] = "\n".join(lines) + "\n"
    else:  # systemd / custom.toml（Bookworm 系列）
        t = [
            "config_version = 1",
            "",
            "[system]",
            f"hostname = {_q(cfg['hostname'])}",
            "",
            "[user]",
            f"name = {_q(cfg['username'])}",
            f"password = {_q(hashed)}",
            "password_encrypted = true",
            "",
            "[ssh]",
            "enabled = true",
            "password_authentication = true",
            "",
            "[locale]",
            f"keymap = {_q(cfg['keyboard'])}",
            f"timezone = {_q(cfg['timezone'])}",
            "",
        ]
        if wifi:
            t += [
                "[wlan]",
                f"ssid = {_q(cfg['wifi_ssid'])}",
                f"password = {_q(cfg['wifi_password'])}",
                "password_encrypted = false",
                "hidden = false",
                f"country = {_q(cfg['wifi_country'])}",
                "",
            ]
        files["custom.toml"] = "\n".join(t)
    return files


def _boot_letter(disk):
    script = (
        f"Update-Disk -Number {disk}; "
        f"$p = Get-Partition -DiskNumber {disk} -PartitionNumber 1; "
        "if (-not $p.DriveLetter) { $p | Add-PartitionAccessPath -AssignDriveLetter; "
        f"$p = Get-Partition -DiskNumber {disk} -PartitionNumber 1 }}; "
        "$p.DriveLetter"
    )
    for _ in range(10):
        r = _ps(script)
        letter = r.stdout.strip()
        if re.match(r"^[A-Za-z]$", letter):
            return letter
        time.sleep(2)
    raise FlashError(tr("寫完了，但 Windows 沒有掛出 boot 分割區，沒辦法寫入設定"))


def apply_config(disk, files):
    letter = _boot_letter(disk)
    root = Path(f"{letter}:\\")
    for name, content in files.items():
        with open(root / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    _ps(f"Write-VolumeCache -DriveLetter {letter}", timeout=60)


# ---------------------------------------------------------------- 工作排程

JOBS = {}
_lock = threading.Lock()

PHASE_LABEL = {
    "image": "準備映像（校驗並寫入開機設定）",
    "connect": "連線並檢查樹莓派",
    "stream": "寫入樹莓派的 SD 卡",
    "reboot": "完成，樹莓派重新開機中",
    "prepare": "準備中",
    "download": "下載系統映像",
    "clean": "清除磁碟",
    "write": "寫入 SD 卡",
    "verify": "校驗",
    "configure": "寫入開機設定",
    "done": "完成",
}


def _run(job, image, drive, cfg, verify):
    set_lang(job.get("lang", "zh"))
    def progress(phase, done, total):
        job.update(phase=phase, done=done, total=total)

    keep_awake(True)
    try:
        if os.name != "nt":
            raise FlashError(tr("燒錄功能目前只支援 Windows"))
        if not is_admin():
            raise FlashError(tr("需要系統管理員權限才能寫入磁碟，請用「以系統管理員身分執行」開啟"))

        files = make_config(image["init_format"], cfg)

        src = cache_dir() / image["url"].rsplit("/", 1)[-1]
        _download(image["url"], src, progress)

        progress("clean", 0, 0)
        # 清不掉也不一定致命（可能本來就是空的），真的有問題寫入時會報錯
        _ps(f"Clear-Disk -Number {drive['number']} -RemoveData -RemoveOEM -Confirm:$false")

        write_image(
            src, rf"\\.\PhysicalDrive{drive['number']}",
            image["sha256"], image["size"], progress, verify,
        )

        progress("configure", 0, 0)
        apply_config(drive["number"], files)
        progress("done", 1, 1)
        job["state"] = "done"
    except FlashError as e:
        job.update(state="error", error=str(e))
    except Exception as e:  # 不要讓執行緒默默死掉
        job.update(state="error", error=tr("發生未預期的錯誤：{e}", e=e))
    finally:
        keep_awake(False)
        # 寫入已經開始卻沒完成，這張卡就是半成品，要讓介面明確提示
        if job.get("state") == "error" and job.get("phase") in ("write", "verify", "configure"):
            job["recover"] = True


def cache_dir():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    d = Path(base) / "piscout" / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def start_job(image_url, disk_number, disk_size, cfg, verify=True):
    validate_config(cfg)
    image = find_image(image_url)

    # 再確認一次這顆磁碟還在、容量跟使用者看到的一樣
    drive = next((d for d in list_drives() if d["number"] == disk_number), None)
    if drive is None or drive["size"] != disk_size:
        raise FlashError(tr("找不到那顆磁碟，或容量跟你選的不一樣，請重新整理後再選"))

    with _lock:
        if any(j["state"] == "running" for j in JOBS.values()):
            raise FlashError(tr("已經有一個燒錄工作在進行了"))
        job_id = uuid.uuid4().hex[:8]
        job = {
            "id": job_id, "state": "running", "phase": "prepare",
            "done": 0, "total": 0, "error": "", "lang": get_lang(),
        }
        JOBS[job_id] = job
    threading.Thread(
        target=_run, args=(job, image, drive, cfg, verify), daemon=True
    ).start()
    return job_id


def get_job(job_id):
    job = JOBS.get(job_id)
    if job is None:
        raise FlashError(tr("沒有這個工作"))
    return {**job, "label": tr(PHASE_LABEL.get(job["phase"], job["phase"]))}
