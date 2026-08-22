"""
Unit tests: packaging/launcher consistency for the keyrgb entrypoint.

Checks that pyproject.toml [project.scripts] and the keyrgb wrapper script
agree on the module/function being launched.
"""

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_PYPROJECT = _ROOT / "pyproject.toml"
_WRAPPER = _ROOT / "keyrgb.sh"

EXPECTED_CONSOLE_SCRIPT = "keyrgb.tray.entrypoint:main"
EXPECTED_MODULE = "keyrgb.tray"


def _read_pyproject_text() -> str:
    return _PYPROJECT.read_text(encoding="utf-8")


def _read_wrapper_text() -> str:
    return _WRAPPER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# pyproject.toml assertions
# ---------------------------------------------------------------------------


def test_setuptools_package_discovery_is_keyrgb_only():
    """The installable distribution must not include the buildpython checkout helper."""
    text = _read_pyproject_text()
    match = re.search(
        r"(?ms)^\[tool\.setuptools\.packages\.find\].*?^include\s*=\s*\[(.*?)\]",
        text,
    )
    assert match is not None, "Could not find [tool.setuptools.packages.find] include list"
    includes = re.findall(r'"([^"]+)"', match.group(1))
    assert includes == ["keyrgb*"], f"package discovery include is {includes!r}, expected ['keyrgb*']"


def test_keyrgb_script_entry_in_pyproject():
    """[project.scripts] must declare keyrgb = 'keyrgb.tray.entrypoint:main'."""
    text = _read_pyproject_text()
    # Match the assignment inside [project.scripts]
    match = re.search(r"^\s*keyrgb\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
    assert match is not None, "Could not find 'keyrgb = ...' under [project.scripts] in pyproject.toml"
    actual = match.group(1)
    assert actual == EXPECTED_CONSOLE_SCRIPT, (
        f"pyproject.toml keyrgb script is {actual!r}, expected {EXPECTED_CONSOLE_SCRIPT!r}"
    )


# ---------------------------------------------------------------------------
# wrapper script assertions
# ---------------------------------------------------------------------------


def test_wrapper_invokes_correct_module():
    """keyrgb wrapper must pass '-m keyrgb.tray' to Python."""
    text = _read_wrapper_text()
    assert f"-m {EXPECTED_MODULE}" in text, f"keyrgb wrapper does not contain '-m {EXPECTED_MODULE}'"


def test_wrapper_uses_dash_B_flag():
    """keyrgb wrapper must pass '-B' to Python (dev bytecode policy)."""
    text = _read_wrapper_text()
    # Accept both '-B' standalone and as part of a combined flag group like '-Bm'.
    assert re.search(r"-B\b", text) is not None, "keyrgb wrapper does not include the '-B' flag"
