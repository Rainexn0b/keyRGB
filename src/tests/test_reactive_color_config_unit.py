from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def test_config_has_reactive_color_defaults(monkeypatch) -> None:
    from src.core.config import Config

    # Ensure we don't touch user config location.
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", os.path.join(REPO_ROOT, "buildlog", "test-config-reactive"))

    cfg = Config()

    assert isinstance(cfg.reactive_color, tuple)
    assert len(cfg.reactive_color) == 3
    assert all(isinstance(x, int) for x in cfg.reactive_color)

    assert cfg.reactive_use_manual_color is False


def test_config_persists_reactive_color(monkeypatch) -> None:
    from src.core.config import Config

    tmp_dir = os.path.join(REPO_ROOT, "buildlog", "test-config-reactive-persist")
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", tmp_dir)

    cfg = Config()
    cfg.reactive_color = (12, 34, 56)
    cfg.reactive_use_manual_color = True

    cfg2 = Config()
    assert cfg2.reactive_color == (12, 34, 56)
    assert cfg2.reactive_use_manual_color is True
