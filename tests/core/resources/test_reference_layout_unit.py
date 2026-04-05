from __future__ import annotations

import src.core.resources.layout as layout_mod

from src.core.resources.layout import (
    ISO_ONLY_KEY_IDS,
    build_layout,
    get_layout_keys,
    key_id_for_slot_id,
    KeyDef,
    resolve_physical_layout,
    slot_id_for_key_id,
)
import src.core.resources.layout_slots as layout_slots_mod
from src.core.resources.layout_slots import apply_layout_slot_overrides, clear_layout_slot_cache, get_layout_slot_states
from src.core.resources.layout_specs import load_layout_spec


def test_reference_layout_includes_iso_extra_key() -> None:
    key_ids = {key.key_id for key in build_layout()}

    assert "nonusbackslash" in key_ids
    assert "lshift" in key_ids
    assert "enter" in key_ids


def test_iso_layout_includes_nonusbackslash() -> None:
    keys = build_layout(include_iso=True)
    key_ids = {k.key_id for k in keys}
    assert "nonusbackslash" in key_ids
    assert "nonushash" in key_ids


def test_ansi_layout_excludes_nonusbackslash() -> None:
    keys = build_layout(include_iso=False)
    key_ids = {k.key_id for k in keys}
    assert "nonusbackslash" not in key_ids
    assert "nonushash" not in key_ids
    assert "lshift" in key_ids


def test_ansi_left_shift_is_wider_than_iso() -> None:
    iso_keys = {k.key_id: k for k in build_layout(include_iso=True)}
    ansi_keys = {k.key_id: k for k in build_layout(include_iso=False)}

    iso_shift_w = iso_keys["lshift"].rect[2]
    ansi_shift_w = ansi_keys["lshift"].rect[2]
    assert ansi_shift_w > iso_shift_w, "ANSI left shift should be wider than ISO"


def test_ansi_z_position_matches_iso() -> None:
    """The Z key should start at the same x position in both layouts."""
    iso_keys = {k.key_id: k for k in build_layout(include_iso=True)}
    ansi_keys = {k.key_id: k for k in build_layout(include_iso=False)}

    iso_z_x = iso_keys["z"].rect[0]
    ansi_z_x = ansi_keys["z"].rect[0]
    assert iso_z_x == ansi_z_x, f"Z key x should match: ISO={iso_z_x}, ANSI={ansi_z_x}"


def test_iso_enter_is_taller_than_ansi_enter() -> None:
    iso_keys = {k.key_id: k for k in build_layout(variant="iso")}
    ansi_keys = {k.key_id: k for k in build_layout(variant="ansi")}

    assert iso_keys["enter"].rect[3] > ansi_keys["enter"].rect[3]


def test_ansi_has_top_row_backslash_but_iso_does_not() -> None:
    ansi_keys = {k.key_id for k in build_layout(variant="ansi")}
    iso_keys = {k.key_id for k in build_layout(variant="iso")}

    assert "bslash" in ansi_keys
    assert "bslash" not in iso_keys


def test_get_layout_keys_ansi() -> None:
    keys = get_layout_keys("ansi")
    key_ids = {k.key_id for k in keys}
    assert "nonusbackslash" not in key_ids
    assert "z" in key_ids


def test_get_layout_keys_iso() -> None:
    keys = get_layout_keys("iso")
    key_ids = {k.key_id for k in keys}
    assert "nonusbackslash" in key_ids


def test_get_layout_keys_can_apply_sparse_legend_pack_without_changing_identity() -> None:
    keys = get_layout_keys("iso", legend_pack_id="iso-de-qwertz")
    slot_map = {str(key.slot_id): key for key in keys}

    assert slot_map["top_06"].key_id == "y"
    assert slot_map["top_06"].label == "Z"
    assert slot_map["shift_02"].key_id == "z"
    assert slot_map["shift_02"].label == "Y"


def test_build_layout_assigns_unique_slot_ids_per_layout() -> None:
    keys = build_layout(variant="iso")
    slot_ids = [str(key.slot_id) for key in keys]

    assert all(slot_id for slot_id in slot_ids)
    assert len(slot_ids) == len(set(slot_ids))


def test_alpha_rows_use_physical_slot_ids_not_letter_ids() -> None:
    ansi_keys = {key.key_id: key for key in build_layout(variant="ansi")}
    iso_keys = {key.key_id: key for key in build_layout(variant="iso")}

    assert ansi_keys["q"].slot_id == "top_01"
    assert ansi_keys["a"].slot_id == "home_01"
    assert ansi_keys["z"].slot_id == "shift_01"
    assert iso_keys["z"].slot_id == "shift_02"
    assert iso_keys["nonusbackslash"].slot_id == "shift_01"


def test_slot_id_mapping_helpers_resolve_both_directions() -> None:
    assert slot_id_for_key_id("ansi", "q") == "top_01"
    assert key_id_for_slot_id("ansi", "top_01") == "q"
    assert slot_id_for_key_id("iso", "nonusbackslash") == "shift_01"
    assert key_id_for_slot_id("iso", "shift_01") == "nonusbackslash"
    assert slot_id_for_key_id("ansi", "missing") is None
    assert key_id_for_slot_id("ansi", "missing") is None


def test_get_layout_keys_applies_slot_visibility_and_label_overrides() -> None:
    keys = get_layout_keys(
        "iso",
        slot_overrides={
            "nonusbackslash": {"visible": False},
            "nonushash": {"label": "Alt #"},
        },
    )
    key_map = {key.key_id: key for key in keys}

    assert "nonusbackslash" not in key_map
    assert key_map["nonushash"].label == "Alt #"


def test_get_layout_slot_states_uses_layout_defaults_when_no_overrides() -> None:
    states = get_layout_slot_states("jis")
    state_map = {state.key_id: state for state in states}

    assert state_map["jp_at"].visible is True
    assert state_map["jp_at"].default_label == "@"


def test_get_layout_slot_states_includes_optional_bottom_row_keys_for_ansi() -> None:
    states = get_layout_slot_states("ansi")
    state_map = {state.key_id: state for state in states}

    assert state_map["fn"].default_label == "Fn"
    assert state_map["menu"].default_label == "Copilot"


def test_get_layout_slot_states_can_use_selected_legend_pack(monkeypatch) -> None:
    menu_slot_id = str(slot_id_for_key_id("ansi", "menu") or "menu")
    clear_layout_slot_cache()
    monkeypatch.setattr(
        layout_slots_mod,
        "get_layout_legend_labels",
        lambda layout_id, legend_pack_id=None: {menu_slot_id: "Legend Menu"} if legend_pack_id == "ansi-test" else {},
    )

    states = get_layout_slot_states("ansi", legend_pack_id="ansi-test")
    state_map = {state.key_id: state for state in states}

    assert state_map["menu"].default_label == "Legend Menu"


def test_apply_layout_slot_overrides_preserves_optional_legend_pack_labels(monkeypatch) -> None:
    menu_slot_id = str(slot_id_for_key_id("ansi", "menu") or "menu")
    clear_layout_slot_cache()
    monkeypatch.setattr(
        layout_slots_mod,
        "get_layout_legend_labels",
        lambda layout_id, legend_pack_id=None: {menu_slot_id: "Legend Menu"} if legend_pack_id == "ansi-test" else {},
    )

    keys = [KeyDef("menu", "Legend Menu", (0, 0, 10, 10), slot_id=menu_slot_id)]
    resolved = apply_layout_slot_overrides(keys, layout_id="ansi", legend_pack_id="ansi-test")

    assert resolved[0].label == "Legend Menu"


def test_get_layout_keys_can_hide_optional_menu_key_on_ansi() -> None:
    keys = get_layout_keys("ansi", slot_overrides={"menu": {"visible": False}})
    key_ids = {key.key_id for key in keys}

    assert "menu" not in key_ids
    assert "fn" in key_ids


def test_ansi_layout_excludes_right_ctrl() -> None:
    key_ids = {k.key_id for k in build_layout(variant="ansi")}
    assert "rctrl" not in key_ids


def test_iso_and_abnt_bottom_row_include_right_ctrl() -> None:
    for variant in ("iso", "abnt"):
        key_ids = {k.key_id for k in build_layout(variant=variant)}
        assert "rctrl" in key_ids


def test_jis_bottom_row_includes_extra_modifiers() -> None:
    keys = {k.key_id: k for k in build_layout(variant="jis")}

    assert "menu" in keys
    assert "rctrl" in keys


def test_jis_enter_clears_top_row_key() -> None:
    keys = {k.key_id: k for k in build_layout(variant="jis")}
    enter = keys["enter"]
    jp_at = keys["jp_at"]

    assert enter.shape_segments is None
    enter_top_left = enter.rect[0]
    jp_at_right = jp_at.rect[0] + jp_at.rect[2]

    assert jp_at_right <= enter_top_left


def test_iso_only_key_ids_constant() -> None:
    assert "nonusbackslash" in ISO_ONLY_KEY_IDS
    assert "nonushash" in ISO_ONLY_KEY_IDS


def test_resolve_physical_layout_explicit() -> None:
    assert resolve_physical_layout("ansi") == "ansi"
    assert resolve_physical_layout("iso") == "iso"
    assert resolve_physical_layout("ks") == "ks"
    assert resolve_physical_layout("abnt") == "abnt"
    assert resolve_physical_layout("jis") == "jis"
    assert resolve_physical_layout("ANSI") == "ansi"
    assert resolve_physical_layout("ISO") == "iso"


def test_end_x_returns_zero_for_empty_key_list() -> None:
    assert layout_mod._end_x([]) == 0


def test_abnt_layout_spec_inherits_iso_rows() -> None:
    spec = load_layout_spec("abnt")
    rows = spec.get("rows")

    assert isinstance(rows, dict)
    assert "top" in rows
    assert "home" in rows
    assert "shift" in rows

    home_ids = [item.get("key_id") for item in rows["home"] if isinstance(item, dict)]
    shift_ids = [item.get("key_id") for item in rows["shift"] if isinstance(item, dict)]

    assert "nonushash" in home_ids
    assert "abnt2slash" in shift_ids
