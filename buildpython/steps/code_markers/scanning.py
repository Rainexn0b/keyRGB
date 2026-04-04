from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ...utils.paths import repo_root
from .baseline import MARKERS, REF_EXTS


COMMENTED_CODE_RE = re.compile(
    r"^\s*#\s*(def |class |import |from |if |elif |else:|for |while |try:|except |with |return |raise )"
)


def iter_source_files() -> list[Path]:
    root = repo_root()
    src = root / "src"
    if not src.exists():
        return []

    files: list[Path] = []
    for path in src.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        files.append(path)

    for path in [root / "keyrgb", root / "keyrgb-tuxedo"]:
        if path.exists() and path.is_file():
            files.append(path)

    return files


def scan_one_file(
    *,
    file: Path,
    root: Path,
    counts: Counter[str],
    counts_by_file_marker: Counter[tuple[str, str]],
    marker_hits: list[str],
    commented_code_hits: list[str],
    max_marker_hits: int = 200,
    max_commented_hits: int = 200,
) -> None:
    try:
        text = file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    rel = file.relative_to(root)
    rel_str = str(rel)
    for idx, line in enumerate(text.splitlines(), start=1):
        for marker in MARKERS:
            if marker not in line:
                continue
            counts[marker] += 1
            counts_by_file_marker[(rel_str, marker)] += 1
            if len(marker_hits) < max_marker_hits:
                marker_hits.append(f"{rel}:{idx}: {line.strip()}")

        if COMMENTED_CODE_RE.match(line) and len(commented_code_hits) < max_commented_hits:
            commented_code_hits.append(f"{rel}:{idx}: {line.strip()}")


def scan_source_files(
    files: list[Path], *, root: Path
) -> tuple[Counter[str], Counter[tuple[str, str]], list[str], list[str]]:
    counts: Counter[str] = Counter()
    counts_by_file_marker: Counter[tuple[str, str]] = Counter()
    marker_hits: list[str] = []
    commented_code_hits: list[str] = []
    for file in files:
        scan_one_file(
            file=file,
            root=root,
            counts=counts,
            counts_by_file_marker=counts_by_file_marker,
            marker_hits=marker_hits,
            commented_code_hits=commented_code_hits,
        )
    return counts, counts_by_file_marker, marker_hits, commented_code_hits


def top_marker_files(counts_by_file_marker: Counter[tuple[str, str]]) -> dict[str, list[tuple[str, int]]]:
    grouped: dict[str, Counter[str]] = {marker: Counter() for marker in MARKERS}
    for (path_str, marker), count in counts_by_file_marker.items():
        grouped.setdefault(marker, Counter())[path_str] += count
    return {marker: grouped[marker].most_common(10) for marker in MARKERS if grouped.get(marker)}


def find_ref_files(*, root: Path) -> list[str]:
    ref_files: list[str] = []
    for ext in REF_EXTS:
        for path in root.rglob(f"*{ext}"):
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            ref_files.append(str(path.relative_to(root)))
    return ref_files
