from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ...utils.paths import repo_root
from ...utils.subproc import python_exe

from .common import chmod_x


def _python_runtime_manifest() -> dict[str, str]:
    # Query the build-time interpreter. We'll bundle this runtime into the AppImage
    # to avoid relying on the user's system python version.
    code = """
import json
import sys
import sysconfig

paths = sysconfig.get_paths()

out = {
    \"executable\": sys.executable,
    \"prefix\": sys.prefix,
    \"version\": f\"{sys.version_info.major}.{sys.version_info.minor}\",
    \"stdlib\": paths.get(\"stdlib\") or \"\",
    \"platstdlib\": paths.get(\"platstdlib\") or \"\",
    \"libdir\": sysconfig.get_config_var(\"LIBDIR\") or \"\",
    \"ldlibrary\": sysconfig.get_config_var(\"LDLIBRARY\") or \"\",
    \"instsoname\": sysconfig.get_config_var(\"INSTSONAME\") or \"\",
}

print(json.dumps(out))
"""
    proc = subprocess.run(
        [python_exe(), "-c", code],
        cwd=str(repo_root()),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    try:
        data = json.loads(proc.stdout)
    except Exception:
        raise SystemExit(f"Failed to parse python runtime manifest: {proc.stdout}\n{proc.stderr}")

    if not isinstance(data, dict):
        raise SystemExit("Invalid python runtime manifest")
    return {str(k): str(v) for k, v in data.items()}


def bundle_python_runtime(*, appdir: Path) -> None:
    manifest = _python_runtime_manifest()
    prefix = Path(manifest.get("prefix", ""))
    version = manifest.get("version", "")
    stdlib = Path(manifest.get("stdlib", ""))
    platstdlib = Path(manifest.get("platstdlib", ""))
    libdir = Path(manifest.get("libdir", ""))
    ldlibrary = manifest.get("ldlibrary", "")
    instsoname = manifest.get("instsoname", "")

    if not version or not stdlib.exists() or not prefix.exists():
        raise SystemExit(f"Cannot bundle python runtime (stdlib missing): {stdlib}")

    usr_bin = appdir / "usr" / "bin"
    usr_lib = appdir / "usr" / "lib"
    usr_bin.mkdir(parents=True, exist_ok=True)
    usr_lib.mkdir(parents=True, exist_ok=True)

    def rel_under_prefix(path: Path) -> Path:
        try:
            return path.relative_to(prefix)
        except Exception:
            # Fallback: keep our previous lib layout.
            return Path("lib") / f"python{version}"

    # Interpreter
    py_src = Path(python_exe())
    py_dst = usr_bin / "python3"
    shutil.copy2(py_src, py_dst)
    chmod_x(py_dst)

    # Standard library (pure + platform stdlib). Some distros use lib64.
    # Place stdlib in the same relative location under prefix so the bundled
    # interpreter can find it via PYTHONHOME.
    std_rel = rel_under_prefix(stdlib)
    dst_stdlib = appdir / "usr" / std_rel
    if dst_stdlib.exists():
        shutil.rmtree(dst_stdlib)
    dst_stdlib.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(stdlib, dst_stdlib, symlinks=False)

    if platstdlib != stdlib and platstdlib.exists():
        plat_rel = rel_under_prefix(platstdlib)
        dst_plat = appdir / "usr" / plat_rel
        if not dst_plat.exists():
            dst_plat.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(platstdlib, dst_plat, symlinks=False)

    # libpython (if the interpreter is dynamically linked against it)
    # Prefer INSTSONAME (libpython3.x.so.1.0) over LDLIBRARY (libpython3.x.so)
    # because the latter may be a missing symlink on some distros.
    lib_candidates = [instsoname, ldlibrary] if instsoname else [ldlibrary]
    lib_src: Path | None = None
    for candidate in lib_candidates:
        if candidate and libdir.exists():
            maybe = libdir / candidate
            if maybe.exists():
                lib_src = maybe
                break

    if lib_src is not None:
        lib_rel = rel_under_prefix(lib_src)
        lib_dst = appdir / "usr" / lib_rel
        lib_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lib_src, lib_dst)

        # Also place a copy in usr/lib so the dynamic loader can find it
        # via our simpler LD_LIBRARY_PATH.
        flat_dst = appdir / "usr" / "lib" / lib_src.name
        if flat_dst != lib_dst:
            flat_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(lib_src, flat_dst)
