from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests._validation_env import (
    access_tripwire_enabled,
    hardware_opted_in,
    led_snapshot_tripwire_enabled,
    usb_import_tripwire_enabled,
)


def test_default_suite_isolates_keyrgb_and_xdg_roots() -> None:
    if hardware_opted_in():
        pytest.skip("hardware opted in; default isolation is not required")

    config_dir = Path(os.environ["KEYRGB_CONFIG_DIR"])
    assert "keyrgb-test-config-" in config_dir.name

    for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
        assert key in os.environ
        value = Path(os.environ[key])
        assert value.is_dir()
        if "keyrgb-test-xdg-" in str(value):
            assert Path.home() not in value.parents


def test_access_tripwire_is_on_by_default_when_hardware_is_not_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)
    monkeypatch.delenv("KEYRGB_TEST_HARDWARE_TRIPWIRE", raising=False)
    monkeypatch.delenv("KEYRGB_TEST_BLOCK_USB_IMPORTS", raising=False)
    monkeypatch.delenv("KEYRGB_TEST_HARDWARE_LED_SNAPSHOT", raising=False)

    assert access_tripwire_enabled() is True
    assert usb_import_tripwire_enabled() is False
    assert led_snapshot_tripwire_enabled() is False


def test_legacy_tripwire_flag_still_enables_import_and_led_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.delenv("KEYRGB_HW_TESTS", raising=False)
    monkeypatch.setenv("KEYRGB_TEST_HARDWARE_TRIPWIRE", "1")

    assert access_tripwire_enabled() is True
    assert usb_import_tripwire_enabled() is True
    assert led_snapshot_tripwire_enabled() is True
