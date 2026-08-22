from __future__ import annotations

from pathlib import Path

import tests._paths as test_paths


def test_repo_root_points_at_checkout() -> None:
    root = Path(test_paths.REPO_ROOT)
    assert (root / "pyproject.toml").is_file()
    assert (root / "keyrgb").is_dir()
    assert (root / "tests" / "_paths.py").is_file()
