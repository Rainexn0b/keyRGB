#!/usr/bin/env python3
"""Hardware integration smoke test for the ITE backend.

This is NOT a unit test. It talks to real hardware and may change your
keyboard lighting.

- Under pytest: skipped unless KEYRGB_HW_TESTS=1.
- Manual run: `KEYRGB_HW_TESTS=1 python3 src/tests/test_ite_backend.py`
"""

from __future__ import annotations

import os


def _hw_tests_enabled() -> bool:
    return os.environ.get("KEYRGB_HW_TESTS") == "1"


def test_ite_backend_smoke() -> None:
    """Very small smoke test; requires real hardware."""

    if not _hw_tests_enabled():
        try:
            import pytest

            pytest.skip("Hardware test skipped (set KEYRGB_HW_TESTS=1 to enable)")
        except Exception:
            return

    from src.core.backends.registry import select_backend

    backend = select_backend()
    assert backend is not None, "No backend selected; cannot run hardware test"

    # This test is intended for ITE-based devices. If you run it on other
    # hardware/backends, adapt as needed.
    assert getattr(backend, "name", None) == "ite8291r3", f"Unexpected backend: {getattr(backend, 'name', None)}"

    kb = backend.get_device()

    # Basic API sanity checks (these methods are used by the tray/GUI paths).
    assert hasattr(kb, "set_color")
    assert hasattr(kb, "turn_off")

    # Make a minimal, low-brightness write.
    kb.set_color((255, 0, 0), brightness=1)
    kb.turn_off()


def main() -> None:
    if not _hw_tests_enabled():
        raise SystemExit("Set KEYRGB_HW_TESTS=1 to run hardware tests")

    # Reuse pytest-style test function for a simple manual run.
    test_ite_backend_smoke()
    print("Hardware smoke test completed")


if __name__ == "__main__":
    main()
