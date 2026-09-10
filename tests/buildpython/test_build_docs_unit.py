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
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# Declared/tested runtime support: runtime matrix and classifiers grow
# together, while the type-check floor stays pinned.
_TESTED_PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14")
_QUALITY_GATE_PYTHON = "3.12"
_MYPY_FLOOR_PYTHON = "3.10"


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

    assert ci_workflow.count("uses: actions/upload-artifact@") >= 2
    assert "uses: actions/upload-artifact@" in release_workflow


def test_contributing_doc_points_at_existing_backend_guides() -> None:
    text = _CONTRIBUTING.read_text(encoding="utf-8")
    assert "docs/developement/backends/" not in text
    assert "docs/B-backend-guides/" in text
    assert (_REPO_ROOT / "docs" / "B-backend-guides").is_dir()
    assert (_REPO_ROOT / "docs" / "2-usage" / "validation.md").is_file()
    assert (_REPO_ROOT / "docs" / "3-contributing" / "01-build_runner.md").is_file()


def test_ci_runtime_matrix_covers_tested_python_versions() -> None:
    ci_workflow = _CI_WORKFLOW.read_text(encoding="utf-8")

    for version in _TESTED_PYTHON_VERSIONS:
        assert f'"{version}"' in ci_workflow, f"CI runtime matrix is missing Python {version}"
    assert f'python-version: "{_QUALITY_GATE_PYTHON}"' in ci_workflow, "quality gate must stay on Python 3.12"


def test_project_classifiers_track_tested_python_versions() -> None:
    text = _PYPROJECT.read_text(encoding="utf-8")

    for version in _TESTED_PYTHON_VERSIONS:
        assert f"Programming Language :: Python :: {version}" in text, f"project classifier is missing Python {version}"
    assert 'requires-python = ">=3.10"' in text, "minimum supported Python must stay at 3.10"
    assert f'python_version = "{_MYPY_FLOOR_PYTHON}"' in text, "mypy language floor must stay at 3.10"


def test_ci_doc_states_tested_matrix_and_mypy_floor() -> None:
    text = _CI_DOC.read_text(encoding="utf-8")

    for version in _TESTED_PYTHON_VERSIONS:
        assert version in text, f"CI doc is missing tested Python {version}"
    assert "Quality Gate" in text and _QUALITY_GATE_PYTHON in text
    assert "3.10" in text and "mypy" in text, "CI doc must state the 3.10 mypy floor"
