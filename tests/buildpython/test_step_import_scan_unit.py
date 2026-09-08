from __future__ import annotations

import pytest

from buildpython.steps import step_import_scan
from buildpython.utils.import_probe import ImportProbeResult


def test_parse_imports_reports_unreadable_files(tmp_path) -> None:
    with pytest.raises(OSError):
        step_import_scan._parse_imports(tmp_path / "missing.py")


@pytest.mark.parametrize("source", [b"def broken(:", b"\xff", None])
def test_import_scan_fails_instead_of_silently_ignoring_unscannable_source(tmp_path, monkeypatch, source) -> None:
    path = tmp_path / "broken.py"
    if source is not None:
        path.write_bytes(source)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [path])
    result = step_import_scan.import_scan_runner()
    assert result.exit_code == 1
    assert "Scan errors: 1" in result.stdout
    assert str(path) in result.stderr


def test_import_scan_runner_captures_import_failures_and_continues(monkeypatch, tmp_path, capsys) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import required_mod\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"required_mod", "gi", "ok_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())

    def fake_probe(name: str, *, cwd):
        assert cwd == tmp_path
        if name == "ok_mod":
            return ImportProbeResult(name, f"probe {name}", "", "", 0)
        if name == "gi":
            return ImportProbeResult(
                name,
                f"probe {name}",
                "",
                "Traceback (most recent call last):\nRuntimeError: optional boom\n",
                1,
            )
        return ImportProbeResult(
            name,
            f"probe {name}",
            "",
            "Traceback (most recent call last):\nImportError: required boom\n",
            1,
        )

    monkeypatch.setattr(step_import_scan, "probe_module_import", fake_probe)

    result = step_import_scan.import_scan_runner()

    assert result.exit_code == 1
    assert "Modules seen: 3" in result.stdout
    assert "required_mod (ImportError: required boom)" in result.stdout
    assert "gi (RuntimeError: optional boom)" in result.stdout
    assert "  - ok_mod" in result.stdout

    assert "--- gi ---" in result.stderr
    assert "RuntimeError: optional boom" in result.stderr
    assert "--- required_mod ---" in result.stderr
    assert "ImportError: required boom" in result.stderr
    assert capsys.readouterr().err == ""


def test_import_scan_runner_treats_gi_as_optional_without_live_traceback(monkeypatch, tmp_path, capsys) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import gi\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"gi", "ok_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())

    def fake_probe(name: str, *, cwd):
        assert cwd == tmp_path
        if name == "ok_mod":
            return ImportProbeResult(name, f"probe {name}", "", "", 0)
        return ImportProbeResult(
            name,
            f"probe {name}",
            "",
            "Traceback (most recent call last):\nModuleNotFoundError: No module named 'gi'\n",
            1,
        )

    monkeypatch.setattr(step_import_scan, "probe_module_import", fake_probe)

    result = step_import_scan.import_scan_runner()

    assert result.exit_code == 0
    assert "Missing required imports:" not in result.stdout
    assert "Missing optional imports:" in result.stdout
    assert "gi (ModuleNotFoundError: No module named 'gi')" in result.stdout
    assert "  - ok_mod" in result.stdout

    assert "ModuleNotFoundError: No module named 'gi'" in result.stderr
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_import_scan_runner_propagates_unexpected_probe_failures(monkeypatch, tmp_path) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import required_mod\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"required_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())
    monkeypatch.setattr(
        step_import_scan,
        "probe_module_import",
        lambda _name, *, cwd: (_ for _ in ()).throw(AssertionError("unexpected probe bug")),
    )

    with pytest.raises(AssertionError, match="unexpected probe bug"):
        step_import_scan.import_scan_runner()
