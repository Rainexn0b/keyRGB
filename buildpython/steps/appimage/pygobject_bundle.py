from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ...utils.paths import repo_root
from ...utils.subproc import python_exe


def bundle_pygobject(*, appdir: Path, site_packages: Path) -> None:
    """Best-effort bundle of PyGObject (gi) for tray/AppIndicator support.

    We do not attempt to fully vendor GTK; instead we bundle the Python bindings
    plus typelibs so pystray can use AppIndicator on desktop environments.
    """

    code = r"""
import json
import sysconfig
paths = sysconfig.get_paths()
print(json.dumps({
    "purelib": paths.get("purelib") or "",
    "platlib": paths.get("platlib") or "",
}))
"""
    proc = subprocess.run(
        [python_exe(), "-c", code],
        cwd=str(repo_root()),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return

    try:
        data = json.loads(proc.stdout)
    except Exception:
        return

    candidates: list[Path] = []
    for k in ("purelib", "platlib"):
        v = str(data.get(k, "") or "")
        if v:
            candidates.append(Path(v))

    # Also consider system Python dist-packages. On Ubuntu runners we install
    # python3-gi via apt which lives here (and matches the system CPython ABI).
    candidates.extend(
        [
            Path("/usr/lib/python3/dist-packages"),
            Path("/usr/lib/python3.12/dist-packages"),
        ]
    )

    gi_src: Path | None = None
    for base in candidates:
        maybe = base / "gi"
        if maybe.exists() and maybe.is_dir():
            gi_src = maybe
            break

    if gi_src is None:
        return

    gi_dst = site_packages / "gi"
    if gi_dst.exists():
        shutil.rmtree(gi_dst)
    shutil.copytree(gi_src, gi_dst, symlinks=False)

    # Bundle typelibs (girepository). Prefer the multiarch path when present.
    typelib_src_candidates = [
        Path("/usr/lib/x86_64-linux-gnu/girepository-1.0"),
        Path("/usr/lib64/girepository-1.0"),
        Path("/usr/lib/girepository-1.0"),
    ]
    typelib_src = next((p for p in typelib_src_candidates if p.exists()), None)
    if typelib_src is None:
        return

    typelib_dst = appdir / "usr" / "lib" / "girepository-1.0"
    typelib_dst.mkdir(parents=True, exist_ok=True)

    for name in typelib_src.glob("*.typelib"):
        if name.name.startswith(
            (
                "Gtk-",
                "Gdk-",
                "GdkPixbuf-",
                "Gio-",
                "GLib-",
                "GObject-",
                "Pango-",
                "PangoCairo-",
                "cairo-",
                "AppIndicator3-",
                "AyatanaAppIndicator3-",
            )
        ):
            shutil.copy2(name, typelib_dst / name.name)
