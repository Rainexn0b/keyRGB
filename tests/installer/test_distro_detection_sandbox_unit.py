from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMON_CORE = _REPO_ROOT / "scripts" / "lib" / "common_core.sh"
_README = _REPO_ROOT / "README.md"

_FEDORA_OS_RELEASE = textwrap.dedent(
    """\
    NAME="Fedora Linux"
    VERSION="42 (Workstation Edition)"
    ID=fedora
    VERSION_ID=42
    PRETTY_NAME="Fedora Linux 42 (Workstation Edition)"
    """
)

_ARCH_OS_RELEASE = textwrap.dedent(
    """\
    NAME="Arch Linux"
    PRETTY_NAME="Arch Linux"
    ID=arch
    BUILD_ID=rolling
    """
)

# Binaries that must never execute during a non-privileged planning smoke.
# Hyphenated names (apt-get, usbhid-dump) cannot be shell functions, so every
# entry is also shadowed on PATH; valid identifiers get a function tripwire too.
_TRIPWIRE_BINARIES = (
    "sudo",
    "dnf",
    "apt-get",
    "pacman",
    "zypper",
    "apk",
    "udevadm",
    "systemctl",
    "pkexec",
    "lsusb",
    "usbhid-dump",
    "modprobe",
)


def _write_shadow_bin(shadow: Path) -> None:
    shadow.mkdir(parents=True, exist_ok=True)
    for name in _TRIPWIRE_BINARIES:
        candidate = shadow / name
        candidate.write_text(
            "#!/bin/sh\n"
            'printf \'TRIPWIRE:%s %s\\n\' "$(basename "$0")" "$*" >>"$KEYRGB_SMOKE_SENTINEL"\n'
            'printf \'tripwire blocked: %s %s\\n\' "$(basename "$0")" "$*" >&2\n'
            "exit 99\n",
            encoding="utf-8",
        )
        candidate.chmod(0o755)


def _run_distro_smoke(tmp_path: Path, *, os_release_text: str, present_cmd: str) -> tuple[int, str, dict[str, str]]:
    fixture = tmp_path / "os-release"
    fixture.write_text(os_release_text, encoding="utf-8")
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    (home / ".local" / "share").mkdir(parents=True)
    (home / ".cache").mkdir(parents=True)
    sentinel = tmp_path / "tripwire-sentinel"
    shadow = tmp_path / "shadow-bin"
    _write_shadow_bin(shadow)

    script = textwrap.dedent(
        f"""\
        set -euo pipefail
        source "{_COMMON_CORE}"
        _keyrgb_os_release_path() {{ printf '%s' "{fixture}"; }}
        have_cmd() {{ [ "${{1:-}}" = "{present_cmd}" ]; }}
        _trip() {{
          printf 'TRIPWIRE:%s\\n' "$*" >>"$KEYRGB_SMOKE_SENTINEL"
          printf 'tripwire blocked: %s\\n' "$*" >&2
          exit 99
        }}
        sudo() {{ _trip "sudo $*"; }}
        dnf() {{ _trip "dnf $*"; }}
        pacman() {{ _trip "pacman $*"; }}
        zypper() {{ _trip "zypper $*"; }}
        apk() {{ _trip "apk $*"; }}
        udevadm() {{ _trip "udevadm $*"; }}
        systemctl() {{ _trip "systemctl $*"; }}
        pkexec() {{ _trip "pkexec $*"; }}
        lsusb() {{ _trip "lsusb $*"; }}
        modprobe() {{ _trip "modprobe $*"; }}
        tee() {{
          for __arg in "$@"; do
            case "$__arg" in
              /etc/*|/usr/*|/dev/*|/run/*) _trip "tee $__arg" ;;
            esac
          done
          command tee "$@"
        }}
        load_os_release
        _profile="$(distro_support_profile)"
        _label="$(distro_support_profile_label "$_profile")"
        _status="$(distro_support_profile_status "$_profile")"
        _note="$(distro_support_profile_note "$_profile")"
        detect_pkg_manager
        printf 'profile=%s\\n' "$_profile"
        printf 'label=%s\\n' "$_label"
        printf 'status=%s\\n' "$_status"
        printf 'note=%s\\n' "$_note"
        printf 'pkg_mgr=%s\\n' "$PKG_MGR"
        printf 'pretty=%s\\n' "$(os_pretty_name)"
        """
    )
    env = {**os.environ}
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_RUNTIME_DIR": str(home),
            "PATH": f"{shadow}{os.pathsep}{os.environ.get('PATH', '')}",
            "KEYRGB_SMOKE_SENTINEL": str(sentinel),
            "KEYRGB_HW_TESTS": "0",
            "KEYRGB_ALLOW_HARDWARE": "0",
            "KEYRGB_DISABLE_USB_SCAN": "1",
            "KEYRGB_TEST_HARDWARE_TRIPWIRE": "1",
        }
    )
    env.pop("KEYRGB_DISTRO_PROFILE", None)
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
        env=env,
    )
    values: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in {"profile", "label", "status", "note", "pkg_mgr", "pretty"}:
            values[key] = value
    assert not sentinel.exists(), f"tripwire fired during planning smoke:\n{completed.stdout}"
    return completed.returncode, completed.stdout, values


def test_fedora_smoke_resolves_tested_dnf_plan(tmp_path: Path) -> None:
    rc, output, values = _run_distro_smoke(tmp_path, os_release_text=_FEDORA_OS_RELEASE, present_cmd="dnf")
    assert rc == 0, output
    assert values["profile"] == "fedora", output
    assert values["label"] == "Fedora / Red Hat family", output
    assert values["status"] == "tested", output
    assert "dnf" in values["note"], output
    assert values["pkg_mgr"] == "dnf", output
    assert "Fedora" in values["pretty"], output


def test_arch_smoke_resolves_tested_pacman_plan(tmp_path: Path) -> None:
    rc, output, values = _run_distro_smoke(tmp_path, os_release_text=_ARCH_OS_RELEASE, present_cmd="pacman")
    assert rc == 0, output
    assert values["profile"] == "arch", output
    assert values["label"] == "Arch / CachyOS / EndeavourOS / Manjaro", output
    assert values["status"] == "tested", output
    assert "AUR" in values["note"], output
    assert values["pkg_mgr"] == "pacman", output
    assert "Arch" in values["pretty"], output


def test_production_os_release_path_defaults_to_etc() -> None:
    text = _COMMON_CORE.read_text(encoding="utf-8")
    assert "KEYRGB_OS_RELEASE" not in text, "os-release seam must not use a public environment variable"
    assert "OS_RELEASE_PATH" not in text.replace("os_release_path", ""), "no public path override expected"
    completed = subprocess.run(
        ["bash", "-c", f'set -euo pipefail\nsource "{_COMMON_CORE}"\n_keyrgb_os_release_path'],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
        env={**os.environ},
    )
    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.strip() == "/etc/os-release", completed.stdout


def test_readme_distro_status_stays_evidence_based() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "Fedora/Nobara and Arch/CachyOS are the main tested development targets" in text
    assert "| Fedora / Red Hat family | Tested |" in text
    assert "| Arch / CachyOS / EndeavourOS / Manjaro | Tested |" in text
    assert "| Debian / Ubuntu / Linux Mint | Experimental |" in text
    assert "| openSUSE / other Linux | Best-effort |" in text
    for line in text.splitlines():
        lowered = line.lower()
        if "ubuntu" in lowered and "tested" in lowered and line.strip().startswith("|"):
            raise AssertionError(f"Ubuntu must not be promoted to tested: {line}")
        if "opensuse" in lowered and "tested" in lowered and line.strip().startswith("|"):
            raise AssertionError(f"openSUSE must not be promoted to tested: {line}")
