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
    _scan_python_assignments,
    _scan_python_calls,
    _scan_python_lock_acquisitions,
    _scan_python_signals,
    _ScannedAssignment,
    _ScannedAttribute,
    _ScannedCall,
    _ScannedImport,
    _ScannedLockAcquisition,
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
class ArchitectureAssignmentRule:
    targets: tuple[str, ...]
    target_suffixes: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ArchitectureKeywordExemption:
    name: str
    equals: object


@dataclass(frozen=True)
class ArchitectureCallRule:
    receivers: tuple[str, ...]
    receiver_suffixes: tuple[str, ...]
    methods: tuple[str, ...]
    allowed_files: tuple[str, ...]
    required_locks: tuple[str, ...]
    skip_if_keywords: tuple[ArchitectureKeywordExemption, ...]
    message: str
    lock_message: str


@dataclass(frozen=True)
class ArchitectureForbiddenUnderLockCallRule:
    receivers: tuple[str, ...]
    receiver_suffixes: tuple[str, ...]
    methods: tuple[str, ...]
    match_any_receiver: bool
    required_locks: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ArchitectureLock:
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ArchitectureLockOrderRule:
    locks: tuple[ArchitectureLock, ...]
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
    calls: tuple[ArchitectureCallRule, ...] = ()
    forbidden_under_locks: tuple[ArchitectureForbiddenUnderLockCallRule, ...] = ()
    lock_orders: tuple[ArchitectureLockOrderRule, ...] = ()
    assignments: tuple[ArchitectureAssignmentRule, ...] = ()

    @property
    def call_rules(self) -> tuple[ArchitectureCallRule, ...]:
        """Compatibility alias for callers that name the rule category explicitly."""

        return self.calls

    @property
    def assignment_rules(self) -> tuple[ArchitectureAssignmentRule, ...]:
        """Compatibility alias for callers that name the rule category explicitly."""

        return self.assignments

    @property
    def forbidden_call_rules(self) -> tuple[ArchitectureForbiddenUnderLockCallRule, ...]:
        """Compatibility alias for the forbidden-under-lock call category."""

        return self.forbidden_under_locks

    @property
    def forbidden_calls(self) -> tuple[ArchitectureForbiddenUnderLockCallRule, ...]:
        """Short compatibility alias for forbidden-under-lock calls."""

        return self.forbidden_under_locks


@dataclass(frozen=True)
class ArchitectureFinding:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    snippet: str
    regex: str
    lock: str = ""
    outer_locks: tuple[str, ...] = ()


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

        assignments: list[ArchitectureAssignmentRule] = []
        raw_assignments = raw_rule.get("assignments", raw_rule.get("assignment_rules", []))
        if raw_assignments is None:
            raw_assignments = []
        if not isinstance(raw_assignments, list):
            raise ValueError(f"architecture rule {rule_id!r} has invalid assignment rules")  # noqa: TRY004
        for raw_assignment in raw_assignments:
            if not isinstance(raw_assignment, dict):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid assignment entry")  # noqa: TRY004
            targets = _load_assignment_string_values(
                raw_assignment.get("targets", []), rule_id=rule_id, field="targets"
            )
            target_suffixes = _load_assignment_string_values(
                raw_assignment.get("target_suffixes", []), rule_id=rule_id, field="target_suffixes"
            )
            raw_message = raw_assignment.get("message", "")
            if not isinstance(raw_message, str) or not raw_message.strip():
                raise ValueError(f"architecture rule {rule_id!r} has an invalid assignment entry")
            message = raw_message.strip()
            if not targets and not target_suffixes:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid assignment entry")
            assignments.append(
                ArchitectureAssignmentRule(
                    targets=targets,
                    target_suffixes=target_suffixes,
                    message=message,
                )
            )

        calls: list[ArchitectureCallRule] = []
        raw_calls = raw_rule.get("calls", raw_rule.get("call_rules", [])) or []
        for raw_call in raw_calls:
            receivers = tuple(str(item).strip() for item in (raw_call.get("receivers", []) or []) if str(item).strip())
            receiver_suffixes = tuple(
                str(item).strip() for item in (raw_call.get("receiver_suffixes", []) or []) if str(item).strip()
            )
            methods = tuple(str(item).strip() for item in (raw_call.get("methods", []) or []) if str(item).strip())
            allowed_files = tuple(
                str(item).strip() for item in (raw_call.get("allowed_files", []) or []) if str(item).strip()
            )
            required_locks = tuple(
                str(item).strip() for item in (raw_call.get("required_locks", []) or []) if str(item).strip()
            )
            skip_if_keywords: list[ArchitectureKeywordExemption] = []
            for raw_exemption in raw_call.get("skip_if_keywords", []) or []:
                name = str(raw_exemption.get("name", "")).strip()
                if not name or "equals" not in raw_exemption:
                    raise ValueError(f"architecture rule {rule_id!r} has an invalid keyword exemption")
                equals = raw_exemption["equals"]
                if equals is not None and not isinstance(equals, (bool, int, float, str)):
                    raise ValueError(f"architecture rule {rule_id!r} has a non-literal keyword exemption")
                skip_if_keywords.append(ArchitectureKeywordExemption(name=name, equals=equals))
            message = str(raw_call.get("message", "")).strip()
            lock_message = str(raw_call.get("lock_message", "")).strip()
            if (
                (not receivers and not receiver_suffixes)
                or not methods
                or not allowed_files
                or not message
                or (required_locks and not lock_message)
            ):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid call entry")
            calls.append(
                ArchitectureCallRule(
                    receivers=receivers,
                    receiver_suffixes=receiver_suffixes,
                    methods=methods,
                    allowed_files=allowed_files,
                    required_locks=required_locks,
                    skip_if_keywords=tuple(skip_if_keywords),
                    message=message,
                    lock_message=lock_message,
                )
            )

        forbidden_under_locks: list[ArchitectureForbiddenUnderLockCallRule] = []
        raw_forbidden = (
            raw_rule.get(
                "forbidden_under_locks",
                raw_rule.get(
                    "forbidden_calls_under_locks",
                    raw_rule.get("forbidden_calls_under_lock", raw_rule.get("forbidden_calls", [])),
                ),
            )
            or []
        )
        if not isinstance(raw_forbidden, list):
            raise ValueError(  # noqa: TRY004
                f"architecture rule {rule_id!r} has invalid forbidden-under-lock call rules"
            )
        for raw_forbidden_call in raw_forbidden:
            if not isinstance(raw_forbidden_call, dict):
                raise ValueError(  # noqa: TRY004
                    f"architecture rule {rule_id!r} has an invalid forbidden-under-lock call entry"
                )
            receivers = _load_string_values(raw_forbidden_call.get("receivers", []), rule_id=rule_id, field="receivers")
            receiver_suffixes = _load_string_values(
                raw_forbidden_call.get("receiver_suffixes", []), rule_id=rule_id, field="receiver_suffixes"
            )
            methods = _load_string_values(raw_forbidden_call.get("methods", []), rule_id=rule_id, field="methods")
            required_locks = _load_string_values(
                raw_forbidden_call.get("required_locks", raw_forbidden_call.get("locks", [])),
                rule_id=rule_id,
                field="required_locks",
            )
            match_any_receiver = raw_forbidden_call.get("match_any_receiver", False)
            message = str(raw_forbidden_call.get("message", "")).strip()
            if (
                (not receivers and not receiver_suffixes and match_any_receiver is not True)
                or not methods
                or not required_locks
                or not message
                or type(match_any_receiver) is not bool
            ):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid forbidden-under-lock call entry")
            forbidden_under_locks.append(
                ArchitectureForbiddenUnderLockCallRule(
                    receivers=receivers,
                    receiver_suffixes=receiver_suffixes,
                    methods=methods,
                    match_any_receiver=match_any_receiver,
                    required_locks=required_locks,
                    message=message,
                )
            )

        lock_orders = _load_lock_order_rules(raw_rule=raw_rule, rule_id=rule_id)
        if (
            not patterns
            and not imports
            and not attributes
            and not assignments
            and not calls
            and not forbidden_under_locks
            and not lock_orders
        ):
            raise ValueError(
                f"architecture rule {rule_id!r} has no patterns, import rules, attribute rules, call rules, "
                "assignment rules, forbidden-under-lock call rules, or lock-order rules"
            )

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
                assignments=tuple(assignments),
                calls=tuple(calls),
                forbidden_under_locks=tuple(forbidden_under_locks),
                lock_orders=tuple(lock_orders),
            )
        )

    return rules


def scan_architecture(root: Path, rules: Iterable[ArchitectureRule]) -> ArchitectureScanResult:
    findings: list[ArchitectureFinding] = []
    seen_findings: set[tuple[str, str, int, str, str]] = set()
    scanned_files: set[str] = set()
    scanned_python_signals: dict[str, tuple[tuple[_ScannedImport, ...], tuple[_ScannedAttribute, ...]]] = {}
    scanned_python_assignments: dict[str, tuple[_ScannedAssignment, ...]] = {}
    scanned_python_calls: dict[str, tuple[_ScannedCall, ...]] = {}
    scanned_python_lock_acquisitions: dict[str, tuple[_ScannedLockAcquisition, ...]] = {}
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

            assignments: tuple[_ScannedAssignment, ...] = ()
            if rule.assignments:
                cached_assignments = scanned_python_assignments.get(rel)
                if cached_assignments is None:
                    cached_assignments = _scan_python_assignments(text)
                    scanned_python_assignments[rel] = cached_assignments
                assignments = cached_assignments

            calls: tuple[_ScannedCall, ...] = ()
            if rule.calls or rule.forbidden_under_locks:
                cached_calls = scanned_python_calls.get(rel)
                if cached_calls is None:
                    cached_calls = _scan_python_calls(text)
                    scanned_python_calls[rel] = cached_calls
                calls = cached_calls

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

            for assignment_rule in rule.assignments:
                for scanned_assignment in assignments:
                    target_matches = scanned_assignment.target in assignment_rule.targets or any(
                        scanned_assignment.target.endswith(suffix) for suffix in assignment_rule.target_suffixes
                    )
                    if not target_matches:
                        continue

                    finding_token = f"assignment:{scanned_assignment.target}"
                    finding_key = (rule.rule_id, rel, scanned_assignment.line, assignment_rule.message, finding_token)
                    if finding_key in seen_findings:
                        continue
                    seen_findings.add(finding_key)
                    findings.append(
                        ArchitectureFinding(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            path=rel,
                            line=scanned_assignment.line,
                            message=assignment_rule.message,
                            snippet=_line_snippet(lines=lines, line=scanned_assignment.line),
                            regex=finding_token,
                        )
                    )

            if rule.lock_orders:
                acquisitions = scanned_python_lock_acquisitions.get(rel)
                if acquisitions is None:
                    acquisitions = _scan_python_lock_acquisitions(text)
                    scanned_python_lock_acquisitions[rel] = acquisitions
                for lock_order in rule.lock_orders:
                    levels = {
                        alias: index
                        for index, lock in enumerate(lock_order.locks)
                        for alias in (lock.name, *lock.aliases)
                    }
                    for acquisition in acquisitions:
                        inner_level = _lock_level(acquisition.lock, lock_order=lock_order, levels=levels)
                        if inner_level is None:
                            continue
                        violating_outer_locks = tuple(
                            outer_lock
                            for outer_lock in acquisition.outer_locks
                            if (outer_level := _lock_level(outer_lock, lock_order=lock_order, levels=levels))
                            is not None
                            and outer_level > inner_level
                        )
                        if not violating_outer_locks:
                            continue
                        inner_name = lock_order.locks[inner_level].name
                        message = lock_order.message
                        finding_token = f"lock-order:{acquisition.lock}"
                        finding_key = (rule.rule_id, rel, acquisition.line, message, finding_token)
                        if finding_key in seen_findings:
                            continue
                        seen_findings.add(finding_key)
                        findings.append(
                            ArchitectureFinding(
                                rule_id=rule.rule_id,
                                severity=rule.severity,
                                path=rel,
                                line=acquisition.line,
                                message=message,
                                snippet=_line_snippet(lines=lines, line=acquisition.line),
                                regex=finding_token,
                                lock=inner_name,
                                outer_locks=acquisition.outer_locks,
                            )
                        )

            for call_rule in rule.calls:
                for scanned_call in calls:
                    receiver_matches = scanned_call.receiver in call_rule.receivers or any(
                        scanned_call.receiver.endswith(suffix) for suffix in call_rule.receiver_suffixes
                    )
                    if not receiver_matches or scanned_call.method not in call_rule.methods:
                        continue

                    if any(
                        any(
                            name == exemption.name and _literal_keyword_matches(actual=value, expected=exemption.equals)
                            for name, value in scanned_call.literal_keywords
                        )
                        for exemption in call_rule.skip_if_keywords
                    ):
                        continue

                    if not _path_matches_any(rel, call_rule.allowed_files):
                        message = call_rule.message
                    elif call_rule.required_locks and not any(
                        lock in call_rule.required_locks for lock in scanned_call.lexical_locks
                    ):
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

            for forbidden_rule in rule.forbidden_under_locks:
                for scanned_call in calls:
                    receiver_matches = forbidden_rule.match_any_receiver or (
                        scanned_call.receiver in forbidden_rule.receivers
                        or any(scanned_call.receiver.endswith(suffix) for suffix in forbidden_rule.receiver_suffixes)
                    )
                    if not receiver_matches or scanned_call.method not in forbidden_rule.methods:
                        continue
                    matching_lock = next(
                        (lock for lock in scanned_call.lexical_locks if lock in forbidden_rule.required_locks),
                        None,
                    )
                    if matching_lock is None:
                        continue

                    finding_token = f"forbidden-under-lock:{scanned_call.receiver}.{scanned_call.method}"
                    finding_key = (rule.rule_id, rel, scanned_call.line, forbidden_rule.message, finding_token)
                    if finding_key in seen_findings:
                        continue
                    seen_findings.add(finding_key)
                    findings.append(
                        ArchitectureFinding(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            path=rel,
                            line=scanned_call.line,
                            message=forbidden_rule.message,
                            snippet=_line_snippet(lines=lines, line=scanned_call.line),
                            regex=finding_token,
                            lock=matching_lock,
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


def _literal_keyword_matches(*, actual: object, expected: object) -> bool:
    """Compare literal keyword values without treating ``False`` as ``0``."""

    return type(actual) is type(expected) and actual == expected


def _load_string_values(raw_values: object, *, rule_id: str, field: str) -> tuple[str, ...]:
    if raw_values is None:
        return ()
    if not isinstance(raw_values, list) or any(not isinstance(value, str) or not value.strip() for value in raw_values):
        raise ValueError(f"architecture rule {rule_id!r} has invalid forbidden-under-lock {field}")
    return tuple(value.strip() for value in raw_values)


def _load_assignment_string_values(raw_values: object, *, rule_id: str, field: str) -> tuple[str, ...]:
    if raw_values is None:
        return ()
    if not isinstance(raw_values, list) or any(not isinstance(value, str) or not value.strip() for value in raw_values):
        raise ValueError(f"architecture rule {rule_id!r} has invalid assignment {field}")
    return tuple(value.strip() for value in raw_values)


def _load_lock_order_rules(*, raw_rule: object, rule_id: str) -> list[ArchitectureLockOrderRule]:
    if not isinstance(raw_rule, dict):
        raise ValueError(f"architecture rule {rule_id!r} must be an object")  # noqa: TRY004
    raw_lock_orders = raw_rule.get(
        "lock_orders",
        raw_rule.get("lock_order", raw_rule.get("lock_order_rules", [])),
    )
    if raw_lock_orders is None:
        return []
    if isinstance(raw_lock_orders, dict):
        raw_lock_orders = [raw_lock_orders]
    if not isinstance(raw_lock_orders, list):
        raise ValueError(f"architecture rule {rule_id!r} has invalid lock-order rules")  # noqa: TRY004

    lock_orders: list[ArchitectureLockOrderRule] = []
    for raw_lock_order in raw_lock_orders:
        if not isinstance(raw_lock_order, dict):
            raise ValueError(f"architecture rule {rule_id!r} has an invalid lock-order entry")  # noqa: TRY004
        raw_locks = raw_lock_order.get("locks", raw_lock_order.get("levels", raw_lock_order.get("order")))
        raw_alias_map = raw_lock_order.get("aliases", {})
        message = str(raw_lock_order.get("message", "")).strip()
        if not isinstance(raw_locks, list) or len(raw_locks) < 2 or not message:
            raise ValueError(f"architecture rule {rule_id!r} has an invalid lock-order entry")
        if not isinstance(raw_alias_map, (dict, list)):
            raise ValueError(f"architecture rule {rule_id!r} has an invalid lock alias map")  # noqa: TRY004

        locks: list[ArchitectureLock] = []
        seen_names: set[str] = set()
        for raw_lock in raw_locks:
            if isinstance(raw_lock, str):
                name = raw_lock.strip()
                mapped_aliases = raw_alias_map.get(name, []) if isinstance(raw_alias_map, dict) else []
                if not isinstance(mapped_aliases, list):
                    raise ValueError(f"architecture rule {rule_id!r} has an invalid lock alias list")  # noqa: TRY004
                aliases = tuple(str(alias).strip() for alias in mapped_aliases)
            elif isinstance(raw_lock, dict):
                name = str(raw_lock.get("name", "")).strip()
                raw_aliases = raw_lock.get("aliases", [])
                if not isinstance(raw_aliases, list):
                    raise ValueError(f"architecture rule {rule_id!r} has an invalid lock alias list")  # noqa: TRY004
                aliases = tuple(str(alias).strip() for alias in raw_aliases)
            else:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid lock entry")  # noqa: TRY004
            if not name or any(not alias for alias in aliases):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid lock entry")
            names = (name, *aliases)
            if len(set(names)) != len(names) or seen_names.intersection(names):
                raise ValueError(f"architecture rule {rule_id!r} has duplicate lock names or aliases")
            seen_names.update(names)
            locks.append(ArchitectureLock(name=name, aliases=aliases))
        lock_orders.append(ArchitectureLockOrderRule(locks=tuple(locks), message=message))
    return lock_orders


def _lock_level(
    lock_name: str,
    *,
    lock_order: ArchitectureLockOrderRule,
    levels: dict[str, int],
) -> int | None:
    direct_level = levels.get(lock_name)
    if direct_level is not None:
        return direct_level
    terminal_name = lock_name.rsplit(".", 1)[-1]
    for level, lock in enumerate(lock_order.locks):
        if terminal_name == lock.name:
            return level
    return None
