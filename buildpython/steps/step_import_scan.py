from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult


OPTIONAL_TOPLEVEL = {
    "PyQt6",  # optional UI sliders
    "ruff",  # optional lint/format
    "pystray",  # optional tray icon (headless CI)

    # Legacy / optional Tuxedo integration (not required for KeyRGB core)
    "backlight_control",
    "ite_backend",
    "ui",
    "config",
    "effects",
}


def _stdlib_modules() -> set[str]:
    # Python 3.10+ provides stdlib_module_names.
    names = getattr(sys, "stdlib_module_names", None)
    if names:
        return set(names)
    # Fallback: best-effort minimal set
    return {
        "sys",
        "os",
        "pathlib",
        "time",
        "threading",
        "subprocess",
        "logging",
        "json",
        "re",
        "typing",
        "dataclasses",
        "contextlib",
        "queue",
        "math",
        "itertools",
        "functools",
        "datetime",
        "collections",
        "statistics",
        "traceback",
    }


def _iter_py_files() -> list[Path]:
    root = repo_root()
    files: list[Path] = []

    for base in [root / "src", root / "buildpython"]:
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            # Exclude tests from import-scan (they may reference optional hardware/integration modules)
            if base.name == "src" and "tests" in p.parts:
                continue
            files.append(p)

    # top-level scripts
    for p in [root / "keyrgb", root / "keyrgb-tuxedo"]:
        if p.exists() and p.is_file():
            files.append(p)

    return files


def _parse_imports(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return set()

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return set()

    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".", 1)[0]
                imports.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            # skip relative imports
            if getattr(node, "level", 0):
                continue
            name = node.module.split(".", 1)[0]
            imports.add(name)

    return imports


def import_scan_runner() -> RunResult:
    root = repo_root()

    # mimic runtime behavior: repo root + vendored dependency first
    sys.path.insert(0, str(root))
    vendored = root / "ite8291r3-ctl"
    if vendored.exists():
        sys.path.insert(0, str(vendored))

    stdlib = _stdlib_modules()

    all_imports: set[str] = set()
    for p in _iter_py_files():
        all_imports.update(_parse_imports(p))

    # Filter out obvious project-internal top-levels
    ignore = {"src", "buildpython"}
    candidates = sorted(i for i in all_imports if i not in stdlib and i not in ignore)

    missing: list[str] = []
    optional_missing: list[str] = []
    ok: list[str] = []

    for name in candidates:
        try:
            importlib.import_module(name)
            ok.append(name)
        except Exception as exc:
            if name in OPTIONAL_TOPLEVEL:
                optional_missing.append(f"{name} ({exc})")
            else:
                missing.append(f"{name} ({exc})")

    stdout_lines: list[str] = []
    stdout_lines.append("Import scan")
    stdout_lines.append("")
    stdout_lines.append(f"Modules seen: {len(candidates)}")

    if missing:
        stdout_lines.append("")
        stdout_lines.append("Missing required imports:")
        stdout_lines.extend(f"  - {m}" for m in missing)

    if optional_missing:
        stdout_lines.append("")
        stdout_lines.append("Missing optional imports:")
        stdout_lines.extend(f"  - {m}" for m in optional_missing)

    stdout_lines.append("")
    stdout_lines.append("OK:")
    stdout_lines.extend(f"  - {m}" for m in ok)

    exit_code = 1 if missing else 0

    return RunResult(
        command_str="(internal) import scan",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
