from __future__ import annotations

from types import SimpleNamespace

from src.gui.perkey import editor as editor_module


def test_perkey_editor_close_releases_device_and_hardware_lock(monkeypatch) -> None:
    calls: list[str] = []
    editor = editor_module.PerKeyEditor.__new__(editor_module.PerKeyEditor)
    editor.kb = SimpleNamespace(close=lambda: calls.append("device:close"))
    editor.root = SimpleNamespace(destroy=lambda: calls.append("root:destroy"))
    monkeypatch.setattr(editor_module.dirty_state, "confirm_destructive_action", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(editor_module.hardware, "release_hardware_control", lambda: calls.append("lock:release"))

    editor._on_close()

    assert calls == ["device:close", "lock:release", "root:destroy"]
    assert editor.kb is None
