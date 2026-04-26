#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
INSTALL_SH = ROOT / "install.sh"
UNINSTALL_SH = ROOT / "uninstall.sh"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _replace_once(text: str, pattern: str, replacement: str, *, file_label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Could not update expected pattern in {file_label}")
    return updated


def _update_pyproject(version: str) -> None:
    original = _read_text(PYPROJECT)
    updated = _replace_once(
        original,
        r'^version = "\d+\.\d+\.\d+"$',
        f'version = "{version}"',
        file_label="pyproject.toml",
    )
    if updated != original:
        _write_text(PYPROJECT, updated)


def _update_dispatcher_refs(version: str) -> None:
    tag = f"v{version}"

    install_original = _read_text(INSTALL_SH)
    install_updated = install_original
    install_updated = _replace_once(
        install_updated,
        r'^KEYRGB_BOOTSTRAP_REF="\$\{KEYRGB_BOOTSTRAP_REF:-v\d+\.\d+\.\d+\}"$',
        f'KEYRGB_BOOTSTRAP_REF="${{KEYRGB_BOOTSTRAP_REF:-{tag}}}"',
        file_label="install.sh",
    )
    install_updated = _replace_once(
        install_updated,
        r'(--ref <git-ref>\s+Git ref for downloading scripts/ from GitHub raw \(default: )v\d+\.\d+\.\d+(\))',
        rf'\g<1>{tag}\2',
        file_label="install.sh",
    )
    install_updated = _replace_once(
        install_updated,
        r'/(v\d+\.\d+\.\d+/install\.sh \| bash" >&2)$',
        f'/{tag}/install.sh | bash" >&2',
        file_label="install.sh",
    )
    if install_updated != install_original:
        _write_text(INSTALL_SH, install_updated)

    uninstall_original = _read_text(UNINSTALL_SH)
    uninstall_updated = uninstall_original
    uninstall_updated = _replace_once(
        uninstall_updated,
        r'^KEYRGB_BOOTSTRAP_REF="\$\{KEYRGB_BOOTSTRAP_REF:-v\d+\.\d+\.\d+\}"$',
        f'KEYRGB_BOOTSTRAP_REF="${{KEYRGB_BOOTSTRAP_REF:-{tag}}}"',
        file_label="uninstall.sh",
    )
    uninstall_updated = _replace_once(
        uninstall_updated,
        r'(--ref <git-ref>\s+Git ref for downloading scripts/ from GitHub raw \(default: )v\d+\.\d+\.\d+(\))',
        rf'\g<1>{tag}\2',
        file_label="uninstall.sh",
    )
    if uninstall_updated != uninstall_original:
        _write_text(UNINSTALL_SH, uninstall_updated)


def _update_changelog(version: str, date_str: str) -> None:
    original = _read_text(CHANGELOG)

    if re.search(rf"^## {re.escape(version)} \(\d{{4}}-\d{{2}}-\d{{2}}\)$", original, flags=re.MULTILINE):
        raise SystemExit(f"CHANGELOG.md already contains a section for {version}")

    marker = "## Unreleased"
    idx = original.find(marker)
    if idx < 0:
        raise SystemExit("Could not find '## Unreleased' in CHANGELOG.md")

    insert_at = idx + len(marker)
    section = f"\n\n## {version} ({date_str})\n\n- "
    updated = original[:insert_at] + section + original[insert_at:]
    _write_text(CHANGELOG, updated)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bump KeyRGB version metadata and scaffold changelog release entry"
    )
    parser.add_argument("version", help="Version in X.Y.Z format")
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="Release date for changelog heading (default: today, YYYY-MM-DD)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = args.version.strip()
    date_str = args.date.strip()

    if not VERSION_RE.match(version):
        raise SystemExit("Version must be in X.Y.Z format")

    try:
        dt.date.fromisoformat(date_str)
    except ValueError as exc:
        raise SystemExit("--date must use YYYY-MM-DD") from exc

    _update_pyproject(version)
    _update_dispatcher_refs(version)
    _update_changelog(version, date_str)

    print(f"Updated release metadata for {version}")
    print("Touched files:")
    print("- pyproject.toml")
    print("- CHANGELOG.md")
    print("- install.sh")
    print("- uninstall.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
