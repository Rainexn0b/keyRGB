from __future__ import annotations

from ...utils.paths import repo_root
from ...utils.subproc import RunResult
from .constants import SIZE_SCAN_ROOTS
from .reporting import build_stdout_lines, write_reports
from .scanning import collect_hotspots


def file_size_runner() -> RunResult:
    root = repo_root()
    file_rows, import_rows, flat_directories, flat_directories_allowed, facade_rows = collect_hotspots(
        root, roots=SIZE_SCAN_ROOTS
    )
    write_reports(
        root=root,
        file_rows=file_rows,
        import_rows=import_rows,
        flat_directories=flat_directories,
        flat_directories_allowed=flat_directories_allowed,
        facade_rows=facade_rows,
    )
    stdout = "\n".join(
        build_stdout_lines(
            file_rows=file_rows,
            import_rows=import_rows,
            flat_directories=flat_directories,
            flat_directories_allowed=flat_directories_allowed,
            facade_rows=facade_rows,
        )
    )
    return RunResult(
        command_str="(internal) file size analysis",
        stdout=stdout + "\n",
        stderr="",
        exit_code=0,
    )
