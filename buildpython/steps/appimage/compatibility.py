from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

# Ubuntu 22.04 is the oldest Ubuntu LTS in standard support. Keep this ceiling
# aligned with release.yml and the default container smoke matrix.
GLIBC_BASELINE = (2, 35)


def glibc_symbol_exceeds_baseline(symbol: str) -> bool:
    """Return whether a version-need symbol is newer than Ubuntu 22.04 or unrecognized."""

    suffix = symbol.removeprefix("GLIBC_")
    if not re.fullmatch(r"\d+(?:\.\d+)+", suffix):
        return True
    return tuple(int(part) for part in suffix.split(".")) > GLIBC_BASELINE


def elf_exceeds_glibc_baseline(path: Path) -> bool:
    """Return whether a regular ELF file needs a glibc newer than the AppImage ceiling."""

    if not path.is_file() or path.is_symlink():
        return False
    with path.open("rb") as stream:
        if stream.read(4) != b"\x7fELF":
            return False
    return any(glibc_symbol_exceeds_baseline(symbol) for symbol in _glibc_need_symbols(path))


def _glibc_need_symbols(path: Path) -> list[str]:
    readelf = shutil.which("readelf")
    if readelf is None:
        raise SystemExit("AppImage ABI check requires readelf (install binutils in the build environment).")
    proc = subprocess.run(
        [readelf, "--version-info", str(path)],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )
    if proc.returncode != 0:
        raise SystemExit(f"Cannot inspect AppImage ELF {path}: {proc.stderr}")
    needs = proc.stdout.partition("Version needs section")[2]
    return re.findall(r"Name:\s+(GLIBC_[\w.]+)", needs)


def validate_appdir_glibc(appdir: Path) -> None:
    """Reject newer glibc requirements in *any* bundled ELF, including wheels.

    glibc and its loader deliberately remain host-provided. Copying them into an
    AppImage is not a safe substitute for building on the supported ABI floor.
    Inspect version *needs*, not definitions or strings in an ELF's data section.
    """
    readelf = shutil.which("readelf")
    if readelf is None:
        raise SystemExit("AppImage ABI check requires readelf (install binutils in the build environment).")

    highest: tuple[int, ...] = (0,)
    checked: set[Path] = set()
    for path in sorted(appdir.rglob("*")):
        if not path.is_file() or path.resolve() in checked:
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        checked.add(path.resolve())
        for symbol in _glibc_need_symbols(path):
            if glibc_symbol_exceeds_baseline(symbol):
                raise SystemExit(
                    f"AppImage ABI baseline exceeded: {path.relative_to(appdir)} requires {symbol}; "
                    "maximum GLIBC_2.35. Rebuild on Ubuntu 22.04 with matching native dependencies."
                )
            suffix = symbol.removeprefix("GLIBC_")
            highest = max(highest, tuple(int(part) for part in suffix.split(".")))
    if not checked:
        raise SystemExit("Cannot verify AppImage ABI: AppDir contains no ELF files.")
    print(f"AppImage ABI checked: {len(checked)} ELF files; highest GLIBC_{'.'.join(map(str, highest))} (ceiling 2.35)")
