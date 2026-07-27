from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.perkey.editor as perkey_editor
from src.gui.perkey.editor import PerKeyEditor


class _FakeVar:
    def __init__(self, value) -> None:
        self.value = value
        self.set_calls: list[object] = []

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value
        self.set_calls.append(value)


class _FakeCanvas:
    def __init__(self, *, redraw_error: Exception | None = None, reload_error: Exception | None = None) -> None:
        self.redraw_error = redraw_error
        self.reload_error = reload_error
        self.reload_calls = 0

    def redraw(self) -> None:
        if self.redraw_error is not None:
            raise self.redraw_error

    def reload_backdrop_image(self) -> None:
        self.reload_calls += 1
        if self.reload_error is not None:
            raise self.reload_error


def _capture_logs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple[object, ...], dict[str, object]]]:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_log_throttled(*args, **kwargs) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(perkey_editor, "log_throttled", fake_log_throttled)
    return calls


def test_apply_backdrop_transparency_redraw_logs_boundary_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    editor = SimpleNamespace(
        _backdrop_transparency_redraw_job="job-1",
        canvas=_FakeCanvas(redraw_error=RuntimeError("boom")),
    )

    PerKeyEditor._apply_backdrop_transparency_redraw(editor)

    assert editor._backdrop_transparency_redraw_job is None
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.editor.backdrop_transparency_redraw"
    assert kwargs["msg"] == "Failed to redraw perkey backdrop transparency change"
    assert isinstance(kwargs["exc"], RuntimeError)


def test_apply_backdrop_transparency_redraw_reraises_unexpected_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    editor = SimpleNamespace(
        _backdrop_transparency_redraw_job="job-1",
        canvas=_FakeCanvas(redraw_error=LookupError("unexpected redraw failure")),
    )

    with pytest.raises(LookupError, match="unexpected redraw failure"):
        PerKeyEditor._apply_backdrop_transparency_redraw(editor)

    assert editor._backdrop_transparency_redraw_job is None
    assert logs == []


def test_persist_backdrop_transparency_logs_save_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    editor = SimpleNamespace(
        _backdrop_transparency_save_job="job-2",
        backdrop_transparency=_FakeVar(42),
        profile_name="gaming",
    )

    def fail_save(_value: int, _profile_name: str) -> None:
        raise OSError("save failed")

    monkeypatch.setattr(perkey_editor.profiles, "save_backdrop_transparency", fail_save)

    PerKeyEditor._persist_backdrop_transparency(editor)

    assert editor._backdrop_transparency_save_job is None
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.editor.backdrop_transparency_save"
    assert kwargs["msg"] == "Failed to persist perkey backdrop transparency"
    assert isinstance(kwargs["exc"], OSError)


def test_persist_backdrop_transparency_reraises_unexpected_save_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    editor = SimpleNamespace(
        _backdrop_transparency_save_job="job-2",
        backdrop_transparency=_FakeVar(42),
        profile_name="gaming",
    )

    def fail_save(_value: int, _profile_name: str) -> None:
        raise LookupError("unexpected save failure")

    monkeypatch.setattr(perkey_editor.profiles, "save_backdrop_transparency", fail_save)

    with pytest.raises(LookupError, match="unexpected save failure"):
        PerKeyEditor._persist_backdrop_transparency(editor)

    assert editor._backdrop_transparency_save_job is None
    assert logs == []


def test_on_backdrop_mode_changed_logs_save_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    mode_var = _FakeVar("custom")
    editor = SimpleNamespace(
        _backdrop_mode_var=mode_var,
        profile_name="gaming",
        canvas=_FakeCanvas(),
    )

    monkeypatch.setattr(perkey_editor.profiles, "normalize_backdrop_mode", lambda mode: str(mode))

    def fail_save(_mode: str, _profile_name: str) -> None:
        raise OSError("save failed")

    monkeypatch.setattr(perkey_editor.profiles, "save_backdrop_mode", fail_save)

    PerKeyEditor._on_backdrop_mode_changed(editor)

    assert mode_var.set_calls == ["custom"]
    assert editor.canvas.reload_calls == 0
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.editor.backdrop_mode_save"
    assert kwargs["msg"] == "Failed to persist perkey backdrop mode"
    assert isinstance(kwargs["exc"], OSError)


def test_on_backdrop_mode_changed_logs_reload_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    mode_var = _FakeVar("custom")
    editor = SimpleNamespace(
        _backdrop_mode_var=mode_var,
        profile_name="gaming",
        canvas=_FakeCanvas(reload_error=RuntimeError("reload failed")),
    )

    monkeypatch.setattr(perkey_editor.profiles, "normalize_backdrop_mode", lambda mode: str(mode))
    monkeypatch.setattr(perkey_editor.profiles, "save_backdrop_mode", lambda _mode, _profile_name: None)

    PerKeyEditor._on_backdrop_mode_changed(editor)

    assert mode_var.set_calls == ["custom"]
    assert editor.canvas.reload_calls == 1
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.editor.backdrop_mode_reload"
    assert kwargs["msg"] == "Failed to reload perkey backdrop after mode change"
    assert isinstance(kwargs["exc"], RuntimeError)


def test_on_backdrop_mode_changed_reraises_unexpected_save_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    mode_var = _FakeVar("custom")
    editor = SimpleNamespace(
        _backdrop_mode_var=mode_var,
        profile_name="gaming",
        canvas=_FakeCanvas(),
    )

    monkeypatch.setattr(perkey_editor.profiles, "normalize_backdrop_mode", lambda mode: str(mode))

    def fail_save(_mode: str, _profile_name: str) -> None:
        raise LookupError("unexpected save failure")

    monkeypatch.setattr(perkey_editor.profiles, "save_backdrop_mode", fail_save)

    with pytest.raises(LookupError, match="unexpected save failure"):
        PerKeyEditor._on_backdrop_mode_changed(editor)

    assert mode_var.set_calls == ["custom"]
    assert editor.canvas.reload_calls == 0
    assert logs == []


def test_on_backdrop_mode_changed_reraises_unexpected_reload_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)
    mode_var = _FakeVar("custom")
    editor = SimpleNamespace(
        _backdrop_mode_var=mode_var,
        profile_name="gaming",
        canvas=_FakeCanvas(reload_error=LookupError("unexpected reload failure")),
    )

    monkeypatch.setattr(perkey_editor.profiles, "normalize_backdrop_mode", lambda mode: str(mode))
    monkeypatch.setattr(perkey_editor.profiles, "save_backdrop_mode", lambda _mode, _profile_name: None)

    with pytest.raises(LookupError, match="unexpected reload failure"):
        PerKeyEditor._on_backdrop_mode_changed(editor)

    assert mode_var.set_calls == ["custom"]
    assert editor.canvas.reload_calls == 1
    assert logs == []


def test_detect_lightbar_device_logs_discovery_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)

    def fail_collect(*, include_usb: bool):
        assert include_usb is True
        raise RuntimeError("discovery failed")

    monkeypatch.setattr(perkey_editor, "collect_device_discovery", fail_collect)

    assert PerKeyEditor._detect_lightbar_device(SimpleNamespace()) is False
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.editor.lightbar_discovery"
    assert kwargs["msg"] == "Failed to collect perkey lightbar discovery snapshot"
    assert isinstance(kwargs["exc"], RuntimeError)


def test_detect_lightbar_device_propagates_unexpected_discovery_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logs = _capture_logs(monkeypatch)

    def fail_collect(*, include_usb: bool):
        assert include_usb is True
        raise AssertionError("unexpected discovery bug")

    monkeypatch.setattr(perkey_editor, "collect_device_discovery", fail_collect)

    with pytest.raises(AssertionError, match="unexpected discovery bug"):
        PerKeyEditor._detect_lightbar_device(SimpleNamespace())

    assert logs == []
