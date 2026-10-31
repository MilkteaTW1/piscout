"""擴充套件：一鍵在樹莓派上裝好常見的服務（NAS、Docker……）。

清單寫死在 CATALOG：畫面只能指定「哪一個」和「安裝 / 移除」，指令都在這裡，不接受任意指令。
全部只用 apt 的官方套件，不執行從網路下載來的腳本。每個項目的指令都可以重複執行（已經裝好再裝一次不會壞）。

要新增一個擴充套件，在 CATALOG 加一筆就好：
  id        英數字的代號
  title     名稱；desc 一句話說明；steps 安裝時會做的事（裝之前會給使用者看）
  ports     會開放的連接埠（給使用者看）；warn 要注意的風險（可省略）
  check     印出 0 代表已經裝好的 shell 指令
  install   安裝腳本；remove 移除腳本（不刪使用者的資料）
  after     裝好後怎麼用；可以寫 {ip}、{user}
  needs_password  安裝需要這個登入的密碼（例如 NAS 要建 Samba 帳號）
腳本以 root 在 bash 裡執行，可以用環境變數 PI_USER（登入的使用者）和 PI_PW（登入密碼）。
"""
import shlex
import threading
import time
import uuid

from . import remote, tools
from .i18n import tr

APT = "DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=180 -y"


def _pkg(name):
    """套件真的裝著才算（`dpkg -s` 對「已移除但設定檔還在」的套件也會成功，不能用）。"""
    return "dpkg-query -W -f='${Status}' %s 2>/dev/null | grep -q 'install ok installed'" % name

CATALOG = [
    {
        "id": "nas",
        "title": "NAS：網路檔案分享（Samba）",
        "desc": "把樹莓派變成區網裡的檔案伺服器，Windows、macOS、手機都能存取，適合接外接硬碟。",
        "steps": [
            "安裝 Samba（apt 官方套件）",
            "建立共用資料夾 /srv/nas，擁有者是你登入的帳號",
            "在 /etc/samba/smb.conf 加一段 [pi-nas]（改之前會先備份一份）",
            "用這台樹莓派的登入密碼建立你的 Samba 帳號，並啟動服務",
        ],
        "ports": "TCP 445、139，UDP 137、138（只在區網使用，不要對外網開放）",
        "warn": "要用密碼登入才能安裝。如果要用外接硬碟，請先把它掛載到 /srv/nas。",
        "needs_password": True,
        "check": "grep -qs '^# >>> piscout nas$' /etc/samba/smb.conf && echo 0 || echo 1",
        "install": f"""
{APT} install samba
mkdir -p /srv/nas
chown "$PI_USER":"$(id -gn "$PI_USER")" /srv/nas
conf=/etc/samba/smb.conf
[ -f "$conf.piscout-backup" ] || cp "$conf" "$conf.piscout-backup"
sed -i '/^# >>> piscout nas$/,/^# <<< piscout nas$/d' "$conf"
cat >> "$conf" <<EOF
# >>> piscout nas
[pi-nas]
   comment = piscout NAS
   path = /srv/nas
   browseable = yes
   read only = no
   guest ok = no
   valid users = $PI_USER
   create mask = 0664
   directory mask = 0775
# <<< piscout nas
EOF
if ! testparm -s "$conf" >/dev/null 2>&1; then
  cp "$conf.piscout-backup" "$conf"
  echo "smb.conf did not validate, restored the backup" >&2
  exit 1
fi
printf '%s\\n%s\\n' "$PI_PW" "$PI_PW" | smbpasswd -s -a "$PI_USER"
systemctl enable smbd nmbd
systemctl restart smbd nmbd
echo "NAS ready: //$(hostname -I | cut -d' ' -f1)/pi-nas"
""",
        "remove": f"""
conf=/etc/samba/smb.conf
[ -f "$conf" ] && sed -i '/^# >>> piscout nas$/,/^# <<< piscout nas$/d' "$conf"
smbpasswd -x "$PI_USER" 2>/dev/null || true
systemctl disable --now smbd nmbd 2>/dev/null || true
{APT} remove samba
echo "Removed. Files in /srv/nas were kept."
""",
        "after": "在 Windows 檔案總管的網址列輸入 \\\\{ip}\\pi-nas，帳號 {user}，密碼就是這台樹莓派的登入密碼。macOS 用 smb://{ip}/pi-nas。",
    },
    {
        "id": "docker",
        "title": "Docker：容器引擎",
        "desc": "用容器跑各種服務（Home Assistant、資料庫、網站……），不用一個個手動設定環境。",
        "steps": [
            "安裝 docker.io（apt 官方套件）並設為開機啟動",
            "把你登入的帳號加進 docker 群組（重新登入後才不用 sudo）",
        ],
        "ports": "不開放任何連接埠（之後跑的容器才會開）",
        "warn": "docker 群組的成員等同於可以取得這台樹莓派的 root 權限，只給你信任的帳號。",
        "needs_password": False,
        "check": "command -v docker >/dev/null 2>&1 && echo 0 || echo 1",
        "install": f"""
{APT} install docker.io
systemctl enable --now docker
usermod -aG docker "$PI_USER"
docker --version
""",
        "remove": f"""
systemctl disable --now docker docker.socket 2>/dev/null || true
{APT} remove docker.io
echo "Removed. Images and containers in /var/lib/docker were kept."
""",
        "after": "重新登入後，在終端機輸入 docker run hello-world 試試看。",
    },
    {
        "id": "fail2ban",
        "title": "fail2ban：擋住亂猜密碼的人",
        "desc": "有人在短時間內一直猜 SSH 密碼，就自動把他的 IP 擋掉一段時間。樹莓派要開放給外網時特別有用。",
        "steps": [
            "安裝 fail2ban（apt 官方套件）",
            "使用內建的預設設定（保護 SSH），並設為開機啟動",
        ],
        "ports": "不開放任何連接埠",
        "needs_password": False,
        "check": _pkg("fail2ban") + " && echo 0 || echo 1",
        "install": f"""
{APT} install fail2ban
systemctl enable --now fail2ban
# the service needs a few seconds before it answers, longer on a slow Pi
ready=0
for i in $(seq 1 30); do
  if fail2ban-client ping >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [ "$ready" != 1 ]; then echo "fail2ban did not start within 30 s" >&2; systemctl status fail2ban --no-pager -l >&2 || true; exit 1; fi
fail2ban-client status
""",
        "remove": f"""
systemctl disable --now fail2ban 2>/dev/null || true
{APT} remove fail2ban
""",
        "after": "用 sudo fail2ban-client status sshd 可以看目前擋了哪些 IP。",
    },
    {
        "id": "autoupdate",
        "title": "自動安全更新",
        "desc": "樹莓派會自己安裝安全性更新，不用記得手動 apt upgrade。",
        "steps": [
            "安裝 unattended-upgrades（apt 官方套件）",
            "寫入 /etc/apt/apt.conf.d/20auto-upgrades，每天檢查並安裝安全更新",
        ],
        "ports": "不開放任何連接埠",
        "warn": "更新偶爾需要重新開機才會完全生效；它不會自動重開機。",
        "needs_password": False,
        "check": _pkg("unattended-upgrades") + " && grep -qs 'Unattended-Upgrade.*1' /etc/apt/apt.conf.d/20auto-upgrades && echo 0 || echo 1",
        "install": f"""
{APT} install unattended-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
echo "Automatic security updates are on."
""",
        "remove": """
rm -f /etc/apt/apt.conf.d/20auto-upgrades
echo "Automatic updates turned off. The package stays installed."
""",
        "after": "更新紀錄在 /var/log/unattended-upgrades/。",
    },
]
BY_ID = {a["id"]: a for a in CATALOG}


def status(client, ip, user):
    """所有項目的狀態一次查完（一次往返），並檢查這台能不能用 apt。"""
    lines = ['echo "apt=$(command -v apt-get >/dev/null 2>&1 && echo 1 || echo 0)"']
    lines += ['echo "%s=$( { %s; } 2>/dev/null | head -1 )"' % (a["id"], a["check"]) for a in CATALOG]
    code, out, _ = remote._run_script(client, "\n".join(lines), timeout=30)
    raw = tools.parse(out)
    return {"apt": raw.get("apt") == "1", "items": [_describe(a, raw.get(a["id"]) == "0", ip, user) for a in CATALOG]}


def _describe(a, installed, ip, user):
    return {
        "id": a["id"], "title": tr(a["title"]), "desc": tr(a["desc"]),
        "steps": [tr(s) for s in a["steps"]], "ports": tr(a["ports"]),
        "warn": tr(a["warn"]) if a.get("warn") else "",
        "needs_password": a.get("needs_password", False),
        "after": tr(a["after"]).format(ip=ip, user=user), "installed": installed,
    }


# ---------------------------------------------------------------- 執行（背景工作，畫面輪詢進度）

JOBS = {}
_lock = threading.Lock()
KEEP_SECONDS = 1800


def _script(spec, op, user, password):
    head = f"set -e\nPI_USER={shlex.quote(user)}\nPI_PW={shlex.quote(password or '')}\nexport PI_USER PI_PW\n"
    return head + spec[op].strip() + "\n"


def run_script_as_root(client, script, sudo_password, on_text, timeout=900):
    """用 sudo 跑腳本。密碼和腳本都從 stdin 送，不會出現在樹莓派的程序列表（ps）裡。"""
    cmd = "sudo -S -p '' bash -s" if sudo_password else "sudo -n bash -s"
    chan = client.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(cmd)
    chan.sendall(((sudo_password + "\n") if sudo_password else "") + script)
    chan.shutdown_write()
    deadline = time.time() + timeout
    while True:
        if chan.recv_ready():
            on_text(chan.recv(4096).decode(errors="replace"))
        elif chan.exit_status_ready():
            while chan.recv_ready():
                on_text(chan.recv(4096).decode(errors="replace"))
            return chan.recv_exit_status()
        else:
            time.sleep(0.1)
        if time.time() > deadline:
            chan.close()
            raise remote.RemoteError(tr("等太久了，已經停止。樹莓派上的安裝可能還在背景繼續。"))


def _job_text(job, text):
    with _lock:
        job["text"] += text.replace("\r", "")


def _worker(job, host, login, spec, op):
    client = None
    try:
        client = remote.connect(host, login["username"], login.get("password"), login.get("key_path"),
                                port=login.get("port") or 22)
        script = _script(spec, op, login["username"], login.get("password"))
        code = run_script_as_root(client, script, login.get("password"), lambda t: _job_text(job, t))
        with _lock:
            if code == 0:
                job["state"] = "ok"
            else:
                job["state"] = "error"
                job["error"] = _explain(job["text"], code)
    except remote.RemoteError as e:
        with _lock:
            job["state"], job["error"] = "error", str(e)
    except Exception as e:  # 背景執行緒裡的錯誤不能讓它默默消失
        with _lock:
            job["state"], job["error"] = "error", str(e)
    finally:
        if client is not None:
            client.close()
        with _lock:
            job["finished"] = time.time()


def _explain(text, code):
    low = text.lower()
    if "a password is required" in low or "no tty present" in low or "incorrect password" in low:
        return tr("這個帳號用 sudo 需要密碼，請用密碼登入再試一次。")
    if "could not get lock" in low or "unable to acquire the dpkg" in low:
        return tr("樹莓派正在更新套件（apt 被占用），請等幾分鐘再試。")
    if "temporary failure resolving" in low or "could not resolve" in low or "failed to fetch" in low:
        return tr("樹莓派連不上網路，沒辦法下載套件。請確認它有連上網路。")
    return tr("安裝指令失敗（代碼 {code}），詳細內容看下面的紀錄。", code=code)


def start(host, login, addon_id, op):
    spec = BY_ID.get(addon_id)
    if spec is None or op not in ("install", "remove"):
        raise remote.RemoteError(tr("不支援的操作"))
    if spec.get("needs_password") and op == "install" and not login.get("password"):
        raise remote.RemoteError(tr("這個擴充套件要用密碼登入才能安裝。"))
    with _lock:
        now = time.time()
        for k in [k for k, j in JOBS.items() if j.get("finished") and now - j["finished"] > KEEP_SECONDS]:
            del JOBS[k]
        if any(j["host"] == host and j["state"] == "running" for j in JOBS.values()):
            raise remote.RemoteError(tr("這台樹莓派正在安裝或移除別的東西，請等它完成。"))
        job_id = uuid.uuid4().hex
        job = JOBS[job_id] = {"host": host, "addon": addon_id, "op": op, "state": "running",
                              "text": "", "error": "", "started": now}
    threading.Thread(target=_worker, args=(job, host, login, spec, op), daemon=True).start()
    return job_id


def poll(job_id, since=0):
    with _lock:
        job = JOBS.get(job_id)
        if job is None:
            raise remote.RemoteError(tr("找不到這個工作（可能已經過期）"))
        return {"state": job["state"], "error": job["error"], "addon": job["addon"], "op": job["op"],
                "text": job["text"][since:], "next": len(job["text"])}
