from __future__ import annotations

import logging

import buildpython.steps.step_import_scan as step_import_scan


def test_parse_imports_skips_unreadable_files(tmp_path) -> None:
    assert step_import_scan._parse_imports(tmp_path / "missing.py") == set()


def test_import_scan_runner_logs_import_failures_and_continues(monkeypatch, tmp_path, caplog) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import required_mod\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"required_mod", "PyQt6", "ok_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())

    def fake_import_module(name: str):
        if name == "ok_mod":
            return object()
        if name == "PyQt6":
            raise RuntimeError("optional boom")
        raise ImportError("required boom")

    monkeypatch.setattr(step_import_scan.importlib, "import_module", fake_import_module)

    with caplog.at_level(logging.ERROR, logger=step_import_scan.__name__):
        result = step_import_scan.import_scan_runner()

    assert result.exit_code == 1
    assert "Modules seen: 3" in result.stdout
    assert "required_mod (ImportError: required boom)" in result.stdout
    assert "PyQt6 (RuntimeError: optional boom)" in result.stdout
    assert "  - ok_mod" in result.stdout

    records = [record for record in caplog.records if "Import scan failed for candidate module" in record.getMessage()]
    assert len(records) == 2
    assert any("PyQt6" in record.getMessage() for record in records)
    assert any("required_mod" in record.getMessage() for record in records)
    assert all(record.exc_info is not None for record in records)


def test_import_scan_runner_treats_gi_as_optional(monkeypatch, tmp_path, caplog) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import gi\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"gi", "ok_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())

    def fake_import_module(name: str):
        if name == "ok_mod":
            return object()
        raise ModuleNotFoundError("No module named 'gi'")

    monkeypatch.setattr(step_import_scan.importlib, "import_module", fake_import_module)

    with caplog.at_level(logging.ERROR, logger=step_import_scan.__name__):
        result = step_import_scan.import_scan_runner()

    assert result.exit_code == 0
    assert "Missing required imports:" not in result.stdout
    assert "Missing optional imports:" in result.stdout
    assert "gi (ModuleNotFoundError: No module named 'gi')" in result.stdout
    assert "  - ok_mod" in result.stdout

    records = [record for record in caplog.records if "Import scan failed for candidate module" in record.getMessage()]
    assert len(records) == 1
    assert "gi" in records[0].getMessage()
    assert records[0].exc_info is not None
