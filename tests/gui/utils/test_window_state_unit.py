"""Unit tests for the Tk-free UI-state geometry owner (UX-06)."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from keyrgb.gui.utils import window_state
from keyrgb.gui.utils.window_state import (
    WindowGeometry,
    WindowGeometryTracker,
    geometry_string,
    load_window_geometry,
    prepare_restored_geometry,
    save_window_geometry,
    ui_state_lock_path,
    ui_state_path,
)


@pytest.fixture(autouse=True)
def _isolated_config_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path))
    for var in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
        monkeypatch.delenv(var, raising=False)
    yield tmp_path


class _FakeRoot:
    """Minimal duck-typed Tk root for tracker tests (no Tkinter import)."""

    def __init__(self, width=880, height=840, x=100, y=80, screen=(2560, 1600)):
        self._width = width
        self._height = height
        self._x = x
        self._y = y
        self._screen = screen
        self.bindings: list[tuple[str, object]] = []
        self.scheduled: list[tuple[int, object]] = []
        self.cancelled: list[object] = []
        self.applied: list[str] = []
        self._next_after_id = 0

    def bind(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback, add))

    def after(self, delay_ms, callback):
        self._next_after_id += 1
        token = f"after-{self._next_after_id}"
        self.scheduled.append((int(delay_ms), callback, token))
        return token

    def after_cancel(self, token):
        self.cancelled.append(token)
        self.scheduled = [entry for entry in self.scheduled if entry[2] != token]

    def fire_pending(self):
        pending = [entry[1] for entry in self.scheduled]
        self.scheduled.clear()
        for callback in pending:
            callback()

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def winfo_x(self):
        return self._x

    def winfo_y(self):
        return self._y

    def winfo_screenwidth(self):
        return self._screen[0]

    def winfo_screenheight(self):
        return self._screen[1]

    def geometry(self, value):
        self.applied.append(value)


def _config_digest_and_mtime(path: Path) -> tuple[str | None, float | None]:
    if not path.exists():
        return None, None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest, path.stat().st_mtime_ns


# --- paths -----------------------------------------------------------------


def test_state_and_lock_paths_are_distinct_and_config_scoped(tmp_path) -> None:
    assert ui_state_path() == tmp_path / "ui-state.json"
    assert ui_state_lock_path() == tmp_path / "ui-state.lock"
    assert ui_state_path() != ui_state_lock_path()
    assert ui_state_path().name != "config.json"


def test_module_is_tk_free() -> None:
    source = Path(window_state.__file__).read_text(encoding="utf-8")
    assert "import tkinter" not in source
    assert "from tkinter" not in source


# --- window id validation (UX-09 parity, public functions only) -------------


def test_valid_ux09_ids_roundtrip() -> None:
    from keyrgb.gui.single_instance import gui_instance_lock_path

    static_ids = ["settings", "reactive-color", "power-mode", "support", "perkey", "calibrator"]
    for window_id in static_ids:
        gui_instance_lock_path(window_id)  # public UX-09 validation; must not raise
        assert save_window_geometry(window_id, WindowGeometry(width=800, height=600, x=10, y=10)) is True
        assert load_window_geometry(window_id) == WindowGeometry(width=800, height=600, x=10, y=10)


def test_uniform_ids_roundtrip() -> None:
    from keyrgb.gui.single_instance import gui_instance_lock_path
    from keyrgb.gui.windows.uniform import uniform_instance_identity

    identities = {
        uniform_instance_identity(target_context="keyboard"),
        "uniform-lightbar",
        "uniform-ite8258-chassis-logo",
    }
    for window_id in identities:
        gui_instance_lock_path(window_id)  # public UX-09 validation; must not raise
        assert save_window_geometry(window_id, WindowGeometry(width=640, height=480)) is not None
        assert load_window_geometry(window_id) == WindowGeometry(width=640, height=480)


@pytest.mark.parametrize("window_id", ["", "unknown", "../settings", "settings ", "uniform-", "uniform-x_y", None, 123])
def test_invalid_window_ids_fail_safely(window_id) -> None:
    assert load_window_geometry(window_id) is None  # type: ignore[arg-type]
    assert save_window_geometry(window_id, WindowGeometry(width=100, height=100)) is False  # type: ignore[arg-type]


# --- roundtrip / sibling preservation ---------------------------------------


def test_roundtrip_with_position() -> None:
    assert save_window_geometry("settings", WindowGeometry(width=880, height=840, x=100, y=80)) is True
    assert load_window_geometry("settings") == WindowGeometry(width=880, height=840, x=100, y=80)


def test_roundtrip_size_only() -> None:
    assert save_window_geometry("support", WindowGeometry(width=700, height=500)) is True
    assert load_window_geometry("support") == WindowGeometry(width=700, height=500)


def test_sibling_and_unknown_state_preserved(tmp_path) -> None:
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600, x=5, y=5)) is True
    state_path = ui_state_path()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["custom-unsupported-key"] = {"note": "keep me"}
    data["windows"]["perkey"] = {"width": 1, "height": 1, "foreign": True}
    state_path.write_text(json.dumps(data), encoding="utf-8")

    assert save_window_geometry("support", WindowGeometry(width=700, height=500, x=1, y=2)) is True
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["custom-unsupported-key"] == {"note": "keep me"}
    assert data["windows"]["settings"] == {"width": 800, "height": 600, "x": 5, "y": 5}
    assert data["windows"]["support"] == {"width": 700, "height": 500, "x": 1, "y": 2}


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


# --- prepare / clamp / offscreen / formatting --------------------------------


def test_prepare_clamps_to_min_and_screen_cap() -> None:
    prepared = prepare_restored_geometry(WindowGeometry(width=100, height=100), 1920, 1080, 460, 520, 0.95)
    assert prepared == WindowGeometry(width=460, height=520)
    prepared = prepare_restored_geometry(WindowGeometry(width=5000, height=5000), 1920, 1080, 460, 520, 0.95)
    assert prepared == WindowGeometry(width=int(1920 * 0.95), height=int(1080 * 0.95))


def test_prepare_tiny_screen_keeps_window_within_screen_cap() -> None:
    prepared = prepare_restored_geometry(WindowGeometry(width=800, height=600), 400, 300, 460, 520, 0.95)
    assert prepared == WindowGeometry(width=380, height=285)


def test_prepare_size_only_returns_size_only() -> None:
    prepared = prepare_restored_geometry(WindowGeometry(width=800, height=600), 1920, 1080, 460, 520, 0.95)
    assert prepared is not None
    assert prepared.x is None and prepared.y is None
    assert geometry_string(prepared) == f"{prepared.width}x{prepared.height}"


@pytest.mark.parametrize(
    "geometry",
    [
        WindowGeometry(width=800, height=600, x=5000, y=5000),
        WindowGeometry(width=800, height=600, x=-900, y=-700),
        WindowGeometry(width=800, height=600, x=1920, y=100),
        WindowGeometry(width=800, height=600, x=100, y=1080),
    ],
)
def test_prepare_wholly_offscreen_rejected(geometry) -> None:
    assert prepare_restored_geometry(geometry, 1920, 1080, 460, 520, 0.95) is None


def test_prepare_partially_visible_kept() -> None:
    prepared = prepare_restored_geometry(
        WindowGeometry(width=800, height=600, x=-100, y=-100), 1920, 1080, 460, 520, 0.95
    )
    assert prepared == WindowGeometry(width=800, height=600, x=-100, y=-100)


def test_prepare_malformed_inputs_rejected() -> None:
    assert prepare_restored_geometry(None, 1920, 1080, 460, 520, 0.95) is None  # type: ignore[arg-type]
    assert prepare_restored_geometry(WindowGeometry(width=0, height=600), 1920, 1080, 460, 520, 0.95) is None
    assert prepare_restored_geometry(WindowGeometry(width=10**9, height=600), 1920, 1080, 460, 520, 0.95) is None
    assert prepare_restored_geometry(WindowGeometry(width=800, height=600), 0, 1080, 460, 520, 0.95) is None
    assert prepare_restored_geometry(WindowGeometry(width=800, height=600), 1920, 1080, 0, 520, 0.95) is None


def test_geometry_string_formats() -> None:
    assert geometry_string(WindowGeometry(width=800, height=600)) == "800x600"
    assert geometry_string(WindowGeometry(width=800, height=600, x=10, y=20)) == "800x600+10+20"
    assert geometry_string(WindowGeometry(width=800, height=600, x=-10, y=-20)) == "800x600-10-20"


# --- tracker ------------------------------------------------------------------


def test_tracker_restore_applies_clamped_geometry() -> None:
    assert save_window_geometry("settings", WindowGeometry(width=5000, height=5000, x=50, y=60)) is True
    root = _FakeRoot(screen=(1920, 1080))
    tracker = WindowGeometryTracker(root, "settings", 460, 520)
    assert tracker.restore() is True
    assert root.applied == [f"{int(1920 * 0.95)}x{int(1080 * 0.95)}+50+60"]


def test_tracker_restore_falls_back_when_missing_or_offscreen() -> None:
    tracker = WindowGeometryTracker(_FakeRoot(), "settings", 460, 520)
    assert tracker.restore() is False

    assert save_window_geometry("settings", WindowGeometry(width=800, height=600, x=9000, y=9000)) is True
    root = _FakeRoot()
    assert WindowGeometryTracker(root, "settings", 460, 520).restore() is False
    assert root.applied == []


def test_tracker_start_tracking_only_binds() -> None:
    root = _FakeRoot()
    tracker = WindowGeometryTracker(root, "settings", 460, 520)
    tracker.start_tracking()
    assert root.bindings == [("<Configure>", tracker._on_configure, "+")]
    assert load_window_geometry("settings") is None
    assert root.scheduled == []


def test_tracker_ignores_bubbled_descendant_events() -> None:
    root = _FakeRoot()
    tracker = WindowGeometryTracker(root, "settings", 460, 520)
    tracker.start_tracking()
    child = object()
    tracker._on_configure(SimpleNamespace(widget=child))
    assert root.scheduled == []
    tracker._on_configure(SimpleNamespace(widget=root))
    assert len(root.scheduled) == 1
    assert root.scheduled[0][0] == 500


def test_tracker_debounce_cancels_pending() -> None:
    root = _FakeRoot()
    tracker = WindowGeometryTracker(root, "settings", 460, 520, debounce_ms=500)
    tracker.start_tracking()
    tracker._on_configure(SimpleNamespace(widget=root))
    first_token = root.scheduled[0][2]
    tracker._on_configure(SimpleNamespace(widget=root))
    assert root.cancelled == [first_token]
    assert len(root.scheduled) == 1  # pending write replaced, not duplicated
    assert root.scheduled[0][0] == 500
    root.fire_pending()
    assert load_window_geometry("settings") == WindowGeometry(width=880, height=840, x=100, y=80)


def test_tracker_save_now_cancels_pending_and_writes() -> None:
    root = _FakeRoot(width=700, height=500, x=11, y=22)
    tracker = WindowGeometryTracker(root, "support", 460, 520)
    tracker.start_tracking()
    tracker._on_configure(SimpleNamespace(widget=root))
    token = root.scheduled[0][2]
    assert tracker.save_now() is True
    assert root.cancelled == [token]
    assert root.scheduled == []
    assert load_window_geometry("support") == WindowGeometry(width=700, height=500, x=11, y=22)


def test_tracker_wayland_save_is_size_only(monkeypatch) -> None:
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    root = _FakeRoot(width=700, height=500, x=11, y=22)
    tracker = WindowGeometryTracker(root, "support", 460, 520)
    assert tracker.save_now() is True
    assert load_window_geometry("support") == WindowGeometry(width=700, height=500)
    raw = json.loads(ui_state_path().read_text(encoding="utf-8"))
    assert raw["windows"]["support"] == {"width": 700, "height": 500}


def test_tracker_xdg_session_type_wayland_save_is_size_only(monkeypatch) -> None:
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert save_window_geometry("settings", WindowGeometry(width=800, height=600, x=5, y=6)) is True
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
