from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ._architecture_validation_helpers import (
    _iter_rule_files,
    _line_number,
    _line_snippet,
    _module_matches_import_rule,
    _rel_path,
    _scan_python_calls,
    _scan_python_signals,
    _ScannedAttribute,
    _ScannedCall,
    _ScannedImport,
)


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
class ArchitectureCallRule:
    receivers: tuple[str, ...]
    receiver_suffixes: tuple[str, ...]
    methods: tuple[str, ...]
    allowed_files: tuple[str, ...]
    required_locks: tuple[str, ...]
    message: str
    lock_message: str


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
    calls: tuple[ArchitectureCallRule, ...] = ()

    @property
    def call_rules(self) -> tuple[ArchitectureCallRule, ...]:
        """Compatibility alias for callers that name the rule category explicitly."""

        return self.calls


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

        calls: list[ArchitectureCallRule] = []
        raw_calls = raw_rule.get("calls", raw_rule.get("call_rules", [])) or []
        for raw_call in raw_calls:
            receivers = tuple(str(item).strip() for item in (raw_call.get("receivers", []) or []) if str(item).strip())
            receiver_suffixes = tuple(
                str(item).strip()
                for item in (raw_call.get("receiver_suffixes", []) or [])
                if str(item).strip()
            )
            methods = tuple(str(item).strip() for item in (raw_call.get("methods", []) or []) if str(item).strip())
            allowed_files = tuple(
                str(item).strip() for item in (raw_call.get("allowed_files", []) or []) if str(item).strip()
            )
            required_locks = tuple(
                str(item).strip() for item in (raw_call.get("required_locks", []) or []) if str(item).strip()
            )
            message = str(raw_call.get("message", "")).strip()
            lock_message = str(raw_call.get("lock_message", "")).strip()
            if (
                (not receivers and not receiver_suffixes)
                or not methods
                or not allowed_files
                or not required_locks
                or not message
                or not lock_message
            ):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid call entry")
            calls.append(
                ArchitectureCallRule(
                    receivers=receivers,
                    receiver_suffixes=receiver_suffixes,
                    methods=methods,
                    allowed_files=allowed_files,
                    required_locks=required_locks,
                    message=message,
                    lock_message=lock_message,
                )
            )

        if not patterns and not imports and not attributes and not calls:
            raise ValueError(f"architecture rule {rule_id!r} has no patterns, import rules, attribute rules, or call rules")

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
                calls=tuple(calls),
            )
        )

    return rules


def scan_architecture(root: Path, rules: Iterable[ArchitectureRule]) -> ArchitectureScanResult:
    findings: list[ArchitectureFinding] = []
    seen_findings: set[tuple[str, str, int, str, str]] = set()
    scanned_files: set[str] = set()
    scanned_python_signals: dict[str, tuple[tuple[_ScannedImport, ...], tuple[_ScannedAttribute, ...]]] = {}
    scanned_python_calls: dict[str, tuple[_ScannedCall, ...]] = {}
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

            calls = ()
            if rule.calls:
                calls = scanned_python_calls.get(rel)
                if calls is None:
                    calls = _scan_python_calls(text)
                    scanned_python_calls[rel] = calls

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

            for call_rule in rule.calls:
                for scanned_call in calls:
                    receiver_matches = scanned_call.receiver in call_rule.receivers or any(
                        scanned_call.receiver.endswith(suffix) for suffix in call_rule.receiver_suffixes
                    )
                    if not receiver_matches or scanned_call.method not in call_rule.methods:
                        continue

                    if not _path_matches_any(rel, call_rule.allowed_files):
                        message = call_rule.message
                    elif not any(lock in call_rule.required_locks for lock in scanned_call.lexical_locks):
                        message = call_rule.lock_message
                    else:
                        continue

                    finding_token = f"call:{scanned_call.receiver}.{scanned_call.method}"
                    finding_key = (rule.rule_id, rel, scanned_call.line, message, finding_token)
                    if finding_key in seen_findings:
                        continue
                    seen_findings.add(finding_key)
                    findings.append(
                        ArchitectureFinding(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            path=rel,
                            line=scanned_call.line,
                            message=message,
                            snippet=_line_snippet(lines=lines, line=scanned_call.line),
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


def _path_matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    posix_path = Path(path).as_posix()
    return any(posix_path == pattern or Path(posix_path).match(pattern) for pattern in patterns)
