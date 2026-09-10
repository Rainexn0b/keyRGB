"""Unit coverage for guided app behavior: save routing, close, main argv, button copy."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from keyrgb.gui import single_instance
from keyrgb.gui.calibrator import _app_bootstrap as boot, _app_logic, app as calibrator_app
from keyrgb.gui.calibrator.guided import GuidedSessionError


class _FakeLabel:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)


def _standalone_app(**overrides: object) -> SimpleNamespace:
    app = SimpleNamespace(
        profile_name="gaming",
        lbl_status=_FakeLabel(),
        keymap={"esc": ((0, 0),)},
        cfg=SimpleNamespace(physical_layout="ansi"),
        guided_session_path=None,
    )
    for name, value in overrides.items():
        setattr(app, name, value)
    return app


def _guided_app(session_path: Path, **overrides: object) -> SimpleNamespace:
    return _standalone_app(guided_session_path=session_path, **overrides)


# --- save routing ---------------------------------------------------------------


def test_guided_save_writes_session_result_not_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps({"physical_layout": "ansi"}), encoding="utf-8")
    app = _guided_app(session_path)

    def _forbid_profile_save(*args: object, **kwargs: object) -> None:
        raise AssertionError("guided save must not touch profile storage")

    monkeypatch.setattr(calibrator_app, "_save_keymap", _forbid_profile_save)
    monkeypatch.setattr(calibrator_app, "_keymap_path", _forbid_profile_save)

    calibrator_app.KeymapCalibrator._save(app)

    payload = json.loads(session_path.read_text(encoding="utf-8"))
    assert payload["result"]["keymap"] == {"frow_00": "0,0"}
    assert payload["result"]["physical_layout"] == "ansi"
    assert app.lbl_status.options["text"] == f"Wrote result to {session_path!s}"


def test_standalone_save_still_writes_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _standalone_app()
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(
        calibrator_app,
        "_save_keymap",
        lambda keymap, **kwargs: calls.append((keymap, kwargs)),
    )
    monkeypatch.setattr(calibrator_app, "_keymap_path", lambda: tmp_path / "keymap.json")

    calibrator_app.KeymapCalibrator._save(app)

    assert calls == [({"esc": ((0, 0),)}, {"physical_layout": "ansi"})]
    assert app.lbl_status.options["text"] == f"Saved to {tmp_path / 'keymap.json'!s}"


def test_legacy_fake_without_guided_attr_stays_standalone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unbound-method fakes predating guided mode keep profile Save behavior."""

    app = SimpleNamespace(
        lbl_status=_FakeLabel(),
        keymap={"esc": ((0, 0),)},
        cfg=SimpleNamespace(physical_layout="ansi"),
    )
    calls: list[object] = []
    monkeypatch.setattr(calibrator_app, "_save_keymap", lambda keymap, **kwargs: calls.append(keymap))
    monkeypatch.setattr(calibrator_app, "_keymap_path", lambda: tmp_path / "keymap.json")

    calibrator_app.KeymapCalibrator._save(app)

    assert calls == [{"esc": ((0, 0),)}]


def test_save_guided_result_logic_never_calls_profile_save() -> None:
    session_path = Path("/tmp/guided-session.json")
    writes: list[tuple[object, object, object]] = []
    app = SimpleNamespace(
        keymap={"esc": ((0, 0),)},
        lbl_status=_FakeLabel(),
    )

    _app_logic.save_guided_result(
        app,
        session_path=session_path,
        physical_layout="ansi",
        write_result_fn=lambda path, keymap, **kwargs: writes.append((path, keymap, kwargs)) or session_path,
    )

    assert writes == [(session_path, {"esc": ((0, 0),)}, {"physical_layout": "ansi"})]
    assert app.lbl_status.options["text"] == f"Wrote result to {session_path!s}"


# --- close without using result ---------------------------------------------------


def test_close_without_save_leaves_session_result_absent(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps({"physical_layout": "ansi"}), encoding="utf-8")
    writes: list[object] = []
    destroyed: list[str] = []
    app = SimpleNamespace(
        guided_session_path=session_path,
        _restore_original_config=lambda: None,
        destroy=lambda: destroyed.append("destroy"),
    )

    _app_logic.on_close(app)

    assert destroyed == ["destroy"]
    assert writes == []
    assert "result" not in json.loads(session_path.read_text(encoding="utf-8"))


# --- main argv ----------------------------------------------------------------------


def test_main_rejects_malformed_session_without_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    acquired: list[str] = []
    monkeypatch.setattr(single_instance, "acquire_gui_instance_or_exit", acquired.append)
    monkeypatch.setattr(calibrator_app, "KeymapCalibrator", lambda **kwargs: (_ for _ in ()).throw(AssertionError()))

    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        calibrator_app.main(["--guided-session", str(bad)])

    assert exc_info.value.code == 2
    assert acquired == []
    assert "keyrgb-calibrate" in capsys.readouterr().err


def test_main_rejects_unknown_flags_before_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    acquired: list[str] = []
    monkeypatch.setattr(single_instance, "acquire_gui_instance_or_exit", acquired.append)

    with pytest.raises(SystemExit) as exc_info:
        calibrator_app.main(["--nope"])

    assert exc_info.value.code == 2
    assert acquired == []


def test_main_standalone_acquires_calibrator_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    acquired: list[str] = []
    created: list[dict[str, object]] = []
    monkeypatch.setattr(single_instance, "acquire_gui_instance_or_exit", acquired.append)
    monkeypatch.setattr(calibrator_app.Config, "CONFIG_DIR", Path("/tmp/keyrgb-test-config"))
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)

    class _FakeApp:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

        def mainloop(self) -> None:
            created.append({"mainloop": True})

    monkeypatch.setattr(calibrator_app, "KeymapCalibrator", _FakeApp)

    calibrator_app.main([])

    assert acquired == ["calibrator"]
    assert created[0] == {"guided_session_path": None, "guided_session": None}


def test_main_guided_loads_once_and_passes_session_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acquired: list[str] = []
    created: list[dict[str, object]] = []
    monkeypatch.setattr(single_instance, "acquire_gui_instance_or_exit", acquired.append)
    monkeypatch.setattr(calibrator_app.Config, "CONFIG_DIR", Path("/tmp/keyrgb-test-config"))
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)

    class _FakeApp:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)

        def mainloop(self) -> None:
            created.append({"mainloop": True})

    monkeypatch.setattr(calibrator_app, "KeymapCalibrator", _FakeApp)

    loads: list[str] = []
    real_load = calibrator_app.load_guided_session

    def _counting_load(path: object, **kwargs: object):
        loads.append(str(path))
        return real_load(path, **kwargs)

    monkeypatch.setattr(calibrator_app, "load_guided_session", _counting_load)

    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps({"physical_layout": "ansi", "keymap": {"esc": [[0, 0]]}}), encoding="utf-8")

    calibrator_app.main(["--guided-session", str(session_path)])

    assert acquired == ["calibrator"]
    # Single validation load in main; the constructor receives it (no double read).
    assert loads == [str(session_path)]
    assert created[0]["guided_session_path"] == session_path
    assert isinstance(created[0]["guided_session"], calibrator_app.GuidedSession)
    assert created[0]["guided_session"].source_path == session_path
    assert created[0]["guided_session"].physical_layout == "ansi"


def test_main_help_prints_usage_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    acquired: list[str] = []
    monkeypatch.setattr(single_instance, "acquire_gui_instance_or_exit", acquired.append)

    assert calibrator_app.main(["--help"]) is None
    assert calibrator_app.main(["-h"]) is None

    out = capsys.readouterr().out
    assert "usage: keyrgb-calibrate" in out
    assert "--guided-session PATH" in out
    assert acquired == []


def test_parse_help_flags_raise_help_request() -> None:
    from keyrgb.gui.calibrator.guided import GuidedSessionHelpRequested, parse_guided_session_argv

    with pytest.raises(GuidedSessionHelpRequested):
        parse_guided_session_argv(["--help"])
    with pytest.raises(GuidedSessionHelpRequested):
        parse_guided_session_argv(["-h", "--guided-session", "x.json"])


# --- button copy ----------------------------------------------------------------------


class _Widget:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def grid(self, *args: object, **kwargs: object) -> None:
        return None

    def bind(self, *args: object, **kwargs: object) -> None:
        return None

    def configure(self, **kwargs: object) -> None:
        return None

    def columnconfigure(self, *args: object, **kwargs: object) -> None:
        return None

    def rowconfigure(self, *args: object, **kwargs: object) -> None:
        return None

    def winfo_width(self) -> int:
        return 300


class _FakeTk:
    def __init__(self, widgets: list[_Widget]) -> None:
        self._widgets = widgets

    def Canvas(self, *args: object, **kwargs: object) -> _Widget:
        widget = _Widget(**kwargs)
        self._widgets.append(widget)
        return widget

    def BooleanVar(self, *args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(value=True, get=lambda: True)


class _FakeTtk:
    def __init__(self, widgets: list[_Widget]) -> None:
        self._widgets = widgets

    def Frame(self, *args: object, **kwargs: object) -> _Widget:
        widget = _Widget(**kwargs)
        self._widgets.append(widget)
        return widget

    def Label(self, *args: object, **kwargs: object) -> _Widget:
        widget = _Widget(**kwargs)
        self._widgets.append(widget)
        return widget

    def Button(self, *args: object, **kwargs: object) -> _Widget:
        widget = _Widget(**kwargs)
        self._widgets.append(widget)
        return widget

    def Checkbutton(self, *args: object, **kwargs: object) -> _Widget:
        widget = _Widget(**kwargs)
        self._widgets.append(widget)
        return widget


def _button_texts(**build_kwargs: object) -> list[str]:
    widgets: list[_Widget] = []
    app = SimpleNamespace(
        bg_color="#101010",
        _redraw=lambda: None,
        _on_click=lambda event: None,
        _prev=lambda: None,
        _next=lambda: None,
        _assign=lambda: None,
        _skip=lambda: None,
        _on_show_backdrop_changed=lambda: None,
        _reset_keymap_defaults=lambda: None,
        _save=lambda: None,
        _save_and_close=lambda: None,
        _on_close=lambda: None,
        columnconfigure=lambda *args, **kwargs: None,
        rowconfigure=lambda *args, **kwargs: None,
        bind=lambda *args, **kwargs: None,
        after=lambda *args, **kwargs: None,
    )
    boot.build_widgets(
        app,
        tk=_FakeTk(widgets),
        ttk=_FakeTtk(widgets),
        tk_runtime_errors=(RuntimeError,),
        wrap_sync_errors=(RuntimeError,),
        **build_kwargs,
    )
    return [str(widget.kwargs.get("text", "")) for widget in widgets if "text" in widget.kwargs]


def test_standalone_button_copy_is_unchanged() -> None:
    texts = _button_texts()

    assert "Save" in texts
    assert "Save && Close" in texts
    assert "Use Result" not in texts


def test_guided_button_copy_prefers_use_result() -> None:
    texts = _button_texts(save_text="Use Result", save_and_close_text="Use Result && Close")

    assert "Use Result" in texts
    assert "Use Result && Close" in texts


def test_guided_session_error_is_a_value_error() -> None:
    assert issubclass(GuidedSessionError, ValueError)
