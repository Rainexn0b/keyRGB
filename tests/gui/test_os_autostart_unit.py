from __future__ import annotations

from pathlib import Path

import pytest

import src.gui.settings.os_autostart as os_autostart


def test_autostart_desktop_path_uses_home_config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(os_autostart.Path, "home", lambda: tmp_path)

    assert os_autostart.autostart_desktop_path() == tmp_path / ".config" / "autostart" / "keyrgb.desktop"


def test_detect_os_autostart_enabled_reflects_file_existence(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakePath:
        def __init__(self, *, exists_result: bool = False, exists_error: Exception | None = None) -> None:
            self.exists_result = exists_result
            self.exists_error = exists_error

        def exists(self) -> bool:
            if self.exists_error is not None:
                raise self.exists_error
            return self.exists_result

    monkeypatch.setattr(os_autostart, "autostart_desktop_path", lambda: _FakePath(exists_result=True))
    assert os_autostart.detect_os_autostart_enabled() is True

    monkeypatch.setattr(os_autostart, "autostart_desktop_path", lambda: _FakePath(exists_result=False))
    assert os_autostart.detect_os_autostart_enabled() is False

    monkeypatch.setattr(os_autostart, "autostart_desktop_path", lambda: _FakePath(exists_error=RuntimeError("boom")))
    assert os_autostart.detect_os_autostart_enabled() is False


def test_set_os_autostart_disables_by_unlinking(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakePath:
        def __init__(self) -> None:
            self.unlink_calls: list[bool] = []
            self.parent = self

        def unlink(self, *, missing_ok: bool) -> None:
            self.unlink_calls.append(bool(missing_ok))

    fake_path = _FakePath()
    monkeypatch.setattr(os_autostart, "autostart_desktop_path", lambda: fake_path)

    os_autostart.set_os_autostart(False)

    assert fake_path.unlink_calls == [True]


def test_set_os_autostart_enables_and_writes_desktop_file(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeParent:
        def __init__(self) -> None:
            self.mkdir_calls: list[tuple[bool, bool]] = []

        def mkdir(self, *, parents: bool, exist_ok: bool) -> None:
            self.mkdir_calls.append((bool(parents), bool(exist_ok)))

    class _FakePath:
        def __init__(self) -> None:
            self.parent = _FakeParent()
            self.writes: list[tuple[str, str]] = []

        def write_text(self, text: str, *, encoding: str) -> None:
            self.writes.append((text, encoding))

    fake_path = _FakePath()
    monkeypatch.setattr(os_autostart, "autostart_desktop_path", lambda: fake_path)

    os_autostart.set_os_autostart(True)

    assert fake_path.parent.mkdir_calls == [(True, True)]
    assert fake_path.writes == [
        (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=KeyRGB\n"
            "Comment=Keyboard RGB tray\n"
            "Exec=keyrgb\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            "utf-8",
        )
    ]