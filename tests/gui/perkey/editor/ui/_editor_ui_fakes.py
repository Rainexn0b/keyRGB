"""Shared fakes for per-key editor UI unit-test modules."""

from __future__ import annotations

from tests.gui.perkey.editor.ui.fakes._controls import (
    _FakeEditor,
    _FakeLayoutSetupControls,
    _FakeLightbarControls,
    _FakeLightingAreasPanel,
    _FakeOptionalKeysControls,
    _FakeOverlayControls,
)
from tests.gui.perkey.editor.ui.fakes._install import _build_ui, _install_fake_ui
from tests.gui.perkey.editor.ui.fakes._widgets import (
    _FakeColorWheel,
    _FakeKeyboardCanvas,
    _FakeRoot,
    _FakeVar,
    _FakeWidget,
)

__all__ = [
    "_FakeColorWheel",
    "_FakeEditor",
    "_FakeKeyboardCanvas",
    "_FakeLayoutSetupControls",
    "_FakeLightbarControls",
    "_FakeLightingAreasPanel",
    "_FakeOptionalKeysControls",
    "_FakeOverlayControls",
    "_FakeRoot",
    "_FakeVar",
    "_FakeWidget",
    "_build_ui",
    "_install_fake_ui",
]
