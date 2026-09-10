from __future__ import annotations

"""Isolated config dir for window-state tests."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_config_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    for var in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
        monkeypatch.delenv(var, raising=False)
    yield tmp_path
