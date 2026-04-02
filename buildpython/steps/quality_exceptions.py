"""Helpers for typed quality-exception tags used by buildpython steps."""

from __future__ import annotations

import re
from dataclasses import dataclass


QUALITY_EXCEPTION_MARKER = "@quality-exception"
_QUALITY_EXCEPTION_TAG_RE = re.compile(
    r"@quality-exception\s+(?P<step>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?P<explanation>\s*(?::|-)?\s*.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QualityExceptionTag:
    step_slug: str
    explanation: str


def normalize_quality_exception_step_slug(step_slug: object) -> str:
    return str(step_slug or "").strip().lower()


def parse_quality_exception_tag(comment: str | None) -> QualityExceptionTag | None:
    if comment is None:
        return None

    match = _QUALITY_EXCEPTION_TAG_RE.search(comment)
    if match is None:
        return None

    return QualityExceptionTag(
        step_slug=normalize_quality_exception_step_slug(match.group("step")),
        explanation=_normalize_quality_exception_explanation(match.group("explanation")),
    )


def explanation_for_quality_exception_step(comment: str | None, *, step_slug: str) -> str | None:
    tag = parse_quality_exception_tag(comment)
    if tag is None or tag.step_slug != normalize_quality_exception_step_slug(step_slug):
        return None
    return tag.explanation


def _normalize_quality_exception_explanation(raw_explanation: str) -> str:
    explanation = str(raw_explanation or "").strip()
    explanation = explanation.lstrip(":").lstrip("-").strip()
    return explanation
