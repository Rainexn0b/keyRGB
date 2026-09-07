from __future__ import annotations

from pathlib import Path

from buildpython.steps.architecture_validation import ArchitectureScanResult, load_architecture_rules, scan_architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
_RULES_PATH = REPO_ROOT / "buildpython/config/architecture_rules.json"


def scan_configured_rule(
    tmp_path,
    source: str,
    *,
    rule_id: str,
    relative_path: str,
) -> ArchitectureScanResult:
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    rules = [rule for rule in load_architecture_rules(_RULES_PATH) if rule.rule_id == rule_id]
    return scan_architecture(root, rules)


def scan_configured_secondary_device_rule(tmp_path, source: str, *, relative_path: str) -> ArchitectureScanResult:
    return scan_configured_rule(
        tmp_path,
        source,
        rule_id="secondary-device-no-primary-keyboard-mutations",
        relative_path=relative_path,
    )


def production_architecture_rules():
    return load_architecture_rules(_RULES_PATH)
