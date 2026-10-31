"""擴充套件的自動檢查（給貢獻者在本機跑，CI 也會跑同一份）。

  python tools/check_addons.py            靜態檢查 piscout/addons.py 裡每一個擴充套件
  python tools/check_addons.py --run      （只能在 Linux、有免密碼 sudo 的測試機上）真的安裝、再裝一次、移除，驗證

靜態檢查會擋：缺欄位、重複 id、從網路抓東西來執行、加第三方 apt 來源、危險指令、bash 語法錯誤、
沒有英文翻譯、翻譯的 {變數} 對不上。只有 apt 官方套件可以用。
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from piscout import addons  # noqa: E402

REQUIRED = ("id", "title", "desc", "steps", "ports", "check", "install", "remove", "after")
TEXT_KEYS = ("title", "desc", "ports", "warn", "after")
FIELD = re.compile(r"\{(\w*)\}")

# (pattern, 為什麼不行)
FORBIDDEN = [
    (r"\bcurl\b|\bwget\b|\bfetch\b", "不能從網路下載東西（只能用 apt 官方套件）"),
    (r"https?://|ftp://", "腳本裡不能出現網址"),
    (r"\|\s*(sudo\s+)?(ba|da|z)?sh\b", "不能把東西 pipe 給 shell 執行"),
    (r"\beval\b|\bsource\s+<\(|/dev/tcp|/dev/udp|\bnc\b|\bncat\b|\bsocat\b", "不能用 eval、開網路連線"),
    (r"base64\s+(-d|--decode)|\bxxd\s+-r", "不能執行編碼過的內容"),
    (r"add-apt-repository|apt-key|sources\.list|/etc/apt/(sources|trusted|keyrings)|signed-by", "不能加第三方 apt 來源或金鑰"),
    (r"\b(pip|pip3|npm|npx|gem|cargo|go)\s+(install|get)\b|\bgit\s+clone\b|\bsnap\s+install\b|\bdpkg\s+-i\b", "只能用 apt 的官方套件"),
    (r"\brm\s+-[a-zA-Z]*r", "不能遞迴刪除（用 rm -f 刪明確的檔案）"),
    (r"\bmkfs|\bdd\s+if=|\bfdisk\b|\bparted\b|>\s*/dev/(sd|mmcblk|nvme)", "不能動磁碟"),
    (r"chmod\s+(-R\s+)?(0?777|a\+w|o\+w)|chpasswd|passwd\s|useradd|adduser|\bvisudo\b|/etc/sudoers|authorized_keys|/etc/shadow", "不能改密碼、使用者、sudo、SSH 金鑰"),
    (r"\breboot\b|\bshutdown\b|\bhalt\b|poweroff|init\s+[06]", "不能重開機或關機"),
    (r"\bapt(-get)?\s+(dist-)?upgrade|full-upgrade", "不能做全系統升級"),
]
def _find_bash():
    """找得到能用的 bash 才做語法檢查（Windows 上的 WSL 轉接器不算）。"""
    path = shutil.which("bash")
    if not path:
        return None
    try:
        ok = subprocess.run([path, "-c", "true"], capture_output=True, timeout=20).returncode == 0
    except Exception:
        ok = False
    return path if ok else None


BASH = _find_bash()


def check_entry(a, en_backend):
    errs = []
    name = a.get("id", "?")

    def err(msg):
        errs.append(f"[{name}] {msg}")

    for k in REQUIRED:
        if not a.get(k):
            err(f"缺少欄位 {k}")
    if errs:
        return errs
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", a["id"]):
        err("id 只能是小寫英數字和底線，2–31 字，英文字母開頭")
    if not isinstance(a["steps"], list) or not all(isinstance(s, str) and s for s in a["steps"]):
        err("steps 必須是一串非空的字串")
    if not a.get("needs_password", False) in (True, False):
        err("needs_password 必須是 true / false")

    for key in ("install", "remove", "check"):
        body = a[key]
        for pat, why in FORBIDDEN:
            if re.search(pat, body):
                err(f"{key}：{why}（符合 {pat!r}）")
    if not re.search(r"apt-get", a["install"]):
        err("install 要用 apt-get 安裝套件")
    for op in ("install", "remove"):
        script = addons._script(a, op, "pi", "pw")
        r = subprocess.run([BASH, "-n"], input=script, text=True, capture_output=True) if BASH else None
        if r is not None and r.returncode != 0:
            err(f"{op} 的 bash 語法錯誤：{r.stderr.strip()}")
    if "$PI_PW" in a["install"] + a["remove"] and not a.get("needs_password"):
        err("用到 $PI_PW 就要設 needs_password: True")
    try:
        a["after"].format(ip="1.2.3.4", user="pi")
    except Exception as e:
        err(f"after 的 {{ip}} / {{user}} 格式錯誤：{e}")

    for key in TEXT_KEYS:
        if a.get(key):
            err_msgs = _translated(a[key], en_backend)
            errs += [f"[{name}] {key}：{m}" for m in err_msgs]
    for i, s in enumerate(a["steps"]):
        errs += [f"[{name}] steps[{i}]：{m}" for m in _translated(s, en_backend)]
    return errs


def _translated(zh, en_backend):
    en = en_backend.get(zh)
    if not en:
        return ["en.json 的 backend 沒有這句的英文翻譯（把中文原句當 key 加進去）"]
    if sorted(FIELD.findall(zh)) != sorted(FIELD.findall(en)):
        return ["英文翻譯的 {變數} 和中文不一樣"]
    return []


def check_all():
    en = json.loads((ROOT / "piscout" / "static" / "locales" / "en.json").read_text(encoding="utf-8"))["backend"]
    errs, seen = [], set()
    for a in addons.CATALOG:
        if a.get("id") in seen:
            errs.append(f"[{a.get('id')}] id 重複")
        seen.add(a.get("id"))
        errs += check_entry(a, en)
    return errs


def run_live():
    """在 Linux 測試機上真的跑：安裝、再裝一次（要能重複執行）、移除。已經裝著的跳過，不動它。"""
    user = os.environ.get("USER") or subprocess.check_output(["id", "-un"], text=True).strip()
    bad = []

    def sh(script):
        return subprocess.run(["sudo", "-n", "bash", "-s"], input=script, text=True).returncode

    def installed(a):
        r = subprocess.run(["bash", "-c", a["check"]], capture_output=True, text=True)
        return r.stdout.strip().splitlines()[-1:] == ["0"] if r.stdout.strip() else False

    for a in addons.CATALOG:
        print(f"::group::{a['id']}")
        if installed(a):
            print("已經裝著，跳過")
            print("::endgroup::")
            continue
        steps = [("install", 0, True), ("install again", 0, True), ("remove", 0, False)]
        for label, _, want in steps:
            op = "install" if label.startswith("install") else "remove"
            code = sh(addons._script(a, op, user, "ci-test-pw"))
            if code != 0:
                bad.append(f"[{a['id']}] {label} 失敗（結束碼 {code}）")
                break
            if installed(a) != want:
                bad.append(f"[{a['id']}] {label} 之後 check 的結果不對（應該是{'已安裝' if want else '未安裝'}）")
                break
        print("::endgroup::")
    return bad


if __name__ == "__main__":
    problems = check_all()
    if "--run" in sys.argv and not problems:
        problems = run_live()
    for p in problems:
        print("✗", p)
    print("OK" if not problems else f"{len(problems)} 個問題")
    sys.exit(1 if problems else 0)
