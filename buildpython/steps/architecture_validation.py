from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ._architecture_validation_helpers import _iter_rule_files
from ._architecture_validation_helpers import _line_number
from ._architecture_validation_helpers import _line_snippet
from ._architecture_validation_helpers import _module_matches_import_rule
from ._architecture_validation_helpers import _rel_path
from ._architecture_validation_helpers import _ScannedAttribute
from ._architecture_validation_helpers import _ScannedImport
from ._architecture_validation_helpers import _scan_python_signals


@dataclass(frozen=True)
class ArchitecturePattern:
    regex: str
    message: str
    flags: str
    compiled: re.Pattern[str]


@dataclass(frozen=True)
class ArchitectureImportRule:
    module: str
    message: str


@dataclass(frozen=True)
class ArchitectureAttributeRule:
    name: str
    message: str


@dataclass(frozen=True)
class ArchitectureRule:
    rule_id: str
    description: str
    severity: str
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    patterns: tuple[ArchitecturePattern, ...]
    imports: tuple[ArchitectureImportRule, ...]
    attributes: tuple[ArchitectureAttributeRule, ...]


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

        imports: list[ArchitectureImportRule] = []
        for raw_import in raw_rule.get("imports", []) or []:
            module = str(raw_import.get("module", "")).strip()
            message = str(raw_import.get("message", "")).strip()
            if not module or not message:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid import entry")
            imports.append(ArchitectureImportRule(module=module, message=message))

        attributes: list[ArchitectureAttributeRule] = []
        for raw_attribute in raw_rule.get("attributes", []) or []:
            name = str(raw_attribute.get("name", "")).strip()
            message = str(raw_attribute.get("message", "")).strip()
            if not name or not message:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid attribute entry")
            attributes.append(ArchitectureAttributeRule(name=name, message=message))

        if not patterns and not imports and not attributes:
            raise ValueError(f"architecture rule {rule_id!r} has no patterns, import rules, or attribute rules")

        rules.append(
            ArchitectureRule(
                rule_id=rule_id,
                description=description,
                severity=severity,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                patterns=tuple(patterns),
                imports=tuple(imports),
                attributes=tuple(attributes),
            )
        )

    return rules


def scan_architecture(root: Path, rules: Iterable[ArchitectureRule]) -> ArchitectureScanResult:
    findings: list[ArchitectureFinding] = []
    seen_findings: set[tuple[str, str, int, str, str]] = set()
    scanned_files: set[str] = set()
    scanned_python_signals: dict[str, tuple[tuple[_ScannedImport, ...], tuple[_ScannedAttribute, ...]]] = {}
    rules_list = list(rules)

    for rule in rules_list:
        for path in _iter_rule_files(root=root, rule=rule):
            rel = _rel_path(root, path)
            scanned_files.add(rel)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
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

            if rule.imports or rule.attributes:
                signals = scanned_python_signals.get(rel)
                if signals is None:
                    signals = _scan_python_signals(text)
                    scanned_python_signals[rel] = signals
                imports, attributes = signals

            if rule.imports:
                for import_rule in rule.imports:
                    finding_token = f"import:{import_rule.module}"
                    for scanned_import in imports:
                        if not _module_matches_import_rule(scanned_import.module, import_rule.module):
                            continue

                        line = scanned_import.line
                        snippet = _line_snippet(lines=lines, line=line)
                        finding_key = (rule.rule_id, rel, line, import_rule.message, finding_token)
                        if finding_key in seen_findings:
                            continue
                        seen_findings.add(finding_key)
                        findings.append(
                            ArchitectureFinding(
                                rule_id=rule.rule_id,
                                severity=rule.severity,
                                path=rel,
                                line=line,
                                message=import_rule.message,
                                snippet=snippet,
                                regex=finding_token,
                            )
                        )

            if rule.attributes:
                for attribute_rule in rule.attributes:
                    finding_token = f"attribute:{attribute_rule.name}"
                    for scanned_attribute in attributes:
                        if scanned_attribute.name != attribute_rule.name:
                            continue

                        line = scanned_attribute.line
                        snippet = _line_snippet(lines=lines, line=line)
                        finding_key = (rule.rule_id, rel, line, attribute_rule.message, finding_token)
                        if finding_key in seen_findings:
                            continue
                        seen_findings.add(finding_key)
                        findings.append(
                            ArchitectureFinding(
                                rule_id=rule.rule_id,
                                severity=rule.severity,
                                path=rel,
                                line=line,
                                message=attribute_rule.message,
                                snippet=snippet,
                                regex=finding_token,
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
