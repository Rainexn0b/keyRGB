from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def bundle_tkinter(*, appdir: Path) -> None:
    """Bundle Tkinter native libraries and Tcl/Tk script libraries into the AppImage.

    Tkinter needs both native .so files AND the Tcl/Tk script directories
    (containing init.tcl, tk.tcl, and other support scripts) to work.
    """

    usr_lib = appdir / "usr" / "lib"
    usr_lib.mkdir(parents=True, exist_ok=True)

    # Common system library paths for tk/tcl shared libraries.
    lib_search_paths = [
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/lib64"),
        Path("/usr/lib"),
    ]

    # Look for libtk and libtcl (we need both for tkinter to work).
    # Prefer versioned .so files (e.g., libtk8.6.so) over unversioned symlinks.
    tk_patterns = ["libtk8.*.so*", "libtk.so*"]
    tcl_patterns = ["libtcl8.*.so*", "libtcl.so*"]

    def find_lib(patterns: list[str]) -> Path | None:
        for search_path in lib_search_paths:
            if not search_path.exists():
                continue
            for pattern in patterns:
                matches = list(search_path.glob(pattern))
                # Prefer versioned .so files (not symlinks ending in just .so)
                for candidate in matches:
                    if candidate.is_file() and not candidate.is_symlink():
                        return candidate
                # Fallback: use any match including symlinks
                if matches:
                    return matches[0]
        return None

    tk_lib = find_lib(tk_patterns)
    tcl_lib = find_lib(tcl_patterns)

    if tk_lib is None or tcl_lib is None:
        # Tkinter libraries not found; AppImage will require system tk/tcl.
        return

    # Copy both libraries into the AppImage usr/lib.
    shutil.copy2(tk_lib, usr_lib / tk_lib.name)
    shutil.copy2(tcl_lib, usr_lib / tcl_lib.name)

    # Also handle any immediate symlink dependencies (e.g., libtk8.6.so -> libtk8.6.so.0)
    for lib in [tk_lib, tcl_lib]:
        if lib.is_symlink():
            real = lib.resolve()
            if real.exists() and real != lib:
                shutil.copy2(real, usr_lib / real.name)

    # Bundle Tcl/Tk script libraries (init.tcl and support files).
    # These are required for tkinter to initialize properly.
    script_search_paths = [
        Path("/usr/share/tcltk"),
        Path("/usr/share"),
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/lib64"),
        Path("/usr/lib"),
    ]

    for search_root in script_search_paths:
        if not search_root.exists():
            continue

        # Look for tcl8.6 and tk8.6 directories
        for script_dir_name in ["tcl8.6", "tk8.6"]:
            script_dir = search_root / script_dir_name
            if script_dir.exists() and script_dir.is_dir():
                dst = usr_lib / script_dir_name
                if not dst.exists():
                    shutil.copytree(script_dir, dst, symlinks=False)
                    print(f"Bundled {script_dir_name} scripts: {script_dir} -> {dst}")

    _bundle_tk_shared_lib_deps(appdir=appdir, usr_lib=usr_lib, tk_lib=tk_lib, tcl_lib=tcl_lib)


def _bundle_tk_shared_lib_deps(*, appdir: Path, usr_lib: Path, tk_lib: Path, tcl_lib: Path) -> None:
    # Bundle shared library deps needed by Tk / _tkinter (e.g. libXft.so.2) so the
    # AppImage works on minimal systems without X11/font libs installed.

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

    def ldd_deps(binary: Path) -> dict[str, Path]:
        """Return DT_NEEDED libs resolved by ldd as {soname: path}."""
        try:
            proc = subprocess.run(
                ["ldd", str(binary)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        except Exception:
            return {}

        if proc.returncode != 0:
            return {}

        out: dict[str, Path] = {}
        for raw in (proc.stdout or "").splitlines():
            line = raw.strip()
            if not line or line.startswith("linux-vdso"):
                continue

            # Formats:
            #   libXft.so.2 => /usr/lib/x86_64-linux-gnu/libXft.so.2 (0x...)
            #   /lib64/ld-linux-x86-64.so.2 (0x...)
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
                p = Path(path_str)
                out[p.name] = p

        return out

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

            # These are commonly provided by every distro and are frequently
            # consumed by system GTK/Pango stacks. Bundling older copies can
            # cause hard-to-debug symbol/version mismatches (notably breaking
            # PyGObject/AppIndicator tray startup on Fedora-like distros).
            "libfontconfig.so.1",
            "libfreetype.so.6",
        }

        for soname, src in ldd_deps(binary).items():
            if soname.startswith(("libfontconfig.so", "libfreetype.so")):
                continue
            if soname in skip_names:
                continue
            if not src.exists():
                continue
            # Only pull from system library locations.
            if not str(src).startswith(("/usr/lib", "/usr/lib64", "/lib", "/lib64")):
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
