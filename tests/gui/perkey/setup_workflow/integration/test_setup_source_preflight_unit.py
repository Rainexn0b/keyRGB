"""Guided-setup source capture and preflight unit tests.

Split out of ``test_setup_integration_unit.py`` to keep test modules under
the LOC gate. Assertions are unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from keyrgb.gui.perkey.setup_workflow import integration
from keyrgb.gui.perkey.setup_workflow.integration import (
    capture_setup_source,
    collect_preflight_evidence,
    config_is_writable,
    is_tray_managed,
    resolve_setup_preflight,
    snapshot_declares_per_key,
)
from keyrgb.gui.perkey.setup_workflow.model import SetupSource
from keyrgb.gui.perkey.setup_workflow.preflight import PreflightMode, PreflightReason
from tests.gui.perkey.setup_workflow._setup_fakes import (
    COLS,
    ROWS,
    VALID_KEYMAP,
    FakeBackend,
    FakeConfig,
    FakeEditor,
    FakeHardwareModule,
    FakeKb,
    _snapshot_env,
)

# -- source capture ----------------------------------------------------


def test_capture_setup_source_reads_editor_fields_without_mutating(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    source = capture_setup_source(editor)

    assert isinstance(source, SetupSource)
    assert source.physical_layout == "ansi"
    assert source.legend_pack == "auto"
    assert source.profile_name == "default"
    assert dict(source.keymap or {}) == VALID_KEYMAP
    assert editor.keymap == VALID_KEYMAP  # untouched


def test_capture_setup_source_tolerates_missing_fields() -> None:
    source = capture_setup_source(object())

    assert source.physical_layout == ""
    assert source.keymap is None


# -- preflight evidence -------------------------------------------------


def test_tray_snapshot_per_key_goes_live(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    result = resolve_setup_preflight(editor, env=_snapshot_env(per_key=True), hardware_module=FakeHardwareModule(None))

    assert result.mode is PreflightMode.LIVE_PREVIEW
    assert result.reason is PreflightReason.OK
    assert (result.rows, result.cols) == (ROWS, COLS)


def test_tray_snapshot_brightness_only_stays_config_only_with_warning(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    result = resolve_setup_preflight(
        editor, env=_snapshot_env(per_key=False), hardware_module=FakeHardwareModule(FakeBackend())
    )

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.UNSUPPORTED_BACKEND
    assert "live key flashing is unavailable" in result.message


def test_standalone_per_key_backend_never_goes_live(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.kb = FakeKb(with_writer=True)
    hardware = FakeHardwareModule(FakeBackend(per_key=True))

    result = resolve_setup_preflight(editor, env={}, hardware_module=hardware)

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.mode is not PreflightMode.LIVE_PREVIEW
    assert "live key flashing is unavailable" in result.message


def test_standalone_without_backend_degrades_to_no_backend(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    result = resolve_setup_preflight(editor, env={}, hardware_module=FakeHardwareModule(None))

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.NO_BACKEND


def test_brightness_only_backend_with_writer_never_upgrades(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.kb = FakeKb(with_writer=True)
    hardware = FakeHardwareModule(FakeBackend(per_key=False))

    evidence = collect_preflight_evidence(editor, env={"KEYRGB_TRAY_MANAGED_GUI": "1"}, hardware_module=hardware)
    result = resolve_setup_preflight(editor, env={"KEYRGB_TRAY_MANAGED_GUI": "1"}, hardware_module=hardware)

    assert evidence.has_per_key_writer is True
    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.UNSUPPORTED_BACKEND


def test_malformed_snapshot_falls_back_without_probing(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    result = resolve_setup_preflight(
        editor,
        env={integration.PREFLIGHT_ENV_VAR: "{not-json"},
        hardware_module=FakeHardwareModule(None),
    )

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.NO_BACKEND


def test_unmanaged_per_key_snapshot_does_not_go_live(tmp_path: Path) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))

    result = resolve_setup_preflight(
        editor, env=_snapshot_env(per_key=True, tray_managed=False), hardware_module=FakeHardwareModule(None)
    )

    assert result.mode is PreflightMode.CONFIG_ONLY


def test_snapshot_declares_per_key_only_for_tray_snapshot() -> None:
    assert snapshot_declares_per_key(_snapshot_env(per_key=True)) is True
    assert snapshot_declares_per_key(_snapshot_env(per_key=False)) is False
    assert snapshot_declares_per_key(_snapshot_env(per_key=True, tray_managed=False)) is True
    assert snapshot_declares_per_key({}) is False
    assert is_tray_managed(_snapshot_env(per_key=True)) is True
    assert is_tray_managed({}) is False


def test_config_unwritable_blocks_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    editor = FakeEditor(FakeConfig(tmp_path))
    monkeypatch.setattr(os, "access", lambda *args, **kwargs: False)

    assert config_is_writable(editor.config) is False
    result = resolve_setup_preflight(editor, env=_snapshot_env(per_key=True), hardware_module=FakeHardwareModule(None))

    assert result.mode is PreflightMode.BLOCKED
    assert result.reason is PreflightReason.CONFIG_UNWRITABLE


def test_config_writable_for_normal_location(tmp_path: Path) -> None:
    assert config_is_writable(FakeConfig(tmp_path)) is True
    assert config_is_writable(object()) is True  # undeterminable fails open
