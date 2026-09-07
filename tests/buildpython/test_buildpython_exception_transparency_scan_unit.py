from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from buildpython.steps.exception_transparency.models import ExceptionTransparencyAnnotationInventory
from buildpython.steps.exception_transparency.reporting import build_stdout, write_reports
from buildpython.steps.exception_transparency.scanner import (
    collect_annotation_inventory,
    collect_findings,
    scan_python_source as _scan_python_source,
)


def test_exception_transparency_scan_suppresses_valid_quality_exception_waivers() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
    # @quality-exception exception-transparency: optional runtime boundary for startup fallback
    except Exception:
        pass

    try:
        run_two()
    except Exception:  # @quality-exception exception-transparency: shutdown cleanup boundary
        pass
""".strip(),
        rel_path="keyrgb/example.py",
    )

    assert findings == []


def test_exception_transparency_scan_ignores_indented_preceding_quality_exception_comment() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
        # @quality-exception exception-transparency: try-body comment should not waive the handler
    except Exception:
        pass
""".strip(),
        rel_path="keyrgb/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 1
    assert counts["broad_except_unlogged"] == 1


def test_exception_transparency_scan_ignores_other_step_quality_exception_tags() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
    except Exception:  # @quality-exception coverage: tracked by another step
        pass
""".strip(),
        rel_path="keyrgb/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 1
    assert counts["broad_except_unlogged"] == 1


def test_exception_transparency_scan_requires_quality_exception_explanation() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
    except Exception:  # @quality-exception exception-transparency
        pass
""".strip(),
        rel_path="keyrgb/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 1
    assert counts["broad_except_unlogged"] == 1


def test_exception_transparency_scan_classifies_broad_handlers_without_waivers() -> None:
    findings = _scan_python_source(
        """
from keyrgb.core.utils.logging_utils import log_throttled

def example(logger):
    try:
        run_one()
    except Exception:
        pass

    try:
        run_two()
    except Exception:
        logger.warning('warn only')

    try:
        run_three()
    except Exception as exc:
        logger.exception('boom: %s', exc)

    try:
        run_throttled()
    except Exception as exc:
        log_throttled(logger, 'demo', interval_s=60, level=40, msg='throttled', exc=exc)

    try:
        run_four()
    except BaseException:
        return None
""".strip(),
        rel_path="keyrgb/example.py",
    )

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1

    assert counts["broad_except_total"] == 5
    assert counts["broad_except_unlogged"] == 2
    assert counts["broad_except_logged_no_traceback"] == 1
    assert counts["broad_except_traceback_logged"] == 2
    assert counts["baseexception_catch"] == 1
    assert counts.get("naked_except", 0) == 0


def test_exception_transparency_scan_resolves_local_exception_aliases() -> None:
    findings = _scan_python_source(
        """
SPECIFIC_ERRORS = (OSError, RuntimeError)
BROAD_ERRORS = SPECIFIC_ERRORS + (Exception,)

def example():
    try:
        run_specific()
    except SPECIFIC_ERRORS:
        pass

    try:
        run_broad()
    except BROAD_ERRORS:
        pass
""".strip(),
        rel_path="keyrgb/example.py",
    )

    counts = Counter(finding.category for finding in findings)
    assert counts == Counter({"broad_except_total": 1, "broad_except_unlogged": 1})


def test_exception_transparency_waiver_cannot_hide_baseexception() -> None:
    findings = _scan_python_source(
        """
def example():
    try:
        run_one()
    except BaseException:  # @quality-exception exception-transparency: finalizer boundary
        pass
""".strip(),
        rel_path="keyrgb/example.py",
    )

    assert [finding.category for finding in findings] == ["baseexception_catch"]


def test_exception_transparency_scan_skips_unparseable_source() -> None:
    findings = _scan_python_source(
        """
def broken(:
    pass
""".strip(),
        rel_path="keyrgb/example.py",
    )

    assert findings == []


def test_exception_transparency_collect_findings_skips_unreadable_files(tmp_path, monkeypatch) -> None:
    readable = tmp_path / "keyrgb" / "ok.py"
    unreadable = tmp_path / "buildpython" / "blocked.py"
    readable.parent.mkdir(parents=True)
    unreadable.parent.mkdir(parents=True)
    readable.write_text(
        """
def example():
    try:
        run_one()
    except Exception:
        pass
""".strip(),
        encoding="utf-8",
    )
    unreadable.write_text("def blocked():\n    return None\n", encoding="utf-8")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs) -> str:
        if self == unreadable:
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert {finding.category for finding in collect_findings(tmp_path)} == {
        "broad_except_total",
        "broad_except_unlogged",
    }


def test_exception_transparency_collect_annotation_inventory_groups_valid_tags_by_subtree(tmp_path) -> None:
    tray_file = tmp_path / "keyrgb" / "tray" / "runtime.py"
    helper_file = tmp_path / "buildpython" / "core" / "helpers.py"
    tray_file.parent.mkdir(parents=True)
    helper_file.parent.mkdir(parents=True)
    tray_file.write_text(
        """
def run_tray():
    # @quality-exception exception-transparency: tray startup boundary
    try:
        launch()
    except RuntimeError:  # @quality-exception exception-transparency: tray runtime boundary
        return None
""".strip(),
        encoding="utf-8",
    )
    helper_file.write_text(
        """
def run_helper():
    # @quality-exception exception-transparency: build helper boundary
    return True

def ignored_helper():
    # @quality-exception exception-transparency
    return False
""".strip(),
        encoding="utf-8",
    )

    inventory = collect_annotation_inventory(tmp_path)

    assert inventory.total == 3
    assert inventory.by_subtree == (("keyrgb/tray", 2), ("buildpython/core", 1))


def test_exception_transparency_reports_include_annotation_inventory(tmp_path) -> None:
    inventory = ExceptionTransparencyAnnotationInventory(
        total=3,
        by_subtree=(("keyrgb/tray", 2), ("keyrgb/core", 1)),
    )

    stdout_lines = build_stdout([], Counter(), 0, inventory)
    write_reports(tmp_path, [], Counter(), 0, inventory)

    report_dir = tmp_path / "buildlog" / "keyrgb"
    payload = json.loads((report_dir / "exception-transparency.json").read_text(encoding="utf-8"))
    report_md = (report_dir / "exception-transparency.md").read_text(encoding="utf-8")

    assert any("Valid @quality-exception exception-transparency annotations: 3" in line for line in stdout_lines)
    assert payload["annotation_inventory"] == {
        "total": 3,
        "by_subtree": [
            {"subtree": "keyrgb/tray", "count": 2},
            {"subtree": "keyrgb/core", "count": 1},
        ],
    }
    assert "## Runtime-Boundary Annotation Inventory" in report_md
    assert "| keyrgb/tray | 2 |" in report_md
