# Validation layers

Status: **Done**

## Purpose

The default pytest gate must prove more than isolated units. Installed
artifacts, desktop-session isolation, installer sandbox flows, and
hardware-access refusal belong in the same contract.

## Layers

| Layer | Default gate | Owner |
|---|---|---|
| Unit / focused integration | yes | `tests/` |
| Installed artifact | yes | wheel + sdist resource smoke |
| Installer sandbox | yes | udev match + desktop integration without sudo |
| Desktop-session isolation | yes | isolated `KEYRGB_CONFIG_DIR` and `XDG_*` |
| Device-access tripwire | yes | refuse real `/sys` writes and `/dev/bus/usb` opens |
| USB-import / LED-snapshot tripwire | opt-in | `KEYRGB_TEST_HARDWARE_TRIPWIRE=1` |
| Live hardware | opt-in | `KEYRGB_ALLOW_HARDWARE=1` or `KEYRGB_HW_TESTS=1` |

## Hardware tripwire

`tests/conftest.py` and `keyrgb/core/backends/sysfs/common.py` share one policy:

- Device-access guards are **on** unless hardware is opted in or
  `KEYRGB_TEST_HARDWARE_TRIPWIRE=0`.
- Blocking the `usb` import is opt-in. Production backends import that module
  during unit tests, so a default import ban would hide real coverage.
- LED snapshot comparison is opt-in because another process can change host
  sysfs brightness.

`KEYRGB_TEST_HARDWARE_TRIPWIRE=1` still enables the older broad mode (import
block + LED snapshot) for targeted slices.

## Non-goals

- A live desktop compositor or login session in CI
- Privileged `install.sh` end-to-end against a real `/etc`
- Changing public entrypoints
