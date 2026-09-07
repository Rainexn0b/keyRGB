from __future__ import annotations

import json
from pathlib import Path

import buildpython.steps.file_size_analysis.step as step_size
from buildpython.steps.file_size_analysis.scanning import (
    scan_delegation_candidate,
    scan_import_block,
)


def _write_python_file(path: Path, *, total_lines: int, import_lines: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [f"import module_{index}" for index in range(import_lines)]
    filler_lines = total_lines - len(lines)
    assert filler_lines > 0
    lines.extend(f"value_{index} = {index}" for index in range(filler_lines))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_delegation_candidate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(  # noqa: FLY002 - explicit generated fixture lines are easier to review
            [
                '"""Delegation candidate."""',
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
                "class DelegationSurface:",
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


def _write_export_facade(path: Path, *, extra_leading_imports: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    alpha_names = [f"alpha_{index:02d}" for index in range(1, 11)]
    beta_names = [f"beta_{index:02d}" for index in range(1, 11)]
    export_names = [*alpha_names, *beta_names]

    lines = ['"""Export facade."""', "", "from __future__ import annotations", "", "from .alpha import ("]
    lines.extend(f"    {name}," for name in alpha_names)
    lines.extend(
        [
            ")",
            "from .beta import (",
        ]
    )
    lines.extend(f"    {name}," for name in beta_names)
    lines.append(")")

    for index in range(extra_leading_imports):
        name = f"gamma_{index + 1:02d}"
        lines.append(f"from .gamma import {name}")
        export_names.append(name)

    lines.extend(["", "__all__ = ["])
    lines.extend(f'    "{name}",' for name in export_names)
    lines.append("]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_small_thin_facade(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ['"""Thin facade below the refactor threshold."""']
    lines.extend(f"from pkg import helper_{index:02d}" for index in range(1, 22))
    lines.extend(
        [
            "delegate_one = helper_01",
            "delegate_two = helper_02",
            "delegate_three = helper_03",
            "delegate_four = helper_04",
        ]
    )
    lines.extend(f"FACADE_META_{index:02d} = {index}" for index in range(1, 49))
    lines.append("class ThinFacade:")
    for index in range(5, 17):
        method_name = f"call_{index:02d}"
        helper_name = f"helper_{index:02d}"
        lines.extend(
            [
                f"    def {method_name}(self):",
                f"        return {helper_name}()",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_scan_import_block_skips_small_pure_export_init_facade(tmp_path) -> None:
    facade_path = tmp_path / "keyrgb" / "package" / "__init__.py"
    _write_export_facade(facade_path)

    assert scan_import_block(facade_path) is None


def test_scan_import_block_still_flags_non_init_export_facade(tmp_path) -> None:
    module_path = tmp_path / "keyrgb" / "package" / "exports.py"
    _write_export_facade(module_path)

    assert scan_import_block(module_path) == (26, 3)


def test_scan_import_block_still_flags_init_facade_with_more_than_three_imports(tmp_path) -> None:
    facade_path = tmp_path / "keyrgb" / "package" / "__init__.py"
    _write_export_facade(facade_path, extra_leading_imports=1)

    assert scan_import_block(facade_path) == (27, 4)


def test_scan_delegation_candidate_skips_small_low_density_thin_facade(tmp_path) -> None:
    facade_path = tmp_path / "keyrgb" / "facade.py"
    _write_small_thin_facade(facade_path)

    assert scan_delegation_candidate(facade_path) is None


def test_scan_delegation_candidate_still_flags_dense_small_delegate_module(tmp_path) -> None:
    candidate_path = tmp_path / "keyrgb" / "delegation_candidate.py"
    _write_delegation_candidate(candidate_path)

    result = scan_delegation_candidate(candidate_path)

    assert result is not None
    assert result["score"] == 10


def test_file_size_runner_suppresses_file_level_quality_exception_waivers(tmp_path, monkeypatch) -> None:
    _write_python_file(
        tmp_path / "keyrgb" / "waived_large.py",
        total_lines=420,
        import_lines=24,
    )
    waived_large = tmp_path / "keyrgb" / "waived_large.py"
    waived_large.write_text(
        "# @quality-exception file-size-analysis: generated compatibility shim module\n"
        + waived_large.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    _write_delegation_candidate(tmp_path / "keyrgb" / "waived_delegation.py")
    waived_delegation = tmp_path / "keyrgb" / "waived_delegation.py"
    waived_delegation.write_text(
        "# @quality-exception file-size-analysis: temporary facade retained for API stability\n"
        + waived_delegation.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    _write_python_file(tmp_path / "keyrgb" / "active_large.py", total_lines=410, import_lines=22)

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()

    assert result.exit_code == 0
    assert "Quality-exception waivers: 2" in result.stdout
    assert "[waived] keyrgb/waived_large.py" in result.stdout
    assert "[waived] keyrgb/waived_delegation.py" in result.stdout

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))

    assert payload["counts"]["waived_files"] == 2
    assert payload["waivers"]["step_slug"] == "file-size-analysis"
    assert payload["waivers"]["files_total"] == 2
    waived_paths = {item["path"] for item in payload["waivers"]["files"]}
    assert waived_paths == {"keyrgb/waived_large.py", "keyrgb/waived_delegation.py"}

    assert all(item["path"] != "keyrgb/waived_large.py" for item in payload["files"])
    assert all(item["path"] != "keyrgb/waived_large.py" for item in payload["import_blocks"])
    assert all(item["path"] != "keyrgb/waived_delegation.py" for item in payload["delegation_candidates"])
    assert any(item["path"] == "keyrgb/active_large.py" for item in payload["files"])

    markdown = (tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.md").read_text(encoding="utf-8")
    assert "## Quality-exception waivers" in markdown
    assert "keyrgb/waived_large.py" in markdown
