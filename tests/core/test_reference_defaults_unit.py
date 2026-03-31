from __future__ import annotations

from pathlib import Path

import src.core.resources.defaults as defaults

from src.core.resources.defaults import (
    DEFAULT_COLORS,
    DEFAULT_KEYMAP,
    REFERENCE_MATRIX_COLS,
    REFERENCE_MATRIX_ROWS,
    build_default_colors,
    get_default_keymap,
    get_default_layout_tweaks,
    get_default_per_key_tweaks,
)
from src.core.resources.layout import build_layout
from src.core.resources.reference_defaults_specs import (
    clear_reference_defaults_spec_cache,
    load_reference_defaults_spec,
)


def test_reference_matrix_dimensions_cover_default_keymap() -> None:
    if not DEFAULT_KEYMAP:
        assert REFERENCE_MATRIX_ROWS > 0
        assert REFERENCE_MATRIX_COLS > 0
        assert len(DEFAULT_COLORS) == REFERENCE_MATRIX_ROWS * REFERENCE_MATRIX_COLS
        return

    max_row = -1
    max_col = -1
    for coord_text in DEFAULT_KEYMAP.values():
        row_text, col_text = coord_text.split(",", 1)
        max_row = max(max_row, int(row_text))
        max_col = max(max_col, int(col_text))

    assert REFERENCE_MATRIX_ROWS == max_row + 1
    assert REFERENCE_MATRIX_COLS == max_col + 1


def test_build_default_colors_uses_requested_dimensions() -> None:
    colors = build_default_colors(num_rows=2, num_cols=3)

    assert len(colors) == 6
    assert colors[(0, 0)] == (255, 255, 255)
    assert colors[(1, 2)] == (255, 255, 255)
    assert (2, 0) not in colors
    assert (0, 3) not in colors


def test_build_default_colors_uses_reference_dimensions_by_default() -> None:
    assert build_default_colors() == build_default_colors(
        num_rows=REFERENCE_MATRIX_ROWS,
        num_cols=REFERENCE_MATRIX_COLS,
    )


def test_default_colors_match_reference_dimensions() -> None:
    assert DEFAULT_COLORS == build_default_colors(
        num_rows=REFERENCE_MATRIX_ROWS,
        num_cols=REFERENCE_MATRIX_COLS,
    )


def test_layout_specific_default_accessors_return_dicts() -> None:
    for layout_id in ("ansi", "iso", "ks", "abnt", "jis"):
        assert get_default_keymap(layout_id)
        assert get_default_layout_tweaks(layout_id)
        assert isinstance(get_default_per_key_tweaks(layout_id), dict)


def test_unknown_layout_defaults_fall_back_to_ansi() -> None:
    assert get_default_keymap("unknown") == get_default_keymap("ansi")
    assert get_default_layout_tweaks("unknown") == get_default_layout_tweaks("ansi")


def test_auto_layout_defaults_follow_resolved_layout(monkeypatch) -> None:
    monkeypatch.setattr(defaults, "resolve_layout_id", lambda _layout_id: "iso")

    assert get_default_keymap("auto") == get_default_keymap("iso")
    assert get_default_per_key_tweaks("auto") == get_default_per_key_tweaks("iso")


def test_layout_specific_default_keymaps_diverge_from_ansi() -> None:
    ansi = get_default_keymap("ansi")
    iso = get_default_keymap("iso")
    abnt = get_default_keymap("abnt")
    ks = get_default_keymap("ks")
    jis = get_default_keymap("jis")

    assert "rctrl" not in ansi

    assert "nonusbackslash" in iso
    assert "nonushash" in iso
    assert "bslash" not in iso

    assert "abnt2slash" in abnt
    assert "nonusbackslash" in abnt
    assert "nonushash" in abnt

    assert "ks_extra" in ks
    assert "hanja" in ks
    assert "hangul" in ks

    assert "yen" in jis
    assert "jp_at" in jis
    assert "jp_colon" in jis
    assert "jp_ro" in jis
    assert "muhenkan" in jis
    assert "henkan" in jis
    assert "katakana" in jis
    assert "menu" in jis
    assert "rctrl" in jis


def test_layout_specific_per_key_tweaks_cover_variant_specific_keys() -> None:
    ansi = get_default_per_key_tweaks("ansi")
    iso = get_default_per_key_tweaks("iso")
    abnt = get_default_per_key_tweaks("abnt")
    ks = get_default_per_key_tweaks("ks")
    jis = get_default_per_key_tweaks("jis")

    assert "rctrl" not in ansi

    assert "nonusbackslash" in iso
    assert "nonushash" in iso

    assert "abnt2slash" in abnt
    assert "nonusbackslash" in abnt
    assert "nonushash" in abnt
    assert "rctrl" in abnt
    assert abnt["menu"]["sx"] < 1.5

    assert "ks_extra" in ks
    assert "hanja" in ks
    assert "hangul" in ks

    assert "yen" in jis
    assert "jp_at" in jis
    assert "jp_colon" in jis
    assert "jp_ro" in jis
    assert "muhenkan" in jis
    assert "henkan" in jis
    assert "katakana" in jis
    assert "menu" in jis
    assert "rctrl" in jis

    assert iso["menu"]["sx"] < 1.5
    assert iso["rctrl"]["dx"] > -10.0
    assert abnt["rctrl"]["dx"] > -10.0


def test_reference_defaults_spec_abnt_inherits_iso_overrides() -> None:
    clear_reference_defaults_spec_cache()

    defaults_spec = load_reference_defaults_spec("abnt")
    keymap = defaults_spec["keymap"]
    per_key_tweaks = defaults_spec["per_key_tweaks"]

    assert "bslash" not in keymap
    assert keymap["nonusbackslash"] == "1,2"
    assert keymap["nonushash"] == "2,13"
    assert keymap["abnt2slash"] == "1,13"
    assert keymap["rctrl"] == "0,11"

    assert "menu" in per_key_tweaks
    assert "nonusbackslash" in per_key_tweaks
    assert "nonushash" in per_key_tweaks
    assert "abnt2slash" in per_key_tweaks
    assert "rctrl" in per_key_tweaks


def test_reference_defaults_spec_ansi_is_self_contained() -> None:
    clear_reference_defaults_spec_cache()

    defaults_spec = load_reference_defaults_spec("ansi")

    assert len(defaults_spec["keymap"]) == 101
    assert len(defaults_spec["per_key_tweaks"]) == 101
    assert defaults_spec["layout_tweaks"]["inset"] == 0.06


def test_load_defaults_falls_back_to_ansi_when_layout_spec_fails(monkeypatch) -> None:
    defaults._load_defaults.cache_clear()

    def fake_load_reference_defaults_spec(layout_id: str) -> dict[str, object]:
        if layout_id == "iso":
            return {}
        if layout_id == "ansi":
            return {"keymap": {"esc": "0,0"}}
        raise AssertionError(f"unexpected layout id: {layout_id}")

    monkeypatch.setattr(defaults, "load_reference_defaults_spec", fake_load_reference_defaults_spec)

    assert defaults._load_defaults("iso") == {"keymap": {"esc": "0,0"}}
    defaults._load_defaults.cache_clear()


def test_load_defaults_returns_empty_when_default_spec_fails(monkeypatch) -> None:
    defaults._load_defaults.cache_clear()

    monkeypatch.setattr(defaults, "load_reference_defaults_spec", lambda _layout_id: {})

    assert defaults._load_defaults("ansi") == {}
    defaults._load_defaults.cache_clear()


def test_legacy_reference_defaults_snapshot_files_are_gone() -> None:
    resources_dir = Path(defaults.__file__).resolve().parent

    for file_name in (
        "reference_defaults_ansi.json",
        "reference_defaults_iso.json",
        "reference_defaults_abnt.json",
        "reference_defaults_ks.json",
        "reference_defaults_jis.json",
    ):
        assert not (resources_dir / file_name).exists()


def test_reference_matrix_dimensions_fall_back_for_invalid_keymap(monkeypatch) -> None:
    monkeypatch.setattr(defaults, "get_default_keymap", lambda _layout_id=None: {"bad": "oops"})

    assert defaults.get_reference_matrix_dimensions("iso") == (6, 21)


def test_default_per_key_tweaks_skip_invalid_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        defaults,
        "_load_defaults",
        lambda _layout_id="ansi": {
            "per_key_tweaks": {
                "ok": {"dx": 1, "dy": 2.5},
                "empty": {"ignored": "x"},
                "not-a-dict": [],
                1: {"dx": 3},
            }
        },
    )

    assert defaults.get_default_per_key_tweaks("ansi") == {"ok": {"dx": 1.0, "dy": 2.5}}


def test_layout_defaults_cover_visible_layout_keys() -> None:
    for layout_id in ("ansi", "iso", "ks", "abnt", "jis"):
        visible_key_ids = {key.key_id for key in build_layout(variant=layout_id)}
        keymap_ids = set(get_default_keymap(layout_id))
        tweak_ids = set(get_default_per_key_tweaks(layout_id))

        assert visible_key_ids <= keymap_ids
        assert visible_key_ids <= tweak_ids
