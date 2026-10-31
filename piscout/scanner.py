"""掃描區網，找出樹莓派。

做法很土：對整個 /24 的 22 埠送一輪 TCP 連線，這樣活著的主機都會進
ARP 表，再讀 ARP 表比對 MAC 前綴。mDNS 只是用來補主機名稱。
"""
import asyncio
import ipaddress
import os
import re
import socket
import subprocess
import time

# 樹莓派基金會 / 代工廠的 MAC 前綴
PI_OUIS = {
    "b8:27:eb",
    "dc:a6:32",
    "e4:5f:01",
    "d8:3a:dd",
    "28:cd:c1",
    "2c:cf:67",
}

ARP_LINE = re.compile(
    r"(\d{1,3}(?:\.\d{1,3}){3})\W+(?:at\s+)?"
    r"([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})"
)


# 這些前綴只用在新款（Pi 4 以後），64 位元系統都能跑，可以先猜 pi4。
# B8:27:EB 同時有 Pi 1 / Zero / 2 / 3，沒辦法靠 MAC 分，所以不猜。
MODERN_OUIS = {"dc:a6:32", "e4:5f:01", "d8:3a:dd", "2c:cf:67", "28:cd:c1"}


def local_network():
    """用本機 IP 猜出所在的 /24。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # UDP connect 不會真的送封包
        ip = s.getsockname()[0]
    except OSError:
        ip = "192.168.1.2"
    finally:
        s.close()
    return ipaddress.ip_network(f"{ip}/24", strict=False)


def normalize_mac(raw):
    # macOS 會把 0a 寫成 a，Windows 用 - 分隔，全部統一
    parts = re.split(r"[:-]", raw)
    return ":".join(p.zfill(2) for p in parts).lower()


def parse_arp(text):
    """把 `arp -a` 的輸出解析成 {ip: mac}。"""
    table = {}
    for line in text.splitlines():
        m = ARP_LINE.search(line)
        if not m:
            continue
        ip, mac = m.group(1), normalize_mac(m.group(2))
        if mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"):
            continue
        if mac.startswith("01:00:5e"):  # 多播
            continue
        table[ip] = mac
    return table


WINDOWS = os.name == "nt"

NEIGH_LINE = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})\s.*?lladdr\s+([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})"
)


def parse_ip_neigh(text):
    """把 Linux `ip neigh` 的輸出解析成 {ip: mac}（沒有 lladdr 的 FAILED / INCOMPLETE 會被略過）。"""
    table = {}
    for line in text.splitlines():
        m = NEIGH_LINE.search(line.strip())
        if not m:
            continue
        ip, mac = m.group(1), normalize_mac(m.group(2))
        if mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") or mac.startswith("01:00:5e"):
            continue
        table[ip] = mac
    return table


def _run(cmd):
    kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10, **kw).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def read_arp():
    table = parse_arp(_run(["arp", "-a"]))
    if not table and not WINDOWS:
        # 新的 Linux 發行版常常沒裝 net-tools，沒有 arp 指令，改讀 `ip neigh`
        table = parse_ip_neigh(_run(["ip", "neigh"]))
    return table


async def _probe(ip, port, timeout):
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout
        )
    except (OSError, asyncio.TimeoutError):
        return False
    writer.close()
    return True


async def _sweep(hosts, port=22, timeout=0.7, limit=128):
    sem = asyncio.Semaphore(limit)

    async def one(h):
        async with sem:
            return str(h), await _probe(str(h), port, timeout)

    return dict(await asyncio.gather(*(one(h) for h in hosts)))


def mdns_names(wait=2.0):
    """用 mDNS 撈 ip -> 主機名稱。沒裝 zeroconf 就當作沒有。"""
    found = {}
    try:
        from zeroconf import ServiceBrowser, Zeroconf
    except ImportError:
        return found

    class Listener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name, timeout=1000)
            if info and info.server:
                for addr in info.parsed_addresses():
                    found[addr] = info.server.rstrip(".")

        def update_service(self, *args):
            pass

        def remove_service(self, *args):
            pass

    try:
        zc = Zeroconf()
    except OSError:
        return found
    try:
        ServiceBrowser(
            zc, ["_ssh._tcp.local.", "_workstation._tcp.local."], Listener()
        )
        time.sleep(wait)
    finally:
        zc.close()
    return found


def scan(network=None):
    net = network or local_network()
    hosts = list(net.hosts())

    ssh_open = asyncio.run(_sweep(hosts))
    arp = read_arp()
    names = mdns_names()

    devices = []
    for ip, mac in arp.items():
        if ipaddress.ip_address(ip) not in net:
            continue
        hostname = names.get(ip, "")
        is_pi = mac[:8] in PI_OUIS or hostname.lower().startswith("raspberrypi")
        devices.append(
            {
                "ip": ip,
                "mac": mac,
                "hostname": hostname,
                "ssh_open": bool(ssh_open.get(ip)),
                "is_pi": is_pi,
                "hint_model": "pi4" if mac[:8] in MODERN_OUIS else None,
            }
        )

    devices.sort(key=lambda d: (not d["is_pi"], ipaddress.ip_address(d["ip"])))
    return {"network": str(net), "devices": devices}
