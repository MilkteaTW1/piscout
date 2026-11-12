"""不拔卡：從電腦經 SSH 把系統直接寫進樹莓派自己的 SD 卡。

做法：
  1. 電腦端下載官方映像，解壓縮時把開機設定（user-data / custom.toml…）
     直接寫進映像裡的 boot 分割區，這樣 Pi 端不用掛載任何東西
  2. 在 Pi 上把 dash / dd / sha256sum 連同函式庫複製到記憶體（/dev/shm），
     之後的動作都只用記憶體裡的程式，不再碰會被覆蓋的 SD 卡
  3. 把映像串流進 ssh，由記憶體裡的 dd 寫到 Pi 的開機磁碟
  4. 讀回前段資料算 SHA-256，一致才用 sysrq 重新開機

這是在「執行中的系統」上覆寫它自己的磁碟，天生有風險：寫到一半斷線或斷電，
那張卡就開不了機，只能拿下來重燒。
"""
import hashlib
import lzma
import re
import shutil
import struct
import tempfile
import threading
import time
import uuid
from pathlib import Path

from . import flasher, remote
from .flasher import CHUNK, FlashError
from .i18n import get_lang, set_lang, tr

STAGE_DIR = "/dev/shm/piscout-flash"
DISK_RE = re.compile(r"^/dev/(mmcblk\d+|sd[a-z]+|nvme\d+n\d+)$")
MIN_FREE_MB = 150

# ---------------------------------------------------------------- 映像處理

def _chunks(src):
    return flasher._decompressed(src)


def _partition1(first_sector):
    """從 MBR 讀出第一個分割區的 (起始位元組, 長度位元組)。"""
    if len(first_sector) < 512 or first_sector[510:512] != b"\x55\xaa":
        raise FlashError(tr("這個映像不是 MBR 格式，沒辦法預先寫入開機設定"))
    ptype = first_sector[0x1BE + 4]
    if ptype not in (0x0B, 0x0C):
        raise FlashError(tr("第一個分割區不是 FAT32，沒辦法預先寫入開機設定"))
    start, count = struct.unpack_from("<II", first_sector, 0x1BE + 8)
    return start * 512, count * 512


def patch_boot_files(head_path, offset, files):
    from pyfatfs.PyFatFS import PyFatFS

    fs = PyFatFS(str(head_path), offset=offset)
    try:
        for name, content in files.items():
            fs.writetext(name, content)
    finally:
        fs.close()


def prepare_image(src, size, sha256, files, workdir, progress):
    """跑一遍映像：校驗來源、把設定寫進 boot 分割區。

    回傳 dict：head（已寫入設定的前段檔案）、head_len、prefix_len、prefix_sha。
    prefix 是之後要在 Pi 上讀回比對的範圍（4 MiB 的整數倍）。
    """
    raw = hashlib.sha256()
    pre = hashlib.sha256()
    prefix_len = (size // CHUNK) * CHUNK
    head_path = Path(workdir) / "head.img"

    total = 0
    head_len = None
    head_f = None
    head_written = 0
    pre_done = 0

    def feed_prefix(b):
        nonlocal pre_done
        room = prefix_len - pre_done
        if room > 0:
            part = b[:room]
            pre.update(part)
            pre_done += len(part)

    try:
        for data in _chunks(src):
            raw.update(data)
            total += len(data)
            progress("image", total, size)

            if head_len is None:
                off, length = _partition1(data[:512])
                head_len = off + length
                head_f = open(head_path, "wb")

            if head_f is not None:
                take = data[: head_len - head_written]
                head_f.write(take)
                head_written += len(take)
                data = data[len(take):]
                if head_written >= head_len:
                    head_f.close()
                    head_f = None
                    with open(head_path, "rb") as f:
                        offset, _ = _partition1(f.read(512))
                    patch_boot_files(head_path, offset, files)
                    with open(head_path, "rb") as f:
                        while True:
                            b = f.read(CHUNK)
                            if not b:
                                break
                            feed_prefix(b)
            if head_f is None and data:
                feed_prefix(data)
    except lzma.LZMAError as e:
        raise FlashError(tr("映像檔損毀：{e}", e=e))
    finally:
        if head_f is not None:
            head_f.close()

    if head_len is None or head_written < head_len:
        raise FlashError(tr("映像檔比預期的短"))
    if total != size or raw.hexdigest() != sha256:
        raise FlashError(tr("映像檔校驗碼不符（下載可能不完整），已放棄"))
    if pre_done != prefix_len:
        raise FlashError(tr("映像大小異常"))
    return {
        "head": head_path, "head_len": head_len,
        "prefix_len": prefix_len, "prefix_sha": pre.hexdigest(),
    }


def stream_image(src, prepared):
    """依序吐出要寫進磁碟的位元組：先是寫入過設定的前段，再接原本的後段。"""
    head_len = prepared["head_len"]
    with open(prepared["head"], "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            yield b
    skipped = 0
    for data in _chunks(src):
        if skipped < head_len:
            cut = min(len(data), head_len - skipped)
            skipped += cut
            data = data[cut:]
        if data:
            yield data


# ---------------------------------------------------------------- Pi 端腳本

PREFLIGHT = r"""
ROOT=$(findmnt -no SOURCE / 2>/dev/null)
PK=$(lsblk -no PKNAME "$ROOT" 2>/dev/null | head -n1)
echo "DISK=/dev/$PK"
echo "SIZE=$(lsblk -bdno SIZE /dev/$PK 2>/dev/null | head -n1)"
echo "MEM=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)"
echo "ARCH=$(uname -m)"
echo "MODEL=$(tr -d '\\0' < /proc/device-tree/model 2>/dev/null)"
if sudo -n true 2>/dev/null; then echo "SUDO=nopass"; else echo "SUDO=pass"; fi
for t in dash dd sha256sum ldd; do command -v $t >/dev/null 2>&1 || echo "MISSING=$t"; done
"""

STAGE = f"""
set -e
D={STAGE_DIR}
rm -rf $D
mkdir -p $D/lib
for b in dash dd sha256sum; do
  p=$(command -v $b)
  cp "$p" $D/$b
  for l in $(ldd "$p" | grep -o '/[^ ]*'); do cp -L "$l" $D/lib/; done
done
LDSO=$(ls $D/lib/ld-linux* | head -n1)
echo "LDSO=$LDSO"
$LDSO --library-path $D/lib $D/dd --version | head -n1
$LDSO --library-path $D/lib $D/dash -c 'echo STAGE_OK'
"""

RUN_SH = """D={stage}
L="{ldso} --library-path $D/lib"
DISK=$1
BLOCKS=$2
EXP=$3
echo 1 > /proc/sys/kernel/sysrq
echo READY
echo u > /proc/sysrq-trigger
$L $D/dd of=$DISK bs=4M iflag=fullblock oflag=direct conv=fsync 2> $D/dd.log
RC=$?
echo "DD $RC"
while read -r line; do echo "LOG $line"; done < $D/dd.log
if [ "$RC" != 0 ]; then
  echo FAIL
  exit 1
fi
GOT=$($L $D/dd if=$DISK iflag=direct bs=4M count=$BLOCKS 2>/dev/null | $L $D/sha256sum)
GOT=${{GOT%% *}}
echo "SUM $GOT"
if [ "$GOT" = "$EXP" ]; then
  echo OK
  echo s > /proc/sysrq-trigger
  echo b > /proc/sysrq-trigger
  exit 0
fi
echo MISMATCH
exit 1
"""


def _kv(text):
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def check_pi(client, sudo_password, image):
    """寫入前的檢查，回傳 (disk, sudo_mode)。任何一項不通過就丟 FlashError。"""
    _, out, err = remote._run_script(client, PREFLIGHT)
    info = _kv(out)
    missing = [l.split("=")[1] for l in out.splitlines() if l.startswith("MISSING=")]
    if missing:
        raise FlashError(tr("Pi 上缺少必要工具：{tools}", tools=", ".join(missing)))
    image_size = image["size"]
    model = flasher.model_id(info.get("MODEL", ""))
    if model:
        tag = flasher.MODELS[model][1]
        if image.get("devices") and tag not in image["devices"]:
            raise FlashError(tr(
                "這台是 {model}，但「{image}」不支援這個型號，寫進去會開不了機。請回上一步改選建議的系統",
                model=flasher.MODELS[model][0], image=image["name"],
            ))
    disk = info.get("DISK", "")
    if not DISK_RE.match(disk):
        raise FlashError(tr("認不出開機磁碟（{disk}），為了安全不動手",
                            disk=disk or tr("空白")))
    try:
        disk_size = int(info.get("SIZE", "0"))
    except ValueError:
        disk_size = 0
    if disk_size and disk_size < image_size:
        raise FlashError(tr(
            "這張卡只有 {have:.1f} GB，放不下 {need:.1f} GB 的映像。請改選比較小的版本（例如精簡版）",
            have=disk_size / 1e9, need=image_size / 1e9,
        ))
    if int(info.get("MEM", "0") or 0) < MIN_FREE_MB:
        raise FlashError(tr("Pi 的可用記憶體太少，不適合在線上覆寫"))

    mode = info.get("SUDO", "pass")
    if mode == "pass":
        if sudo_password is None:
            raise FlashError(tr("這台需要 sudo 密碼，請填寫登入密碼"))
        code, _, _ = remote.run(client, "true", sudo_password=sudo_password)
        if code != 0:
            raise FlashError(tr("sudo 驗證失敗，密碼不對或這個帳號沒有 sudo 權限"))
    return disk, mode


def stage_tools(client):
    _, out, err = remote._run_script(client, STAGE, timeout=60)
    if "STAGE_OK" not in out:
        raise FlashError(tr(
            "無法在記憶體裡準備寫入工具（/dev/shm 可能不允許執行）：{why}",
            why=err.strip() or out.strip(),
        ))
    ldso = _kv(out).get("LDSO")
    if not ldso or not ldso.startswith(STAGE_DIR + "/lib/"):
        raise FlashError(tr("找不到動態載入器"))
    return ldso


def _drain(chan, buf):
    while chan.recv_ready():
        buf += chan.recv(65536)
    while chan.recv_stderr_ready():
        chan.recv_stderr(65536)


def flash_remote(client, sudo_password, sudo_mode, disk, ldso, src, prepared,
                 size, progress):
    transport = client.get_transport()
    chan = transport.open_session(window_size=4 * 1024 * 1024)
    chan.settimeout(120)

    blocks = prepared["prefix_len"] // CHUNK
    script = RUN_SH.format(stage=STAGE_DIR, ldso=ldso)
    # 腳本放進記憶體，之後只用記憶體裡的 dash 來跑它
    sftp = client.open_sftp()
    try:
        with sftp.open(f"{STAGE_DIR}/run.sh", "w") as f:
            f.write(script)
    finally:
        sftp.close()

    sudo = "sudo -n" if sudo_mode == "nopass" else "sudo -S -p ''"
    cmd = (
        f"{sudo} {ldso} --library-path {STAGE_DIR}/lib {STAGE_DIR}/dash "
        f"{STAGE_DIR}/run.sh {disk} {blocks} {prepared['prefix_sha']}"
    )
    chan.exec_command(cmd)
    if sudo_mode != "nopass":
        chan.sendall((sudo_password + "\n").encode())

    # 等腳本說它準備好了才開始送資料，不然資料會被 sudo 當成密碼讀走
    buf = bytearray()
    deadline = time.time() + 30
    while b"READY" not in buf:
        if time.time() > deadline or (chan.exit_status_ready() and not chan.recv_ready()):
            raise FlashError(tr("Pi 上的寫入腳本沒有啟動：{out}",
                                out=buf.decode(errors="replace").strip()))
        _drain(chan, buf)
        time.sleep(0.1)

    sent = 0
    progress("stream", 0, size)
    try:
        for data in stream_image(src, prepared):
            chan.sendall(data)
            sent += len(data)
            _drain(chan, buf)
            progress("stream", sent, size)
        chan.shutdown_write()
    except OSError as e:
        raise FlashError(tr("傳輸中斷：{e}。Pi 上的卡可能只寫了一半，需要拔下來用電腦重燒", e=e))

    progress("verify", 0, 0)
    chan.settimeout(600)
    try:
        while True:
            data = chan.recv(65536)
            if not data:
                break
            buf += data
    except OSError:
        pass  # 重新開機時連線會被切斷，這是預期的

    return buf.decode(errors="replace")


def _interpret(output):
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    if "MISMATCH" in lines:
        raise FlashError(tr(
            "寫入後讀回的校驗碼不一致，我沒有重新開機。Pi 目前的系統可能已損壞，請再試一次，或把卡拿下來用電腦重燒"
        ))
    dd = next((l for l in lines if l.startswith("DD ")), "")
    if dd and dd != "DD 0":
        logs = [l[4:] for l in lines if l.startswith("LOG ")]
        raise FlashError(tr("dd 寫入失敗：{log}", log=" ".join(logs[-3:])))
    if "OK" not in lines:
        raise FlashError(tr("沒有收到 Pi 的完成回報。如果它之後有重新開機，通常代表成功，請掃描確認"))


# ---------------------------------------------------------------- 工作排程

def _run(job, host, login, image, cfg):
    set_lang(job.get("lang", "zh"))
    def progress(phase, done, total):
        job.update(phase=phase, done=done, total=total)

    workdir = tempfile.mkdtemp(prefix="piscout-")
    client = None
    flasher.keep_awake(True)
    try:
        files = flasher.make_config(image["init_format"], cfg)

        src = flasher.cache_dir() / image["url"].rsplit("/", 1)[-1]
        flasher._download(image["url"], src, progress)

        prepared = prepare_image(
            src, image["size"], image["sha256"], files, workdir, progress
        )

        progress("connect", 0, 0)
        client = remote.connect_saved(host, login)
        client.get_transport().set_keepalive(15)  # 長時間傳輸不要被中間設備斷線
        disk, mode = check_pi(client, login.get("password"), image)
        ldso = stage_tools(client)

        output = flash_remote(
            client, login.get("password"), mode, disk, ldso, src, prepared,
            image["size"], progress,
        )
        _interpret(output)
        progress("reboot", 1, 1)
        job.update(state="done", phase="reboot")
    except FlashError as e:
        job.update(state="error", error=str(e))
    except remote.RemoteError as e:
        job.update(state="error", error=str(e))
    except Exception as e:
        job.update(state="error", error=tr("發生未預期的錯誤：{e}", e=e))
    finally:
        flasher.keep_awake(False)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        shutil.rmtree(workdir, ignore_errors=True)
        # 已經開始寫入 Pi 的卡卻沒成功，這張卡就是半成品
        if job.get("state") == "error" and job.get("phase") in ("stream", "verify"):
            job["recover"] = True


def start_job(host, login, image_url, cfg):
    flasher.validate_config(cfg)
    image = flasher.find_image(image_url)
    with flasher._lock:
        if any(j["state"] == "running" for j in flasher.JOBS.values()):
            raise FlashError(tr("已經有一個燒錄工作在進行了"))
        job_id = uuid.uuid4().hex[:8]
        job = {"id": job_id, "state": "running", "phase": "download",
               "done": 0, "total": 0, "error": "", "lang": get_lang()}
        flasher.JOBS[job_id] = job
    threading.Thread(
        target=_run, args=(job, host, login, image, cfg), daemon=True
    ).start()
    return job_id
