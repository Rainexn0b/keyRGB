from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LOC_SCAN_ROOTS = ("src", "buildpython", "tests")


@dataclass(frozen=True)
class LocBucket:
    key: str
    label: str
    minimum: int
    maximum: int | None = None


DEFAULT_LOC_BUCKETS = (
    LocBucket("monitor", "Monitor", 350, 399),
    LocBucket("refactor", "Refactor", 400, 449),
    LocBucket("critical", "Critical", 450, 549),
    LocBucket("severe", "Severe", 550),
)

TEST_LOC_BUCKETS = (
    LocBucket("monitor", "Monitor", 400, 449),
    LocBucket("refactor", "Refactor", 450, 499),
    LocBucket("critical", "Critical", 500, 600),
    LocBucket("severe", "Severe", 601),
)

LOC_BUCKET_ORDER = tuple(bucket.key for bucket in DEFAULT_LOC_BUCKETS)
LOC_BUCKET_LABELS = {bucket.key: bucket.label for bucket in DEFAULT_LOC_BUCKETS}
DEFAULT_THRESHOLD_LINES = DEFAULT_LOC_BUCKETS[0].minimum


def is_test_path(rel_path: Path) -> bool:
    return "tests" in rel_path.parts


def loc_scope(rel_path: Path) -> str:
    return "tests" if is_test_path(rel_path) else "default"


def loc_bucket(line_count: int, *, rel_path: Path) -> str | None:
    for bucket in reversed(bucket_definitions_for_path(rel_path)):
        if line_count >= bucket.minimum:
            return bucket.label.upper()
    return None


def bucket_definitions_for_path(rel_path: Path) -> tuple[LocBucket, ...]:
    return TEST_LOC_BUCKETS if is_test_path(rel_path) else DEFAULT_LOC_BUCKETS


def bucket_range_text(bucket: LocBucket) -> str:
    if bucket.maximum is None:
        return f"{bucket.minimum}+"
    return f"{bucket.minimum}-{bucket.maximum}"


def threshold_descriptions() -> dict[str, str]:
    return {
        "default": ", ".join(f"{bucket.key}={bucket_range_text(bucket)}" for bucket in DEFAULT_LOC_BUCKETS),
        "tests": ", ".join(f"{bucket.key}={bucket_range_text(bucket)}" for bucket in TEST_LOC_BUCKETS),
    }


def threshold_map() -> dict[str, dict[str, dict[str, int]]]:
    return {
        "default": _bucket_threshold_map(DEFAULT_LOC_BUCKETS),
        "tests": _bucket_threshold_map(TEST_LOC_BUCKETS),
    }


def _bucket_threshold_map(buckets: tuple[LocBucket, ...]) -> dict[str, dict[str, int]]:
    thresholds: dict[str, dict[str, int]] = {}
    for bucket in buckets:
        item: dict[str, int] = {"min": bucket.minimum}
        if bucket.maximum is not None:
            item["max"] = bucket.maximum
        thresholds[bucket.key] = item
    return thresholds