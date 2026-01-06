from __future__ import annotations

import os
import sys
import builtins
import importlib.abc
import traceback
import tempfile
from pathlib import Path

import pytest


_SKIP_AGENT_TESTS_ENV = "KEYRGB_SKIP_AGENT_TESTS"


def _hardware_opted_in() -> bool:
    return os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"


# Safety default: during pytest, avoid touching the user's real config/state.
# This also prevents any running KeyRGB tray/daemon from reacting to test writes.
if not _hardware_opted_in():
    os.environ.setdefault(
        "KEYRGB_CONFIG_DIR",
        tempfile.mkdtemp(prefix="keyrgb-test-config-"),
    )


# Safety default: running pytest should never scan real USB devices unless
# explicitly opted in.
if not _hardware_opted_in():
    os.environ.setdefault("KEYRGB_DISABLE_USB_SCAN", "1")


def _install_tripwire() -> None:
    """Install a hard-fail tripwire for unexpected hardware access during pytest.

    This is intentionally broad and only enabled when:
    - KEYRGB_TEST_HARDWARE_TRIPWIRE=1
    - and hardware is NOT opted in.

    It aims to provide a traceback for the first attempted access.
    """

    if os.environ.get("KEYRGB_TEST_HARDWARE_TRIPWIRE") != "1":
        return
    if _hardware_opted_in():
        return

    # 1) Block imports that commonly lead to real USB access.
    blocked_prefixes = (
        "usb",  # pyusb
        "ite8291r3_ctl",  # may load libusb / open device in some environments
    )

    class _BlockImportsFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
            # Allow tests that inject fakes via sys.modules.
            if fullname in sys.modules:
                return None
            if any(fullname == prefix or fullname.startswith(f"{prefix}.") for prefix in blocked_prefixes):
                raise RuntimeError(
                    "Tripwire: attempted to import a hardware/USB module during pytest: "
                    f"{fullname}\n\n" + "".join(traceback.format_stack(limit=50))
                )
            return None

    # Prepend so it wins.
    sys.meta_path.insert(0, _BlockImportsFinder())

    # 2) Block writes to /sys and opens to /dev/bus/usb to catch sysfs LED writes
    # and direct USB device opens.
    _orig_open = builtins.open

    def _is_write_mode(mode: str) -> bool:
        return any(ch in mode for ch in ("w", "a", "+"))

    def _path_str(file) -> str:
        try:
            return os.fspath(file)
        except Exception:
            return str(file)

    def _tripwire_open(file, mode="r", *args, **kwargs):  # type: ignore[override]
        p = _path_str(file)
        # Only guard absolute paths; relative paths are project/test files.
        if isinstance(p, str) and p.startswith("/"):
            if p.startswith("/sys/") and _is_write_mode(str(mode)):
                raise RuntimeError(
                    f"Tripwire: attempted write to real /sys path during pytest: {p}\n\n"
                    + "".join(traceback.format_stack(limit=50))
                )
            if p.startswith("/dev/bus/usb"):
                raise RuntimeError(
                    f"Tripwire: attempted open of USB device node during pytest: {p}\n\n"
                    + "".join(traceback.format_stack(limit=50))
                )
        return _orig_open(file, mode, *args, **kwargs)

    builtins.open = _tripwire_open  # type: ignore[assignment]

    # os.open can also be used; guard it too.
    _orig_os_open = os.open

    def _tripwire_os_open(path, flags, *args, **kwargs):  # type: ignore[override]
        p = _path_str(path)
        if isinstance(p, str) and p.startswith("/dev/bus/usb"):
            raise RuntimeError(
                f"Tripwire: attempted os.open of USB device node during pytest: {p}\n\n"
                + "".join(traceback.format_stack(limit=50))
            )
        return _orig_os_open(path, flags, *args, **kwargs)

    os.open = _tripwire_os_open  # type: ignore[assignment]


_BASELINE_SYSFS_LEDS: dict[str, str] | None = None


def _read_text_best_effort(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _candidate_keyboard_led_dirs() -> list[Path]:
    root = Path("/sys/class/leds")
    if not root.exists():
        return []

    out: list[Path] = []
    try:
        for child in root.iterdir():
            if child.is_dir():
                out.append(child)
    except Exception:
        return []

    return sorted(out, key=lambda p: p.name)


def _read_led_snapshot() -> dict[str, str]:
    # The physical keyboard light can turn off without the visible
    # /sys/class/leds/*/brightness changing (e.g. actual_brightness, trigger,
    # driver-specific attrs). Snapshot a small set of commonly relevant files.
    snap: dict[str, str] = {}

    def add_if_exists(p: Path) -> None:
        if not p.exists() or not p.is_file():
            return
        v = _read_text_best_effort(p)
        if v is None:
            return
        snap[str(p)] = v

    # LED class
    for led_dir in _candidate_keyboard_led_dirs():
        for rel in (
            "brightness",
            "actual_brightness",
            "max_brightness",
            "trigger",
            "color",
            "multi_intensity",
            "multi_index",
        ):
            add_if_exists(led_dir / rel)

        # Power management attrs can indirectly affect LEDs.
        for rel in (
            "device/power/control",
            "device/power/runtime_status",
            "device/power/wakeup",
            "device/power/autosuspend_delay_ms",
        ):
            add_if_exists(led_dir / rel)

    # Some laptops expose keyboard lighting under backlight class instead.
    backlight_root = Path("/sys/class/backlight")
    if backlight_root.exists():
        try:
            for bl_dir in sorted(
                [p for p in backlight_root.iterdir() if p.is_dir()],
                key=lambda p: p.name,
            ):
                for rel in (
                    "brightness",
                    "actual_brightness",
                    "max_brightness",
                    "bl_power",
                    "type",
                ):
                    add_if_exists(bl_dir / rel)
        except Exception:
            pass

    return snap


def _tripwire_enabled() -> bool:
    return os.environ.get("KEYRGB_TEST_HARDWARE_TRIPWIRE") == "1" and not _hardware_opted_in()


def pytest_sessionstart(session: pytest.Session) -> None:  # pragma: no cover
    # In tripwire mode, record a baseline of candidate keyboard LEDs so we can
    # detect unexpected state changes even if they happen via C libs / kernel.
    global _BASELINE_SYSFS_LEDS
    if not _tripwire_enabled():
        return
    _BASELINE_SYSFS_LEDS = _read_led_snapshot()


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:  # pragma: no cover
    # If the physical keyboard backlight turns off during the suite, fail the
    # first test after which the observed sysfs brightness changed.
    global _BASELINE_SYSFS_LEDS
    if not _tripwire_enabled():
        return
    if not _BASELINE_SYSFS_LEDS:
        return

    current = _read_led_snapshot()
    diffs: list[str] = []
    for path, before in _BASELINE_SYSFS_LEDS.items():
        after = current.get(path)
        if after is None:
            continue
        if str(after) != str(before):
            diffs.append(f"{path}: {before} -> {after}")

    if diffs:
        # Keep output readable; show the first few diffs.
        diffs = diffs[:25]
        raise RuntimeError(
            "Tripwire: detected sysfs LED brightness change during pytest. "
            f"First observed after: {item.nodeid}\n" + "\n".join(diffs)
        )


_install_tripwire()


@pytest.fixture
def temp_profile_dir(tmp_path: Path) -> Path:
    """Create a temporary profile directory structure."""
    profile_dir = tmp_path / "profiles" / "test_profile"
    profile_dir.mkdir(parents=True)
    return profile_dir


@pytest.fixture
def profile_paths_factory():
    """Factory to build ProfilePaths rooted at a temp profile dir."""

    def _make(
        root: Path,
        *,
        keymap: Path | None = None,
        layout_global: Path | None = None,
        layout_per_key: Path | None = None,
        per_key_colors: Path | None = None,
        backdrop_image: Path | None = None,
        backdrop_settings: Path | None = None,
    ):
        from src.core.profile.paths import ProfilePaths

        return ProfilePaths(
            root=root,
            keymap=keymap or (root / "keymap.json"),
            layout_global=layout_global or (root / "layout.json"),
            layout_per_key=layout_per_key or (root / "layout_per_key.json"),
            per_key_colors=per_key_colors or (root / "colors.json"),
            backdrop_image=backdrop_image or (root / "backdrop.png"),
            backdrop_settings=backdrop_settings or (root / "backdrop_settings.json"),
        )

    return _make


# A small set of recently-added suites that are useful but not required
# for debugging hardware side-effects.
_AGENT_ADDED_TEST_FILES = {
    "test_config_file_storage_unit.py",
    "test_effect_selection_unit.py",
    "test_hw_payloads_unit.py",
    "test_power_manager_battery_saver_loop_unit.py",
    "test_power_manager_brightness_unit.py",
    "test_power_manager_config_gating_unit.py",
    "test_power_manager_event_handlers_unit.py",
    "test_power_manager_monitoring_unit.py",
    "test_power_manager_shape_unit.py",
    "test_profile_storage_apply_profile_unit.py",
    "test_profile_storage_backdrop_transparency_unit.py",
    "test_profile_storage_keymap_unit.py",
    "test_profile_storage_layout_global_unit.py",
    "test_profile_storage_layout_per_key_unit.py",
    "test_profile_storage_per_key_colors_unit.py",
    "test_software_loops_unit.py",
    "test_tray_lighting_controller_unit.py",
}


def _is_agent_added_test(item: pytest.Item) -> bool:
    path = Path(str(getattr(item, "fspath", "")))
    return path.name in _AGENT_ADDED_TEST_FILES


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # Opt-in switch: lets us quickly bisect whether newly-added tests are the trigger.
    if os.environ.get(_SKIP_AGENT_TESTS_ENV) != "1":
        return

    skip_marker = pytest.mark.skip(reason=f"Skipped via {_SKIP_AGENT_TESTS_ENV}=1")

    for item in items:
        if _is_agent_added_test(item):
            item.add_marker(skip_marker)
