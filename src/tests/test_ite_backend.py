#!/usr/bin/env python3
"""Hardware integration sanity check for the Tuxedo ITE backend.

This is NOT a unit test. It talks to real hardware.

- Under pytest: skipped unless KEYRGB_HW_TESTS=1.
- Manual run: `KEYRGB_HW_TESTS=1 python3 src/tests/test_ite_backend.py`
"""

import sys
import os


def _hw_tests_enabled() -> bool:
	return os.environ.get("KEYRGB_HW_TESTS") == "1"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _get_ite_backend():
	"""Import the tuxedo-src ite backend after enabling repo-local paths."""
	sys.path.insert(0, os.path.join(REPO_ROOT, "tuxedo-src"))
	from ite_backend import ite_backend  # type: ignore

	return ite_backend


def test_ite_backend_smoke():
	"""Very small smoke test; requires hardware."""
	if not _hw_tests_enabled():
		try:
			import pytest

			pytest.skip("Hardware test skipped (set KEYRGB_HW_TESTS=1 to enable)")
		except Exception:
			return

	ite_backend = _get_ite_backend()

	assert ite_backend.get_device_param('state') is not None
	assert ite_backend.get_device_param('mode') is not None
	assert ite_backend.get_device_param('brightness') is not None


def main() -> None:
	if not _hw_tests_enabled():
		raise SystemExit("Set KEYRGB_HW_TESTS=1 to run hardware tests")

	ite_backend = _get_ite_backend()

	print("Testing ITE Backend...")
	print(f"State: {ite_backend.get_device_param('state')}")
	print(f"Mode: {ite_backend.get_device_param('mode')}")
	print(f"Brightness: {ite_backend.get_device_param('brightness')}")

	print("\nSetting red color...")
	ite_backend.set_device_param('color_left', '0xFF0000')
	print("Done!")

	print("\nSetting breathing effect...")
	ite_backend.set_device_param('mode', '1')  # Index 1 = breathe
	print("Done!")


if __name__ == "__main__":
	main()
