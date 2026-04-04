from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult
from .code_markers.baseline import MarkerBaseline, load_marker_baseline as _load_marker_baseline, marker_regressions
from .code_markers.reporting import build_stdout_lines, write_reports
from .code_markers.scanning import (
    find_ref_files,
    iter_source_files,
    scan_source_files,
    top_marker_files,
)


def code_markers_runner() -> RunResult:
    root = repo_root()
    baseline = _load_marker_baseline(root)
    files = iter_source_files()
    counts, counts_by_file_marker, marker_hits, commented_code_hits = scan_source_files(files, root=root)
    top_marker_files_map = top_marker_files(counts_by_file_marker)
    ref_files = find_ref_files(root=root)
    stdout_lines = build_stdout_lines(
        counts=counts,
        baseline=baseline,
        top_marker_files=top_marker_files_map,
        marker_hits=marker_hits,
        commented_code_hits=commented_code_hits,
        ref_files=ref_files,
    )
    write_reports(
        root=root,
        counts=counts,
        baseline=baseline,
        top_marker_files=top_marker_files_map,
        marker_hits=marker_hits,
        commented_code_hits=commented_code_hits,
        ref_files=ref_files,
    )

    exit_code = 1 if marker_regressions(counts, baseline) else 0

    return RunResult(
        command_str="(internal) code marker scan",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
