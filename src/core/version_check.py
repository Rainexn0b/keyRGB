from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_VERSION_LIKE_RE = re.compile(r"v?\d+(?:\.\d+){1,3}(?:a\d+|b\d+|rc\d+)?", re.IGNORECASE)
_PRE_RE = re.compile(r"^(?P<main>\d+(?:\.\d+)*)(?:(?P<pre>a|b|rc)(?P<pre_n>\d+))?$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedVersion:
    parts: tuple[int, ...]
    pre_kind: str | None  # a, b, rc
    pre_num: int


def normalize_version_text(text: str | None) -> str | None:
    """Extract a version-like string and strip a leading 'v'.

    Examples:
    - 'v0.4.0' -> '0.4.0'
    - '0.4.0' -> '0.4.0'
    - 'release v0.1.5' -> '0.1.5'
    """

    if not text:
        return None

    m = _VERSION_LIKE_RE.search(str(text).strip())
    if not m:
        return None

    v = m.group(0).strip()
    if v.lower().startswith("v"):
        v = v[1:]
    return v


def parse_version(text: str | None) -> ParsedVersion | None:
    """Parse a small subset of PEP 440 used in this repo (X.Y.Z + optional a/b/rcN)."""

    v = normalize_version_text(text)
    if not v:
        return None

    m = _PRE_RE.match(v)
    if not m:
        return None

    main = m.group("main")
    parts = tuple(int(p) for p in main.split(".") if p.strip().isdigit())
    pre_kind = m.group("pre")
    pre_num_txt = m.group("pre_n")
    pre_num = int(pre_num_txt) if pre_num_txt and pre_num_txt.isdigit() else 0

    return ParsedVersion(parts=parts, pre_kind=(pre_kind.lower() if pre_kind else None), pre_num=pre_num)


def compare_versions(a: str | None, b: str | None) -> int | None:
    """Compare versions.

    Returns:
    - -1 if a < b
    - 0 if a == b
    - 1 if a > b
    - None if either side can't be parsed
    """

    pa = parse_version(a)
    pb = parse_version(b)
    if pa is None or pb is None:
        return None

    max_len = max(len(pa.parts), len(pb.parts), 3)
    a_parts = pa.parts + (0,) * (max_len - len(pa.parts))
    b_parts = pb.parts + (0,) * (max_len - len(pb.parts))

    if a_parts < b_parts:
        return -1
    if a_parts > b_parts:
        return 1

    # Same numeric parts; compare pre-release.
    order = {"a": 0, "b": 1, "rc": 2, None: 3}
    a_kind = order.get(pa.pre_kind, 3)
    b_kind = order.get(pb.pre_kind, 3)

    if a_kind < b_kind:
        return -1
    if a_kind > b_kind:
        return 1

    # Same pre kind.
    if int(pa.pre_num) < int(pb.pre_num):
        return -1
    if int(pa.pre_num) > int(pb.pre_num):
        return 1

    return 0
