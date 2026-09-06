from __future__ import annotations

from collections.abc import Iterable
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
from ._architecture_validation_models import (
    ArchitectureFinding,
    ArchitectureLockOrderRule,
    ArchitectureRule,
    ArchitectureScanResult,
)


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

                    if call_rule.forbid_all or not _path_matches_any(rel, call_rule.allowed_files):
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


def _path_matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    posix_path = Path(path).as_posix()
    return any(posix_path == pattern or Path(posix_path).match(pattern) for pattern in patterns)


def _literal_keyword_matches(*, actual: object, expected: object) -> bool:
    """Compare literal keyword values without treating ``False`` as ``0``."""

    return type(actual) is type(expected) and actual == expected


def _lock_level(
    lock_name: str,
    *,
    lock_order: ArchitectureLockOrderRule,
    levels: dict[str, int],
) -> int | None:
    return levels.get(lock_name)
