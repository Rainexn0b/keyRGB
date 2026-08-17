from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_RELEASE = _REPO_ROOT / ".github" / "workflows" / "release.yml"
_COMMON_CORE = _REPO_ROOT / "scripts" / "lib" / "common_core.sh"


def _assert_action_pinned(text: str, *, action_prefix: str) -> None:
    pattern = rf"uses:\s+{re.escape(action_prefix)}@([0-9a-f]{{40}})\s+#\s*v\d+"
    matches = re.findall(pattern, text)
    assert matches, f"expected SHA-pinned action for {action_prefix}"
    assert not re.search(rf"uses:\s+{re.escape(action_prefix)}@v\d+\s*$", text, flags=re.MULTILINE)


def test_github_workflows_pin_actions_to_commit_shas() -> None:
    ci = _CI.read_text(encoding="utf-8")
    release = _RELEASE.read_text(encoding="utf-8")

    _assert_action_pinned(ci, action_prefix="actions/checkout")
    _assert_action_pinned(ci, action_prefix="actions/setup-python")
    _assert_action_pinned(release, action_prefix="actions/checkout")
    _assert_action_pinned(release, action_prefix="actions/setup-python")
    _assert_action_pinned(release, action_prefix="softprops/action-gh-release")


def test_require_checksum_fails_closed_without_sidecar(tmp_path: Path) -> None:
    payload = tmp_path / "artifact.bin"
    payload.write_bytes(b"payload")
    script = textwrap.dedent(
        f"""
        set -euo pipefail
        SCRIPT_DIR="{_REPO_ROOT / "scripts"}"
        # shellcheck disable=SC1091
        source "$SCRIPT_DIR/lib/common_core.sh"
        download_url_quiet() {{ return 1; }}
        have_cmd() {{
          if [ "$1" = "sha256sum" ]; then
            return 0
          fi
          command -v "$1" >/dev/null 2>&1
        }}
        KEYRGB_REQUIRE_CHECKSUM=1
        verify_downloaded_sha256 "{payload}" "https://example.invalid/missing.sha256"
        """
    )
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert completed.returncode != 0, completed.stdout
    assert "KEYRGB_REQUIRE_CHECKSUM=1" in completed.stdout
    assert not payload.exists()


def test_common_core_documents_require_checksum_contract() -> None:
    text = _COMMON_CORE.read_text(encoding="utf-8")
    assert "KEYRGB_REQUIRE_CHECKSUM" in text
    assert "fail closed" in text or "require_checksum=1" in text
