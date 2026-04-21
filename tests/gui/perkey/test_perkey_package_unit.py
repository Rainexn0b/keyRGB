from __future__ import annotations

import src.gui.perkey as perkey
from src.gui.perkey import launch as perkey_launch


def test_perkey_package_re_exports_launch_main() -> None:
    assert perkey.main is perkey_launch.main
    assert "main" in perkey.__all__
