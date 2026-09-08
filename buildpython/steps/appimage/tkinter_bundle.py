from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ...utils.paths import repo_root
from ...utils.subproc import python_exe

#: Stable AppDir directory names for the Tcl/Tk script trees. These carry no
#: version suffix so AppRun and container smoke exports never hardcode one.
TCL_APPDIR_DIRNAME = "tcl"
TK_APPDIR_DIRNAME = "tk"


@dataclass(frozen=True)
class TkinterManifest:
    """Build-interpreter Tkinter facts derived from the interpreter itself."""

    extension: Path
    tcl_version: str
    tk_version: str
    base_prefix: Path


_TKINTER_MANIFEST_CODE = (
    "import json, sys, tkinter, _tkinter\n"
    "out = {'extension': _tkinter.__file__, 'tcl_version': str(tkinter.TclVersion),"
    " 'tk_version': str(tkinter.TkVersion), 'base_prefix': sys.base_prefix}\n"
    "print(json.dumps(out))\n"
)


def _parse_tkinter_manifest(payload: str) -> TkinterManifest:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise SystemExit(f"Failed to parse tkinter manifest: {payload}") from None

    if not isinstance(data, dict):
        raise SystemExit(f"Invalid tkinter manifest: {payload!r}")

    fields = {key: str(data.get(key, "")) for key in ("extension", "tcl_version", "tk_version", "base_prefix")}
    if not all(fields.values()):
        raise SystemExit(f"Invalid tkinter manifest (missing fields): {payload!r}")

    return TkinterManifest(
        extension=Path(fields["extension"]),
        tcl_version=fields["tcl_version"],
        tk_version=fields["tk_version"],
        base_prefix=Path(fields["base_prefix"]),
    )


def _tkinter_manifest() -> TkinterManifest:
    proc = subprocess.run(
        [python_exe(), "-c", _TKINTER_MANIFEST_CODE],
        cwd=str(repo_root()),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"Cannot query tkinter manifest from {python_exe()}: {proc.stderr}")
    return _parse_tkinter_manifest(proc.stdout)


def runtime_script_env_exports(here: str = "$HERE") -> tuple[str, str]:
    """Return canonical TCL_LIBRARY/TK_LIBRARY export lines for ``here``."""
    return (
        f'export TCL_LIBRARY="{here}/usr/lib/{TCL_APPDIR_DIRNAME}"',
        f'export TK_LIBRARY="{here}/usr/lib/{TK_APPDIR_DIRNAME}"',
    )


def _ldd_deps(binary: Path, *, lib_dirs: Sequence[Path] = ()) -> dict[str, Path]:
    """Return DT_NEEDED libs resolved by ldd as {soname: path}.

    ``lib_dirs`` are prepended to ``LD_LIBRARY_PATH`` for ldd so extension deps
    that only resolve via the interpreter layout (e.g. standalone Tcl 9 libs)
    are reported instead of ``not found``.
    """
    search = [str(item) for item in lib_dirs if str(item)]
    env: dict[str, str] | None = None
    if search:
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        combined = [*search, existing] if existing else search
        env = {**os.environ, "LD_LIBRARY_PATH": os.pathsep.join(combined)}

    try:
        proc = subprocess.run(
            ["ldd", str(binary)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=env,
        )
    except OSError:
        return {}

    if proc.returncode != 0:
        return {}

    out: dict[str, Path] = {}
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("linux-vdso"):
            continue

        if "=>" in line:
            left, right = line.split("=>", 1)
            soname = left.strip()
            right = right.strip()
            if not soname or right.startswith("not found"):
                continue
            path_str = right.split("(", 1)[0].strip()
            if not path_str.startswith("/"):
                continue
            out[soname] = Path(path_str)
            continue

        if line.startswith("/"):
            path_str = line.split("(", 1)[0].strip()
            path = Path(path_str)
            out[path.name] = path

    return out


def _ordered_existing_dirs(candidates: Sequence[Path]) -> list[Path]:
    seen: set[str] = set()
    dirs: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key in seen or not candidate.exists():
            continue
        seen.add(key)
        dirs.append(candidate)
    return dirs


def _native_lib_dirs(manifest: TkinterManifest) -> list[Path]:
    """Library dirs to search, interpreter base prefix first (exact matches only)."""
    base = manifest.base_prefix
    return _ordered_existing_dirs(
        [
            base / "lib",
            base / "lib64",
            base / "lib" / "x86_64-linux-gnu",
            base / "lib64" / "x86_64-linux-gnu",
            Path("/usr/lib/x86_64-linux-gnu"),
            Path("/usr/lib64"),
            Path("/usr/lib"),
        ]
    )


def _script_search_dirs(manifest: TkinterManifest) -> list[Path]:
    """Script-tree dirs to search, interpreter base prefix first (exact matches only)."""
    base = manifest.base_prefix
    return _ordered_existing_dirs(
        [
            base / "lib",
            base / "lib64",
            Path("/usr/share/tcltk"),
            Path("/usr/share"),
            Path("/usr/lib/x86_64-linux-gnu"),
            Path("/usr/lib64"),
            Path("/usr/lib"),
        ]
    )


def _find_exact_lib(search_dirs: Sequence[Path], *, stem: str) -> Path | None:
    """Find ``stem`` + ``.so*`` exactly; never fall back to another version."""
    for search_path in search_dirs:
        matches = sorted(search_path.glob(f"{stem}.so*"))
        # Prefer versioned .so files (not symlinks ending in just .so).
        for candidate in matches:
            if candidate.is_file() and not candidate.is_symlink():
                return candidate
        # Fallback: use any match including symlinks.
        if matches:
            return matches[0]
    return None


def _find_native_libs(manifest: TkinterManifest, search_dirs: Sequence[Path]) -> tuple[Path, Path]:
    """Locate exact Tcl/Tk native libs: separate ``libtcl<V>`` + ``libtk<V>`` or standalone combined ``libtcl<major>tk<V>``."""
    tcl_lib = _find_exact_lib(search_dirs, stem=f"libtcl{manifest.tcl_version}")

    tk_lib = _find_exact_lib(search_dirs, stem=f"libtk{manifest.tk_version}")
    if tk_lib is None:
        major = manifest.tk_version.split(".")[0]
        tk_lib = _find_exact_lib(search_dirs, stem=f"libtcl{major}tk{manifest.tk_version}")

    if tcl_lib is None or tk_lib is None:
        raise SystemExit(
            "Cannot bundle tkinter: no exact native library match for "
            f"Tcl {manifest.tcl_version} / Tk {manifest.tk_version} "
            f"(base_prefix={manifest.base_prefix}). KeyRGB requires tkinter."
        )
    assert tcl_lib is not None and tk_lib is not None
    return (tcl_lib, tk_lib)


def _find_script_dir(search_dirs: Sequence[Path], *, name: str) -> Path | None:
    for search_root in search_dirs:
        candidate = search_root / name
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def bundle_tkinter(*, appdir: Path) -> None:
    """Bundle Tkinter native libs + Tcl/Tk script trees into the AppImage.

    Versions come from the build interpreter's own ``_tkinter`` manifest, never
    from host distro Tcl packages. Script trees land at stable ``usr/lib/tcl``
    / ``usr/lib/tk`` paths so runtime exports carry no hardcoded version.
    """
    manifest = _tkinter_manifest()
    lib_dirs = _native_lib_dirs(manifest)
    tcl_lib, tk_lib = _find_native_libs(manifest, lib_dirs)

    usr_lib = appdir / "usr" / "lib"
    usr_lib.mkdir(parents=True, exist_ok=True)

    # Copy both libraries into the AppImage usr/lib.
    shutil.copy2(tcl_lib, usr_lib / tcl_lib.name)
    shutil.copy2(tk_lib, usr_lib / tk_lib.name)

    # Also handle any immediate symlink dependencies (e.g., libtk8.6.so -> libtk8.6.so.0)
    for lib in [tcl_lib, tk_lib]:
        if lib.is_symlink():
            real = lib.resolve()
            if real.exists() and real != lib:
                shutil.copy2(real, usr_lib / real.name)

    # Bundle Tcl/Tk script libraries (init.tcl and support files) under stable
    # version-free names. These are required for tkinter to initialize properly.
    script_dirs = _script_search_dirs(manifest)
    for dirname, version in (
        (TCL_APPDIR_DIRNAME, manifest.tcl_version),
        (TK_APPDIR_DIRNAME, manifest.tk_version),
    ):
        src = _find_script_dir(script_dirs, name=f"{dirname}{version}")
        if src is None:
            raise SystemExit(
                f"Cannot bundle tkinter: missing {dirname}{version} script tree "
                f"(base_prefix={manifest.base_prefix}). KeyRGB requires tkinter."
            )
        dst = usr_lib / dirname
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=False)
        print(f"Bundled {dirname}{version} scripts: {src} -> {dst}")

    _bundle_tk_shared_lib_deps(appdir=appdir, usr_lib=usr_lib, tk_lib=tk_lib, tcl_lib=tcl_lib, lib_dirs=lib_dirs)


def _bundle_tk_shared_lib_deps(
    *,
    appdir: Path,
    usr_lib: Path,
    tk_lib: Path,
    tcl_lib: Path,
    lib_dirs: Sequence[Path] = (),
) -> None:
    # Bundle shared lib deps needed by Tk / _tkinter (e.g. libXft.so.2) for minimal systems.

    def bundle_symlink_chain(src: Path) -> None:
        """Copy a library and its symlink chain into usr/lib."""
        current = src
        seen: set[str] = set()

        while current.exists() and current.name not in seen:
            dst = usr_lib / current.name
            if current.is_symlink():
                link_target = os.readlink(current)
                if os.path.isabs(link_target):
                    link_target = os.path.basename(link_target)
                if dst.exists() or dst.is_symlink():
                    dst.unlink()
                os.symlink(link_target, dst)
                seen.add(current.name)

                next_target = current.readlink()
                if next_target.is_absolute():
                    current = next_target
                else:
                    current = current.parent / next_target
                continue

            shutil.copy2(current, dst)
            seen.add(current.name)
            break

    def bundle_deps_for(binary: Path) -> None:
        # Avoid bundling glibc/loader core libs.
        skip_names = {
            "ld-linux-x86-64.so.2",
            "libc.so.6",
            "libm.so.6",
            "libpthread.so.0",
            "libdl.so.2",
            "librt.so.1",
            "libutil.so.1",
            "libgcc_s.so.1",
            "libstdc++.so.6",
            # libfontconfig/freetype come from every distro's GTK/Pango stack;
            # bundling older copies breaks tray startup on Fedora-like distros.
            "libfontconfig.so.1",
            "libfreetype.so.6",
        }

        allowed_roots = ("/usr/lib", "/usr/lib64", "/lib", "/lib64", *(str(item) for item in lib_dirs))
        for soname, src in _ldd_deps(binary, lib_dirs=lib_dirs).items():
            if soname.startswith(("libfontconfig.so", "libfreetype.so")):
                continue
            if soname in skip_names:
                continue
            if not src.exists():
                continue
            # Only pull from known library locations (system dirs or the
            # interpreter base-prefix lib dirs); the Tcl/Tk libs themselves
            # are already copied explicitly above.
            if not str(src).startswith(allowed_roots):
                continue
            # If we already have this soname in the AppDir, skip.
            if (usr_lib / soname).exists() or (usr_lib / soname).is_symlink():
                continue
            bundle_symlink_chain(src)

    # Bundle deps for both Tk and the _tkinter extension (the latter is what
    # triggers missing libXft errors on minimal systems).
    bundle_deps_for(tk_lib)
    bundle_deps_for(tcl_lib)

    for ext in (appdir / "usr").glob("lib/python*/lib-dynload/_tkinter*.so"):
        if ext.exists():
            bundle_deps_for(ext)
