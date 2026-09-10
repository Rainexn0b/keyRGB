from __future__ import annotations

"""Window-state storage: corruption, atomicity, locks, and failures."""

import json
import os
import threading

import pytest

from keyrgb.gui.utils.window_state import (
    WindowGeometry,
    WindowGeometryTracker,
    load_window_geometry,
    save_window_geometry,
    ui_state_lock_path,
    ui_state_path,
)
from tests.gui.utils.window_state._window_state_fakes import _config_digest_and_mtime, _FakeRoot


# --- corruption / malformed --------------------------------------------------
def test_corrupt_json_falls_back_and_allows_later_save() -> None:
    ui_state_path().write_text("{not valid json", encoding="utf-8")
    assert load_window_geometry("settings") is None
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600)) is True
    assert load_window_geometry("settings") == WindowGeometry(width=800, height=600)


@pytest.mark.parametrize(
    "raw",
    [
        {"width": 0, "height": 600},
        {"width": -5, "height": 600},
        {"width": 99999, "height": 600},
        {"width": "800", "height": 600},
        {"width": 800.5, "height": 600},
        {"width": True, "height": 600},
        {"width": 800},
        {"height": 600},
        {"width": 800, "height": 600, "x": "a", "y": 1},
        {"width": 800, "height": 600, "x": 999999, "y": 1},
        [800, 600],
        "nope",
        None,
    ],
)
def test_malformed_entries_rejected(raw) -> None:
    state = {"windows": {"settings": raw}}
    ui_state_path().write_text(json.dumps(state), encoding="utf-8")
    assert load_window_geometry("settings") is None


def test_non_dict_top_level_rejected() -> None:
    ui_state_path().write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert load_window_geometry("settings") is None


def test_absurd_save_rejected() -> None:
    assert save_window_geometry("settings", WindowGeometry(width=0, height=600)) is False
    assert save_window_geometry("settings", WindowGeometry(width=10**9, height=600)) is False
    assert load_window_geometry("settings") is None


# --- atomicity / temp cleanup / locks ----------------------------------------
def test_atomic_replace_preserves_siblings_and_cleans_temp(tmp_path) -> None:
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600, x=1, y=1)) is True
    before = json.loads(ui_state_path().read_text(encoding="utf-8"))
    assert before["windows"]["settings"]["width"] == 800

    assert save_window_geometry("perkey", WindowGeometry(width=900, height=700)) is True
    leftovers = list(tmp_path.glob(".ui-state.*.tmp")) + list(tmp_path.glob("*.tmp"))
    assert leftovers == []
    data = json.loads(ui_state_path().read_text(encoding="utf-8"))
    assert data["windows"]["settings"] == {"width": 800, "height": 600, "x": 1, "y": 1}
    assert data["windows"]["perkey"] == {"width": 900, "height": 700}


def test_concurrent_rmw_preserves_both_windows() -> None:
    errors: list[Exception] = []

    def _worker(window_id: str, width: int) -> None:
        try:
            for _ in range(10):
                assert save_window_geometry(window_id, WindowGeometry(width=width, height=600)) is True
        except Exception as exc:  # noqa: BLE001 - collect for the main thread to assert
            errors.append(exc)

    threads = [
        threading.Thread(target=_worker, args=("settings", 800)),
        threading.Thread(target=_worker, args=("support", 700)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    assert load_window_geometry("settings") == WindowGeometry(width=800, height=600)
    assert load_window_geometry("support") == WindowGeometry(width=700, height=600)


def test_lock_file_created_and_shared_lock_allows_reads(tmp_path) -> None:
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600)) is True
    assert ui_state_lock_path().is_file()
    assert load_window_geometry("settings") == WindowGeometry(width=800, height=600)


def test_blocking_exclusive_lock_serializes_slow_writer() -> None:
    import fcntl

    lock_path = ui_state_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    release: threading.Event = threading.Event()
    held: threading.Event = threading.Event()
    done: threading.Event = threading.Event()
    outcome: list[bool] = []

    def _slow_holder() -> None:
        with lock_path.open("a+", encoding="utf-8") as holder:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
            held.set()
            assert release.wait(timeout=30)
            fcntl.flock(holder.fileno(), fcntl.LOCK_UN)

    def _writer() -> None:
        outcome.append(save_window_geometry("settings", WindowGeometry(width=800, height=600)))
        done.set()

    holder_thread = threading.Thread(target=_slow_holder)
    holder_thread.start()
    assert held.wait(timeout=30)  # holder owns the lock before the writer starts
    writer_thread = threading.Thread(target=_writer)
    writer_thread.start()
    # Give the writer a moment to block behind the held exclusive lock.
    threading.Event().wait(0.5)
    assert not done.is_set()  # writer is blocked behind the exclusive lock
    release.set()
    assert done.wait(timeout=30)
    holder_thread.join(timeout=30)
    writer_thread.join(timeout=30)
    assert outcome == [True]
    assert load_window_geometry("settings") == WindowGeometry(width=800, height=600)


def test_failed_filesystem_save_returns_false(monkeypatch) -> None:
    monkeypatch.setattr("tempfile.mkstemp", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600)) is False


# --- config.json untouched -----------------------------------------------------
def test_geometry_save_restore_leaves_config_json_untouched(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"brightness": 80}), encoding="utf-8")
    before_digest, before_mtime = _config_digest_and_mtime(config_path)

    assert save_window_geometry("settings", WindowGeometry(width=880, height=840, x=100, y=80)) is True
    root = _FakeRoot()
    assert WindowGeometryTracker(root, "settings", 460, 520).restore() is True
    assert WindowGeometryTracker(root, "settings", 460, 520).save_now() is True

    assert _config_digest_and_mtime(config_path) == (before_digest, before_mtime)
    assert os.environ.get("KEYRGB_CONFIG_DIR") == str(tmp_path)
