"""Unit coverage for the calibrator preview recovery journal."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from keyrgb.gui.calibrator import guided as preview_journal
from keyrgb.gui.calibrator.helpers.keyboard_preview import KeyboardPreviewSession


def _fake_cfg(config_dir: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "effect": "wave",
        "speed": 9,
        "brightness": 40,
        "color": (7, 8, 9),
        "per_key_colors": {(0, 0): (7, 8, 9)},
        "CONFIG_DIR": config_dir,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _valid_journal_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": 1,
        "effect": "wave",
        "speed": 9,
        "brightness": 40,
        "color": [7, 8, 9],
        "per_key_colors": {"0,0": [7, 8, 9]},
    }
    payload.update(overrides)
    return payload


# --- journal path / fields ----------------------------------------------------


def test_journal_lives_under_config_dir(tmp_path: Path) -> None:
    assert preview_journal.journal_path(tmp_path) == tmp_path / preview_journal.PREVIEW_JOURNAL_FILENAME
    assert set(preview_journal.journal_snapshot_fields()) == {
        "effect",
        "speed",
        "brightness",
        "color",
        "per_key_colors",
    }


# --- record before first mutation ----------------------------------------------


def test_preview_records_journal_before_first_mutation_and_clears_on_restore(tmp_path: Path) -> None:
    cfg = _fake_cfg(tmp_path)
    session = KeyboardPreviewSession(cfg=cfg, rows=2, cols=2)

    assert preview_journal.journal_path(tmp_path).exists() is False

    session.apply_probe_cell(1, 1)

    journal = json.loads(preview_journal.journal_path(tmp_path).read_text(encoding="utf-8"))
    assert journal["effect"] == "wave"
    assert journal["speed"] == 9
    assert journal["brightness"] == 40
    assert journal["color"] == [7, 8, 9]
    assert journal["per_key_colors"] == {"0,0": [7, 8, 9]}
    # Preview still mutates through Config exactly like standalone mode.
    assert cfg.per_key_colors[(1, 1)] == (255, 255, 255)

    second_journal_mtime = preview_journal.journal_path(tmp_path).stat().st_mtime_ns
    session.apply_probe_cell(0, 0)
    assert preview_journal.journal_path(tmp_path).stat().st_mtime_ns == second_journal_mtime

    session.restore()
    assert preview_journal.journal_path(tmp_path).exists() is False
    assert cfg.effect == "wave"
    assert cfg.per_key_colors == {(0, 0): (7, 8, 9)}


def test_preview_without_config_dir_skips_journal_silently() -> None:
    cfg = SimpleNamespace(effect="wave", speed=1, brightness=10, color=(1, 2, 3), per_key_colors={})
    session = KeyboardPreviewSession(cfg=cfg, rows=1, cols=1)

    session.apply_probe_cell(0, 0)
    session.restore()

    assert cfg.per_key_colors == {}


def test_journal_write_failure_does_not_break_preview(tmp_path: Path) -> None:
    cfg = _fake_cfg(tmp_path / "not-a-dir-file")
    cfg.CONFIG_DIR.write_text("blocking file", encoding="utf-8")
    session = KeyboardPreviewSession(cfg=cfg, rows=1, cols=1)

    session.apply_probe_cell(0, 0)

    assert cfg.per_key_colors[(0, 0)] == (255, 255, 255)


# --- stale recovery -------------------------------------------------------------


def test_recover_stale_journal_restores_and_removes(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    preview_journal.write_preview_journal(tmp_path, _valid_journal_payload())
    cfg = _fake_cfg(
        tmp_path,
        effect="perkey",
        speed=1,
        brightness=50,
        color=(0, 0, 0),
        per_key_colors={(1, 1): (255, 255, 255)},
    )

    with caplog.at_level(logging.WARNING, logger="keyrgb.gui.calibrator.guided.journal_recovery"):
        assert preview_journal.recover_stale_preview_journal(cfg) is True

    assert cfg.effect == "wave"
    assert cfg.speed == 9
    assert cfg.brightness == 40
    assert cfg.color == (7, 8, 9)
    assert cfg.per_key_colors == {(0, 0): (7, 8, 9)}
    assert preview_journal.journal_path(tmp_path).exists() is False
    assert any("automatically restored" in record.message for record in caplog.records)


def test_recover_without_journal_is_quiet_success(tmp_path: Path) -> None:
    cfg = _fake_cfg(tmp_path)

    assert preview_journal.recover_stale_preview_journal(cfg) is False
    assert cfg.effect == "wave"


def test_recover_corrupt_journal_discards_and_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    preview_journal.journal_path(tmp_path).write_text("{corrupt", encoding="utf-8")
    cfg = _fake_cfg(tmp_path)

    with caplog.at_level(logging.WARNING, logger="keyrgb.gui.calibrator.guided.journal_recovery"):
        assert preview_journal.recover_stale_preview_journal(cfg) is False

    assert preview_journal.journal_path(tmp_path).exists() is False
    assert cfg.effect == "wave"
    assert caplog.records


def test_recover_non_object_journal_discards(tmp_path: Path) -> None:
    preview_journal.journal_path(tmp_path).write_text("[1, 2]", encoding="utf-8")
    cfg = _fake_cfg(tmp_path)

    assert preview_journal.recover_stale_preview_journal(cfg) is False
    assert preview_journal.journal_path(tmp_path).exists() is False


def test_clear_missing_journal_never_raises(tmp_path: Path) -> None:
    preview_journal.clear_preview_journal(tmp_path)


# --- schema validation ----------------------------------------------------------


@pytest.mark.parametrize(
    "bad_field",
    [
        {"speed": "bad"},
        {"speed": 11},
        {"speed": -1},
        {"speed": True},
        {"speed": 9.5},
        {"brightness": "bright"},
        {"brightness": 51},
        {"brightness": -1},
        {"brightness": False},
        {"effect": ""},
        {"effect": "   "},
        {"effect": 42},
        {"effect": None},
        {"effect": True},
        {"color": [1, 2]},
        {"color": [1, 2, 3, 4]},
        {"color": [300, 0, 0]},
        {"color": [1, 2, True]},
        {"color": "red"},
        {"color": None},
        {"per_key_colors": {"nope": [1, 2, 3]}},
        {"per_key_colors": {"0,0": "red"}},
        {"per_key_colors": {"0,0": [1, 2]}},
        {"per_key_colors": {"0,0": [1, 2, 300]}},
        {"per_key_colors": {"-1,0": [1, 2, 3]}},
        {"per_key_colors": "nope"},
        {"per_key_colors": None},
        {"version": 2},
        {"version": "1"},
        {"version": True},
    ],
)
def test_malformed_field_discards_journal_without_changing_config(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, bad_field: dict[str, object]
) -> None:
    """One malformed field makes the journal unusable; config stays untouched."""

    payload = _valid_journal_payload(**bad_field)
    preview_journal.journal_path(tmp_path).write_text(json.dumps(payload), encoding="utf-8")
    before = {
        "effect": "perkey",
        "speed": 1,
        "brightness": 50,
        "color": (0, 0, 0),
        "per_key_colors": {(1, 1): (255, 255, 255)},
    }
    cfg = _fake_cfg(tmp_path, **before)

    with caplog.at_level(logging.WARNING, logger="keyrgb.gui.calibrator.guided.journal_recovery"):
        assert preview_journal.recover_stale_preview_journal(cfg) is False

    assert preview_journal.journal_path(tmp_path).exists() is False
    assert cfg.effect == before["effect"]
    assert cfg.speed == before["speed"]
    assert cfg.brightness == before["brightness"]
    assert cfg.color == before["color"]
    assert cfg.per_key_colors == before["per_key_colors"]
    assert caplog.records


def test_missing_version_discards_journal(tmp_path: Path) -> None:
    payload = _valid_journal_payload()
    del payload["version"]
    preview_journal.journal_path(tmp_path).write_text(json.dumps(payload), encoding="utf-8")
    cfg = _fake_cfg(tmp_path)

    assert preview_journal.recover_stale_preview_journal(cfg) is False
    assert preview_journal.journal_path(tmp_path).exists() is False
    assert cfg.effect == "wave"


def test_validate_journal_payload_accepts_valid_document() -> None:
    snapshot = preview_journal.validate_journal_payload(_valid_journal_payload())

    assert snapshot is not None
    assert snapshot.effect == "wave"
    assert snapshot.speed == 9
    assert snapshot.brightness == 40
    assert snapshot.color == (7, 8, 9)
    assert snapshot.per_key_colors == {(0, 0): (7, 8, 9)}


# --- partial restore retains journal for retry ------------------------------------


class _FlakyConfig:
    """Config double whose setattr fails for selected keys (like persist errors)."""

    def __init__(self, config_dir: Path, fail_keys: frozenset[str] = frozenset()) -> None:
        object.__setattr__(self, "_fail_keys", fail_keys)
        object.__setattr__(self, "CONFIG_DIR", config_dir)
        object.__setattr__(self, "effect", "perkey")
        object.__setattr__(self, "speed", 1)
        object.__setattr__(self, "brightness", 50)
        object.__setattr__(self, "color", (0, 0, 0))
        object.__setattr__(self, "per_key_colors", {(1, 1): (255, 255, 255)})

    def __setattr__(self, name: str, value: object) -> None:
        if name in object.__getattribute__(self, "_fail_keys"):
            raise OSError(f"injected persist failure for {name}")
        object.__setattr__(self, name, value)


def test_apply_snapshot_reports_partial_failure(tmp_path: Path) -> None:
    snapshot = preview_journal.validate_journal_payload(_valid_journal_payload())
    assert snapshot is not None

    assert preview_journal.apply_snapshot_to_config(_fake_cfg(tmp_path), snapshot) is True
    assert preview_journal.apply_snapshot_to_config(_FlakyConfig(tmp_path, frozenset({"color"})), snapshot) is False


def test_partial_recovery_retains_journal_then_later_retry_succeeds(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    preview_journal.write_preview_journal(tmp_path, _valid_journal_payload())
    cfg = _FlakyConfig(tmp_path, frozenset({"brightness"}))

    with caplog.at_level(logging.WARNING, logger="keyrgb.gui.calibrator.guided.journal_recovery"):
        assert preview_journal.recover_stale_preview_journal(cfg) is False

    # Untouched-by-failure fields were restored; the journal is retained.
    assert cfg.effect == "wave"
    assert cfg.brightness == 50
    assert preview_journal.journal_path(tmp_path).exists() is True
    assert any("retained for retry" in record.message for record in caplog.records)

    # A later launch with a healthy config completes the recovery.
    object.__setattr__(cfg, "_fail_keys", frozenset())
    with caplog.at_level(logging.WARNING, logger="keyrgb.gui.calibrator.guided.journal_recovery"):
        assert preview_journal.recover_stale_preview_journal(cfg) is True

    assert cfg.brightness == 40
    assert preview_journal.journal_path(tmp_path).exists() is False


def test_new_preview_session_preserves_originals_from_retained_journal(tmp_path: Path) -> None:
    preview_journal.write_preview_journal(tmp_path, _valid_journal_payload())
    cfg = _FlakyConfig(tmp_path, frozenset({"brightness"}))
    assert preview_journal.recover_stale_preview_journal(cfg) is False

    session = KeyboardPreviewSession(cfg=cfg, rows=2, cols=2)
    object.__setattr__(cfg, "_fail_keys", frozenset())
    session.apply_probe_cell(0, 0)

    assert session.restore() is True
    assert cfg.effect == "wave"
    assert cfg.speed == 9
    assert cfg.brightness == 40
    assert cfg.color == (7, 8, 9)
    assert cfg.per_key_colors == {(0, 0): (7, 8, 9)}
    assert preview_journal.journal_path(tmp_path).exists() is False


def test_preview_restore_partial_failure_retains_journal(tmp_path: Path) -> None:
    cfg = _FlakyConfig(tmp_path, frozenset({"speed"}))
    session = KeyboardPreviewSession(cfg=cfg, rows=2, cols=2)
    session.apply_probe_cell(0, 0)
    assert preview_journal.journal_path(tmp_path).exists() is True

    assert session.restore() is False

    assert preview_journal.journal_path(tmp_path).exists() is True
    assert cfg.speed == 1
    assert cfg.effect == "perkey"


def test_preview_restore_success_returns_true_and_clears(tmp_path: Path) -> None:
    cfg = _fake_cfg(tmp_path)
    session = KeyboardPreviewSession(cfg=cfg, rows=2, cols=2)
    session.apply_probe_cell(0, 0)

    assert session.restore() is True

    assert preview_journal.journal_path(tmp_path).exists() is False


def test_config_dir_of_narrow_helper(tmp_path: Path) -> None:
    assert preview_journal.config_dir_of(_fake_cfg(tmp_path)) == tmp_path
    assert preview_journal.config_dir_of(SimpleNamespace()) is None
    assert preview_journal.config_dir_of(SimpleNamespace(CONFIG_DIR="  ")) is None
    assert preview_journal.config_dir_of(SimpleNamespace(CONFIG_DIR=str(tmp_path))) == tmp_path
