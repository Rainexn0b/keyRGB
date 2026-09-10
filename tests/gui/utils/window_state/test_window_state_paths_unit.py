from __future__ import annotations

"""Window-state paths, ID validation, and roundtrips."""

import json
from pathlib import Path

import pytest

from keyrgb.gui.utils import window_state
from keyrgb.gui.utils.window_state import (
    WindowGeometry,
    load_window_geometry,
    save_window_geometry,
    ui_state_lock_path,
    ui_state_path,
)


# --- paths -----------------------------------------------------------------
def test_state_and_lock_paths_are_distinct_and_config_scoped(tmp_path) -> None:
    assert ui_state_path() == tmp_path / "ui-state.json"
    assert ui_state_lock_path() == tmp_path / "ui-state.lock"
    assert ui_state_path() != ui_state_lock_path()
    assert ui_state_path().name != "config.json"


def test_module_is_tk_free() -> None:
    source = Path(window_state.__file__).read_text(encoding="utf-8")
    assert "import tkinter" not in source
    assert "from tkinter" not in source


# --- window id validation (UX-09 parity, public functions only) -------------
def test_valid_ux09_ids_roundtrip() -> None:
    from keyrgb.gui.single_instance import gui_instance_lock_path

    static_ids = ["settings", "reactive-color", "power-mode", "support", "perkey", "calibrator"]
    for window_id in static_ids:
        gui_instance_lock_path(window_id)  # public UX-09 validation; must not raise
        assert save_window_geometry(window_id, WindowGeometry(width=800, height=600, x=10, y=10)) is True
        assert load_window_geometry(window_id) == WindowGeometry(width=800, height=600, x=10, y=10)


def test_uniform_ids_roundtrip() -> None:
    from keyrgb.gui.single_instance import gui_instance_lock_path
    from keyrgb.gui.windows.uniform import uniform_instance_identity

    identities = {
        uniform_instance_identity(target_context="keyboard"),
        "uniform-lightbar",
        "uniform-ite8258-chassis-logo",
    }
    for window_id in identities:
        gui_instance_lock_path(window_id)  # public UX-09 validation; must not raise
        assert save_window_geometry(window_id, WindowGeometry(width=640, height=480)) is not None
        assert load_window_geometry(window_id) == WindowGeometry(width=640, height=480)


@pytest.mark.parametrize("window_id", ["", "unknown", "../settings", "settings ", "uniform-", "uniform-x_y", None, 123])
def test_invalid_window_ids_fail_safely(window_id) -> None:
    assert load_window_geometry(window_id) is None  # type: ignore[arg-type]
    assert save_window_geometry(window_id, WindowGeometry(width=100, height=100)) is False  # type: ignore[arg-type]


# --- roundtrip / sibling preservation ---------------------------------------
def test_roundtrip_with_position() -> None:
    assert save_window_geometry("settings", WindowGeometry(width=880, height=840, x=100, y=80)) is True
    assert load_window_geometry("settings") == WindowGeometry(width=880, height=840, x=100, y=80)


def test_roundtrip_size_only() -> None:
    assert save_window_geometry("support", WindowGeometry(width=700, height=500)) is True
    assert load_window_geometry("support") == WindowGeometry(width=700, height=500)


def test_sibling_and_unknown_state_preserved(tmp_path) -> None:
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600, x=5, y=5)) is True
    state_path = ui_state_path()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["custom-unsupported-key"] = {"note": "keep me"}
    data["windows"]["perkey"] = {"width": 1, "height": 1, "foreign": True}
    state_path.write_text(json.dumps(data), encoding="utf-8")

    assert save_window_geometry("support", WindowGeometry(width=700, height=500, x=1, y=2)) is True
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["custom-unsupported-key"] == {"note": "keep me"}
    assert data["windows"]["settings"] == {"width": 800, "height": 600, "x": 5, "y": 5}
    assert data["windows"]["support"] == {"width": 700, "height": 500, "x": 1, "y": 2}
