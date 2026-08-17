from __future__ import annotations

import shutil
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, run

_SHELL_SCRIPTS = (
    "install.sh",
    "uninstall.sh",
    "scripts/common.sh",
    "scripts/install_dev.sh",
    "scripts/install_user.sh",
    "scripts/uninstall.sh",
    "scripts/release/version.sh",
    "scripts/lib/common_core.sh",
    "scripts/lib/optional_components.sh",
    "scripts/lib/privileged_helpers.sh",
    "scripts/lib/state.sh",
    "scripts/lib/uninstall_match.sh",
    "scripts/lib/user_integration.sh",
    "scripts/lib/user_prompts.sh",
)


def shell_scripts() -> tuple[str, ...]:
    return _SHELL_SCRIPTS


def shellcheck_bin() -> str | None:
    return shutil.which("shellcheck")


def shellcheck_runner() -> RunResult:
    root = repo_root()
    binary = shellcheck_bin()
    if binary is None:
        return RunResult(
            command_str="shellcheck",
            stdout="ShellCheck not installed\n",
            stderr="",
            exit_code=0,
        )

    missing = [path for path in _SHELL_SCRIPTS if not (root / path).is_file()]
    if missing:
        listed = ", ".join(missing)
        return RunResult(
            command_str=f"{binary} -x <scripts>",
            stdout=f"ShellCheck script list is stale; missing: {listed}\n",
            stderr="",
            exit_code=1,
        )

    args = [binary, "-x", *[str(Path(path)) for path in _SHELL_SCRIPTS]]
    return run(
        args,
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
