from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Iterable


@dataclass(frozen=True)
class ArchitecturePattern:
    regex: str
    message: str
    flags: str
    compiled: re.Pattern[str]


@dataclass(frozen=True)
class ArchitectureRule:
    rule_id: str
    description: str
    severity: str
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    patterns: tuple[ArchitecturePattern, ...]


@dataclass(frozen=True)
class ArchitectureFinding:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    snippet: str
    regex: str


@dataclass(frozen=True)
class ArchitectureScanResult:
    findings: tuple[ArchitectureFinding, ...]
    scanned_files: int
    rules_checked: int


_FLAG_MAP = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
}


def load_architecture_rules(config_path: Path) -> list[ArchitectureRule]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    raw_rules = payload.get("rules", [])

    rules: list[ArchitectureRule] = []
    for raw_rule in raw_rules:
        rule_id = str(raw_rule.get("id", "")).strip()
        description = str(raw_rule.get("description", "")).strip()
        severity = str(raw_rule.get("severity", "error")).strip().lower()
        corpus = raw_rule.get("corpus", {}) or {}
        include_globs = tuple(str(item) for item in (corpus.get("include", []) or []))
        exclude_globs = tuple(str(item) for item in (corpus.get("exclude", []) or []))

        if not rule_id:
            raise ValueError("architecture rule missing 'id'")
        if severity not in {"error", "warning"}:
            raise ValueError(f"architecture rule {rule_id!r} has invalid severity {severity!r}")
        if not include_globs:
            raise ValueError(f"architecture rule {rule_id!r} has no corpus include globs")

        patterns: list[ArchitecturePattern] = []
        for raw_pattern in raw_rule.get("patterns", []) or []:
            regex = str(raw_pattern.get("regex", "")).strip()
            message = str(raw_pattern.get("message", "")).strip()
            flags = str(raw_pattern.get("flags", "")).strip().lower()
            if not regex or not message:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid pattern entry")
            patterns.append(
                ArchitecturePattern(
                    regex=regex,
                    message=message,
                    flags=flags,
                    compiled=re.compile(regex, _regex_flags(flags)),
                )
            )

        if not patterns:
            raise ValueError(f"architecture rule {rule_id!r} has no patterns")

        rules.append(
            ArchitectureRule(
                rule_id=rule_id,
                description=description,
                severity=severity,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                patterns=tuple(patterns),
            )
        )

    return rules


def scan_architecture(root: Path, rules: Iterable[ArchitectureRule]) -> ArchitectureScanResult:
    findings: list[ArchitectureFinding] = []
    seen_findings: set[tuple[str, str, int, str, str]] = set()
    scanned_files: set[str] = set()
    rules_list = list(rules)

    for rule in rules_list:
        for path in _iter_rule_files(root=root, rule=rule):
            rel = _rel_path(root, path)
            scanned_files.add(rel)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = text.splitlines()
            for pattern in rule.patterns:
                for match in pattern.compiled.finditer(text):
                    line = _line_number(text=text, offset=match.start())
                    snippet = _line_snippet(lines=lines, line=line)
                    finding_key = (rule.rule_id, rel, line, pattern.message, pattern.regex)
                    if finding_key in seen_findings:
                        continue
                    seen_findings.add(finding_key)
                    findings.append(
                        ArchitectureFinding(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            path=rel,
                            line=line,
                            message=pattern.message,
                            snippet=snippet,
                            regex=pattern.regex,
                        )
                    )

    findings.sort(key=lambda item: (item.severity != "error", item.path, item.line, item.rule_id))
    return ArchitectureScanResult(
        findings=tuple(findings),
        scanned_files=len(scanned_files),
        rules_checked=len(rules_list),
    )


def _regex_flags(raw_flags: str) -> int:
    flags = 0
    for flag in raw_flags:
        flags |= _FLAG_MAP.get(flag, 0)
    return flags


def _iter_rule_files(*, root: Path, rule: ArchitectureRule) -> list[Path]:
    matched: dict[str, Path] = {}
    for pattern in rule.include_globs:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            rel = _rel_path(root, path)
            if any(PurePosixPath(rel).match(exclude) for exclude in rule.exclude_globs):
                continue
            matched[rel] = path
    return [matched[key] for key in sorted(matched)]


def _rel_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _line_number(*, text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _line_snippet(*, lines: list[str], line: int) -> str:
    if line <= 0 or line > len(lines):
        return ""
    return lines[line - 1].strip()[:200]