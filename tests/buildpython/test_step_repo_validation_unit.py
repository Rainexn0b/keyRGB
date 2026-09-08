from __future__ import annotations

from pathlib import Path

from buildpython.steps import step_repo_validation

_INSTALLED_HELPER = step_repo_validation.POWER_HELPER_INSTALLED_PATH


def _write_power_helper_files(tmp_path: Path, *, installed_path: str = _INSTALLED_HELPER) -> None:
    (tmp_path / "system" / "bin").mkdir(parents=True, exist_ok=True)
    (tmp_path / "system" / "bin" / "keyrgb-power-helper").write_text(
        "#!/usr/bin/env python3\n",
        encoding="utf-8",
    )
    (tmp_path / "system" / "polkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / "system" / "polkit" / "90-keyrgb-power-helper.rules").write_text(
        f'program !== "{installed_path}"\n',
        encoding="utf-8",
    )
    (tmp_path / "system" / "polkit" / "org.keyrgb.power-helper.policy").write_text(
        "<policyconfig/>\n",
        encoding="utf-8",
    )
    consumers = {
        "keyrgb/core/backends/sysfs/privileged.py": f'os.environ.get("KEYRGB_POWER_HELPER", "{installed_path}")\n',
        "keyrgb/core/power/system/_apply.py": f'os.environ.get("KEYRGB_POWER_HELPER", "{installed_path}")\n',
        "keyrgb/core/power/system/_observe.py": f'os.environ.get("KEYRGB_POWER_HELPER", "{installed_path}")\n',
        "scripts/lib/privileged_helpers.sh": f'sudo install -D -m 0755 helper "{installed_path}"\n',
        "scripts/uninstall.sh": f'POWER_HELPER_DST="{installed_path}"\n',
    }
    for relative_path, text in consumers.items():
        candidate = tmp_path / relative_path
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(text, encoding="utf-8")


def _write_required_repo_files(
    tmp_path,
    *,
    install_text: str,
    user_install_text: str = "",
    user_integration_text: str = "",
    dependencies: str = 'dependencies = [\n    "pystray>=0.19.5",\n]',
) -> None:
    (tmp_path / "README.md").write_text("# KeyRGB\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("license\n", encoding="utf-8")
    (tmp_path / "install.sh").write_text(install_text, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "keyrgb"\n{dependencies}\n\n'
        '[project.urls]\nHomepage = "https://github.com/Rainexn0b/keyRGB"\n',
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "lib").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "install_user.sh").write_text(user_install_text, encoding="utf-8")
    (tmp_path / "scripts" / "lib" / "user_integration.sh").write_text(user_integration_text, encoding="utf-8")
    _write_power_helper_files(tmp_path)


def test_repo_validation_accepts_autostart_in_delegated_user_installer(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        user_install_text="# dispatcher target\n",
        user_integration_text='autostart_dir="$HOME/.config/autostart"\n',
    )
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 0
    assert "Warnings:" not in result.stdout
    assert "OK: repo looks consistent." in result.stdout


def test_repo_validation_warns_when_no_installer_path_mentions_autostart(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        user_install_text="# no desktop integration here\n",
        user_integration_text="# no autostart path here\n",
    )
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 0
    assert "Warnings:" in result.stdout
    assert "installer: autostart entry not detected" in result.stdout


def test_repo_validation_accepts_non_empty_project_dependencies(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        dependencies='dependencies = [\n    "pystray>=0.19.5",\n    "Pillow>=12.2.0",\n]',
    )
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 0
    assert "dependencies" not in result.stdout


def test_repo_validation_errors_on_missing_project_dependencies(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        dependencies="",
    )
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 1
    assert "[project].dependencies must declare at least one dependency" in result.stdout


def test_repo_validation_errors_on_empty_project_dependencies(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        dependencies="dependencies = []",
    )
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 1
    assert "[project].dependencies must declare at least one dependency" in result.stdout


def test_repo_validation_errors_on_missing_power_helper_files(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        user_integration_text='autostart_dir="$HOME/.config/autostart"\n',
    )
    (tmp_path / "system" / "bin" / "keyrgb-power-helper").unlink()
    (tmp_path / "system" / "polkit" / "org.keyrgb.power-helper.policy").unlink()
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 1
    assert "Missing required power-helper files:" in result.stdout
    assert "system/bin/keyrgb-power-helper" in result.stdout
    assert "system/polkit/org.keyrgb.power-helper.policy" in result.stdout


def test_repo_validation_errors_on_power_helper_path_drift(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        user_integration_text='autostart_dir="$HOME/.config/autostart"\n',
    )
    (tmp_path / "keyrgb" / "core" / "backends" / "sysfs" / "privileged.py").write_text(
        'os.environ.get("KEYRGB_POWER_HELPER", "/opt/keyrgb/helper")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 1
    assert "keyrgb/core/backends/sysfs/privileged.py" in result.stdout
    assert _INSTALLED_HELPER in result.stdout


def test_repo_validation_errors_on_missing_path_consumer(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        user_integration_text='autostart_dir="$HOME/.config/autostart"\n',
    )
    (tmp_path / "scripts" / "uninstall.sh").unlink()
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 1
    assert "scripts/uninstall.sh" in result.stdout
    assert _INSTALLED_HELPER in result.stdout


def test_repo_validation_accepts_consistent_power_helper_integration(monkeypatch, tmp_path) -> None:
    _write_required_repo_files(
        tmp_path,
        install_text="#!/usr/bin/env bash\nexec bash scripts/install_user.sh\n",
        user_integration_text='autostart_dir="$HOME/.config/autostart"\n',
    )
    monkeypatch.setattr(step_repo_validation, "repo_root", lambda: tmp_path)

    result = step_repo_validation.repo_validation_runner()

    assert result.exit_code == 0
    assert "OK: repo looks consistent." in result.stdout
