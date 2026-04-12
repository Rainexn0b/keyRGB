from __future__ import annotations

import pytest

import buildpython.steps.step_imports as step_imports
from buildpython.utils.import_probe import ImportProbeResult


def _probe_result(module: str, *, stderr: str = "", exit_code: int = 0) -> ImportProbeResult:
    return ImportProbeResult(
        module=module,
        command_str=f"probe {module}",
        stdout="",
        stderr=stderr,
        exit_code=exit_code,
    )


def test_import_validation_runner_reports_probe_failures(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_imports, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_imports, "_has_tkinter", lambda: True)

    def fake_probe(module: str, *, cwd):
        assert cwd == tmp_path
        if module == "src.gui.perkey":
            return _probe_result(
                module,
                stderr="Traceback (most recent call last):\nImportError: gui boom\n",
                exit_code=1,
            )
        return _probe_result(module)

    monkeypatch.setattr(step_imports, "probe_module_import", fake_probe)

    result = step_imports.import_validation_runner()

    assert result.exit_code == 1
    assert "Failed to import src.gui.perkey: gui boom" in result.stdout
    assert "ImportError: gui boom" in result.stdout


def test_import_validation_runner_skips_gui_imports_without_tk(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_imports, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_imports, "_has_tkinter", lambda: False)
    seen: list[str] = []

    def fake_probe(module: str, *, cwd):
        assert cwd == tmp_path
        seen.append(module)
        return _probe_result(module)

    monkeypatch.setattr(step_imports, "probe_module_import", fake_probe)

    result = step_imports.import_validation_runner()

    assert result.exit_code == 0
    assert seen == ["src.tray.entrypoint"]
    assert "Tkinter not available; skipped Tk GUI imports." in result.stdout


def test_import_validation_runner_propagates_unexpected_probe_failures(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_imports, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_imports, "_has_tkinter", lambda: True)

    def fake_probe(_module: str, *, cwd):
        assert cwd == tmp_path
        raise AssertionError("unexpected probe bug")

    monkeypatch.setattr(step_imports, "probe_module_import", fake_probe)

    with pytest.raises(AssertionError, match="unexpected probe bug"):
        step_imports.import_validation_runner()