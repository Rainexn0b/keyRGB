from __future__ import annotations

from src.core.config import Config
from src.core.profile import paths


def test_safe_profile_name_aliases_default_and_sanitizes() -> None:
    assert paths.safe_profile_name(" default ") == "light"
    assert paths.safe_profile_name(" Custom Profile! ") == "Custom_Profile"
    assert paths.safe_profile_name("!!!") == "light"


def test_paths_for_renames_previous_default_dir_and_y15_pro_files(
    tmp_path,
    monkeypatch,
) -> None:
    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(Config, "CONFIG_DIR", cfg_dir, raising=False)

    old_root = cfg_dir / "profiles" / "default"
    old_root.mkdir(parents=True)

    old_files = {
        "keymap_y15_pro.json": "{\"esc\": \"0,0\"}",
        "layout_tweaks_y15_pro.json": "{\"inset\": 0.1}",
        "layout_tweaks_y15_pro_perkey.json": "{\"esc\": {\"x\": 1}}",
        "backdrop_y15_pro.png": "png-bytes",
        "backdrop_settings_y15_pro.json": "{\"mode\": \"seed\"}",
    }
    for filename, content in old_files.items():
        (old_root / filename).write_text(content, encoding="utf-8")

    resolved = paths.paths_for("default")

    new_root = cfg_dir / "profiles" / "light"
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
