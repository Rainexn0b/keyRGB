from __future__ import annotations

from keyrgb.gui import perkey
from keyrgb.gui.perkey import launch as perkey_launch


def test_perkey_package_re_exports_launch_main() -> None:
    assert perkey.main is perkey_launch.main
    assert "main" in perkey.__all__
