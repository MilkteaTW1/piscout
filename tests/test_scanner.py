from piscout.scanner import PI_OUIS, normalize_mac, parse_arp

WINDOWS = """
Interface: 192.168.1.20 --- 0x7
  Internet Address      Physical Address      Type
  192.168.1.1           a4-2b-b0-11-22-33     dynamic
  192.168.1.37          dc-a6-32-0a-bc-de     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
"""

LINUX = """
? (192.168.1.1) at a4:2b:b0:11:22:33 [ether] on eth0
raspberrypi.lan (192.168.1.37) at dc:a6:32:0a:bc:de [ether] on eth0
? (192.168.1.50) at <incomplete> on eth0
"""

MACOS = "? (192.168.1.37) at dc:a6:32:a:bc:de on en0 ifscope [ethernet]"


def test_parse_windows():
    t = parse_arp(WINDOWS)
    assert t == {
        "192.168.1.1": "a4:2b:b0:11:22:33",
        "192.168.1.37": "dc:a6:32:0a:bc:de",
    }


def test_parse_linux_skips_incomplete():
    t = parse_arp(LINUX)
    assert set(t) == {"192.168.1.1", "192.168.1.37"}


def test_parse_macos_short_octet():
    assert parse_arp(MACOS)["192.168.1.37"] == "dc:a6:32:0a:bc:de"


def test_pi_detected_by_oui():
    mac = parse_arp(LINUX)["192.168.1.37"]
    assert mac[:8] in PI_OUIS
    assert normalize_mac("B8-27-EB-1-2-3") == "b8:27:eb:01:02:03"


IP_NEIGH = """
192.168.1.1 dev eth0 lladdr a4:2b:b0:11:22:33 REACHABLE
192.168.1.37 dev eth0 lladdr dc:a6:32:0a:bc:de STALE
192.168.1.50 dev eth0  FAILED
192.168.1.51 dev eth0 INCOMPLETE
224.0.0.251 dev eth0 lladdr 01:00:5e:00:00:fb PERMANENT
fe80::1 dev eth0 lladdr a4:2b:b0:11:22:33 router STALE
"""


def test_parse_ip_neigh_skips_failed_multicast_and_ipv6():
    from piscout.scanner import parse_ip_neigh
    assert parse_ip_neigh(IP_NEIGH) == {
        "192.168.1.1": "a4:2b:b0:11:22:33",
        "192.168.1.37": "dc:a6:32:0a:bc:de",
    }


def test_read_arp_falls_back_to_ip_neigh_when_arp_is_missing(monkeypatch):
    from piscout import scanner
    monkeypatch.setattr(scanner, "WINDOWS", False)
    monkeypatch.setattr(scanner, "_run", lambda cmd: "" if cmd[0] == "arp" else IP_NEIGH)
    assert scanner.read_arp()["192.168.1.37"] == "dc:a6:32:0a:bc:de"


def test_read_arp_does_not_call_ip_neigh_when_arp_works(monkeypatch):
    from piscout import scanner
    monkeypatch.setattr(scanner, "WINDOWS", False)
    calls = []
    monkeypatch.setattr(scanner, "_run", lambda cmd: calls.append(cmd[0]) or LINUX)
    scanner.read_arp()
    assert calls == ["arp"]


def test_scan_cli_prints_only_pis_and_json(monkeypatch, capsys):
    from piscout import __main__ as cli, scanner
    devices = [
        {"ip": "192.168.1.37", "mac": "dc:a6:32:0a:bc:de", "hostname": "raspberrypi", "ssh_open": True,
         "is_pi": True, "hint_model": "pi4"},
        {"ip": "192.168.1.1", "mac": "a4:2b:b0:11:22:33", "hostname": "", "ssh_open": False,
         "is_pi": False, "hint_model": None},
    ]
    monkeypatch.setattr(scanner, "scan", lambda network=None: {"network": "192.168.1.0/24", "devices": devices})
    assert cli.scan_cli([]) == 0
    out = capsys.readouterr().out
    assert "192.168.1.37" in out and "192.168.1.1 " not in out and "2 devices, 1 Raspberry Pi" in out
    cli.scan_cli(["--all", "--json"])
    import json
    assert len(json.loads(capsys.readouterr().out)["devices"]) == 2
