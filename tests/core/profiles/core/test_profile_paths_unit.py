from __future__ import annotations

import json

import pytest

from src.core.config import Config
from src.core.profile import paths


def test_safe_profile_name_aliases_light_and_sanitizes() -> None:
    assert paths.safe_profile_name(" light ") == "default"
    assert paths.safe_profile_name(" Custom Profile! ") == "Custom_Profile"
    assert paths.safe_profile_name("!!!") == "default"


@pytest.mark.parametrize("name", [".", ".."])
def test_safe_profile_name_maps_reserved_dot_components_to_default(name: str) -> None:
    assert paths.safe_profile_name(name) == paths.DEFAULT_PROFILE_NAME


@pytest.mark.parametrize("name", [".gaming", "gaming.v2", "gaming-profile"])
def test_safe_profile_name_preserves_supported_dots_and_hyphens(name: str) -> None:
    assert paths.safe_profile_name(name) == name


@pytest.mark.parametrize("name", ["/tmp/gaming", "../gaming", r"..\gaming", "a/b"])
def test_non_dot_path_like_names_resolve_below_profiles_root(tmp_path, monkeypatch, name: str) -> None:
    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    resolved = paths.paths_for(name).root.resolve()
    profiles_root = (cfg_dir / "profiles").resolve()

    assert resolved != profiles_root
    assert resolved.is_relative_to(profiles_root)


@pytest.mark.parametrize("name", [".", ".."])
def test_reserved_dot_names_resolve_to_builtin_profile(tmp_path, monkeypatch, name: str) -> None:
    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    resolved = paths.paths_for(name).root

    assert resolved == cfg_dir / "profiles" / paths.DEFAULT_PROFILE_NAME


def test_delete_profile_dotdot_preserves_config_tree(tmp_path, monkeypatch) -> None:
    cfg_dir = tmp_path / "config"
    profiles_dir = cfg_dir / "profiles"
    profiles_dir.mkdir(parents=True)
    sentinel = cfg_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    assert paths.delete_profile("..") is False
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert profiles_dir.is_dir()


@pytest.mark.parametrize(
    ("setter_name", "marker_name"),
    [
        ("set_active_profile", "active_profile.json"),
        ("set_default_profile", "default_profile.json"),
    ],
)
def test_profile_markers_persist_only_confined_dot_name(
    tmp_path,
    monkeypatch,
    setter_name: str,
    marker_name: str,
) -> None:
    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    result = getattr(paths, setter_name)("..")

    assert result == paths.DEFAULT_PROFILE_NAME
    assert json.loads((cfg_dir / marker_name).read_text(encoding="utf-8")) == {"name": paths.DEFAULT_PROFILE_NAME}
    assert (cfg_dir / "profiles" / paths.DEFAULT_PROFILE_NAME).is_dir()


def test_paths_for_rejects_profile_directory_symlink_escape(tmp_path, monkeypatch) -> None:
    cfg_dir = tmp_path / "config"
    profiles_dir = cfg_dir / "profiles"
    outside_dir = tmp_path / "outside"
    profiles_dir.mkdir(parents=True)
    outside_dir.mkdir()
    (profiles_dir / "escaped").symlink_to(outside_dir, target_is_directory=True)
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    with pytest.raises(paths.ProfilePathError, match="outside the profiles root"):
        paths.paths_for("escaped")


def test_delete_profile_rejects_symlink_escape_and_preserves_outside_tree(tmp_path, monkeypatch) -> None:
    cfg_dir = tmp_path / "config"
    profiles_dir = cfg_dir / "profiles"
    outside_dir = tmp_path / "outside"
    profiles_dir.mkdir(parents=True)
    outside_dir.mkdir()
    sentinel = outside_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    (profiles_dir / "escaped").symlink_to(outside_dir, target_is_directory=True)
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    assert paths.delete_profile("escaped") is False
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_list_profiles_excludes_directory_symlinks(tmp_path, monkeypatch) -> None:
    cfg_dir = tmp_path / "config"
    profiles_dir = cfg_dir / "profiles"
    outside_dir = tmp_path / "outside"
    (profiles_dir / "gaming").mkdir(parents=True)
    outside_dir.mkdir()
    (profiles_dir / "escaped").symlink_to(outside_dir, target_is_directory=True)
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    assert paths.list_profiles() == [paths.DEFAULT_PROFILE_NAME, "gaming"]


@pytest.mark.parametrize(
    ("setter_name", "marker_name"),
    [
        ("set_active_profile", "active_profile.json"),
        ("set_default_profile", "default_profile.json"),
    ],
)
def test_profile_marker_is_preserved_when_profile_root_escapes(
    tmp_path,
    monkeypatch,
    setter_name: str,
    marker_name: str,
) -> None:
    cfg_dir = tmp_path / "config"
    profiles_dir = cfg_dir / "profiles"
    outside_dir = tmp_path / "outside"
    profiles_dir.mkdir(parents=True)
    outside_dir.mkdir()
    marker = cfg_dir / marker_name
    marker.write_text(json.dumps({"name": "stable"}), encoding="utf-8")
    (profiles_dir / "escaped").symlink_to(outside_dir, target_is_directory=True)
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    with pytest.raises(paths.ProfilePathError, match="outside the profiles root"):
        getattr(paths, setter_name)("escaped")

    assert json.loads(marker.read_text(encoding="utf-8")) == {"name": "stable"}


@pytest.mark.parametrize(
    ("setter_name", "marker_name"),
    [
        ("set_active_profile", "active_profile.json"),
        ("set_default_profile", "default_profile.json"),
    ],
)
def test_profile_marker_uses_atomic_writer_and_preserves_previous_value_on_failure(
    tmp_path,
    monkeypatch,
    setter_name: str,
    marker_name: str,
) -> None:
    cfg_dir = tmp_path / "config"
    marker = cfg_dir / marker_name
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({"name": "stable"}), encoding="utf-8")
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    def fail_write(_path, _payload, **_kwargs) -> None:
        raise OSError("atomic marker write failed")

    monkeypatch.setattr(paths, "write_json_atomic", fail_write, raising=False)

    with pytest.raises(OSError, match="atomic marker write failed"):
        getattr(paths, setter_name)("new-profile")

    assert json.loads(marker.read_text(encoding="utf-8")) == {"name": "stable"}


def test_paths_for_renames_previous_light_dir_and_y15_pro_files(
    tmp_path,
    monkeypatch,
) -> None:
    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    old_root = cfg_dir / "profiles" / "light"
    old_root.mkdir(parents=True)

    old_files = {
        "keymap_y15_pro.json": '{"esc": "0,0"}',
        "layout_tweaks_y15_pro.json": '{"inset": 0.1}',
        "layout_tweaks_y15_pro_perkey.json": '{"esc": {"x": 1}}',
        "backdrop_y15_pro.png": "png-bytes",
        "backdrop_settings_y15_pro.json": '{"mode": "seed"}',
    }
    for filename, content in old_files.items():
        (old_root / filename).write_text(content, encoding="utf-8")

    resolved = paths.paths_for("light")

    new_root = cfg_dir / "profiles" / "default"
    assert resolved.root == new_root
    assert not old_root.exists()

    assert resolved.keymap == new_root / "keymap.json"
    assert resolved.layout_global == new_root / "layout_tweaks.json"
    assert resolved.layout_per_key == new_root / "layout_tweaks_per_key.json"
    assert resolved.backdrop_image == new_root / "backdrop.png"
    assert resolved.backdrop_settings == new_root / "backdrop_settings.json"

    assert resolved.keymap.read_text(encoding="utf-8") == old_files["keymap_y15_pro.json"]
    assert resolved.layout_global.read_text(encoding="utf-8") == old_files["layout_tweaks_y15_pro.json"]
    assert resolved.layout_per_key.read_text(encoding="utf-8") == old_files["layout_tweaks_y15_pro_perkey.json"]
    assert resolved.backdrop_image.read_text(encoding="utf-8") == old_files["backdrop_y15_pro.png"]
    assert resolved.backdrop_settings.read_text(encoding="utf-8") == old_files["backdrop_settings_y15_pro.json"]

    assert not (new_root / "keymap_y15_pro.json").exists()
    assert not (new_root / "layout_tweaks_y15_pro.json").exists()
    assert not (new_root / "layout_tweaks_y15_pro_perkey.json").exists()
    assert not (new_root / "backdrop_y15_pro.png").exists()
    assert not (new_root / "backdrop_settings_y15_pro.json").exists()
