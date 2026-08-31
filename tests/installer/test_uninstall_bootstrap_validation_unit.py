from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_UNINSTALL = _REPO_ROOT / "uninstall.sh"


def _run_copied_uninstall(tmp_path: Path, *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    dest = tmp_path / "uninstall.sh"
    dest.write_text(_UNINSTALL.read_text(encoding="utf-8"), encoding="utf-8")
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        ["bash", str(dest)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=tmp_path,
        env=merged,
    )


def test_uninstall_dispatcher_validates_owner_before_curl() -> None:
    text = _UNINSTALL.read_text(encoding="utf-8")
    owner_call = text.index('_validate_github_owner "$KEYRGB_REPO_OWNER"')
    repo_call = text.index('_validate_github_repo "$KEYRGB_REPO_NAME"')
    first_bootstrap_curl = text.index('curl -fsSL "$base/')
    assert owner_call < first_bootstrap_curl
    assert repo_call < first_bootstrap_curl


def test_uninstall_bootstrap_rejects_invalid_repo_owner(tmp_path: Path) -> None:
    completed = _run_copied_uninstall(tmp_path, env={"KEYRGB_REPO_OWNER": "evil;rm"})
    assert completed.returncode != 0, completed.stdout
    assert "Invalid KEYRGB_REPO_OWNER" in completed.stdout


def test_uninstall_bootstrap_rejects_invalid_repo_name(tmp_path: Path) -> None:
    completed = _run_copied_uninstall(tmp_path, env={"KEYRGB_REPO_NAME": "bad/name"})
    assert completed.returncode != 0, completed.stdout
    assert "Invalid KEYRGB_REPO_NAME" in completed.stdout
