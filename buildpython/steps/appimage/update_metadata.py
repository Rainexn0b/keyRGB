"""Build-time AppImage update contract; no application update checks or downloads."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

APPIMAGE_NAME = "keyrgb-x86_64.AppImage"
UPDATE_INFORMATION = f"gh-releases-zsync|Rainexn0b|keyRGB|latest|{APPIMAGE_NAME}.zsync"


def require_zsyncmake() -> None:
    if shutil.which("zsyncmake") is None:
        raise SystemExit("AppImage updates require zsyncmake (install the zsync package).")


def packaging_args(appimagetool: Path, appdir: Path, out: Path) -> list[str]:
    """Explicit stable channel, independent of ambient CI/repository variables."""

    return [
        str(appimagetool),
        "--appimage-extract-and-run",
        "-u",
        UPDATE_INFORMATION,
        "--file-url",
        APPIMAGE_NAME,
        str(appdir),
        str(out),
    ]


def validate_update_artifacts(appimage: Path) -> None:
    """Require the embedded route and a matching, complete zsync control file.

    The runtime option only prints metadata; it does not mount or launch KeyRGB.
    SHA-1 here is zsync's format checksum, not a signature or trust mechanism.
    The release's separate SHA-256 sidecar remains unchanged.
    """

    proc = subprocess.run(
        [str(appimage), "--appimage-updateinformation"],
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in os.environ.items() if key != "APPIMAGE_EXTRACT_AND_RUN"},
    )
    if proc.returncode != 0:
        raise SystemExit(f"Cannot read AppImage update information: {proc.stderr.strip()}")
    if proc.stdout.strip() != UPDATE_INFORMATION:
        raise SystemExit(f"AppImage update information mismatch: {proc.stdout.strip()!r}")
    _validate_zsync(appimage, Path(f"{appimage}.zsync"))
    print("AppImage updates checked: latest stable GitHub release; matching .zsync sidecar.")


def _validate_zsync(appimage: Path, sidecar: Path) -> None:
    if not sidecar.is_file():
        raise SystemExit(f"Missing AppImage update sidecar: {sidecar}")
    header, separator, table = sidecar.read_bytes().partition(b"\n\n")
    if not separator:
        raise SystemExit("Invalid zsync sidecar: missing header/checksum table separator")
    try:
        fields: dict[str, str] = {}
        for line in header.decode("ascii").splitlines():
            key, value = line.split(": ", 1)
            if key in fields:
                raise ValueError(f"duplicate {key}")
            fields[key] = value
        blocksize = int(fields["Blocksize"])
        length = int(fields["Length"])
        sequence, weak, strong = (int(value) for value in fields["Hash-Lengths"].split(","))
    except (UnicodeError, KeyError, ValueError) as exc:
        raise SystemExit(f"Invalid zsync sidecar header: {exc}") from exc
    if not fields.get("zsync"):
        raise SystemExit("Invalid zsync sidecar: missing format version")
    if fields.get("Filename") != APPIMAGE_NAME or fields.get("URL") != APPIMAGE_NAME:
        raise SystemExit("Invalid zsync sidecar: filename/URL must be the relative AppImage asset name")
    if length <= 0 or length != appimage.stat().st_size:
        raise SystemExit("Invalid zsync sidecar: AppImage length mismatch")
    if blocksize <= 0 or blocksize & (blocksize - 1):
        raise SystemExit("Invalid zsync sidecar: block size must be a positive power of two")
    if not (1 <= sequence <= 2 and 1 <= weak <= 4 and 1 <= strong <= 16):
        raise SystemExit("Invalid zsync sidecar: unsupported checksum lengths")
    blocks = (length + blocksize - 1) // blocksize
    if len(table) != blocks * (weak + strong):
        raise SystemExit("Invalid zsync sidecar: incomplete or oversized block checksum table")
    digest = hashlib.sha1(usedforsecurity=False)
    with appimage.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if fields.get("SHA-1") != digest.hexdigest():
        raise SystemExit("Invalid zsync sidecar: AppImage checksum mismatch")
