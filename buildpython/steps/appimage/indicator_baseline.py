"""Pinned Ubuntu 22.04 indicator libraries for newer build hosts.

GTK, GLib, and glibc stay on the host desktop. Only the small indicator stack
is substituted, and only when the copies found on the build machine need a
glibc newer than 2.35. The substitute packages are immutable Jammy debs.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ...utils.paths import repo_root
from .common import download_verified
from .compatibility import elf_exceeds_glibc_baseline

_ARCHIVE = "https://archive.ubuntu.com/ubuntu"
_MANAGED_PREFIXES = (
    "libappindicator3.so",
    "libayatana-appindicator3.so",
    "libayatana-indicator3.so",
    "libindicator3.so",
    "libayatana-ido3-0.4.so",
    "libdbusmenu-gtk3.so",
    "libdbusmenu-glib.so",
)
_REQUIRED_SONAMES = (
    "libayatana-appindicator3.so.1",
    "libayatana-indicator3.so.7",
    "libayatana-ido3-0.4.so.0",
    "libdbusmenu-glib.so.4",
    "libdbusmenu-gtk3.so.4",
)


@dataclass(frozen=True, slots=True)
class _BaselineDeb:
    filename: str
    sha256: str
    archive_path: str

    @property
    def url(self) -> str:
        return f"{_ARCHIVE}/{self.archive_path}"


# Jammy binary-amd64 packages. Hashes are the archive SHA256 values.
_BASELINE_DEBS = (
    _BaselineDeb(
        filename="libayatana-appindicator3-1_0.5.90-7ubuntu2_amd64.deb",
        sha256="e66308d293448b6f0384ae6d20b04f6c1a1172d2738da570ce585a574f8cbba9",
        archive_path="pool/main/liba/libayatana-appindicator/libayatana-appindicator3-1_0.5.90-7ubuntu2_amd64.deb",
    ),
    _BaselineDeb(
        filename="libayatana-indicator3-7_0.9.1-1_amd64.deb",
        sha256="27d7fb04242fa4a2157cc0cd8f0c4154965edc8eb4916843f199d9f8e4a5d33e",
        archive_path="pool/main/liba/libayatana-indicator/libayatana-indicator3-7_0.9.1-1_amd64.deb",
    ),
    _BaselineDeb(
        filename="libayatana-ido3-0.4-0_0.9.1-1_amd64.deb",
        sha256="0c1c8eb17cba75494f7e79082e02576fe882ee618f52fb69f27b4826eeb38df2",
        archive_path="pool/main/a/ayatana-ido/libayatana-ido3-0.4-0_0.9.1-1_amd64.deb",
    ),
    _BaselineDeb(
        filename="libdbusmenu-glib4_16.04.1+18.10.20180917-0ubuntu8_amd64.deb",
        sha256="638cb5a015487c9e92f7983ec60946586eb7f8aad70d7767d2e063f469229bff",
        archive_path="pool/main/libd/libdbusmenu/libdbusmenu-glib4_16.04.1+18.10.20180917-0ubuntu8_amd64.deb",
    ),
    _BaselineDeb(
        filename="libdbusmenu-gtk3-4_16.04.1+18.10.20180917-0ubuntu8_amd64.deb",
        sha256="c1db54b87b88a7e5046d75e44b47f49cdaf0faeed1c2b7cc0f0344d130610d7d",
        archive_path="pool/main/libd/libdbusmenu/libdbusmenu-gtk3-4_16.04.1+18.10.20180917-0ubuntu8_amd64.deb",
    ),
)


def host_indicator_stack_exceeds_baseline(usr_lib: Path) -> bool:
    """Return whether a managed indicator library in ``usr_lib`` exceeds the ABI floor."""

    if not usr_lib.is_dir():
        return False
    return any(
        elf_exceeds_glibc_baseline(path)
        for path in usr_lib.iterdir()
        if path.is_file() and not path.is_symlink() and _is_managed(path.name)
    )


def install_ubuntu_2204_indicator_stack(usr_lib: Path, *, cache_dir: Path | None = None) -> None:
    """Replace managed indicator libraries with the pinned Ubuntu 22.04 stack.

    Downloads are verified before the destination is changed. A pinned library
    that itself exceeds the ceiling is rejected and the host copies are left in
    place so a later ABI check can still fail closed.
    """

    cache = cache_dir or (repo_root() / "dist" / "tools" / "ubuntu-22.04")
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "libs"
        staged.mkdir()
        for package in _BASELINE_DEBS:
            archive = cache / package.filename
            download_verified(package.url, archive, expected_sha256=package.sha256)
            _extract_deb_libraries(archive, staged)
        _require_baseline_libraries(staged)
        _replace_managed_libraries(usr_lib, staged)


def _is_managed(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in _MANAGED_PREFIXES)


def _require_baseline_libraries(staged: Path) -> None:
    missing = [name for name in _REQUIRED_SONAMES if not (staged / name).exists()]
    if missing:
        raise SystemExit(f"Ubuntu 22.04 indicator packages did not contain: {', '.join(missing)}")
    for path in staged.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        if elf_exceeds_glibc_baseline(path):
            raise SystemExit(f"Pinned Ubuntu 22.04 indicator library exceeds GLIBC_2.35: {path.name}")


def _replace_managed_libraries(usr_lib: Path, staged: Path) -> None:
    usr_lib.mkdir(parents=True, exist_ok=True)
    for path in list(usr_lib.iterdir()):
        if _is_managed(path.name):
            path.unlink()
    for path in staged.iterdir():
        dest = usr_lib / path.name
        if path.is_symlink():
            os.symlink(os.readlink(path), dest)
        else:
            shutil.copy2(path, dest)


def _extract_deb_libraries(archive: Path, dest: Path) -> None:
    ar = shutil.which("ar")
    if ar is None:
        raise SystemExit("Ubuntu 22.04 indicator fallback requires ar (install binutils).")
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [ar, "x", str(archive)],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise SystemExit(f"Cannot unpack {archive.name}: {proc.stderr.strip()}")
        data = next(Path(tmp).glob("data.tar.*"), None)
        if data is None:
            raise SystemExit(f"{archive.name} has no data.tar payload")
        with _open_data_tar(data) as tar:
            for member in tar.getmembers():
                _extract_library_member(tar, member, dest)


def _extract_library_member(tar: tarfile.TarFile, member: tarfile.TarInfo, dest: Path) -> None:
    name = Path(member.name).name
    if ".so" not in name or name.startswith("."):
        return
    target = dest / name
    if target.exists() or target.is_symlink():
        target.unlink()
    if member.issym() or member.islnk():
        os.symlink(Path(member.linkname).name, target)
        return
    if not member.isfile():
        return
    extracted = tar.extractfile(member)
    if extracted is None:
        raise SystemExit(f"Cannot read {name} from indicator package")
    target.write_bytes(extracted.read())
    target.chmod(0o755)


@contextmanager
def _open_data_tar(path: Path) -> Iterator[tarfile.TarFile]:
    if path.name.endswith(".zst"):
        zstd = shutil.which("zstd")
        if zstd is None:
            raise SystemExit("Ubuntu 22.04 indicator fallback requires zstd to extract pinned packages.")
        proc = subprocess.run([zstd, "-d", "-c", str(path)], capture_output=True, check=False)
        if proc.returncode != 0:
            detail = proc.stderr.decode(errors="replace").strip()
            raise SystemExit(f"Cannot decompress {path.name}: {detail}")
        with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as handle:
            yield handle
        return
    with tarfile.open(path) as handle:
        yield handle
