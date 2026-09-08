from __future__ import annotations

from pathlib import Path

import pytest

from buildpython.steps import step_imports
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
        if module == "keyrgb.gui.perkey":
            return _probe_result(
                module,
                stderr="Traceback (most recent call last):\nImportError: gui boom\n",
                exit_code=1,
            )
        return _probe_result(module)

    monkeypatch.setattr(step_imports, "probe_module_import", fake_probe)

    result = step_imports.import_validation_runner()

    assert result.exit_code == 1
    assert "Failed to import keyrgb.gui.perkey: gui boom" in result.stdout
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
    assert seen == [
        "keyrgb.tray.entrypoint",
        "keyrgb.core.diagnostics",
        "keyrgb.core.diagnostics.diagnostic_session",
    ]
    assert "Skipped GUI imports: Tkinter not available." in result.stdout


def test_import_validation_runner_propagates_unexpected_probe_failures(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_imports, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_imports, "_has_tkinter", lambda: True)

    def fake_probe(_module: str, *, cwd):
        assert cwd == tmp_path
        raise AssertionError("unexpected probe bug")

    monkeypatch.setattr(step_imports, "probe_module_import", fake_probe)

    with pytest.raises(AssertionError, match="unexpected probe bug"):
        step_imports.import_validation_runner()


def _public_script_modules() -> list[str]:
    scripts: list[str] = []
    in_scripts = False
    for raw_line in Path("pyproject.toml").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            in_scripts = line == "[project.scripts]"
            continue
        if not in_scripts or "=" not in line:
            continue
        _name, value = line.split("=", 1)
        target = value.strip().strip('"').strip("'")
        module, _separator, _attr = target.partition(":")
        if module.startswith("keyrgb."):
            scripts.append(module)
    return scripts


def test_import_validation_covers_every_public_script() -> None:
    assert step_imports.DEFAULT_IMPORTS == _public_script_modules()


def test_import_validation_runner_probes_every_default_import(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_imports, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_imports, "_has_tkinter", lambda: True)
    seen: list[str] = []

    def fake_probe(module: str, *, cwd):
        assert cwd == tmp_path
        seen.append(module)
        return _probe_result(module)

    monkeypatch.setattr(step_imports, "probe_module_import", fake_probe)

    result = step_imports.import_validation_runner()

    assert result.exit_code == 0
    assert seen == list(step_imports.DEFAULT_IMPORTS)
    for module in step_imports.DEFAULT_IMPORTS:
        assert f"  - {module}" in result.stdout
