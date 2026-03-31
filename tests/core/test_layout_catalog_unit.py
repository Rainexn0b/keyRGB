"""Unit tests for src/core/resources/layouts/ catalog package."""

from __future__ import annotations

from unittest.mock import patch

from src.core.resources.layouts import (
    LAYOUT_CATALOG,
    LayoutDef,
    clear_layout_cache,
    get_layout_keys,
    resolve_layout_id,
)
from src.core.resources.layouts.catalog import VALID_LAYOUT_IDS, get_layout_def


# ------------------------------------------------------------------ catalog --


def test_layout_catalog_not_empty() -> None:
    assert len(LAYOUT_CATALOG) >= 2


def test_layout_catalog_contains_supported_variants() -> None:
    ids = {ld.layout_id for ld in LAYOUT_CATALOG}
    assert "auto" in ids
    assert "ansi" in ids
    assert "iso" in ids
    assert "ks" in ids
    assert "abnt" in ids
    assert "jis" in ids


def test_layout_catalog_entries_are_layout_def() -> None:
    for entry in LAYOUT_CATALOG:
        assert isinstance(entry, LayoutDef)


def test_layout_def_fields() -> None:
    ansi = next(ld for ld in LAYOUT_CATALOG if ld.layout_id == "ansi")
    assert ansi.label  # non-empty label
    assert ansi.layout_id == "ansi"

    iso = next(ld for ld in LAYOUT_CATALOG if ld.layout_id == "iso")
    assert iso.label
    assert iso.layout_id == "iso"

    ks = next(ld for ld in LAYOUT_CATALOG if ld.layout_id == "ks")
    assert ks.label
    assert ks.layout_id == "ks"

    jis = next(ld for ld in LAYOUT_CATALOG if ld.layout_id == "jis")
    assert jis.label
    assert jis.layout_id == "jis"


def test_valid_layout_ids_matches_catalog() -> None:
    catalog_ids = {ld.layout_id for ld in LAYOUT_CATALOG}
    assert catalog_ids == VALID_LAYOUT_IDS


# ------------------------------------------------------------------ get_layout_def --


def test_get_layout_def_known() -> None:
    ld = get_layout_def("ansi")
    assert ld.layout_id == "ansi"


def test_get_layout_def_unknown_returns_auto() -> None:
    ld = get_layout_def("zzz_unknown")
    assert ld.layout_id == "auto"


def test_get_layout_def_case_insensitive() -> None:
    assert get_layout_def("ISO").layout_id == "iso"
    assert get_layout_def("ANSI").layout_id == "ansi"


# ------------------------------------------------------------------ resolve_layout_id --


def test_resolve_layout_id_ansi() -> None:
    assert resolve_layout_id("ansi") == "ansi"


def test_resolve_layout_id_iso() -> None:
    assert resolve_layout_id("iso") == "iso"


def test_resolve_layout_id_unknown_returns_ansi() -> None:
    clear_layout_cache()
    result = resolve_layout_id("zzz_unknown")
    assert result == "ansi"


def test_resolve_layout_id_empty_string_defaults() -> None:
    clear_layout_cache()
    result = resolve_layout_id("")
    assert result == "ansi"


def test_resolve_layout_id_auto_inconclusive_defaults_to_ansi() -> None:
    clear_layout_cache()
    with patch("src.core.resources.layouts.detect.detect_physical_layout", return_value="auto"):
        assert resolve_layout_id("auto") == "ansi"
    clear_layout_cache()


def test_resolve_layout_id_auto_uses_detected_concrete_layout() -> None:
    clear_layout_cache()
    with patch("src.core.resources.layouts.detect.detect_physical_layout", return_value="jis"):
        assert resolve_layout_id("auto") == "jis"
    clear_layout_cache()


# ------------------------------------------------------------------ get_layout_keys --


def test_get_layout_keys_ansi_excludes_nonusbackslash() -> None:
    keys = get_layout_keys("ansi")
    key_ids = {k.key_id for k in keys}
    assert "nonusbackslash" not in key_ids
    assert "lshift" in key_ids


def test_get_layout_keys_iso_includes_nonusbackslash() -> None:
    keys = get_layout_keys("iso")
    key_ids = {k.key_id for k in keys}
    assert "nonusbackslash" in key_ids


def test_get_layout_keys_abnt_has_abnt_specific_key() -> None:
    keys = get_layout_keys("abnt")
    key_ids = {k.key_id for k in keys}
    assert "abnt2slash" in key_ids


def test_get_layout_keys_jis_has_jis_modifiers() -> None:
    keys = get_layout_keys("jis")
    key_ids = {k.key_id for k in keys}
    assert "muhenkan" in key_ids
    assert "henkan" in key_ids
    assert "katakana" in key_ids


def test_get_layout_keys_returns_list() -> None:
    for ld in LAYOUT_CATALOG:
        if ld.layout_id == "auto":
            continue  # auto triggers sysfs — skip in unit tests
        result = get_layout_keys(ld.layout_id)
        assert isinstance(result, list)
        assert len(result) > 0
