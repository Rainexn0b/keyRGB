from __future__ import annotations

from pathlib import Path

import pytest

from src.core.diagnostics.proc import proc_open_holders
import src.core.diagnostics.proc as proc_mod


class _FakeProcRoot:
    def __init__(self, children: list[object]) -> None:
        self._children = children

    def exists(self) -> bool:
        return True

    def iterdir(self):
        return iter(self._children)


class _ExplodingFdDir:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def exists(self) -> bool:
        return True

    def iterdir(self):
        raise self._exc


class _FakeChild:
    def __init__(self, name: str, *, fd_dir: object) -> None:
        self.name = name
        self._fd_dir = fd_dir

    def is_dir(self) -> bool:
        return True

    def __truediv__(self, part: str) -> object:
        if part != "fd":
            raise AssertionError(f"unexpected child access: {part}")
        return self._fd_dir


class _ExplodingChild:
    name = "999"

    def is_dir(self) -> bool:
        raise RuntimeError("proc iteration failed")


def _patch_proc_root(monkeypatch: pytest.MonkeyPatch, proc_root: object) -> None:
    def fake_path(value: str):
        if value == "/proc":
            return proc_root
        return Path(value)

    monkeypatch.setattr(proc_mod, "Path", fake_path)


def _make_holder(
    base_dir: Path,
    pid: int,
    target_path: Path,
    *,
    comm: str | None = None,
    cmdline: bytes | None = None,
) -> Path:
    holder_root = base_dir / str(pid)
    holder_root.mkdir()
    fd_dir = holder_root / "fd"
    fd_dir.mkdir()
    (fd_dir / "0").symlink_to(target_path)
    if comm is not None:
        (holder_root / "comm").write_text(comm, encoding="utf-8")
    if cmdline is not None:
        (holder_root / "cmdline").write_bytes(cmdline)
    return holder_root


def test_proc_open_holders_stops_after_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target_path = tmp_path / "device0"
    target_path.write_text("device", encoding="utf-8")

    first_holder = _make_holder(tmp_path, 101, target_path, comm="first\n")
    second_holder = _make_holder(tmp_path, 202, target_path, comm="second\n")

    _patch_proc_root(monkeypatch, _FakeProcRoot([first_holder, second_holder]))
    monkeypatch.setattr(proc_mod.os, "getpid", lambda: -1)

    holders = proc_open_holders(target_path, limit=1, pid_limit=10)

    assert holders == [{"pid": 101, "is_self": False, "comm": "first"}]


def test_proc_open_holders_skips_non_numeric_entries_and_stops_at_pid_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "device1"
    target_path.write_text("device", encoding="utf-8")

    proc_file = tmp_path / "meminfo"
    proc_file.write_text("not-a-process", encoding="utf-8")
    non_numeric_dir = tmp_path / "self"
    non_numeric_dir.mkdir()
    missing_fd_dir = tmp_path / "303"
    missing_fd_dir.mkdir()
    matched_holder = _make_holder(tmp_path, 404, target_path, comm="matched\n")
    skipped_by_pid_limit = _make_holder(tmp_path, 505, target_path, comm="late\n")

    proc_root = _FakeProcRoot([proc_file, non_numeric_dir, missing_fd_dir, matched_holder, skipped_by_pid_limit])
    _patch_proc_root(monkeypatch, proc_root)
    monkeypatch.setattr(proc_mod.os, "getpid", lambda: -1)

    holders = proc_open_holders(target_path, limit=10, pid_limit=2)

    assert holders == [{"pid": 404, "is_self": False, "comm": "matched"}]


@pytest.mark.parametrize("exc", [PermissionError("denied"), RuntimeError("boom")])
def test_proc_open_holders_ignores_fd_dir_iteration_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    exc: Exception,
) -> None:
    target_path = tmp_path / "device2"
    target_path.write_text("device", encoding="utf-8")

    proc_root = _FakeProcRoot([_FakeChild("606", fd_dir=_ExplodingFdDir(exc))])
    _patch_proc_root(monkeypatch, proc_root)

    assert proc_open_holders(target_path) == []


def test_proc_open_holders_omits_missing_or_empty_comm_and_cmdline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "missing-device"

    missing_metadata = _make_holder(tmp_path, 707, target_path)
    empty_metadata = _make_holder(tmp_path, 808, target_path, comm="", cmdline=b"")

    _patch_proc_root(monkeypatch, _FakeProcRoot([missing_metadata, empty_metadata]))
    monkeypatch.setattr(proc_mod.os, "getpid", lambda: -1)

    holders = proc_open_holders(target_path, limit=10, pid_limit=10)

    assert holders == [
        {"pid": 707, "is_self": False},
        {"pid": 808, "is_self": False},
    ]


def test_proc_open_holders_omits_exe_and_cmdline_when_metadata_reads_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "device4"
    target_path.write_text("device", encoding="utf-8")

    holder_root = _make_holder(tmp_path, 919, target_path, comm="python\n", cmdline=b"python\x00-m\x00keyrgb\x00")
    exe_target = tmp_path / "python-bin"
    exe_target.write_text("", encoding="utf-8")
    (holder_root / "exe").symlink_to(exe_target)

    _patch_proc_root(monkeypatch, _FakeProcRoot([holder_root]))
    monkeypatch.setattr(proc_mod.os, "getpid", lambda: -1)

    real_resolve = Path.resolve
    real_read_bytes = Path.read_bytes

    def fake_resolve(path: Path, *args: object, **kwargs: object) -> Path:
        if path.name == "exe":
            raise RuntimeError("exe vanished")
        return real_resolve(path, *args, **kwargs)

    def fake_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
        if path.name == "cmdline":
            raise OSError("cmdline vanished")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)
    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    holders = proc_open_holders(target_path, limit=10, pid_limit=10)

    assert holders == [{"pid": 919, "is_self": False, "comm": "python"}]


def test_proc_open_holders_returns_partial_results_on_outer_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "device3"
    target_path.write_text("device", encoding="utf-8")

    matched_holder = _make_holder(tmp_path, 909, target_path)
    proc_root = _FakeProcRoot([matched_holder, _ExplodingChild()])
    _patch_proc_root(monkeypatch, proc_root)
    monkeypatch.setattr(proc_mod.os, "getpid", lambda: -1)

    holders = proc_open_holders(target_path, limit=10, pid_limit=10)

    assert holders == [{"pid": 909, "is_self": False}]
