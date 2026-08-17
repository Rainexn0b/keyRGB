from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import urllib.request
from pathlib import Path


def env_flag(name: str) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(url) as resp, dst.open("wb") as f:
        shutil.copyfileobj(resp, f)


def download_verified(url: str, dst: Path, *, expected_sha256: str) -> None:
    """Download ``url`` to ``dst`` and require an exact SHA-256 match.

    Existing files are reused only when their digest already matches. A mismatch
    deletes the destination and raises ``SystemExit`` so release tooling cannot
    silently continue with a tampered or stale binary.
    """

    expected = str(expected_sha256 or "").strip().lower()
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise SystemExit(f"Invalid expected SHA-256 digest for {dst.name}: {expected_sha256!r}")

    if dst.exists():
        actual_existing = sha256_file(dst).lower()
        if actual_existing == expected:
            return
        dst.unlink(missing_ok=True)

    download(url, dst)
    actual = sha256_file(dst).lower()
    if actual != expected:
        dst.unlink(missing_ok=True)
        raise SystemExit(
            f"SHA-256 mismatch for {dst.name}.\n  expected: {expected}\n  actual:   {actual}\n  url:      {url}"
        )


def chmod_x(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_checked(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
