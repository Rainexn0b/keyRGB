from __future__ import annotations

import json
from pathlib import Path

import buildpython.steps.code_hygiene.baseline as step_code_hygiene_baseline
import buildpython.steps.code_hygiene.step as step_code_hygiene
import buildpython.steps.file_size_analysis._ast_scan_helpers as file_size_ast_scan_helpers
from buildpython.steps.code_hygiene import detectors as code_hygiene_detectors, text_scanners
from buildpython.steps.code_hygiene.baseline import _path_budget_regressions
from buildpython.steps.code_hygiene.models import HygieneBaseline, HygieneIssue


def test_path_budget_regressions_flag_specific_hotspots() -> None:
    issues = [
        HygieneIssue(
            category="silent_broad_except",
            path="keyrgb/tray/app/application.py",
            line=1,
            message="msg",
            snippet="except Exception:",
        ),
        HygieneIssue(
            category="silent_broad_except",
            path="keyrgb/tray/app/application.py",
            line=2,
            message="msg",
            snippet="except Exception:",
        ),
        HygieneIssue(
            category="fallback_broad_except",
            path="keyrgb/core/config/config.py",
            line=3,
            message="msg",
            snippet="except Exception:",
        ),
    ]
    baseline = HygieneBaseline(
        counts={},
        gated_categories=set(),
        path_budgets={
            "silent_broad_except": {"keyrgb/tray/app/application.py": 1},
            "fallback_broad_except": {"keyrgb/core/config/config.py": 2},
        },
    )

    regressions = _path_budget_regressions(issues, baseline)

    assert regressions == [("silent_broad_except", "keyrgb/tray/app/application.py", 2, 1)]


def test_load_hygiene_baseline_returns_empty_on_invalid_json(tmp_path) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text("{not valid json", encoding="utf-8")

    baseline = step_code_hygiene_baseline._load_hygiene_baseline(tmp_path)

    assert baseline == HygieneBaseline(counts={}, gated_categories=set(), path_budgets={})


def test_code_hygiene_runner_uses_cleanup_hotspot_threshold_from_baseline(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps(
            {
                "code_hygiene": {
                    "counts": {
                        "cleanup_hotspot": 94,
                        "silent_broad_except": 0,
                    },
                    "gated_categories": ["cleanup_hotspot", "silent_broad_except"],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    issues = [
        HygieneIssue(
            category="cleanup_hotspot",
            path="keyrgb/example.py",
            line=line,
            message="msg",
            snippet="# TODO",
        )
        for line in range(1, 96)
    ]

    monkeypatch.setattr(step_code_hygiene, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_code_hygiene, "_collect_all_issues", lambda _root: issues)

    result = step_code_hygiene.code_hygiene_runner()
    report = json.loads((tmp_path / "buildlog" / "keyrgb" / "code-hygiene.json").read_text(encoding="utf-8"))

    assert result.exit_code == 1
    assert report["thresholds"]["cleanup_hotspot"] == 94
    assert report["active_counts"]["cleanup_hotspot"] == 95


def test_code_hygiene_runner_uses_gated_non_cleanup_baselines(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "buildpython" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "debt_baselines.json").write_text(
        json.dumps(
            {
                "code_hygiene": {
                    "counts": {
                        "cleanup_hotspot": 94,
                        "silent_broad_except": 0,
                    },
                    "gated_categories": ["cleanup_hotspot", "silent_broad_except"],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    issues = [
        HygieneIssue(
            category="silent_broad_except",
            path="keyrgb/example.py",
            line=1,
            message="msg",
            snippet="except Exception:",
        )
    ]

    monkeypatch.setattr(step_code_hygiene, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_code_hygiene, "_collect_all_issues", lambda _root: issues)

    result = step_code_hygiene.code_hygiene_runner()
    report = json.loads((tmp_path / "buildlog" / "keyrgb" / "code-hygiene.json").read_text(encoding="utf-8"))

    assert result.exit_code == 1
    assert report["thresholds"]["cleanup_hotspot"] == 94
    assert report["thresholds"]["silent_broad_except"] == 0


def test_hygiene_detectors_ignore_missing_or_unparseable_sources(tmp_path) -> None:
    root = tmp_path
    missing_file = root / "keyrgb" / "missing.py"
    broken_file = root / "keyrgb" / "tray" / "ui" / "broken.py"
    broken_file.parent.mkdir(parents=True)
    broken_file.write_text("def broken(:\n    pass\n", encoding="utf-8")

    assert code_hygiene_detectors._detect_cleanup_hotspots(missing_file, root) == []
    assert code_hygiene_detectors._detect_runtime_copy_hotspots(broken_file, root) == []
    assert code_hygiene_detectors._detect_broad_exception_patterns(broken_file, root) == []


def test_text_scanners_match_representative_cleanup_and_defensive_patterns(tmp_path) -> None:
    root = tmp_path
    target = root / "buildpython" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        """
value = int(int(raw))
flag = bool(bool(raw_flag))
ratio = float(float(raw_ratio))
name = str(str(raw_name))
fallback = int(getattr(obj, "count") or 0)
return int(int(result))
# TODO: refactor me
# FIXME: tighten this later
# HACK: compatibility shim
# LEGACY: keep while migrating
# FACADE: remove after split
legacy_alias = thing
facade_alias = thing
migrate_legacy(profile)
compat_layer = True
""".strip(),
        encoding="utf-8",
    )

    defensive_issues = text_scanners._detect_defensive_conversions(target, root)
    cleanup_issues = text_scanners._detect_cleanup_hotspots(target, root)

    assert [issue.line for issue in defensive_issues] == [1, 2, 3, 4, 5, 6, 6]
    assert [issue.message for issue in defensive_issues] == [
        "nested int(int(...))",
        "nested bool(bool(...))",
        "nested float(float(...))",
        "nested str(str(...))",
        "int(getattr(...) or 0) - consider default param",
        "nested int(int(...))",
        "return int(int(...))",
    ]
    assert [issue.line for issue in cleanup_issues] == [7, 8, 9, 10, 11, 12, 13, 14, 15]
    assert all(
        issue.message == "Cleanup/facade/legacy marker found: consider refactor or migration plan"
        for issue in cleanup_issues
    )


def test_text_scanners_do_not_self_flag_cleanup_or_defensive_patterns() -> None:
    scanner_path = Path(text_scanners.__file__).resolve()
    ast_helper_path = Path(file_size_ast_scan_helpers.__file__).resolve()
    root = scanner_path.parents[3]

    assert text_scanners._detect_defensive_conversions(scanner_path, root) == []
    assert text_scanners._detect_cleanup_hotspots(scanner_path, root) == []
    assert text_scanners._detect_cleanup_hotspots(ast_helper_path, root) == []


def test_any_type_hint_scanner_covers_all_src_including_gui_paths(tmp_path) -> None:
    root = tmp_path
    gui_target = root / "keyrgb" / "gui" / "perkey" / "editor.py"
    helper_target = root / "buildpython" / "helper.py"
    gui_target.parent.mkdir(parents=True)
    helper_target.parent.mkdir(parents=True)

    gui_target.write_text(
        "from typing import Any\n\ndef initialize_editor(editor: Any) -> Any:\n    return editor\n",
        encoding="utf-8",
    )
    helper_target.write_text(
        "from typing import Any\n\ndef helper(value: Any) -> Any:\n    return value\n",
        encoding="utf-8",
    )

    issues = text_scanners._detect_any_type_hints(gui_target, root)

    assert [(issue.path, issue.line, issue.message) for issue in issues] == [
        (
            "keyrgb/gui/perkey/editor.py",
            3,
            "Parameter typed as Any - consider Protocol or concrete type",
        ),
        (
            "keyrgb/gui/perkey/editor.py",
            3,
            "Return typed as Any - consider Protocol or concrete type",
        ),
    ]
    assert text_scanners._detect_any_type_hints(helper_target, root) == []
