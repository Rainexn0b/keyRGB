from __future__ import annotations

from pathlib import Path

from ..utils.paths import repo_root
from ..utils.project_metadata import ProjectMetadataError, read_project_dependencies
from ..utils.subproc import RunResult

_REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "install.sh",
    "pyproject.toml",
]

# Installed privileged helper and its polkit policy. These must stay present
# so installer, uninstaller, and privilege escalation keep working.
_POWER_HELPER_REQUIRED_FILES = [
    "system/bin/keyrgb-power-helper",
    "system/polkit/90-keyrgb-power-helper.rules",
    "system/polkit/org.keyrgb.power-helper.policy",
]

# Exact installed path. Application defaults, installer, uninstaller, and the
# polkit rule must all reference this single path; any drift fails closed.
POWER_HELPER_INSTALLED_PATH = "/usr/local/bin/keyrgb-power-helper"

# Every file that must reference POWER_HELPER_INSTALLED_PATH exactly.
POWER_HELPER_PATH_CONSUMERS = (
    "keyrgb/core/backends/sysfs/privileged.py",
    "keyrgb/core/power/system/_apply.py",
    "keyrgb/core/power/system/_observe.py",
    "scripts/lib/privileged_helpers.sh",
    "scripts/uninstall.sh",
    "system/polkit/90-keyrgb-power-helper.rules",
)

_AUTOSTART_INSTALLER_FILES = [
    "install.sh",
    "scripts/install_user.sh",
    "scripts/lib/user_integration.sh",
]

_AUTOSTART_MARKERS = ("~/.config/autostart", ".config/autostart")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _installer_mentions_autostart(root: Path) -> bool:
    for relative_path in _AUTOSTART_INSTALLER_FILES:
        candidate = root / relative_path
        if not candidate.exists():
            continue
        candidate_text = _read_text(candidate)
        if any(marker in candidate_text for marker in _AUTOSTART_MARKERS):
            return True
    return False


def _power_helper_errors(root: Path) -> list[str]:
    errors: list[str] = []

    missing = [p for p in _POWER_HELPER_REQUIRED_FILES if not (root / p).exists()]
    if missing:
        errors.append(
            "Missing required power-helper files:\n" + "\n".join(f"  - {m}" for m in missing),
        )

    for relative_path in POWER_HELPER_PATH_CONSUMERS:
        candidate = root / relative_path
        if not candidate.exists():
            errors.append(f"{relative_path}: missing file; expected reference to {POWER_HELPER_INSTALLED_PATH}")
            continue
        try:
            candidate_text = _read_text(candidate)
        except OSError as exc:
            errors.append(
                f"{relative_path}: unreadable file ({exc}); expected reference to {POWER_HELPER_INSTALLED_PATH}"
            )
            continue
        if POWER_HELPER_INSTALLED_PATH not in candidate_text:
            errors.append(
                f"{relative_path}: does not reference {POWER_HELPER_INSTALLED_PATH}; "
                "installed helper path drift is not allowed",
            )

    return errors


def repo_validation_runner() -> RunResult:
    root = repo_root()

    missing = [p for p in _REQUIRED_FILES if not (root / p).exists()]
    errors: list[str] = []
    warnings: list[str] = []

    if missing:
        errors.append("Missing required repo files:\n" + "\n".join(f"  - {m}" for m in missing))

    errors.extend(_power_helper_errors(root))

    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        py_text = _read_text(pyproject_path)
        if "[project.urls]" not in py_text or "github.com/Rainexn0b/keyRGB" not in py_text:
            warnings.append("pyproject.toml: project.urls does not appear to point at Rainexn0b/keyRGB")

        try:
            read_project_dependencies(pyproject_path)
        except ProjectMetadataError as exc:
            errors.append(f"pyproject.toml: {exc}")

    # install.sh can be a dispatcher; accept autostart handling in the delegated user installer path.
    if not _installer_mentions_autostart(root):
        warnings.append("installer: autostart entry not detected")

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
