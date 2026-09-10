"""Fake-Tk doubles for the guided-setup wizard unit tests.

Split out of ``test_setup_wizard_unit.py`` to keep test modules under the
LOC gate. Covers the ``FakeDialog`` modal double plus the fake ``tk``/``ttk``
shell used to drive the real ``GuidedSetupWizard`` headlessly.
"""

from __future__ import annotations

import tkinter as real_tk
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from keyrgb.gui.perkey.setup_workflow import wizard as wizard_module
from keyrgb.gui.perkey.setup_workflow.integration import (
    GuidedSetupController,
    SetupStep,
    build_setup_commit_callbacks,
    capture_setup_source,
    resolve_setup_preflight,
)
from keyrgb.gui.perkey.setup_workflow.model import draft_from_source
from keyrgb.gui.perkey.setup_workflow.wizard import GuidedSetupWizard, open_guided_setup
from tests.gui.perkey.setup_workflow._setup_fakes import (
    FakeBackend,
    FakeConfig,
    FakeEditor,
    FakeHardwareModule,
    FakeProfiles,
    _snapshot_env,
)


class FakeDialog:
    """Fake-Tk modal double honoring the wizard lifetime contract."""

    instances: ClassVar[list[FakeDialog]] = []

    def __init__(self, editor: object, controller: GuidedSetupController, launcher: Any = None) -> None:
        self.editor = editor
        self.controller = controller
        self.launcher = launcher
        self.alive = True
        self.focus_calls = 0
        self.finished: list[bool] = []
        FakeDialog.instances.append(self)

    def is_alive(self) -> bool:
        return self.alive

    def focus(self) -> None:
        self.focus_calls += 1

    # Fake modal navigation driving the real controller (never persists).
    def press_next(self) -> bool:
        return self.controller.go_next()

    def press_back(self) -> bool:
        return self.controller.go_back()

    def press_cancel(self) -> bool:
        allowed, _ = self.controller.close_allowed()
        if allowed:
            self.alive = False
        return allowed

    def press_finish(self, profiles: FakeProfiles) -> Any:
        editor = self.editor
        assert isinstance(editor, FakeEditor)
        callbacks = build_setup_commit_callbacks(
            editor, self.controller.draft, config_only=self.controller.config_only, profiles_module=profiles
        )
        result = self.controller.finish(callbacks)
        self.finished.append(result.ok)
        if result.ok:
            self.alive = False
        return result


def _open(
    editor: FakeEditor,
    *,
    env: dict[str, str] | None = None,
    launcher: Any = None,
    hardware_module: Any | None = None,
) -> FakeDialog:
    FakeDialog.instances.clear()
    dialog = open_guided_setup(
        editor,
        dialog_class=FakeDialog,  # type: ignore[arg-type]
        launcher=launcher,
        env=dict(env) if env is not None else _snapshot_env(per_key=False),
        hardware_module=hardware_module if hardware_module is not None else FakeHardwareModule(FakeBackend()),
    )
    assert isinstance(dialog, FakeDialog)
    return dialog


# -- real GuidedSetupWizard headless coverage ----------------------------------
#
# The blocks below drive the real ``GuidedSetupWizard`` (not ``FakeDialog``)
# with fake ``tk``/``ttk`` modules so every page renderer, nav state, harvest
# path, child-poll path, and Finish path executes without a display.


class _WWVar:
    def __init__(self, value: Any = "") -> None:
        self._value = value

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value


class _WWBooleanVar(_WWVar):
    def __init__(self, value: Any = False) -> None:
        super().__init__(bool(value))


class _WWWidget:
    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        self.parent = parent
        self.options: dict[str, Any] = dict(kwargs)
        self.configure_calls: list[dict[str, Any]] = []
        self.grid_calls: list[dict[str, Any]] = []
        self.bind_calls: list[tuple[str, Any]] = []
        self.children: list[_WWWidget] = []
        if hasattr(parent, "children"):
            parent.children.append(self)

    def configure(self, **kwargs: Any) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    config = configure

    def grid(self, **kwargs: Any) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, event: str, callback: Any, add: Any = None) -> None:
        self.bind_calls.append((event, callback))

    def destroy(self) -> None:
        parent_children = getattr(self.parent, "children", None)
        if isinstance(parent_children, list) and self in parent_children:
            parent_children.remove(self)

    def winfo_children(self) -> list[_WWWidget]:
        return list(self.children)


class _WWToplevel(_WWWidget):
    raise_on: ClassVar[set[str]] = set()

    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self.destroyed = False
        self.title_calls: list[str] = []
        self.protocol_calls: list[tuple[str, Any]] = []
        self.grab_calls = 0
        self.release_calls = 0
        self.lift_calls = 0
        self.focus_calls = 0

    def _maybe_raise(self, name: str) -> None:
        if name in type(self).raise_on:
            raise RuntimeError(f"fake {name} failure")

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def transient(self, parent: Any = None) -> None:
        self._maybe_raise("transient")

    def protocol(self, name: str, callback: Any) -> None:
        self._maybe_raise("protocol")
        self.protocol_calls.append((name, callback))

    def grab_set(self) -> None:
        self._maybe_raise("grab_set")
        self.grab_calls += 1

    def grab_release(self) -> None:
        self._maybe_raise("grab_release")
        self.release_calls += 1

    def destroy(self) -> None:
        self._maybe_raise("destroy")
        self.destroyed = True

    def lift(self) -> None:
        self._maybe_raise("lift")
        self.lift_calls += 1

    def focus_force(self) -> None:
        self._maybe_raise("focus_force")
        self.focus_calls += 1

    def winfo_exists(self) -> bool:
        self._maybe_raise("winfo_exists")
        return not self.destroyed

    def columnconfigure(self, index: int, **kwargs: Any) -> None:
        return None

    def rowconfigure(self, index: int, **kwargs: Any) -> None:
        return None


class _WWCombo(_WWWidget):
    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self.values: list[str] = list(kwargs.get("values", []) or [])
        self.current: str = ""
        self.set_calls: list[str] = []

    def set(self, value: str) -> None:
        self.set_calls.append(value)
        self.current = value

    def get(self) -> str:
        return self.current


class _WWEntry(_WWWidget):
    def __init__(self, parent: Any = None, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self._text = ""
        self.fail_get = False

    def insert(self, index: Any, text: str) -> None:
        self._text = str(text)

    def get(self) -> str:
        if self.fail_get:
            raise RuntimeError("fake entry get failure")
        return self._text


class _WWRoot:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, Any]] = []
        self.cancel_calls: list[Any] = []
        self.fail_after = False
        self.fail_cancel = False
        self._jobs = 0

    def after(self, delay_ms: int, callback: Any) -> int:
        if self.fail_after:
            raise RuntimeError("fake after failure")
        self._jobs += 1
        self.after_calls.append((delay_ms, callback))
        return self._jobs

    def after_cancel(self, job: Any) -> None:
        if self.fail_cancel:
            raise RuntimeError("fake cancel failure")
        self.cancel_calls.append(job)


def _install_wizard_fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    registry: dict[str, list[Any]] = {"toplevels": [], "combos": [], "entries": [], "buttons": []}
    real_toplevel = _WWToplevel
    real_combo = _WWCombo
    real_entry = _WWEntry

    class FakeToplevel(_WWToplevel):
        def __init__(self, parent: Any = None, **kwargs: Any) -> None:
            super().__init__(parent, **kwargs)
            registry["toplevels"].append(self)

    class FakeFrame(_WWWidget):
        pass

    class FakeLabel(_WWWidget):
        pass

    class FakeButton(_WWWidget):
        def __init__(self, parent: Any = None, **kwargs: Any) -> None:
            super().__init__(parent, **kwargs)
            registry["buttons"].append(self)

    class FakeCombobox(_WWCombo):
        def __init__(self, parent: Any = None, **kwargs: Any) -> None:
            real_combo.__init__(self, parent, **kwargs)
            registry["combos"].append(self)

    class FakeCheckbutton(_WWWidget):
        pass

    class FakeEntry(_WWEntry):
        def __init__(self, parent: Any = None, **kwargs: Any) -> None:
            real_entry.__init__(self, parent, **kwargs)
            registry["entries"].append(self)

    _ = real_toplevel
    monkeypatch.setattr(
        wizard_module,
        "tk",
        SimpleNamespace(
            Toplevel=FakeToplevel,
            StringVar=_WWVar,
            BooleanVar=_WWBooleanVar,
            TclError=real_tk.TclError,
        ),
    )
    monkeypatch.setattr(
        wizard_module,
        "ttk",
        SimpleNamespace(
            Frame=FakeFrame,
            Label=FakeLabel,
            Button=FakeButton,
            Combobox=FakeCombobox,
            Checkbutton=FakeCheckbutton,
            Entry=FakeEntry,
        ),
    )
    return registry


def _real_controller(editor: FakeEditor, *, live: bool) -> GuidedSetupController:
    draft = draft_from_source(capture_setup_source(editor))
    hardware: Any = FakeHardwareModule(None) if live else FakeHardwareModule(FakeBackend())
    preflight = resolve_setup_preflight(editor, env=dict(_snapshot_env(per_key=live)), hardware_module=hardware)
    return GuidedSetupController(draft=draft, preflight=preflight, rows=preflight.rows, cols=preflight.cols)


def _make_real_wizard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    live: bool = False,
    launcher: Any = None,
) -> tuple[GuidedSetupWizard, FakeEditor, GuidedSetupController, dict[str, list[Any]]]:
    registry = _install_wizard_fakes(monkeypatch)
    editor = FakeEditor(FakeConfig(tmp_path))
    editor.root = _WWRoot()  # type: ignore[attr-defined]
    controller = _real_controller(editor, live=live)
    wizard = GuidedSetupWizard(editor, controller, launcher=launcher)
    return wizard, editor, controller, registry


def _step_index(controller: GuidedSetupController, step: SetupStep) -> int:
    return list(controller.steps).index(step)
