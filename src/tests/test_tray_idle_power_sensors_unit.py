from __future__ import annotations

from types import SimpleNamespace


from src.tray.pollers import idle_power_sensors as sensors


def _write_text(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_read_dimmed_state_sets_baseline_first_observation(tmp_path):
    backlight = tmp_path / "sys" / "class" / "backlight" / "intel_backlight"
    _write_text(backlight / "brightness", "100\n")
    _write_text(backlight / "max_brightness", "200\n")

    tray = SimpleNamespace()
    dimmed = sensors.read_dimmed_state(tray, backlight_base=tmp_path / "sys" / "class" / "backlight")

    assert dimmed is False
    assert getattr(tray, "_dim_screen_off") is False
    baselines = getattr(tray, "_dim_backlight_baselines")
    assert baselines[str(backlight)] == 100


def test_read_dimmed_state_detects_significant_drop(tmp_path):
    base = tmp_path / "sys" / "class" / "backlight"
    dev = base / "intel_backlight"
    _write_text(dev / "max_brightness", "200\n")

    tray = SimpleNamespace()
    _write_text(dev / "brightness", "100\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False

    _write_text(dev / "brightness", "80\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is True


def test_read_dimmed_state_tracks_manual_changes_when_not_dimmed(tmp_path):
    base = tmp_path / "sys" / "class" / "backlight"
    dev = base / "intel_backlight"
    _write_text(dev / "max_brightness", "200\n")

    tray = SimpleNamespace()
    _write_text(dev / "brightness", "100\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False

    _write_text(dev / "brightness", "110\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False

    baselines = getattr(tray, "_dim_backlight_baselines")
    assert baselines[str(dev)] == 110


def test_read_dimmed_state_detects_gradual_drop_without_chasing_baseline(tmp_path):
    base = tmp_path / "sys" / "class" / "backlight"
    dev = base / "intel_backlight"
    _write_text(dev / "max_brightness", "200\n")

    tray = SimpleNamespace()
    _write_text(dev / "brightness", "100\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False

    # Simulate desktop dimming gradually (e.g., animations / stepwise fades).
    _write_text(dev / "brightness", "95\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False

    # Once the cumulative drop crosses the 10% threshold, it should be detected.
    _write_text(dev / "brightness", "90\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is True


def test_read_dimmed_state_uses_hysteresis_to_avoid_flapping(tmp_path):
    base = tmp_path / "sys" / "class" / "backlight"
    dev = base / "intel_backlight"
    _write_text(dev / "max_brightness", "200\n")

    tray = SimpleNamespace()

    _write_text(dev / "brightness", "100\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False

    # Enter dim state at/below the 90% threshold.
    _write_text(dev / "brightness", "90\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is True

    # Small bounce above 90% should remain dimmed (hysteresis).
    _write_text(dev / "brightness", "92\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is True

    # Clear undim: above exit threshold.
    _write_text(dev / "brightness", "99\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False


def test_read_dimmed_state_sets_screen_off_flag_when_any_device_zero(tmp_path):
    base = tmp_path / "sys" / "class" / "backlight"
    dev = base / "intel_backlight"
    _write_text(dev / "max_brightness", "200\n")

    tray = SimpleNamespace()
    _write_text(dev / "brightness", "100\n")
    assert sensors.read_dimmed_state(tray, backlight_base=base) is False

    _write_text(dev / "brightness", "0\n")
    dimmed = sensors.read_dimmed_state(tray, backlight_base=base)

    assert dimmed is True
    assert getattr(tray, "_dim_screen_off") is True


def test_read_screen_off_state_drm_returns_none_when_no_candidates(tmp_path):
    drm = tmp_path / "sys" / "class" / "drm"
    drm.mkdir(parents=True, exist_ok=True)
    assert sensors.read_screen_off_state_drm(drm_base=drm) is None


def test_read_screen_off_state_drm_prefers_edp_and_detects_off_via_dpms(tmp_path):
    drm = tmp_path / "sys" / "class" / "drm"

    edp = drm / "card0-eDP-1"
    _write_text(edp / "status", "connected\n")
    _write_text(edp / "enabled", "enabled\n")
    _write_text(edp / "dpms", "Off\n")

    hdmi = drm / "card0-HDMI-A-1"
    _write_text(hdmi / "status", "connected\n")
    _write_text(hdmi / "enabled", "enabled\n")
    _write_text(hdmi / "dpms", "On\n")

    assert sensors.read_screen_off_state_drm(drm_base=drm) is True


def test_read_screen_off_state_drm_external_ignored_when_not_enabled(tmp_path):
    drm = tmp_path / "sys" / "class" / "drm"

    hdmi = drm / "card0-HDMI-A-1"
    _write_text(hdmi / "status", "connected\n")
    _write_text(hdmi / "enabled", "disabled\n")
    _write_text(hdmi / "dpms", "off\n")

    assert sensors.read_screen_off_state_drm(drm_base=drm) is False


def test_run_returns_none_on_nonzero_returncode(monkeypatch):
    class CP:
        def __init__(self, returncode: int, stdout: str = ""):
            self.returncode = returncode
            self.stdout = stdout

    def fake_run(*args, **kwargs):
        return CP(1, "")

    monkeypatch.setattr(sensors.subprocess, "run", fake_run)
    assert sensors.run(["echo", "hi"]) is None


def test_get_session_id_prefers_env(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_ID", "  42  ")
    assert sensors.get_session_id() == "42"


def test_get_session_id_falls_back_to_loginctl_show_user(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_ID", raising=False)
    monkeypatch.setattr(sensors.os, "getuid", lambda: 999)

    def fake_run(argv, *, timeout_s=1.0):
        if argv[:3] == ["loginctl", "show-user", "999"]:
            return "7"
        return None

    monkeypatch.setattr(sensors, "run", fake_run)
    assert sensors.get_session_id() == "7"


def test_get_session_id_falls_back_to_first_listed_session(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_ID", raising=False)
    monkeypatch.setattr(sensors.os, "getuid", lambda: 999)

    def fake_run(argv, *, timeout_s=1.0):
        if argv[:3] == ["loginctl", "show-user", "999"]:
            return None
        if argv[:2] == ["loginctl", "list-sessions"]:
            return "3 cyrilp seat0\n4 other seat0"
        return None

    monkeypatch.setattr(sensors, "run", fake_run)
    assert sensors.get_session_id() == "3"
