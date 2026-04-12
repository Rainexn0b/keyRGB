from __future__ import annotations

import buildpython.steps.step_repo_validation as step_repo_validation


def _write_required_repo_files(tmp_path, *, install_text: str, user_install_text: str = "", user_integration_text: str = "") -> None:
    (tmp_path / "README.md").write_text("# KeyRGB\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("license\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "install.sh").write_text(install_text, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = \"keyrgb\"\n\n[project.urls]\nHomepage = \"https://github.com/Rainexn0b/keyRGB\"\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "lib").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "install_user.sh").write_text(user_install_text, encoding="utf-8")
    (tmp_path / "scripts" / "lib" / "user_integration.sh").write_text(user_integration_text, encoding="utf-8")


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