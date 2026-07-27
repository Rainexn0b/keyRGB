from __future__ import annotations

import fcntl

from src.core.runtime import hardware_ownership


def test_hardware_control_lock_is_exclusive_and_releasable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    hardware_ownership.release_hardware_control_lock()

    assert hardware_ownership.acquire_hardware_control_lock() is True
    lock_path = tmp_path / "keyrgb.lock"
    assert lock_path.read_text(encoding="utf-8").startswith("pid=")

    hardware_ownership.release_hardware_control_lock()
    with lock_path.open("a+", encoding="utf-8") as external_lock:
        fcntl.flock(external_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert hardware_ownership.acquire_hardware_control_lock() is False

    assert hardware_ownership.acquire_hardware_control_lock() is True
    hardware_ownership.release_hardware_control_lock()
