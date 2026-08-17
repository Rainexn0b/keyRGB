from __future__ import annotations

from pathlib import Path

from buildpython.core.profiles import PROFILES
from buildpython.steps.step_defs import steps
from tests._paths import ensure_repo_root_on_sys_path

_REPO_ROOT = Path(ensure_repo_root_on_sys_path())
_BUILD_SYSTEM = _REPO_ROOT / "docs" / "1-buildpython" / "01-Build-system.md"
_BUILD_STEPS = _REPO_ROOT / "docs" / "1-buildpython" / "01.1-Build-steps.md"
_CI_DOC = _REPO_ROOT / "docs" / "1-buildpython" / "03-CI.md"
_CONTRIBUTING = _REPO_ROOT / "CONTRIBUTING.md"


def test_build_steps_doc_lists_every_registered_step() -> None:
    text = _BUILD_STEPS.read_text(encoding="utf-8")
    for step in steps():
        assert f"`{step.name}`" in text, f"step catalog is missing {step.name}"
        assert f"| {step.number} |" in text, f"step catalog is missing number {step.number}"


def test_build_system_doc_lists_every_named_profile() -> None:
    text = _BUILD_SYSTEM.read_text(encoding="utf-8")
    for name in PROFILES:
        assert f"`{name}`:" in text, f"build-system doc is missing profile {name}"
    assert "steps `1` through `21`" in text


def test_ci_doc_matches_current_ci_and_release_workflows() -> None:
    text = _CI_DOC.read_text(encoding="utf-8")
    assert "--profile=ci" in text
    assert "--profile=release" in text
    assert "There is no CI AppImage job." in text
    for step_name in PROFILES["ci"].include_steps:
        assert f"`{step_name}`" in text, f"CI doc is missing ci step {step_name}"


def test_contributing_doc_points_at_existing_backend_guides() -> None:
    text = _CONTRIBUTING.read_text(encoding="utf-8")
    assert "docs/developement/backends/" not in text
    assert "docs/B-backend-guides/" in text
    assert (_REPO_ROOT / "docs" / "B-backend-guides").is_dir()
    assert (_REPO_ROOT / "docs" / "2-usage" / "04-hardware_tests.md").is_file()
    assert (_REPO_ROOT / "docs" / "3-contributing" / "01-build_runner.md").is_file()
