from __future__ import annotations

from pathlib import Path

from buildpython.core.profiles import PROFILES
from buildpython.steps.step_defs import steps
from tests._paths import REPO_ROOT

_REPO_ROOT = Path(REPO_ROOT)
_BUILD_SYSTEM = _REPO_ROOT / "docs" / "1-buildpython" / "01-Build-system.md"
_BUILD_STEPS = _REPO_ROOT / "docs" / "1-buildpython" / "01.1-Build-steps.md"
_CI_DOC = _REPO_ROOT / "docs" / "1-buildpython" / "03-CI.md"
_CONTRIBUTING = _REPO_ROOT / "CONTRIBUTING.md"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_RELEASE_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release.yml"


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


def test_ci_workflows_upload_compact_build_logs_on_failure() -> None:
    ci_workflow = _CI_WORKFLOW.read_text(encoding="utf-8")
    release_workflow = _RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert ci_workflow.count("if: failure()") >= 2
    assert "keyrgb-quality-buildlog" in ci_workflow
    assert "keyrgb-runtime-${{ matrix.python-version }}-buildlog" in ci_workflow
    assert ci_workflow.count("path: buildlog/keyrgb/") >= 2
    assert "keyrgb-release-buildlog" in release_workflow
    assert "if: failure()" in release_workflow
    assert "path: buildlog/keyrgb/" in release_workflow

    for workflow in (ci_workflow, release_workflow):
        assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow


def test_contributing_doc_points_at_existing_backend_guides() -> None:
    text = _CONTRIBUTING.read_text(encoding="utf-8")
    assert "docs/developement/backends/" not in text
    assert "docs/B-backend-guides/" in text
    assert (_REPO_ROOT / "docs" / "B-backend-guides").is_dir()
    assert (_REPO_ROOT / "docs" / "2-usage" / "validation.md").is_file()
    assert (_REPO_ROOT / "docs" / "3-contributing" / "01-build_runner.md").is_file()
