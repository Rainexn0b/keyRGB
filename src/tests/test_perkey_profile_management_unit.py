from __future__ import annotations

from types import SimpleNamespace

import src.gui.perkey.profile_management as profile_management


def test_sanitize_keymap_cells_drops_out_of_range_entries() -> None:
    keymap = {
        "keep": (0, 0),
        "coerce": ("1", "2"),
        "drop_row": (6, 0),
        "drop_col": (0, 20),
    }

    result = profile_management.sanitize_keymap_cells(keymap, num_rows=6, num_cols=20)

    assert result == {
        "keep": (0, 0),
        "coerce": (1, 2),
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
        lambda _name: {"keep": (0, 0), "drop": (0, 20)},
    )
    monkeypatch.setattr(profile_management.profiles, "load_layout_global", lambda _name: {"dx": 1.0})
    monkeypatch.setattr(profile_management.profiles, "load_layout_per_key", lambda _name: {"keep": {"dx": 0.1}})
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
    )

    assert result.name == "safe-p1"
    assert result.keymap == {"keep": (0, 0)}
    assert result.layout_tweaks == {"dx": 1.0}
    assert result.per_key_layout_tweaks == {"keep": {"dx": 0.1}}
    assert result.colors == {(1, 1): (10, 20, 30)}
    assert applied == {
        "config": cfg,
        "colors": {(1, 1): (10, 20, 30)},
    }