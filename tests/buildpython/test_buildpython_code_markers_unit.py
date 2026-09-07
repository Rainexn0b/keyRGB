from __future__ import annotations

from collections import Counter
from pathlib import Path

from buildpython.steps.code_markers.scanning import scan_one_file


def _scan_source(tmp_path: Path, source: str) -> Counter[str]:
    path = tmp_path / "keyrgb" / "example.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    counts: Counter[str] = Counter()
    scan_one_file(
        file=path,
        root=tmp_path,
        counts=counts,
        counts_by_file_marker=Counter(),
        marker_hits=[],
        commented_code_hits=[],
    )
    return counts


def test_code_markers_count_standalone_comment_tokens(tmp_path) -> None:
    counts = _scan_source(
        tmp_path,
        "# NOTE: keep the icon stable\n# TODO: follow up\n# FIXME: broken\n",
    )

    assert counts["NOTE"] == 1
    assert counts["TODO"] == 1
    assert counts["FIXME"] == 1
    assert counts["REVIEW"] == 0


def test_code_markers_ignore_embedded_identifier_substrings(tmp_path) -> None:
    counts = _scan_source(
        tmp_path,
        "_CAP_NOTE_TEXT = 'help'\n_LIVE_PREVIEW_INTERVAL_MS = 1000\n",
    )

    assert counts["NOTE"] == 0
    assert counts["REVIEW"] == 0
