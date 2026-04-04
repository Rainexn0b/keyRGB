from __future__ import annotations

import subprocess

import pytest

from src.core.backends.asusctl.backend import AsusctlAuraBackend, _env_flag, _parse_asusctl_zones
from src.core.backends.asusctl.device import (
    AsusctlAuraKeyboardDevice,
    _asusctl_level_to_brightness,
    _brightness_to_asusctl_level,
    _rgb_to_hex,
)
from src.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS


def test_rgb_and_brightness_helpers_normalize_values() -> None:
    assert _rgb_to_hex((0x12, 0x34, 0x56)) == "123456"
    assert _rgb_to_hex((-1, 999, 16)) == "00ff10"

    assert _brightness_to_asusctl_level(-1) == "off"
    assert _brightness_to_asusctl_level(0) == "off"
    assert _brightness_to_asusctl_level(1) == "low"
    assert _brightness_to_asusctl_level(16) == "low"
    assert _brightness_to_asusctl_level(17) == "med"
    assert _brightness_to_asusctl_level(33) == "med"
    assert _brightness_to_asusctl_level(34) == "high"
    assert _brightness_to_asusctl_level(50) == "high"

    assert _asusctl_level_to_brightness("off") == 0
    assert _asusctl_level_to_brightness("1") == 16
    assert _asusctl_level_to_brightness("medium") == 33
    assert _asusctl_level_to_brightness("HIGH") == 50
    assert _asusctl_level_to_brightness("unknown") == 0


def test_run_ok_raises_with_command_context() -> None:
    device = AsusctlAuraKeyboardDevice()
    device._run = lambda args, timeout_s=2.0: subprocess.CompletedProcess(
        ["asusctl", *args],
        2,
        stdout="stdout text",
        stderr="stderr text",
    )

    with pytest.raises(RuntimeError, match=r"asusctl command failed \(2\): leds set high: stderr text"):
        device._run_ok(["leds", "set", "high"])


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [
        (0, "Current keyboard led brightness: Med\n", 33),
        (0, "brightness: high\n", 50),
        (1, "brightness: low\n", 0),
        (0, "no brightness line here\n", 0),
    ],
)
def test_get_brightness_parses_or_falls_back(returncode: int, stdout: str, expected: int) -> None:
    device = AsusctlAuraKeyboardDevice()
    device._run = lambda args, timeout_s=2.0: subprocess.CompletedProcess(
        ["asusctl", *args],
        returncode,
        stdout=stdout,
        stderr="",
    )

    assert device.get_brightness() == expected


def test_turn_off_and_is_off_delegate_via_brightness(monkeypatch: pytest.MonkeyPatch) -> None:
    device = AsusctlAuraKeyboardDevice()
    brightness_calls: list[int] = []

    monkeypatch.setattr(device, "set_brightness", lambda brightness: brightness_calls.append(int(brightness)))
    monkeypatch.setattr(device, "get_brightness", lambda: 0)

    device.turn_off()

    assert brightness_calls == [0]
    assert device.is_off() is True


def test_set_color_without_zones_sets_brightness_then_uniform_color(monkeypatch: pytest.MonkeyPatch) -> None:
    device = AsusctlAuraKeyboardDevice()
    brightness_calls: list[int] = []
    run_ok_calls: list[list[str]] = []

    monkeypatch.setattr(device, "set_brightness", lambda brightness: brightness_calls.append(int(brightness)))
    monkeypatch.setattr(device, "_run_ok", lambda args, timeout_s=2.0: run_ok_calls.append(list(args)))

    device.set_color((0x12, 0x34, 0x56), brightness=25)

    assert brightness_calls == [25]
    assert run_ok_calls == [["aura", "effect", "static", "-c", "123456"]]


def test_set_color_with_zones_updates_each_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    device = AsusctlAuraKeyboardDevice(zones=["left", "right"])
    brightness_calls: list[int] = []
    run_ok_calls: list[list[str]] = []

    monkeypatch.setattr(device, "set_brightness", lambda brightness: brightness_calls.append(int(brightness)))
    monkeypatch.setattr(device, "_run_ok", lambda args, timeout_s=2.0: run_ok_calls.append(list(args)))

    device.set_color((255, 1, 16), brightness=40)

    assert brightness_calls == [40]
    assert run_ok_calls == [
        ["aura", "effect", "static", "-c", "ff0110", "--zone", "left"],
        ["aura", "effect", "static", "-c", "ff0110", "--zone", "right"],
    ]


def test_set_key_colors_single_zone_averages_to_uniform_color(monkeypatch: pytest.MonkeyPatch) -> None:
    device = AsusctlAuraKeyboardDevice(zones=["single"])
    color_calls: list[tuple[tuple[int, int, int], int]] = []

    monkeypatch.setattr(
        device, "set_color", lambda color, *, brightness: color_calls.append((tuple(color), int(brightness)))
    )

    device.set_key_colors(
        {
            "esc": (30, 0, 0),
            "f1": (0, 60, 0),
            "f2": (0, 0, 90),
        },
        brightness=35,
    )

    assert color_calls == [((10, 20, 30), 35)]


def test_set_key_colors_multi_zone_buckets_and_skips_unknown_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    device = AsusctlAuraKeyboardDevice(zones=["left", "right"])
    device._key_to_zone_idx = {
        "esc": 0,
        "f1": 1,
        "f2": 1,
    }
    brightness_calls: list[int] = []
    run_ok_calls: list[list[str]] = []

    monkeypatch.setattr(device, "set_brightness", lambda brightness: brightness_calls.append(int(brightness)))
    monkeypatch.setattr(device, "_run_ok", lambda args, timeout_s=2.0: run_ok_calls.append(list(args)))

    device.set_key_colors(
        {
            "esc": (10, 20, 30),
            "f1": (0, 100, 0),
            "f2": (0, 0, 50),
            "unknown": (255, 255, 255),
        },
        brightness=45,
    )

    assert brightness_calls == [45]
    assert run_ok_calls == [
        ["aura", "effect", "static", "-c", "0a141e", "--zone", "left"],
        ["aura", "effect", "static", "-c", "003219", "--zone", "right"],
    ]


def test_set_key_colors_ignores_empty_map(monkeypatch: pytest.MonkeyPatch) -> None:
    device = AsusctlAuraKeyboardDevice(zones=["left", "right"])
    brightness_calls: list[int] = []

    monkeypatch.setattr(device, "set_brightness", lambda brightness: brightness_calls.append(int(brightness)))

    device.set_key_colors({}, brightness=25)

    assert brightness_calls == []


def test_set_effect_is_noop() -> None:
    device = AsusctlAuraKeyboardDevice()

    assert device.set_effect({"name": "static"}) is None


def test_backend_env_helpers_and_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ASUSCTL_ENABLED", "yes")
    monkeypatch.setenv("KEYRGB_ASUSCTL_ZONES", " left, right ,, center ")
    backend = AsusctlAuraBackend()

    assert _env_flag("KEYRGB_ASUSCTL_ENABLED") is True
    assert _parse_asusctl_zones(" left, right ,, center ") == ["left", "right", "center"]
    assert backend.capabilities().per_key is True
    assert backend.capabilities().color is True


def test_backend_probe_collects_identifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.setenv("KEYRGB_ASUSCTL_PATH", "/usr/bin/asusctl")
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)

    def fake_run(args: list[str], *, timeout_s: float = 2.0):
        if args == ["info"]:
            return subprocess.CompletedProcess(
                ["asusctl", *args],
                0,
                stdout="Board Name: ROG\nProduct Family: Zephyrus\n",
                stderr="",
            )
        if args == ["aura", "--help"]:
            return subprocess.CompletedProcess(["asusctl", *args], 0, stdout="help", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(backend, "_run", fake_run)

    probe = backend.probe()

    assert probe.available is True
    assert probe.confidence == 92
    assert probe.identifiers == {
        "asusctl": "/usr/bin/asusctl",
        "board_name": "ROG",
        "product_family": "Zephyrus",
        "aura": "true",
    }


def test_backend_probe_reports_disabled_or_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.setenv("KEYRGB_ASUSCTL_DISABLE", "1")
    disabled = backend.probe()
    assert disabled.available is False
    assert "disabled" in disabled.reason

    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE")
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: None)
    missing = backend.probe()
    assert missing.available is False
    assert missing.reason == "asusctl not found"


def test_backend_is_available_delegates_to_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()
    calls = {"count": 0}

    def fake_probe():
        calls["count"] += 1
        return type("Probe", (), {"available": True})()

    monkeypatch.setattr(backend, "probe", fake_probe)

    assert backend.is_available() is True
    assert calls["count"] == 1


def test_backend_probe_reports_info_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE", raising=False)
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)
    monkeypatch.setattr(
        backend, "_run", lambda args, timeout_s=2.0: (_ for _ in ()).throw(subprocess.TimeoutExpired(args, 2.0))
    )

    probe = backend.probe()

    assert probe.available is False
    assert probe.confidence == 0
    assert probe.reason == "asusctl info failed: Command '['info']' timed out after 2.0 seconds"


def test_backend_probe_propagates_unexpected_info_bug(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE", raising=False)
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)
    monkeypatch.setattr(backend, "_run", lambda args, timeout_s=2.0: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        backend.probe()


def test_backend_probe_reports_nonzero_info_return(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE", raising=False)
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)
    monkeypatch.setattr(
        backend,
        "_run",
        lambda args, timeout_s=2.0: subprocess.CompletedProcess(
            ["asusctl", *args],
            3,
            stdout="fallback stdout",
            stderr="permission denied",
        ),
    )

    probe = backend.probe()

    assert probe.available is False
    assert probe.reason == "asusctl info returned 3: permission denied"


def test_backend_probe_reports_empty_info_output(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE", raising=False)
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)
    monkeypatch.setattr(
        backend,
        "_run",
        lambda args, timeout_s=2.0: subprocess.CompletedProcess(["asusctl", *args], 0, stdout="   ", stderr=""),
    )

    probe = backend.probe()

    assert probe.available is False
    assert probe.reason == "asusctl info produced no output"


def test_backend_run_wraps_subprocess_with_resolved_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()
    calls: list[tuple[list[str], bool, bool, float, bool]] = []

    monkeypatch.setenv("KEYRGB_ASUSCTL_PATH", "/custom/asusctl")

    def fake_run(cmd, *, text: bool, capture_output: bool, timeout: float, check: bool):
        calls.append((list(cmd), bool(text), bool(capture_output), float(timeout), bool(check)))
        return subprocess.CompletedProcess(list(cmd), 0, stdout="ok", stderr="")

    monkeypatch.setattr("src.core.backends.asusctl.backend.subprocess.run", fake_run)

    proc = backend._run(["info"], timeout_s=1.5)

    assert proc.returncode == 0
    assert calls == [(["/custom/asusctl", "info"], True, True, 1.5, False)]


def test_backend_probe_ignores_duplicate_and_non_key_value_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.setenv("KEYRGB_ASUSCTL_PATH", "/usr/bin/asusctl")
    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE", raising=False)
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)

    def fake_run(args: list[str], *, timeout_s: float = 2.0):
        if args == ["info"]:
            return subprocess.CompletedProcess(
                ["asusctl", *args],
                0,
                stdout="Board Name: ROG\nnot-a-pair\nBoard Name: Ignore Me\nAura Ready: yes\n",
                stderr="",
            )
        if args == ["aura", "--help"]:
            return subprocess.CompletedProcess(["asusctl", *args], 1, stdout="", stderr="unsupported")
        raise AssertionError(args)

    monkeypatch.setattr(backend, "_run", fake_run)

    probe = backend.probe()

    assert probe.available is True
    assert probe.identifiers == {
        "asusctl": "/usr/bin/asusctl",
        "board_name": "ROG",
        "aura_ready": "yes",
    }


def test_backend_probe_swallows_aura_help_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.setenv("KEYRGB_ASUSCTL_PATH", "/usr/bin/asusctl")
    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE", raising=False)
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)

    def fake_run(args: list[str], *, timeout_s: float = 2.0):
        if args == ["info"]:
            return subprocess.CompletedProcess(["asusctl", *args], 0, stdout="Board Name: ROG\n", stderr="")
        if args == ["aura", "--help"]:
            raise subprocess.TimeoutExpired(args, 2.0)
        raise AssertionError(args)

    monkeypatch.setattr(backend, "_run", fake_run)

    probe = backend.probe()

    assert probe.available is True
    assert probe.identifiers == {
        "asusctl": "/usr/bin/asusctl",
        "board_name": "ROG",
    }


def test_backend_probe_propagates_unexpected_aura_help_bug(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AsusctlAuraBackend()

    monkeypatch.setenv("KEYRGB_ASUSCTL_PATH", "/usr/bin/asusctl")
    monkeypatch.delenv("KEYRGB_ASUSCTL_DISABLE", raising=False)
    monkeypatch.setattr("src.core.backends.asusctl.backend.shutil.which", lambda exe: exe)

    def fake_run(args: list[str], *, timeout_s: float = 2.0):
        if args == ["info"]:
            return subprocess.CompletedProcess(["asusctl", *args], 0, stdout="Board Name: ROG\n", stderr="")
        if args == ["aura", "--help"]:
            raise RuntimeError("buggy helper")
        raise AssertionError(args)

    monkeypatch.setattr(backend, "_run", fake_run)

    with pytest.raises(RuntimeError, match="buggy helper"):
        backend.probe()


def test_backend_accessors_return_expected_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_ASUSCTL_PATH", "/custom/asusctl")
    monkeypatch.setenv("KEYRGB_ASUSCTL_ZONES", " left, right ")
    backend = AsusctlAuraBackend()

    device = backend.get_device()

    assert isinstance(device, AsusctlAuraKeyboardDevice)
    assert device.asusctl_path == "/custom/asusctl"
    assert device.zones == ["left", "right"]
    assert backend.dimensions() == (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)
    assert backend.effects() == {}
    assert backend.colors() == {}
