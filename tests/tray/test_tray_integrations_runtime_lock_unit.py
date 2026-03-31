from __future__ import annotations

import builtins
from pathlib import Path


def test_acquire_single_instance_lock_returns_true_when_fcntl_missing(
    monkeypatch,
) -> None:
    import src.tray.integrations.runtime as runtime

    orig_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fcntl":
            raise ImportError("no fcntl")
        return orig_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert runtime.acquire_single_instance_lock() is True


def test_acquire_single_instance_lock_creates_lock_file_and_writes_pid(monkeypatch, tmp_path) -> None:
    import src.tray.integrations.runtime as runtime

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(runtime, "_instance_lock_fh", None)

    ok = runtime.acquire_single_instance_lock()
    assert ok is True

    lock_path = Path(tmp_path) / "keyrgb.lock"
    assert lock_path.exists()
    txt = lock_path.read_text(encoding="utf-8")
    assert txt.startswith("pid=")


def test_acquire_single_instance_lock_returns_false_if_already_locked(monkeypatch, tmp_path) -> None:
    import fcntl
    import src.tray.integrations.runtime as runtime

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(runtime, "_instance_lock_fh", None)

    lock_path = Path(tmp_path) / "keyrgb.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Hold the lock in this test process with a different file handle.
    with open(lock_path, "a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert runtime.acquire_single_instance_lock() is False

        # Keep the lock held until after the call.
        fh.flush()

    # Sanity: after closing, acquiring should succeed.
    assert runtime.acquire_single_instance_lock() is True
