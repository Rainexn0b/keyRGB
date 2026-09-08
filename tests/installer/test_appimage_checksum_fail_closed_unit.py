from __future__ import annotations

import hashlib
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMON_CORE = _REPO_ROOT / "scripts" / "lib" / "common_core.sh"
_USER_INTEGRATION = _REPO_ROOT / "scripts" / "lib" / "user_integration.sh"

_PAYLOAD = b"keyrgb-checksum-fixture-payload"
_SIDECAR_URL = "https://example.invalid/keyrgb-x86_64.AppImage.sha256"
_MISSING_TOOL_PRELUDE = 'have_cmd() { if [ "$1" = "sha256sum" ]; then return 1; fi; command -v "$1" >/dev/null 2>&1; }'


def _digest(payload: bytes = _PAYLOAD) -> str:
    return hashlib.sha256(payload).hexdigest()


def _run_verify(
    tmp_path: Path,
    *,
    sidecar: str | None,
    tag: str,
    require_checksum: str | None = None,
    prelude: str = "",
    payload_name: str = "artifact.bin",
) -> tuple[int, str]:
    payload = tmp_path / payload_name
    payload.write_bytes(_PAYLOAD)
    if sidecar is None:
        downloader = "download_url_quiet() { return 1; }"
    else:
        fixture = tmp_path / "sidecar.sha256"
        fixture.write_text(sidecar, encoding="utf-8")
        downloader = f'download_url_quiet() {{ cp "{fixture}" "$2"; }}'
    script = (
        f'set -euo pipefail\nsource "{_COMMON_CORE}"\n{prelude}\n{downloader}\n'
        f'verify_downloaded_sha256 "{payload}" "{_SIDECAR_URL}" "{tag}"\n'
    )
    env = {k: v for k, v in os.environ.items() if k != "KEYRGB_REQUIRE_CHECKSUM"}
    if require_checksum is not None:
        env["KEYRGB_REQUIRE_CHECKSUM"] = require_checksum
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
        env=env,
    )
    return completed.returncode, completed.stdout


def _assert_verified(rc: int, tmp_path: Path, output: str, name: str = "artifact.bin") -> None:
    assert rc == 0, output
    assert "Integrity verified" in output, output
    assert (tmp_path / name).exists()


def _assert_rejected(rc: int, tmp_path: Path, output: str, name: str = "artifact.bin") -> None:
    assert rc != 0, output
    assert "Integrity verification failed" in output, output
    assert not (tmp_path / name).exists(), "rejected payload must be removed"


@pytest.mark.parametrize(
    ("sidecar", "tag", "payload_name"),
    [
        (f"{_digest()}\n", "v0.35.0", "artifact.bin"),
        (f"{_digest()}  keyrgb-x86_64.AppImage\n", "v0.23.4", "artifact.bin"),
        (f"{_digest()} *keyrgb-x86_64.AppImage\n", "v0.35.0", "artifact.bin"),
        (f"{_digest().upper()}\n", "v0.35.0", "artifact.bin"),
        (f"{_digest()}  keyrgb-x86_64.AppImage\n", "v0.23.3", "artifact.bin"),
        (f"{_digest()}\n", "v0.35.0", "artifact with space.bin"),
    ],
    ids=["digest-only", "standard", "binary-mode", "uppercase", "historical", "spaced-filename"],
)
def test_valid_sidecars_verify(tmp_path: Path, sidecar: str, tag: str, payload_name: str) -> None:
    rc, output = _run_verify(tmp_path, sidecar=sidecar, tag=tag, payload_name=payload_name)
    _assert_verified(rc, tmp_path, output, payload_name)


@pytest.mark.parametrize(
    ("sidecar", "tag", "marker"),
    [
        (f"{'0' * 64}\n", "v0.35.0", "mismatch"),
        (None, "v0.35.0", "no sha-256 sidecar"),
        ("", "v0.35.0", "empty or malformed"),
        (f"{'0' * 64}\n", "v0.23.3", "mismatch"),
        ("", "v0.23.3", "empty or malformed"),
        ("abc123  keyrgb-x86_64.AppImage\n", "v0.35.0", "empty or malformed"),
        (f"{'z' * 64}  keyrgb-x86_64.AppImage\n", "v0.35.0", "empty or malformed"),
        ("notahash  keyrgb-x86_64.AppImage\n", "v0.35.0", "empty or malformed"),
        ("abc\n", "v0.35.0", "empty or malformed"),
        (f"{_digest()}\n{_digest()}\n", "v0.35.0", "empty or malformed"),
        (f"{_digest()}  keyrgb-x86_64.AppImage\nextra-line\n", "v0.35.0", "empty or malformed"),
        (f"{_digest()} arbitrary\n", "v0.35.0", "empty or malformed"),
        (f"{_digest()} garbage with spaces\n", "v0.35.0", "empty or malformed"),
        (f"{_digest()}\tkeyrgb-x86_64.AppImage\n", "v0.35.0", "empty or malformed"),
        (f"{_digest()} *\n", "v0.35.0", "empty or malformed"),
        (f"{_digest()} -\n", "v0.35.0", "empty or malformed"),
    ],
    ids=[
        "mismatch-current",
        "missing-current",
        "empty-current",
        "mismatch-historical",
        "malformed-historical",
        "short",
        "nonhex",
        "arbitrary-first-field",
        "short-digest-only",
        "extra-line",
        "trailing-garbage",
        "single-space-arbitrary-suffix",
        "multiword-suffix",
        "tab-separator",
        "binary-marker-empty-filename",
        "dash-suffix",
    ],
)
def test_rejected_sidecars_fail_and_remove(tmp_path: Path, sidecar: str | None, tag: str, marker: str) -> None:
    rc, output = _run_verify(tmp_path, sidecar=sidecar, tag=tag)
    assert marker in output.lower(), output
    _assert_rejected(rc, tmp_path, output)


@pytest.mark.parametrize(
    ("prelude", "marker"),
    [
        (_MISSING_TOOL_PRELUDE, "sha256sum not found"),
        ("sha256sum() { return 1; }", "sha256sum failed"),
        ("sha256sum() { printf 'bogus-output\\n'; }", "malformed output"),
        (f"sha256sum() {{ printf '{_digest()} arbitrary-output\\n'; }}", "malformed output"),
        (f"sha256sum() {{ printf '{_digest()}\\tkeyrgb-x86_64.AppImage\\n'; }}", "malformed output"),
        (f"sha256sum() {{ printf '{_digest()}  $1\\nextra-output-line\\n'; }}", "malformed output"),
        ("mktemp() { return 1; }", "could not create a temporary file"),
    ],
    ids=[
        "missing-tool",
        "hash-failure",
        "hash-malformed",
        "hash-nonstandard-single-space",
        "hash-nonstandard-tab-output",
        "hash-extra-line",
        "mktemp-failure",
    ],
)
def test_tool_failures_fail_and_remove(tmp_path: Path, prelude: str, marker: str) -> None:
    rc, output = _run_verify(tmp_path, sidecar=f"{_digest()}\n", tag="v0.35.0", prelude=prelude)
    assert marker in output.lower(), output
    _assert_rejected(rc, tmp_path, output)


@pytest.mark.parametrize(
    ("tag", "prelude"),
    [
        ("v0.23.3", ""),
        ("v0.10.0", _MISSING_TOOL_PRELUDE),
        ("0.23.3", ""),
        ("v0.1.0", ""),
        ("v0.0.0", ""),
        ("v0.22.9", ""),
    ],
    ids=["missing-sidecar", "missing-tool", "no-v-prefix", "old-minor", "zero", "older-minor"],
)
def test_historical_compat_warns_and_continues(tmp_path: Path, tag: str, prelude: str) -> None:
    rc, output = _run_verify(tmp_path, sidecar=None, tag=tag, prelude=prelude)
    assert rc == 0, output
    assert "historical compatibility" in output.lower(), output
    assert (tmp_path / "artifact.bin").exists()


@pytest.mark.parametrize("override", ["1", "true", "yes", "on"])
def test_strict_override_forces_historical_failure(tmp_path: Path, override: str) -> None:
    rc, output = _run_verify(tmp_path, sidecar=None, tag="v0.23.3", require_checksum=override)
    _assert_rejected(rc, tmp_path, output)


@pytest.mark.parametrize("override", ["0", "false", "no", ""])
def test_weak_override_does_not_weaken_current(tmp_path: Path, override: str) -> None:
    rc, output = _run_verify(tmp_path, sidecar=None, tag="v0.35.0", require_checksum=override)
    _assert_rejected(rc, tmp_path, output)


@pytest.mark.parametrize(
    "tag",
    [
        "",
        "main",
        "develop",
        "not-a-version",
        "v0.23.4",
        "v0.23.4-rc1",
        "v1.0.0",
        "v0.24.0",
        "v0.23.03",
        "v01.2.3",
        "v0.02.3",
        "v0.23.3 ",
        "v99999999999999999999999.0.0",
        "v0.99999999999999999999999.0",
        "v0.23.99999999999999999999999",
    ],
    ids=[
        "empty",
        "main",
        "branch",
        "non-semver",
        "boundary",
        "prerelease",
        "major",
        "minor",
        "leading-zero-patch",
        "leading-zero-major",
        "leading-zero-minor",
        "trailing-space",
        "huge-major",
        "huge-minor",
        "huge-patch",
    ],
)
def test_strict_tags_fail_without_sidecar(tmp_path: Path, tag: str) -> None:
    rc, output = _run_verify(tmp_path, sidecar=None, tag=tag)
    _assert_rejected(rc, tmp_path, output)


def _run_appimage_install(tmp_path: Path, *, version_tag: str, resolver_body: str) -> tuple[int, str, str]:
    dst = tmp_path / "keyrgb.AppImage"
    capture = tmp_path / "captured_tag"
    script = (
        "set -euo pipefail\n"
        f'source "{_COMMON_CORE}"\n'
        f'source "{_USER_INTEGRATION}"\n'
        f"resolve_release_with_asset() {{ {resolver_body} }}\n"
        'download_url_progress() { printf "x" >"$2"; return 0; }\n'
        f'verify_downloaded_sha256() {{ printf \'%s\' "$3" >"{capture}"; return 0; }}\n'
        f'appimage_install "{dst}" "keyrgb-x86_64.AppImage" "{version_tag}" "n" >/dev/null\n'
    )
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
        env={**os.environ},
    )
    captured = capture.read_text(encoding="utf-8") if capture.exists() else ""
    return completed.returncode, completed.stdout, captured


@pytest.mark.parametrize(
    ("version_tag", "resolver_body", "expected"),
    [
        ("v0.23.3", 'echo "UNEXPECTED-RESOLVER-CALL" >&2; return 1;', "v0.23.3"),
        ("", 'printf "%s" "v0.35.0|https://example.invalid/keyrgb-x86_64.AppImage|false";', "v0.35.0"),
        ("", "return 1;", "main"),
    ],
    ids=["explicit", "resolved", "fallback-main"],
)
def test_appimage_install_propagates_release_tag(
    tmp_path: Path, version_tag: str, resolver_body: str, expected: str
) -> None:
    rc, output, captured = _run_appimage_install(tmp_path, version_tag=version_tag, resolver_body=resolver_body)
    assert rc == 0, output
    assert captured == expected, output


def test_appimage_install_download_failure_is_distinct_from_integrity(tmp_path: Path) -> None:
    dst = tmp_path / "keyrgb.AppImage"
    script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{_COMMON_CORE}"
        source "{_USER_INTEGRATION}"
        resolve_release_with_asset() {{ return 1; }}
        download_url_progress() {{ return 1; }}
        verify_downloaded_sha256() {{ echo "UNEXPECTED-VERIFY-CALL" >&2; return 0; }}
        appimage_install "{dst}" "keyrgb-x86_64.AppImage" "v0.35.0" "n" >/dev/null
        """
    )
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
        env={**os.environ},
    )
    assert completed.returncode != 0, completed.stdout
    assert "Failed to download AppImage" in completed.stdout, completed.stdout
    assert "Integrity verification failed" not in completed.stdout, completed.stdout
