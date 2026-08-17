from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import venv
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESOURCES_ROOT = _REPO_ROOT / "src" / "core" / "resources"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _resource_data_files() -> list[Path]:
    return sorted(
        path for path in _RESOURCES_ROOT.rglob("*") if path.is_file() and path.suffix.lower() in {".json", ".png"}
    )


_PACKAGE_DATA_SRC_RE = re.compile(
    r"(?ms)^\[tool\.setuptools\.package-data\]\s*(?:#[^\n]*\n)*src\s*=\s*\[(.*?)\]"
)


def _package_data_patterns() -> list[str]:
    # Parse the declared patterns without tomllib so this module collects on 3.10.
    match = _PACKAGE_DATA_SRC_RE.search(_PYPROJECT.read_text(encoding="utf-8"))
    assert match is not None, "src package-data patterns must be declared"
    patterns = re.findall(r'"([^"]+)"', match.group(1))
    assert patterns, "src package-data patterns must be declared"
    return patterns


def _matches_package_data(relative_posix: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(relative_posix, pattern) for pattern in patterns)


def _reference_defaults_manifest() -> tuple[dict[str, object], Path]:
    manifest_path = _RESOURCES_ROOT / "reference_defaults_specs.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    split_root = _RESOURCES_ROOT / str(manifest["base_dir"])
    return manifest, split_root


def _required_reference_defaults_relpaths() -> list[str]:
    manifest, split_root = _reference_defaults_manifest()
    required = [
        split_root / str(manifest["meta"]),
        split_root / str(manifest["keymaps"]),
        split_root / str(manifest["layout_tweaks"]),
    ]
    per_key_root = split_root / str(manifest["per_key_tweaks_dir"])
    required.extend(sorted(per_key_root.glob("*.json")))
    return [path.relative_to(_REPO_ROOT).as_posix() for path in required]


def test_reference_defaults_manifest_closure_exists_and_contains_valid_json() -> None:
    manifest, split_root = _reference_defaults_manifest()

    required_paths = [
        split_root / str(manifest["meta"]),
        split_root / str(manifest["keymaps"]),
        split_root / str(manifest["layout_tweaks"]),
    ]
    per_key_root = split_root / str(manifest["per_key_tweaks_dir"])

    for path in required_paths:
        assert path.is_file(), f"manifest resource is missing: {path.relative_to(_REPO_ROOT)}"
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)

    meta = json.loads(required_paths[0].read_text(encoding="utf-8"))
    layout_ids = set(meta["layouts"])
    per_key_paths = sorted(per_key_root.glob("*.json"))

    assert {path.stem for path in per_key_paths} == layout_ids
    for path in per_key_paths:
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)


def test_package_data_patterns_cover_all_resource_data_files() -> None:
    patterns = _package_data_patterns()
    missing = [
        path.relative_to(_REPO_ROOT / "src").as_posix()
        for path in _resource_data_files()
        if not _matches_package_data(path.relative_to(_REPO_ROOT / "src").as_posix(), patterns)
    ]
    assert missing == [], f"package-data patterns omit resource files: {missing}"


def test_package_data_patterns_cover_nested_reference_defaults_closure() -> None:
    patterns = _package_data_patterns()
    missing = [
        rel
        for rel in _required_reference_defaults_relpaths()
        if not rel.startswith("src/") or not _matches_package_data(rel.removeprefix("src/"), patterns)
    ]
    assert missing == [], f"package-data patterns omit nested reference defaults: {missing}"


def _run_checked(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if completed.returncode != 0:
        joined = " ".join(command)
        raise AssertionError(f"command failed ({joined}):\n{completed.stdout}")
    return completed


def _stage_src_tree(tmp_path: Path) -> Path:
    staging = tmp_path / "src_tree"
    staging.mkdir()
    shutil.copy2(_PYPROJECT, staging / "pyproject.toml")
    shutil.copy2(_REPO_ROOT / "README.md", staging / "README.md")
    shutil.copytree(
        _REPO_ROOT / "src",
        staging / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return staging


def _prepare_build_env(tmp_path: Path, *, name: str) -> tuple[Path, Path]:
    env_dir = tmp_path / name
    venv.EnvBuilder(with_pip=True).create(env_dir)
    env_python = env_dir / "bin" / "python"
    _run_checked([str(env_python), "-m", "pip", "install", "--upgrade", "pip", "build"])
    return env_dir, env_python


def _assert_installed_reference_defaults_load(env_python: Path) -> None:
    probe = """
from src.core.resources.reference_defaults_specs import (
    clear_reference_defaults_spec_cache,
    load_reference_defaults_spec,
)

clear_reference_defaults_spec_cache()
spec = load_reference_defaults_spec("ansi")
assert isinstance(spec, dict) and spec, "ansi reference defaults failed to load from installed artifact"
assert isinstance(spec.get("keymap"), dict) and spec["keymap"], "ansi keymap missing from installed artifact"
print("ok")
"""
    loaded = subprocess.run(
        [str(env_python), "-c", probe],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert loaded.returncode == 0, f"installed artifact failed resource load:\n{loaded.stdout}"
    assert "ok" in loaded.stdout


def _build_and_install_wheel(tmp_path: Path) -> tuple[Path, Path]:
    staging = _stage_src_tree(tmp_path)
    _env_dir, env_python = _prepare_build_env(tmp_path, name="wheel_env")
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()

    _run_checked(
        [str(env_python), "-m", "build", "--wheel", "--outdir", str(wheel_dir)],
        cwd=staging,
    )

    wheels = sorted(wheel_dir.glob("keyrgb-*.whl"))
    assert len(wheels) == 1, f"expected one keyrgb wheel, found {wheels}"
    wheel_path = wheels[0]
    _run_checked([str(env_python), "-m", "pip", "install", "--no-deps", str(wheel_path)])
    return wheel_path, env_python


def _build_and_install_sdist(tmp_path: Path) -> tuple[Path, Path]:
    staging = _stage_src_tree(tmp_path)
    _env_dir, env_python = _prepare_build_env(tmp_path, name="sdist_env")
    dist_dir = tmp_path / "sdists"
    dist_dir.mkdir()

    _run_checked(
        [str(env_python), "-m", "build", "--sdist", "--outdir", str(dist_dir)],
        cwd=staging,
    )

    sdists = sorted(dist_dir.glob("keyrgb-*.tar.gz"))
    assert len(sdists) == 1, f"expected one keyrgb sdist, found {sdists}"
    sdist_path = sdists[0]
    _run_checked([str(env_python), "-m", "pip", "install", "--no-deps", str(sdist_path)])
    return sdist_path, env_python


def test_built_wheel_contains_and_loads_reference_defaults_closure(tmp_path: Path) -> None:
    """End-to-end: nested resource JSON must ship in the wheel and load after install."""
    try:
        wheel_path, env_python = _build_and_install_wheel(tmp_path)
    except (AssertionError, OSError) as exc:
        pytest.skip(f"wheel build tooling unavailable: {exc}")

    required = _required_reference_defaults_relpaths()
    with zipfile.ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
    missing = [rel for rel in required if rel not in names]
    assert missing == [], f"built wheel is missing packaged resources: {missing}"

    _assert_installed_reference_defaults_load(env_python)


def test_built_sdist_installs_and_loads_reference_defaults_closure(tmp_path: Path) -> None:
    """End-to-end: nested resource JSON must survive sdist install."""
    try:
        _sdist_path, env_python = _build_and_install_sdist(tmp_path)
    except (AssertionError, OSError) as exc:
        pytest.skip(f"sdist build tooling unavailable: {exc}")

    _assert_installed_reference_defaults_load(env_python)
