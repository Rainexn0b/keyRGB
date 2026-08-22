from __future__ import annotations


def test_load_tray_dependencies_primary_import_succeeds() -> None:
    from keyrgb.tray.integrations.dependencies import load_tray_dependencies

    EffectsEngine, Config, PowerManager = load_tray_dependencies()

    assert EffectsEngine.__name__ == "EffectsEngine"
    assert Config.__name__ == "Config"
    assert PowerManager.__name__ == "PowerManager"
