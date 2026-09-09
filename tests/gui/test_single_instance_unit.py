from __future__ import annotations

import fcntl
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from keyrgb.gui import single_instance
from keyrgb.gui.single_instance import (
    acquire_gui_instance_lock,
    acquire_gui_instance_or_exit,
    gui_instance_lock_path,
    release_all_gui_instance_locks,
    release_gui_instance_lock,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

VALID_IDENTITIES = [
    "settings",
    "reactive-color",
    "power-mode",
    "support",
    "perkey",
    "calibrator",
    "uniform-keyboard",
    "uniform-secondary-1",
]

INVALID_IDENTITIES = [
    "",
    "unknown",
    "settings ",
    " settings",
    "a/b",
    "a\\b",
    "..",
    "../settings",
    "settings/../x",
    ".",
    "uniform-",
    "uniform--x",
    "uniform-_x",
    "uniform-x_y",
    "uniform-x.y",
    "keyrgb.lock",
    "keyrgb-gui-settings.lock",
]


@pytest.fixture(autouse=True)
def _isolated_config_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    release_all_gui_instance_locks()
    yield tmp_path
    release_all_gui_instance_locks()


def _wait_until(predicate, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


@pytest.mark.parametrize("identity", VALID_IDENTITIES)
def test_valid_identities_map_to_gui_lock_paths(tmp_path, identity) -> None:
    path = gui_instance_lock_path(identity)
    assert path == tmp_path / f"keyrgb-gui-{identity}.lock"
    assert path.name != "keyrgb.lock"


@pytest.mark.parametrize("identity", INVALID_IDENTITIES)
def test_invalid_identities_raise_valueerror(identity) -> None:
    with pytest.raises(ValueError):
        gui_instance_lock_path(identity)
    with pytest.raises(ValueError):
        acquire_gui_instance_lock(identity)
    with pytest.raises(ValueError):
        release_gui_instance_lock(identity)
    with pytest.raises(ValueError):
        acquire_gui_instance_or_exit(identity)


@pytest.mark.parametrize("identity", [None, 123, b"settings"])
def test_non_string_identities_raise_valueerror(identity) -> None:
    with pytest.raises(ValueError):
        gui_instance_lock_path(identity)


def test_config_dir_isolation_and_xdg_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    assert gui_instance_lock_path("settings").parent == tmp_path

    monkeypatch.delenv("KEYRGB_CONFIG_DIR")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert gui_instance_lock_path("settings") == tmp_path / "xdg" / "keyrgb" / "keyrgb-gui-settings.lock"


def test_reentrant_acquire_and_release() -> None:
    assert acquire_gui_instance_lock("perkey") is True
    assert acquire_gui_instance_lock("perkey") is True
    release_gui_instance_lock("perkey")
    assert acquire_gui_instance_lock("perkey") is True
    release_gui_instance_lock("perkey")
    release_gui_instance_lock("perkey")


def test_real_exclusion_and_release(tmp_path) -> None:
    assert acquire_gui_instance_lock("reactive-color") is True
    lock_path = tmp_path / "keyrgb-gui-reactive-color.lock"
    assert lock_path.read_text(encoding="utf-8").startswith("pid=")
    release_gui_instance_lock("reactive-color")

    with lock_path.open("a+", encoding="utf-8") as external_lock:
        fcntl.flock(external_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert acquire_gui_instance_lock("reactive-color") is False

    assert acquire_gui_instance_lock("reactive-color") is True
    assert acquire_gui_instance_lock("reactive-color") is True
    release_gui_instance_lock("reactive-color")


def test_stale_lock_file_is_not_ownership(tmp_path) -> None:
    lock_path = tmp_path / "keyrgb-gui-calibrator.lock"
    lock_path.write_text("pid=999999 identity=calibrator\n", encoding="utf-8")

    assert acquire_gui_instance_lock("calibrator") is True
    assert lock_path.read_text(encoding="utf-8").startswith(f"pid={os.getpid()}")
    release_gui_instance_lock("calibrator")


def test_subprocess_exclusion_and_crash_recovery(tmp_path) -> None:
    identity = "uniform-keyboard"
    ready_path = tmp_path / "holder.ready"
    child_env = dict(os.environ)
    child_env["KEYRGB_CONFIG_DIR"] = str(tmp_path)
    pythonpath = str(REPO_ROOT)
    if child_env.get("PYTHONPATH"):
        pythonpath += os.pathsep + child_env["PYTHONPATH"]
    child_env["PYTHONPATH"] = pythonpath
    holder_script = "\n".join(
        [
            "import sys",
            "import time",
            "from pathlib import Path",
            "from keyrgb.gui.single_instance import acquire_gui_instance_lock",
            f"ok = acquire_gui_instance_lock({identity!r})",
            f"Path({str(ready_path)!r}).write_text('held' if ok else 'failed', encoding='utf-8')",
            "sys.stdout.flush()",
            "while True:",
            "    time.sleep(3600)",
        ]
    )
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c", holder_script],
        env=child_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_until(lambda: ready_path.is_file()), "holder subprocess never signaled readiness"
        assert ready_path.read_text(encoding="utf-8") == "held"
        # Advisory lock is live in the holder: same identity must be contended here.
        assert acquire_gui_instance_lock(identity) is False

        proc.kill()
        proc.wait(timeout=15)
        # Crash recovery relies on descriptor lifetime, not lock-file cleanup.
        assert ready_path.is_file()
        assert _wait_until(lambda: acquire_gui_instance_lock(identity) is True), "lock not released after holder death"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=15)
        release_gui_instance_lock(identity)


def test_fcntl_import_error_fails_open(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "fcntl", None)
    assert acquire_gui_instance_lock("support") is True
    assert "support" not in single_instance._gui_lock_fhs


def test_duplicate_or_exit_raises_clean_exit(tmp_path, caplog) -> None:
    lock_path = tmp_path / "keyrgb-gui-power-mode.lock"
    with (
        lock_path.open("a+", encoding="utf-8") as external_lock,
        caplog.at_level(logging.WARNING, logger="keyrgb.gui.single_instance"),
        pytest.raises(SystemExit) as exc_info,
    ):
        fcntl.flock(external_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquire_gui_instance_or_exit("power-mode")
    assert exc_info.value.code == 0
    assert any("power-mode" in record.message for record in caplog.records)


def test_or_exit_success_returns_none() -> None:
    assert acquire_gui_instance_or_exit("support") is None
    release_gui_instance_lock("support")


def test_hardware_tray_lock_path_untouched(tmp_path) -> None:
    assert acquire_gui_instance_lock("settings") is True
    assert acquire_gui_instance_lock("uniform-keyboard") is True
    assert not (tmp_path / "keyrgb.lock").exists()
    release_all_gui_instance_locks()
