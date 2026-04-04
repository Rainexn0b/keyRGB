from __future__ import annotations

import importlib
import runpy

import pytest


@pytest.mark.parametrize(
    ("run_module_name", "target_module_name"),
    [
        ("src.gui.calibrator.__main__", "src.gui.calibrator.app"),
        ("src.gui.perkey.__main__", "src.gui.perkey.editor"),
        ("src.gui.settings.__main__", "src.gui.settings.window"),
    ],
)
def test_gui_module_trampolines_invoke_main(
    monkeypatch: pytest.MonkeyPatch,
    run_module_name: str,
    target_module_name: str,
) -> None:
    target_module = importlib.import_module(target_module_name)
    called: list[str] = []

    monkeypatch.setattr(target_module, "main", lambda: called.append(run_module_name))

    runpy.run_module(run_module_name, run_name="__main__")

    assert called == [run_module_name]
