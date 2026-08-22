from __future__ import annotations

from pathlib import Path

# Pytest adds the repo root via [tool.pytest.ini_options].pythonpath.
# This constant is only for tests that need a filesystem path to the checkout.
REPO_ROOT = str(Path(__file__).resolve().parents[1])
