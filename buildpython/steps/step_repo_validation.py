from __future__ import annotations

from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult


_REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "install.sh",
    "pyproject.toml",
    "requirements.txt",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def repo_validation_runner() -> RunResult:
    root = repo_root()

    missing = [p for p in _REQUIRED_FILES if not (root / p).exists()]
    errors: list[str] = []
    warnings: list[str] = []

    if missing:
        errors.append("Missing required repo files:\n" + "\n".join(f"  - {m}" for m in missing))

    # requirements.txt should not hard-require PyQt6 (it is optional)
    req_path = root / "requirements.txt"
    if req_path.exists():
        req_text = _read_text(req_path)
        for line in req_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("PyQt6") and not stripped.startswith("#"):
                errors.append("requirements.txt hard-requires PyQt6; it should be optional (commented)")
                break

    # pyproject.toml should include optional dependency group for qt
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        py_text = _read_text(pyproject_path)
        if "[project.optional-dependencies]" not in py_text or "qt" not in py_text:
            warnings.append("pyproject.toml: optional dependency group 'qt' not detected")

        if "[project.urls]" not in py_text or "github.com/Rainexn0b/keyRGB" not in py_text:
            warnings.append("pyproject.toml: project.urls does not appear to point at Rainexn0b/keyRGB")

    # install.sh should set up autostart
    install_path = root / "install.sh"
    if install_path.exists():
        install_text = _read_text(install_path)
        if "~/.config/autostart" not in install_text and ".config/autostart" not in install_text:
            warnings.append("install.sh: autostart entry not detected")

    stdout_lines: list[str] = []
    stdout_lines.append("Repo validation")
    stdout_lines.append("")

    if errors:
        stdout_lines.append("Errors:")
        stdout_lines.extend(f"  - {e}" for e in errors)

    if warnings:
        stdout_lines.append("")
        stdout_lines.append("Warnings:")
        stdout_lines.extend(f"  - {w}" for w in warnings)

    if not errors and not warnings:
        stdout_lines.append("OK: repo looks consistent.")

    exit_code = 1 if errors else 0

    return RunResult(
        command_str="(internal) repo validation",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
