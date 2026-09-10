"""Unit coverage for guided-session parsing, validation, and result writes."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from keyrgb.core.profile import profiles
from keyrgb.gui.calibrator import guided as guided_session
from keyrgb.gui.calibrator.guided import (
    GuidedConfigView,
    GuidedSessionError,
    load_guided_session,
    parse_guided_session_argv,
    write_guided_result,
)

ROWS, COLS = 2, 3


def _write_session(tmp_path: Path, payload: object, name: str = "session.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --- argv parsing -----------------------------------------------------------


def test_parse_argv_none_and_empty_means_standalone() -> None:
    assert parse_guided_session_argv([]) is None
    assert parse_guided_session_argv(()) is None


def test_parse_argv_space_and_equals_forms(tmp_path: Path) -> None:
    assert parse_guided_session_argv(["--guided-session", str(tmp_path)]) == tmp_path
    assert parse_guided_session_argv([f"--guided-session={tmp_path}"]) == tmp_path


@pytest.mark.parametrize(
    "argv",
    [
        ["--guided-session"],
        ["--guided-session="],
        ["--guided-session", "   "],
        ["--guided-session", "a.json", "--guided-session", "b.json"],
        ["--unknown-flag"],
        ["positional.json"],
    ],
)
def test_parse_argv_rejects_bad_input(argv: list[str]) -> None:
    with pytest.raises(GuidedSessionError):
        parse_guided_session_argv(argv)


# --- loading ----------------------------------------------------------------


def test_load_minimal_session_uses_defaults(tmp_path: Path) -> None:
    path = _write_session(tmp_path, {})

    session = load_guided_session(path, num_rows=ROWS, num_cols=COLS)

    assert session.source_path == path
    assert session.physical_layout == "auto"
    assert session.legend_pack is None
    assert session.slot_overrides == {}
    assert session.keymap == {}
    assert session.per_key_layout_tweaks == {}


def test_load_full_session_initializes_displayed_state(tmp_path: Path) -> None:
    from keyrgb.core.resources.layout_slots import get_layout_slot_key_ids

    slot_id = get_layout_slot_key_ids("ansi")[0]
    path = _write_session(
        tmp_path,
        {
            "physical_layout": "ansi",
            "dimensions": [3, 4],
            "legend_pack": "auto",
            "slot_overrides": {slot_id: {"label": "Hi"}},
            "keymap": {"esc": [[0, 0]], "enter": [[1, 2], [99, 99]]},
            "layout_tweaks": {"dx": 1.5},
            "per_key_layout_tweaks": {"esc": {"dx": 0.25}},
        },
    )

    session = load_guided_session(path, num_rows=ROWS, num_cols=COLS)

    assert session.physical_layout == "ansi"
    assert (session.num_rows, session.num_cols) == (3, 4)
    assert session.legend_pack == "auto"
    assert session.slot_overrides[slot_id] == {"label": "Hi"}
    # Out-of-range cells are dropped like standalone sanitize behavior, and
    # identities are canonicalized exactly like standalone profile loads.
    assert session.keymap == {"frow_00": ((0, 0),), "home_12": ((1, 2),)}
    assert session.layout_tweaks["dx"] == 1.5
    assert session.per_key_layout_tweaks["frow_00"] == {"dx": 0.25}


def test_load_accepts_documented_aliases(tmp_path: Path) -> None:
    path = _write_session(
        tmp_path,
        {
            "legend_pack_id": "plain",
            "layout_slot_overrides": {},
            "layout_global": {"dx": 2.0},
            "layout_per_key": {},
        },
    )

    session = load_guided_session(path, num_rows=ROWS, num_cols=COLS)

    assert session.legend_pack == "plain"
    assert session.layout_tweaks["dx"] == 2.0


@pytest.mark.parametrize(
    "payload",
    [
        {"keymap": ["esc"]},
        {"physical_layout": 42},
        {"physical_layout": True},
        {"legend_pack": {"pack": 1}},
        {"slot_overrides": ["x"]},
        {"layout_tweaks": "dx"},
        {"per_key_layout_tweaks": [1]},
        {"dimensions": [0, 20]},
        {"dimensions": [6, "20"]},
        ["top-level-list"],
        "top-level-string",
        42,
    ],
)
def test_load_rejects_malformed_payloads(tmp_path: Path, payload: object) -> None:
    path = _write_session(tmp_path, payload)

    with pytest.raises(GuidedSessionError):
        load_guided_session(path, num_rows=ROWS, num_cols=COLS)


def test_load_rejects_missing_file_and_bad_json(tmp_path: Path) -> None:
    with pytest.raises(GuidedSessionError):
        load_guided_session(tmp_path / "absent.json", num_rows=ROWS, num_cols=COLS)

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(GuidedSessionError):
        load_guided_session(bad, num_rows=ROWS, num_cols=COLS)


def test_malformed_session_rejection_touches_no_profile_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation failures must not mutate profile data."""

    def _forbid_save(*args: object, **kwargs: object) -> None:
        raise AssertionError("profile save must not run during guided validation")

    monkeypatch.setattr(profiles, "save_keymap", _forbid_save)
    config_dir = tmp_path / "isolated-config"
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(config_dir))

    bad = _write_session(tmp_path, {"keymap": ["nope"]})
    with pytest.raises(GuidedSessionError):
        load_guided_session(bad, num_rows=ROWS, num_cols=COLS)

    assert not (config_dir / "profiles").exists()


# --- result writes ------------------------------------------------------------


def test_write_guided_result_stores_normalized_keymap(tmp_path: Path) -> None:
    path = _write_session(tmp_path, {"physical_layout": "ansi", "draft": True, "custom": {"a": 1}})

    returned = write_guided_result(path, {"esc": ((0, 0),)}, physical_layout="ansi")

    assert returned == path
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["physical_layout"] == "ansi"
    assert payload["draft"] is True
    assert payload["custom"] == {"a": 1}
    assert payload["result"]["physical_layout"] == "ansi"
    assert payload["result"]["version"] == 1
    # Same "r,c" keymap schema encoding used by profile saves, with the same
    # canonical slot identities.
    assert payload["result"]["keymap"] == {"frow_00": "0,0"}
    # No stray temp files left behind by the atomic write.
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_guided_result_never_touches_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid_save(*args: object, **kwargs: object) -> None:
        raise AssertionError("profile save must not run for guided results")

    monkeypatch.setattr(profiles, "save_keymap", _forbid_save)
    config_dir = tmp_path / "isolated-config"
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(config_dir))

    path = _write_session(tmp_path, {"physical_layout": "ansi"})
    write_guided_result(path, {"esc": ((0, 0),)}, physical_layout="ansi")

    assert not (config_dir / "profiles").exists()


def test_write_guided_result_refuses_missing_or_non_object_session(tmp_path: Path) -> None:
    with pytest.raises(GuidedSessionError):
        write_guided_result(tmp_path / "absent.json", {}, physical_layout="ansi")

    non_object = tmp_path / "list.json"
    non_object.write_text("[]", encoding="utf-8")
    with pytest.raises(GuidedSessionError):
        write_guided_result(non_object, {}, physical_layout="ansi")


def test_write_guided_result_error_is_transparent_not_silent(tmp_path: Path) -> None:
    """Unwritable destinations raise; they are never swallowed."""

    path = _write_session(tmp_path, {})
    path.chmod(0o400)
    try:
        with pytest.raises(GuidedSessionError):
            write_guided_result(tmp_path / "no-such-dir" / "x" / "session.json", {}, physical_layout="ansi")
    finally:
        path.chmod(0o600)


# --- config view --------------------------------------------------------------


def test_guided_config_view_overrides_layout_only() -> None:
    base = SimpleNamespace(
        physical_layout="iso",
        layout_legend_pack="plain",
        effect="wave",
        CONFIG_DIR=Path("/tmp/cfg"),
    )

    view = GuidedConfigView(base, physical_layout="ansi", legend_pack="custom-pack")

    assert view.physical_layout == "ansi"
    assert view.layout_legend_pack == "custom-pack"
    # Reads forward to the wrapped config.
    assert view.effect == "wave"
    assert view.CONFIG_DIR == Path("/tmp/cfg")
    # Writes forward so Config-mediated preview still reaches real config.
    view.effect = "perkey"
    assert base.effect == "perkey"
    # Base is untouched for the overridden fields (nothing guided persists).
    assert base.physical_layout == "iso"
    assert base.layout_legend_pack == "plain"


def test_guided_config_view_falls_back_to_base_when_empty() -> None:
    base = SimpleNamespace(physical_layout="iso", layout_legend_pack="plain")

    view = GuidedConfigView(base, physical_layout="  ", legend_pack=None)

    assert view.physical_layout == "iso"
    assert view.layout_legend_pack == "plain"


def test_guided_module_exports_flag_and_button_copy() -> None:
    assert guided_session.GUIDED_SESSION_FLAG == "--guided-session"
    assert guided_session._SAVE_BUTTON_TEXT == "Use Result"
    assert guided_session._SAVE_AND_CLOSE_BUTTON_TEXT == "Use Result && Close"


def test_guided_session_path_of_narrow_helper(tmp_path: Path) -> None:
    assert guided_session.guided_session_path_of(SimpleNamespace()) is None
    assert guided_session.guided_session_path_of(SimpleNamespace(guided_session_path=None)) is None
    assert guided_session.guided_session_path_of(SimpleNamespace(guided_session_path=tmp_path)) == tmp_path
    assert guided_session.guided_session_path_of(SimpleNamespace(guided_session_path=str(tmp_path))) == tmp_path


def test_layout_tweaks_fill_defaults_and_clamp_inset(tmp_path: Path) -> None:
    path = _write_session(tmp_path, {"layout_tweaks": {"dx": 2.0, "inset": 99.0, "unknown": 1}})

    session = load_guided_session(path, num_rows=ROWS, num_cols=COLS)

    assert session.layout_tweaks["dx"] == 2.0
    assert session.layout_tweaks["sx"] == 1.0
    assert session.layout_tweaks["inset"] == 0.20
    assert "unknown" not in session.layout_tweaks


def test_result_encoding_matches_profile_keymap_shape(tmp_path: Path) -> None:
    from keyrgb.gui.calibrator.guided import encode_guided_result_keymap

    encoded = encode_guided_result_keymap(
        {"frow_00": ((0, 0),), "home_12": ((1, 2), (1, 3))},
        physical_layout="ansi",
    )

    assert encoded == {"frow_00": "0,0", "home_12": ["1,2", "1,3"]}
    assert list(encoded) == sorted(encoded)


def test_result_encoding_rejects_malformed_cells() -> None:
    from keyrgb.gui.calibrator.guided import _encode_keymap_payload

    with pytest.raises(GuidedSessionError):
        _encode_keymap_payload({"frow_00": (("x", "y"),)})  # type: ignore[dict-item]
    with pytest.raises(GuidedSessionError):
        _encode_keymap_payload({"frow_00": ((True, 0),)})  # type: ignore[dict-item]
