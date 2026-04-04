from __future__ import annotations

import json
from pathlib import Path

import buildpython.steps.file_size_analysis.step as step_size
from buildpython.steps.file_size_analysis.scanning import load_flat_directory_allowlist, scan_flat_directories

from buildpython.core.debt_index import build_debt_index, write_debt_index
from buildpython.core.summary_support.debt_terminal import build_terminal_filesize_highlight


def _write_python_file(path: Path, *, total_lines: int, import_lines: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [f"import module_{index}" for index in range(import_lines)]
    filler_lines = total_lines - len(lines)
    assert filler_lines > 0
    lines.extend(f"value_{index} = {index}" for index in range(filler_lines))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_small_python_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("VALUE = 1\n", encoding="utf-8")


def _write_facade_candidate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                '"""Facade candidate."""',
                "from pkg import helper_01",
                "from pkg import helper_02",
                "from pkg import helper_03",
                "from pkg import helper_04",
                "from pkg import helper_05",
                "from pkg import helper_06",
                "from pkg import helper_07",
                "from pkg import helper_08",
                "from pkg import helper_09",
                "from pkg import helper_10",
                "from pkg import helper_11",
                "from pkg import helper_12",
                "from pkg import helper_13",
                "from pkg import helper_14",
                "from pkg import helper_15",
                "from pkg import helper_16",
                "from pkg import helper_17",
                "from pkg import helper_18",
                "from pkg import helper_19",
                "from pkg import helper_20",
                "from pkg import helper_21",
                "from pkg import helper_22",
                "alias_one = helper_01",
                "alias_two = helper_02",
                "alias_three = helper_03",
                "alias_four = helper_04",
                "class Facade:",
                "    def one(self):",
                "        return helper_05()",
                "",
                "    def two(self):",
                "        return helper_06()",
                "",
                "    def three(self):",
                "        return helper_07()",
                "",
                "    def four(self):",
                "        return helper_08()",
                "",
                "    def five(self):",
                "        return helper_09()",
                "",
                "    def six(self):",
                "        return helper_10()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_file_size_runner_reports_bucketed_sizes_import_blocks_and_flat_directories(tmp_path, monkeypatch) -> None:
    _write_python_file(tmp_path / "src" / "refactor.py", total_lines=360, import_lines=22)
    _write_python_file(tmp_path / "buildpython" / "critical.py", total_lines=420, import_lines=30)
    _write_python_file(tmp_path / "src" / "severe.py", total_lines=520, import_lines=40)
    _write_python_file(tmp_path / "src" / "extreme.py", total_lines=620, import_lines=0)
    _write_facade_candidate(tmp_path / "src" / "facade_candidate.py")

    for index in range(9):
        _write_small_python_file(tmp_path / "src" / "flat" / f"module_{index}.py")
    for index in range(10):
        _write_small_python_file(tmp_path / "tests" / "flat" / f"test_case_{index}.py")

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()

    assert result.exit_code == 0
    assert "Refactor=1 | Critical=1 | Severe=1 | Extreme=1" in result.stdout
    assert "Warning=2 | Critical=1 | Severe=1" in result.stdout
    assert "Flat directories: 2" in result.stdout
    assert "Facade candidates: 1" in result.stdout

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))

    assert payload["counts"]["file_lines"] == {
        "refactor": 1,
        "critical": 1,
        "severe": 1,
        "extreme": 1,
        "total": 4,
    }
    assert payload["counts"]["import_block_lines"] == {
        "warning": 2,
        "critical": 1,
        "severe": 1,
        "total": 4,
    }
    assert payload["counts"]["flat_directories"] == 2
    assert payload["counts"].get("flat_directories_allowed", 0) == 0
    assert payload["counts"]["facade_candidates"] == 1
    assert payload["files"][0]["path"] == "src/extreme.py"
    assert payload["files"][0]["bucket"] == "EXTREME"
    assert payload["import_blocks"][0]["path"] == "src/severe.py"
    assert payload["import_blocks"][0]["level"] == "SEVERE"
    assert [item["path"] for item in payload["flat_directories"]] == ["tests/flat", "src/flat"]
    # Both directories have 0 subdirs so density equals file count — ordering preserved.
    assert payload["flat_directories"][0]["flatness_density"] == 10.0
    assert payload["flat_directories"][1]["flatness_density"] == 9.0
    assert payload["facade_candidates"][0]["path"] == "src/facade_candidate.py"
    assert payload["facade_candidates"][0]["score"] == 10

    markdown = (tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.md").read_text(encoding="utf-8")
    assert "## Import block hotspots" in markdown
    assert "## Flat directory hotspots" in markdown
    assert "## Facade candidates" in markdown


def test_debt_index_includes_file_size_structure_sections(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "file-size-analysis.json").write_text(
        json.dumps(
            {
                "counts": {
                    "file_lines": {"refactor": 2, "critical": 1, "severe": 0, "extreme": 0, "total": 3},
                    "import_block_lines": {"warning": 1, "critical": 0, "severe": 0, "total": 1},
                    "flat_directories": 1,
                    "facade_candidates": 1,
                },
                "files": [{"path": "src/demo.py", "lines": 410, "bucket": "CRITICAL"}],
                "import_blocks": [{"path": "src/demo.py", "lines": 24, "statements": 12, "level": "WARNING"}],
                "flat_directories": [{"path": "src/demo", "direct_python_files": 6, "subdirectories": 0}],
                "facade_candidates": [
                    {
                        "path": "src/facade.py",
                        "score": 12,
                        "import_lines": 24,
                        "alias_bindings": 4,
                        "delegating_callables": 8,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = build_debt_index(buildlog_dir)

    assert payload["sections"]["file_size"]["import_blocks"][0]["path"] == "src/demo.py"
    assert payload["sections"]["file_size"]["flat_directories"][0]["path"] == "src/demo"
    assert payload["sections"]["file_size"]["facade_candidates"][0]["path"] == "src/facade.py"

    write_debt_index(buildlog_dir)
    markdown = (buildlog_dir / "debt-index.md").read_text(encoding="utf-8")
    assert "## File size" in markdown
    assert "- Import blocks: warning=1, critical=0, severe=0" in markdown
    assert "- Flattest directory: src/demo (6 direct Python files)" in markdown
    assert "- Facade candidates: 1" in markdown
    assert "- Top facade candidate: src/facade.py (score=12)" in markdown


def test_terminal_debt_snapshot_includes_file_size_highlights(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "file-size-analysis.json").write_text(
        json.dumps(
            {
                "counts": {
                    "file_lines": {"refactor": 1, "critical": 1, "severe": 1, "extreme": 1, "total": 4},
                    "import_block_lines": {"warning": 1, "critical": 1, "severe": 1, "total": 3},
                    "flat_directories": 2,
                    "facade_candidates": 1,
                },
                "files": [{"path": "src/extreme.py", "lines": 620, "bucket": "EXTREME"}],
                "import_blocks": [{"path": "src/severe.py", "lines": 40, "statements": 40, "level": "SEVERE"}],
                "flat_directories": [{"path": "tests/flat", "direct_python_files": 7, "subdirectories": 0}],
                "facade_candidates": [
                    {
                        "path": "src/facade.py",
                        "score": 12,
                        "import_lines": 24,
                        "alias_bindings": 4,
                        "delegating_callables": 8,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    lines = build_terminal_filesize_highlight(buildlog_dir)

    assert any("refactor 1" in line for line in lines)
    assert any("import-warn 1" in line for line in lines)
    assert any("Top import" in line and "src/severe.py" in line for line in lines)
    assert any("Top flat-dir" in line and "tests/flat" in line for line in lines)
    assert any("facades 1" in line for line in lines)
    assert any("Top facade" in line and "src/facade.py" in line for line in lines)


def test_flat_directory_density_sort_ranks_unsubdivided_before_well_organised(tmp_path, monkeypatch) -> None:
    """A directory with many files AND subdirs should rank below a flat one with fewer files.

    Example: 14 files / 6 subdirs → density 2.0 must sort after 10 files / 0 subdirs → density 10.0.
    """
    # Genuinely flat: 10 files, 0 subdirs → density 10.0
    for index in range(10):
        _write_small_python_file(tmp_path / "src" / "flat_pure" / f"module_{index}.py")

    # Well-organised: 14 files under a parent that also has 6 subdirs → density 14/7 = 2.0
    for index in range(14):
        _write_small_python_file(tmp_path / "src" / "organised" / f"module_{index}.py")
    for sub in range(6):
        _write_small_python_file(tmp_path / "src" / "organised" / f"sub_{sub}" / "placeholder.py")

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()
    assert result.exit_code == 0

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))
    paths = [item["path"] for item in payload["flat_directories"]]

    # flat_pure (density 10.0) must appear before organised (density 2.0)
    assert "src/flat_pure" in paths
    assert "src/organised" in paths
    assert paths.index("src/flat_pure") < paths.index("src/organised")

    densities = {item["path"]: item["flatness_density"] for item in payload["flat_directories"]}
    assert densities["src/flat_pure"] == 10.0
    assert densities["src/organised"] == 2.0


def test_load_flat_directory_allowlist_reads_configured_entries(tmp_path) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps(
            {
                "flat_directories": {
                    "allowed": [
                        {"path": "src/design/primitives", "reason": "design catalogue, intentionally flat"},
                        {"path": "src/other", "reason": "legacy layout"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    allowlist = load_flat_directory_allowlist(tmp_path)

    assert allowlist == {
        "src/design/primitives": "design catalogue, intentionally flat",
        "src/other": "legacy layout",
    }


def test_load_flat_directory_allowlist_returns_empty_when_config_missing(tmp_path) -> None:
    allowlist = load_flat_directory_allowlist(tmp_path)
    assert allowlist == {}


def test_scan_flat_directories_splits_hits_and_allowed(tmp_path) -> None:
    # Three directories exceeding threshold=8:
    #   flagged_a  — 9 files, 0 subdirs, NOT in allowlist → hit
    #   flagged_b  — 9 files, 0 subdirs, NOT in allowlist → hit
    #   exempted   — 9 files, 0 subdirs, IN allowlist    → allowed
    for i in range(9):
        _write_small_python_file(tmp_path / "src" / "flagged_a" / f"m{i}.py")
        _write_small_python_file(tmp_path / "src" / "flagged_b" / f"m{i}.py")
        _write_small_python_file(tmp_path / "src" / "exempted" / f"m{i}.py")

    allowlist = {"src/exempted": "intentionally flat design catalogue"}
    hits, allowed = scan_flat_directories(tmp_path, allowlist=allowlist)

    hit_paths = {item["path"] for item in hits}
    allowed_paths = {item["path"] for item in allowed}

    assert "src/flagged_a" in hit_paths
    assert "src/flagged_b" in hit_paths
    assert "src/exempted" not in hit_paths
    assert "src/exempted" in allowed_paths

    # The allowed entry must carry the reason string.
    exempted_entry = next(item for item in allowed if item["path"] == "src/exempted")
    assert exempted_entry["allowed_reason"] == "intentionally flat design catalogue"
    assert exempted_entry["flatness_density"] == 9.0


def test_scan_flat_directories_allowlist_entry_appears_in_json_report(tmp_path, monkeypatch) -> None:
    for i in range(9):
        _write_small_python_file(tmp_path / "src" / "exempt_dir" / f"m{i}.py")

    # Inject allowlist via config file.
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps({"flat_directories": {"allowed": [{"path": "src/exempt_dir", "reason": "test exemption"}]}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)
    result = step_size.file_size_runner()
    assert result.exit_code == 0

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))
    assert payload["counts"]["flat_directories"] == 0
    assert payload["counts"]["flat_directories_allowed"] == 1
    assert payload["flat_directories_allowed"][0]["path"] == "src/exempt_dir"
    assert payload["flat_directories_allowed"][0]["allowed_reason"] == "test exemption"

    markdown = (tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.md").read_text(encoding="utf-8")
    assert "## Flat directories suppressed by allowlist" in markdown
    assert "test exemption" in markdown
    assert "[allowed] src/exempt_dir" in result.stdout
