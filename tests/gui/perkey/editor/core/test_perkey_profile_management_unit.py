from __future__ import annotations

from types import SimpleNamespace

import src.gui.perkey.profile_management as profile_management
from src.core.resources.layouts import slot_id_for_key_id


def test_sanitize_keymap_cells_drops_out_of_range_entries() -> None:
    keymap = {
        "keep": (0, 0),
        "coerce": ("1", "2"),
        "multi": [(2, 3), (2, 4), (9, 9)],
        "drop_row": (6, 0),
        "drop_col": (0, 20),
    }

    result = profile_management.sanitize_keymap_cells(keymap, num_rows=6, num_cols=20)

    assert result == {
        "keep": ((0, 0),),
        "coerce": ((1, 2),),
        "multi": ((2, 3), (2, 4)),
    }


def test_sanitize_color_map_cells_drops_out_of_range_entries() -> None:
    color_map = {
        (0, 0): (1, 2, 3),
        ("1", "2"): ("4", "5", "6"),
        (6, 0): (7, 8, 9),
        (0, 20): (10, 11, 12),
    }

    result = profile_management.sanitize_color_map_cells(color_map, num_rows=6, num_cols=20)

    assert result == {
        (0, 0): (1, 2, 3),
        (1, 2): (4, 5, 6),
    }


def test_load_profile_colors_prefers_saved_profile_colors_and_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        profile_management.profiles,
        "load_per_key_colors",
        lambda _name: {(0, 0): (1, 2, 3), (0, 20): (9, 9, 9)},
    )

    cfg = SimpleNamespace(per_key_colors={(1, 1): (4, 5, 6)})

    result = profile_management.load_profile_colors(
        name="p1",
        config=cfg,
        current_colors={(2, 2): (7, 8, 9)},
        num_rows=6,
        num_cols=20,
    )

    assert result == {(0, 0): (1, 2, 3)}


def test_load_profile_colors_falls_back_to_config_then_current(monkeypatch) -> None:
    monkeypatch.setattr(profile_management.profiles, "load_per_key_colors", lambda _name: {})

    cfg = SimpleNamespace(per_key_colors={(1, 1): (4, 5, 6), (1, 20): (7, 8, 9)})

    from_config = profile_management.load_profile_colors(
        name="p1",
        config=cfg,
        current_colors={(2, 2): (7, 8, 9)},
        num_rows=6,
        num_cols=20,
    )
    assert from_config == {(1, 1): (4, 5, 6)}

    cfg.per_key_colors = {}
    from_current = profile_management.load_profile_colors(
        name="p1",
        config=cfg,
        current_colors={(2, 2): (7, 8, 9), (2, 20): (1, 1, 1)},
        num_rows=6,
        num_cols=20,
    )
    assert from_current == {(2, 2): (7, 8, 9)}


def test_activate_profile_sanitizes_loaded_state_and_applies_colors(monkeypatch) -> None:
    monkeypatch.setattr(profile_management.profiles, "set_active_profile", lambda name: f"safe-{name}")
    monkeypatch.setattr(
        profile_management.profiles,
        "load_keymap",
        lambda _name, **_kwargs: {"keep": (0, 0), "drop": (0, 20), "enter": [(1, 2), (1, 3)]},
    )
    monkeypatch.setattr(profile_management.profiles, "load_layout_global", lambda _name, **_kwargs: {"dx": 1.0})
    monkeypatch.setattr(
        profile_management.profiles, "load_layout_per_key", lambda _name, **_kwargs: {"keep": {"dx": 0.1}}
    )
    monkeypatch.setattr(
        profile_management.profiles,
        "load_layout_slots",
        lambda _name, **_kwargs: {"nonusbackslash": {"visible": False}},
    )
    monkeypatch.setattr(
        profile_management.profiles, "load_lightbar_overlay", lambda _name: {"visible": True, "length": 0.7}
    )
    monkeypatch.setattr(
        profile_management.profiles,
        "load_per_key_colors",
        lambda _name: {(1, 1): (10, 20, 30), (1, 20): (99, 99, 99)},
    )

    applied = {}

    def fake_apply_profile_to_config(config, colors) -> None:
        applied["config"] = config
        applied["colors"] = dict(colors)

    monkeypatch.setattr(profile_management.profiles, "apply_profile_to_config", fake_apply_profile_to_config)

    cfg = SimpleNamespace(per_key_colors={(2, 2): (1, 1, 1)})

    result = profile_management.activate_profile(
        "p1",
        config=cfg,
        current_colors={(3, 3): (2, 2, 2)},
        num_rows=6,
        num_cols=20,
        physical_layout="iso",
    )

    assert result.name == "safe-p1"
    assert result.keymap == {"keep": ((0, 0),), "enter": ((1, 2), (1, 3))}
    assert result.layout_tweaks == {"dx": 1.0}
    assert result.per_key_layout_tweaks == {"keep": {"dx": 0.1}}
    assert result.colors == {(1, 1): (10, 20, 30)}
    assert result.layout_slot_overrides == {str(slot_id_for_key_id("iso", "nonusbackslash")): {"visible": False}}
    assert result.lightbar_overlay == {"visible": True, "length": 0.7}
    assert applied == {
        "config": cfg,
        "colors": {(1, 1): (10, 20, 30)},
    }


def test_save_profile_persists_lightbar_overlay(monkeypatch) -> None:
    calls: dict[str, object] = {}

    monkeypatch.setattr(profile_management.profiles, "set_active_profile", lambda name: f"safe-{name}")
    monkeypatch.setattr(
        profile_management.profiles,
        "save_keymap",
        lambda *args, **kwargs: calls.setdefault("keymap", (args, kwargs)),
    )
    monkeypatch.setattr(
        profile_management.profiles, "save_layout_global", lambda *args: calls.setdefault("layout_global", args)
    )
    monkeypatch.setattr(
        profile_management.profiles, "save_layout_per_key", lambda *args: calls.setdefault("layout_per_key", args)
    )
    monkeypatch.setattr(
        profile_management.profiles, "save_lightbar_overlay", lambda *args: calls.setdefault("lightbar_overlay", args)
    )
    monkeypatch.setattr(
        profile_management.profiles,
        "save_layout_slots",
        lambda *args, **kwargs: calls.setdefault("layout_slots", (args, kwargs)),
    )
    monkeypatch.setattr(
        profile_management.profiles, "save_per_key_colors", lambda *args: calls.setdefault("colors", args)
    )
    monkeypatch.setattr(
        profile_management.profiles, "apply_profile_to_config", lambda *args: calls.setdefault("apply", args)
    )

    cfg = SimpleNamespace()
    name = profile_management.save_profile(
        "p1",
        config=cfg,
        keymap={"k": ((0, 0),)},
        layout_tweaks={"dx": 1.0},
        per_key_layout_tweaks={"k": {"dx": 0.1}},
        lightbar_overlay={"visible": True, "length": 0.9},
        physical_layout="ansi",
        layout_slot_overrides={"k": {"visible": False}},
        colors={(0, 0): (1, 2, 3)},
    )

    assert name == "safe-p1"
    assert calls["lightbar_overlay"] == ({"visible": True, "length": 0.9}, "safe-p1")


def test_primary_helpers_pick_first_or_colored_cell() -> None:
    colors = {(0, 1): (1, 2, 3)}
    keymap = {"enter": ((0, 0), (0, 1))}

    assert profile_management.keymap_cells_for(keymap, "enter") == ((0, 0), (0, 1))
    assert profile_management.primary_cell_for_key(keymap, "enter") == (0, 0)
    assert profile_management.representative_cell(keymap["enter"], colors=colors) == (0, 1)
