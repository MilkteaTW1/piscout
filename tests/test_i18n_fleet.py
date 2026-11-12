import ast
import pathlib


from piscout import fleet, i18n

PKG = pathlib.Path(__file__).resolve().parent.parent / "piscout"


def test_tr_switches_language_and_formats():
    i18n.set_lang("zh-TW")
    assert i18n.tr("請設定密碼") == "請設定密碼"
    i18n.set_lang("en-US,en;q=0.9")
    assert i18n.tr("請設定密碼") == "Please set a password"
    assert "3.0 GB" in i18n.tr(
        "這張卡只有 {have:.1f} GB，放不下 {need:.1f} GB 的映像。請改選比較小的版本（例如精簡版）",
        have=3.0, need=6.7)
    i18n.set_lang("ja")  # 沒有的語言一律用英文
    assert i18n.get_lang() == "en"
    i18n.set_lang("zh")


def test_every_tr_key_has_english():
    missing = []
    for f in PKG.glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "tr"
                    and n.args and isinstance(n.args[0], ast.Constant)):
                if n.args[0].value not in i18n.EN:
                    missing.append((f.name, n.args[0].value))
    assert not missing


def test_fleet_prefers_agent(monkeypatch):
    monkeypatch.setattr(fleet, "_agent_stats", lambda h: {"model": "Raspberry Pi 4 Model B", "hostname": "x"})
    r = fleet.stats_one("192.168.0.5", "aa:bb:cc:dd:ee:ff", "zh")
    assert r["ok"] and r["via"] == "agent" and r["model_id"] == "pi4"


def test_fleet_without_login_is_flagged(monkeypatch):
    def boom(h):
        raise OSError("no agent")
    monkeypatch.setattr(fleet, "_agent_stats", boom)
    monkeypatch.setattr(fleet.vault, "get", lambda k: None)
    r = fleet.stats_one("192.168.0.5", "aa:bb:cc:dd:ee:ff", "en")
    assert not r["ok"] and r["nologin"] and r["error"] == "No saved login"


def test_fleet_action_needs_saved_password(monkeypatch):
    monkeypatch.setattr(fleet.vault, "get", lambda k: {"username": "pi", "password": None})
    r = fleet.act_one("192.168.0.5", "aa:bb:cc:dd:ee:ff", "reboot", "en")
    assert not r["ok"]
