from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "dependency_audit.py"
_CI = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_RELEASE = _REPO_ROOT / ".github" / "workflows" / "release.yml"
_DEPENDABOT = _REPO_ROOT / ".github" / "dependabot.yml"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _load_audit_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dependency_audit", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dependency_audit"] = module
    spec.loader.exec_module(module)
    return module


_audit = _load_audit_module()

CLEAN_REPORT = {
    "dependencies": [
        {"name": "pystray", "version": "0.19.5", "vulns": []},
        {"name": "pillow", "version": "12.3.0", "vulns": []},
    ],
    "fixes": [],
}

VULNERABLE_REPORT = {
    "dependencies": [
        {"name": "pystray", "version": "0.19.5", "vulns": []},
        {
            "name": "urllib3",
            "version": "1.26.18",
            "vulns": [
                {
                    "id": "PYSEC-2023-123",
                    "fix_versions": ["1.26.19"],
                    "aliases": ["CVE-2023-43804"],
                    "description": "Request body not stripped on redirect.",
                }
            ],
        },
    ],
    "fixes": [],
}


def test_classify_clean_report_is_exit_zero() -> None:
    verdict = _audit.classify_report(CLEAN_REPORT)
    assert verdict.status == "clean"
    assert verdict.findings == ()


def test_classify_known_vulnerable_fixture_reports_findings() -> None:
    verdict = _audit.classify_report(VULNERABLE_REPORT)
    assert verdict.status == "findings"
    assert len(verdict.findings) == 1
    finding = verdict.findings[0]
    assert finding.package == "urllib3"
    assert finding.version == "1.26.18"
    assert finding.vuln_ids == ("PYSEC-2023-123",)
    diagnostic = _audit.format_findings_diagnostic(verdict)
    assert "found 1 vulnerability across 1 package" in diagnostic
    assert "urllib3" in diagnostic and "PYSEC-2023-123" in diagnostic


def test_parse_malformed_report_raises_value_error() -> None:
    with pytest.raises(ValueError):
        _audit.parse_report_text("")
    with pytest.raises(ValueError):
        _audit.parse_report_text("{not-json")


def test_classify_invalid_shapes_are_not_clean() -> None:
    assert _audit.classify_report([]).status == "invalid"
    assert _audit.classify_report({}).status == "invalid"
    assert _audit.classify_report({"dependencies": "nope"}).status == "invalid"
    assert _audit.classify_report({"dependencies": [{"version": "1.0", "vulns": []}]}).status == "invalid"
    assert _audit.classify_report({"dependencies": [{"name": "x", "version": "1.0", "vulns": {}}]}).status == (
        "invalid"
    )


def test_skip_reason_only_entries_are_valid_but_do_not_hide_findings() -> None:
    skip_only = {
        "dependencies": [
            {"name": "keyrgb", "skip_reason": "editable install, skipped"},
        ]
    }
    assert _audit.classify_report(skip_only).status == "clean"
    mixed = {
        "dependencies": [
            {"name": "keyrgb", "skip_reason": "editable install, skipped"},
            VULNERABLE_REPORT["dependencies"][1],
        ]
    }
    verdict = _audit.classify_report(mixed)
    assert verdict.status == "findings"
    assert verdict.findings[0].package == "urllib3"


def test_build_command_invokes_pip_audit_without_shell() -> None:
    command = _audit.build_audit_command(sys.executable, ".")
    assert command == [
        sys.executable,
        "-m",
        "pip_audit",
        ".",
        "--format=json",
        "--desc=off",
        "--progress-spinner=off",
        "--vulnerability-service=pypi",
    ]
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "shell=True" not in source


def _completed(stdout: str, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["pip-audit"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_audit_clean_returns_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        _audit.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(CLEAN_REPORT), returncode=0),
    )
    assert _audit.run_audit(_REPO_ROOT) == 0
    out, _ = capsys.readouterr()
    assert "no known vulnerabilities" in out


def test_run_audit_findings_return_one_with_distinct_diagnostic(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Findings take precedence even when the tool exits nonzero.
    monkeypatch.setattr(
        _audit.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(VULNERABLE_REPORT), returncode=1),
    )
    assert _audit.run_audit(_REPO_ROOT) == 1
    out, err = capsys.readouterr()
    assert "found 1 vulnerability" in out
    assert "failed" not in out.lower()
    assert err == ""


def test_run_audit_nonzero_without_findings_returns_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        _audit.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(CLEAN_REPORT), returncode=2, stderr="service unavailable"),
    )
    assert _audit.run_audit(_REPO_ROOT) == 2
    _, err = capsys.readouterr()
    assert "failed" in err
    assert "service unavailable" in err


def test_run_audit_malformed_stdout_returns_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(_audit.subprocess, "run", lambda *args, **kwargs: _completed("not json", returncode=0))
    assert _audit.run_audit(_REPO_ROOT) == 2
    _, err = capsys.readouterr()
    assert "failed" in err


def test_run_audit_timeout_and_launch_failure_return_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="pip-audit", timeout=1.0)

    monkeypatch.setattr(_audit.subprocess, "run", _timeout)
    assert _audit.run_audit(_REPO_ROOT) == 2
    _, err = capsys.readouterr()
    assert "timed out" in err

    def _missing(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("pip_audit")

    monkeypatch.setattr(_audit.subprocess, "run", _missing)
    assert _audit.run_audit(_REPO_ROOT) == 2
    _, err = capsys.readouterr()
    assert "failed" in err


def test_cli_main_exit_distinctions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fixture'\nversion = '1.0'\n", encoding="utf-8")
    monkeypatch.setattr(
        _audit.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(CLEAN_REPORT), returncode=0),
    )
    assert _audit.main(["--project-dir", str(tmp_path)]) == 0
    monkeypatch.setattr(
        _audit.subprocess,
        "run",
        lambda *args, **kwargs: _completed(json.dumps(VULNERABLE_REPORT), returncode=1),
    )
    assert _audit.main(["--project-dir", str(tmp_path)]) == 1
    monkeypatch.setattr(_audit.subprocess, "run", lambda *args, **kwargs: _completed("broken", returncode=0))
    assert _audit.main(["--project-dir", str(tmp_path)]) == 2


def test_missing_project_and_invalid_timeout_are_tool_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _audit.run_audit(tmp_path) == 2
    _, err = capsys.readouterr()
    assert "no pyproject.toml" in err

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fixture'\nversion = '1.0'\n", encoding="utf-8")
    assert _audit.run_audit(tmp_path, timeout=0) == 2
    _, err = capsys.readouterr()
    assert "timeout must be greater than zero" in err


def test_dependabot_covers_pip_and_github_actions_weekly() -> None:
    text = _DEPENDABOT.read_text(encoding="utf-8")
    assert "version: 2" in text
    assert '"pip"' in text or "'pip'" in text or "pip" in text
    assert "github-actions" in text
    assert text.count("package-ecosystem:") >= 2
    assert text.count('interval: "weekly"') >= 2
    assert 'directory: "/"' in text


def test_ci_permissions_are_read_only_and_audit_runs_before_buildpython() -> None:
    text = _CI.read_text(encoding="utf-8")
    top = text.split("jobs:")[0]
    assert re.search(r"permissions:\s*\n\s+contents:\s*read", top) is not None
    assert "contents: write" not in top
    assert "scripts/dependency_audit.py --project-dir ." in text
    assert text.index("scripts/dependency_audit.py") < text.index("python -m buildpython --profile=ci")


def test_release_write_permission_is_job_local_and_audit_preserves_artifacts() -> None:
    text = _RELEASE.read_text(encoding="utf-8")
    top = text.split("jobs:")[0]
    assert re.search(r"permissions:\s*\n\s+contents:\s*read", top) is not None
    assert "contents: write" not in top
    job_block = text.split("jobs:")[1]
    assert re.search(r"permissions:\s*\n\s+contents:\s*write", job_block) is not None
    assert "scripts/dependency_audit.py --project-dir ." in text
    assert text.index("scripts/dependency_audit.py") < text.index("python -m buildpython --profile=release")
    assert "dist/*.AppImage" in text
    assert "keyrgb-x86_64.AppImage.sha256" in text


def test_pip_audit_is_exactly_pinned_in_dev_extras() -> None:
    with _PYPROJECT.open("rb") as handle:
        pyproject = tomllib.load(handle)
    dev = pyproject["project"]["optional-dependencies"]["dev"]
    assert "pip-audit==2.10.1" in dev
    assert not [entry for entry in dev if entry.startswith("pip-audit") and entry != "pip-audit==2.10.1"]
    runtime = pyproject["project"]["dependencies"]
    assert not any("pip-audit" in entry for entry in runtime)


def test_every_workflow_uses_remains_sha_pinned() -> None:
    for workflow in (_CI, _RELEASE):
        text = workflow.read_text(encoding="utf-8")
        uses_lines = [line.strip() for line in text.splitlines() if "uses:" in line]
        assert uses_lines, workflow
        for line in uses_lines:
            assert re.search(r"uses:\s+\S+@[0-9a-f]{40}\s+#", line), line
