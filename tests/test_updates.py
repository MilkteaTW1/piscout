import pytest

from piscout import updates


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv("PISCOUT_NO_UPDATE_CHECK", raising=False)
    updates._cache.clear()
    monkeypatch.setattr(updates, "__version__", "0.1.7")


def test_parse_versions():
    assert updates.parse("v0.1.8") == (0, 1, 8)
    assert updates.parse("1.10.0") == (1, 10, 0)
    assert updates.parse("nightly") is None and updates.parse(None) is None


def test_newer_release_is_reported():
    out = updates.check(lambda: {"tag_name": "v0.1.8"})
    assert out["newer"] and out["latest"] == "0.1.8" and out["current"] == "0.1.7"
    assert out["url"].startswith("https://github.com/MilkteaTW1/piscout")


def test_same_or_older_release_is_not_an_update():
    assert not updates.check(lambda: {"tag_name": "v0.1.7"})["newer"]
    updates._cache.clear()
    assert not updates.check(lambda: {"tag_name": "v0.1.2"})["newer"]


def test_two_digit_parts_compare_as_numbers():
    updates._cache.clear()
    assert updates.check(lambda: {"tag_name": "v0.1.10"})["newer"]


def test_network_failure_or_garbage_is_silent():
    def boom():
        raise OSError("offline")
    out = updates.check(boom)
    assert out["latest"] is None and out["newer"] is False
    updates._cache.clear()
    assert updates.check(lambda: {"tag_name": "weird"})["newer"] is False


def test_result_is_cached_until_ttl():
    calls = []
    clock = [1000.0]

    def fetch():
        calls.append(1)
        return {"tag_name": "v0.2.0"}

    updates.check(fetch, now=lambda: clock[0])
    updates.check(fetch, now=lambda: clock[0] + 60)
    assert len(calls) == 1
    updates.check(fetch, now=lambda: clock[0] + updates.TTL + 1)
    assert len(calls) == 2


def test_opt_out_never_touches_the_network(monkeypatch):
    monkeypatch.setenv("PISCOUT_NO_UPDATE_CHECK", "1")

    def fetch():
        raise AssertionError("must not be called")
    assert updates.check(fetch)["newer"] is False


def test_install_verifies_checksum_before_launching(monkeypatch):
    import hashlib
    import io
    launched = []
    good = hashlib.sha256(b"installer").hexdigest()

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda *a, **k: R((good + "  piscout-setup.exe").encode()))
    updates.install("0.1.9", launch=lambda cmd, **k: launched.append(cmd), download=lambda url, dest: good)
    assert launched and launched[0][0].endswith("piscout-setup.exe") and "/update=1" in launched[0]

    launched.clear()
    with pytest.raises(RuntimeError):
        updates.install("0.1.9", launch=lambda cmd, **k: launched.append(cmd), download=lambda url, dest: "0" * 64)
    assert not launched


def test_install_refuses_odd_versions_and_source_runs():
    with pytest.raises(RuntimeError):
        updates.install("../evil", launch=lambda *a, **k: None, download=lambda *a: "")
    with pytest.raises(RuntimeError):
        updates.install("0.1.9", launch=lambda *a, **k: None)     # not a frozen exe


def test_pre_channel_picks_highest_including_prerelease(monkeypatch):
    rels = [
        {"tag_name": "v0.1.12", "prerelease": False},
        {"tag_name": "v0.1.13", "prerelease": True},
        {"tag_name": "v0.1.9", "prerelease": False},
        {"tag_name": "v9.9.9", "draft": True},
    ]
    monkeypatch.setattr(updates, "_get", lambda url: rels if "per_page" in url else {"tag_name": "v0.1.12"})
    stable = updates.check(channel="stable")
    pre = updates.check(channel="pre")
    assert stable["latest"] == "0.1.12" and pre["latest"] == "0.1.13"
    assert pre["newer"] and pre["channel"] == "pre"


def test_channels_are_cached_separately_and_force_refetches():
    calls = []

    def fetch():
        calls.append(1)
        return {"tag_name": "v0.2.0"}

    updates.check(fetch, channel="stable")
    updates.check(fetch, channel="pre")
    assert len(calls) == 2
    updates.check(fetch, channel="pre")
    assert len(calls) == 2
    updates.check(fetch, channel="pre", force=True)
    assert len(calls) == 3
