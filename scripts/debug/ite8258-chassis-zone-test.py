#!/usr/bin/env python3
"""One-shot hardware validation for ITE 8258 chassis zone devices.

Run from a repo checkout with the experimental backend enabled:

    KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 \
        scripts/debug/ite8258-chassis-zone-test.py

The script exercises each zone independently and prompts for visual
confirmation. Collect the output and any failures when reporting results.
"""

from __future__ import annotations

import os
import sys
import time


def _repo_root() -> str:
    this_file = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(os.path.dirname(this_file)))


def _main() -> int:
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    os.environ.setdefault("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    from src.core.backends.ite8258_chassis.backend import Ite8258ChassisBackend
    from src.core.backends.ite8258_chassis.device import Ite8258ChassisZoneDevice

    backend = Ite8258ChassisBackend()
    if not backend.is_available():
        print("ITE 8258 chassis backend is not available.")
        print("Check that the device is connected and udev rules are installed.")
        return 1

    zones: list[tuple[str, tuple[int, int, int]]] = [
        ("logo", (255, 0, 0)),
        ("neon", (0, 255, 0)),
        ("vent", (0, 0, 255)),
    ]

    print("ITE 8258 chassis zone validation")
    print("=" * 40)

    devices: list[Ite8258ChassisZoneDevice] = []
    try:
        for zone_name, color in zones:
            print(f"\nAcquiring {zone_name} zone device...")
            device = backend.get_zone_device(zone_name)
            devices.append(device)

            print(f"Setting {zone_name} to RGB{color}...")
            device.set_color(color, brightness=25)
            time.sleep(0.5)

            response = input(f"Is the {zone_name} zone lit RGB{color}? [y/N/e(xit)] ").strip().lower()
            if response.startswith("e"):
                print("Exiting early.")
                return 0
            if not response.startswith("y"):
                print(f"FAIL: {zone_name} zone did not light as expected.")
                return 2

            print(f"Turning {zone_name} off...")
            device.turn_off()
            time.sleep(0.3)

        print("\nAll zones validated successfully.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    finally:
        for device in devices:
            try:
                device.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(_main())
