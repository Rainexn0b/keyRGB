from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ...utils.paths import repo_root
from ...utils.subproc import python_exe


def bundle_pygobject(*, appdir: Path, site_packages: Path) -> None:
    """Bundle working, interpreter-matched GI/Cairo bindings for AppIndicator.

    We do not attempt to fully vendor GTK; instead we bundle the Python bindings
    plus typelibs so pystray can use AppIndicator on desktop environments.
    """

    code = r"""
import json
import sysconfig
from pathlib import Path
import gi
import gi._gi
import cairo
import cairo._cairo
print(json.dumps({
    "gi": str(Path(gi.__file__).parent),
    "cairo": str(Path(cairo.__file__).parent),
    "gi_extension": gi._gi.__file__,
    "cairo_extension": cairo._cairo.__file__,
    "extension_suffix": sysconfig.get_config_var("EXT_SUFFIX"),
}))
"""
    proc = subprocess.run(
        [python_exe(), "-c", code],
        cwd=str(repo_root()),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"AppImage requires working GI/Cairo bindings for the build interpreter: {proc.stderr}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("Invalid AppImage GI/Cairo binding manifest") from exc

    if not isinstance(data, dict) or not isinstance(data.get("extension_suffix"), str) or not data["extension_suffix"]:
        raise SystemExit("Invalid AppImage GI/Cairo extension suffix")
    # Never fall back to arbitrary system dist-packages: Jammy's cp310 _gi is
    # not loadable by the bundled cp311 interpreter. Check both packages before
    # replacing anything, including Cairo's own native extension.
    sources: dict[str, Path] = {}
    for name in ("gi", "cairo"):
        source = Path(str(data.get(name, "")))
        extension = Path(str(data.get(f"{name}_extension", "")))
        if (
            not source.is_dir()
            or not extension.is_file()
            or extension.parent != source
            or not extension.name.endswith(data["extension_suffix"])
        ):
            raise SystemExit(f"AppImage {name} bindings do not match the build interpreter ABI")
        sources[name] = source

    for name, source in sources.items():
        destination = site_packages / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination, symlinks=False)

    # Bundle typelibs (girepository). Prefer the multiarch path when present.
    typelib_src_candidates = [
        Path("/usr/lib/x86_64-linux-gnu/girepository-1.0"),
        Path("/usr/lib64/girepository-1.0"),
        Path("/usr/lib/girepository-1.0"),
    ]
    typelib_src = next((p for p in typelib_src_candidates if p.exists()), None)
    if typelib_src is None:
        raise SystemExit("AppImage requires GI typelibs for the desktop runtime")

    typelib_dst = appdir / "usr" / "lib" / "girepository-1.0"
    typelib_dst.mkdir(parents=True, exist_ok=True)

    # Typelibs reference other namespaces transitively (Gtk -> Gdk -> xlib,
    # Gtk -> Atk, Pango -> HarfBuzz, etc.). A top-level namespace allowlist
    # leaves GI unusable on desktops without system introspection packages.
    # Copy the build environment's small metadata set, not the host GTK stack.
    for typelib in typelib_src.glob("*.typelib"):
        shutil.copy2(typelib, typelib_dst / typelib.name)
