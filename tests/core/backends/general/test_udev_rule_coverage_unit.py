"""Unit tests: udev rule coverage for ITE backend product IDs.

Guards against the class of bug where a backend opens ``/dev/hidraw*`` (or the
USB device node) but ``system/udev/99-ite8291-wootbook.rules`` never granted the
seat user access to that node, so the backend failed with permission-denied on
otherwise supported hardware.

For every ITE backend package this test derives the supported USB product IDs
from the backend's ``protocol`` module and asserts they are covered by a udev
rule of the correct type:

* hidraw backends          -> ``KERNEL=="hidraw*"`` rules
* USB control-transfer     -> ``SUBSYSTEM=="usb"`` rules

The two rule types are *not* interchangeable: a ``SUBSYSTEM=="usb"`` rule does
not grant access to the ``/dev/hidraw*`` node, and vice versa.
"""

from __future__ import annotations

import importlib
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[4]
_BACKENDS_DIR = _ROOT / "src" / "core" / "backends"
_UDEV_RULES = _ROOT / "system" / "udev" / "99-ite8291-wootbook.rules"

# Backends that talk to the device over USB control transfers (pyusb) instead of
# /dev/hidraw*. Every other ITE backend uses hidraw. Keep this in sync with the
# source; the consistency test below verifies it against the code.
USB_CONTROL_BACKENDS = frozenset({"ite8291r3_perkey"})

# Attribute names a backend protocol module may use to declare its product IDs,
# checked in priority order (a set beats a single ID).
_PID_ATTRS = ("SUPPORTED_PRODUCT_IDS", "PRODUCT_IDS", "PRODUCT_ID")

_PID_RE = re.compile(r'ATTRS?\{idProduct\}=="([0-9a-fA-F]{4})"')


def _udev_pid_sets() -> tuple[set[int], set[int]]:
    """Parse the udev rules file into (usb_pids, hidraw_pids)."""
    usb: set[int] = set()
    hidraw: set[int] = set()
    for line in _UDEV_RULES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PID_RE.search(line)
        if match is None:
            continue
        pid = int(match.group(1), 16)
        if 'SUBSYSTEM=="usb"' in line:
            usb.add(pid)
        elif 'KERNEL=="hidraw*"' in line:
            hidraw.add(pid)
    return usb, hidraw


def _ite_backend_packages() -> list[str]:
    return sorted(
        p.name
        for p in _BACKENDS_DIR.iterdir()
        if p.is_dir() and p.name.startswith("ite") and (p / "protocol.py").exists()
    )


def _protocol_pids(package: str) -> tuple[int, ...]:
    protocol = importlib.import_module(f"src.core.backends.{package}.protocol")
    for attr in _PID_ATTRS:
        value = getattr(protocol, attr, None)
        if value is None:
            continue
        if isinstance(value, int):
            return (value,)
        return tuple(int(v) for v in value)
    raise AssertionError(f"{package}: no product-ID constant ({'/'.join(_PID_ATTRS)}) in protocol module")


def _detect_transport(package: str) -> str:
    """Return 'usb' for USB control-transfer backends, 'hidraw' otherwise."""
    pkg_dir = _BACKENDS_DIR / package
    blob = "\n".join(
        (pkg_dir / name).read_text(encoding="utf-8", errors="replace")
        for name in ("backend.py", "usb.py", "transport.py")
        if (pkg_dir / name).exists()
    )
    if "ctrl_transfer" in blob or "usb.core" in blob or "usb.util" in blob:
        return "usb"
    return "hidraw"


def test_every_ite_backend_pids_covered_by_correct_udev_rule_type() -> None:
    usb_pids, hidraw_pids = _udev_pid_sets()
    assert usb_pids, 'no SUBSYSTEM=="usb" product IDs parsed from udev rules'
    assert hidraw_pids, 'no KERNEL=="hidraw*" product IDs parsed from udev rules'

    packages = _ite_backend_packages()
    assert packages, "no ITE backend packages found under src/core/backends"

    for package in packages:
        pids = _protocol_pids(package)
        assert pids, f"{package}: protocol module declared no product IDs"
        transport = "usb" if package in USB_CONTROL_BACKENDS else "hidraw"
        covered = usb_pids if transport == "usb" else hidraw_pids
        missing = sorted(f"0x{pid:04x}" for pid in pids if pid not in covered)
        assert not missing, (
            f"{package} ({transport}) is missing {transport} udev uaccess rule(s) for "
            f'product id(s): {", ".join(missing)}. Add a KERNEL=="hidraw*" rule '
            f'(hidraw backend) or SUBSYSTEM=="usb" rule (USB control-transfer '
            f"backend) to system/udev/99-ite8291-wootbook.rules."
        )


def test_usb_control_backend_classification_matches_source() -> None:
    """The hard-coded USB_CONTROL_BACKENDS set must match what the code uses.

    If a new USB control-transfer backend is added without being classified here
    (or an entry here stops being USB control-transfer), the coverage test above
    would check it against the wrong udev rule type. This keeps the set honest.
    """
    detected_usb = {pkg for pkg in _ite_backend_packages() if _detect_transport(pkg) == "usb"}
    assert detected_usb == set(USB_CONTROL_BACKENDS), (
        f"USB control-transfer backends detected in source: {sorted(detected_usb)}, "
        f"but USB_CONTROL_BACKENDS declares: {sorted(USB_CONTROL_BACKENDS)}. Update "
        f"USB_CONTROL_BACKENDS so each backend's product IDs are validated against "
        f"the correct udev rule type."
    )
