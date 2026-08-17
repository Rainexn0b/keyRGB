from __future__ import annotations

from types import MappingProxyType

import pytest

from src.core.config import Config
from src.core.config.defaults import DEFAULTS
from src.core.config.document import ConfigDocument
from src.core.config.domains import (
    ALL_KNOWN_KEYS,
    DOMAIN_KEYS,
    ConfigDomain,
    assert_defaults_partitioned,
    domain_for_key,
    project_domain,
    project_extras,
)


def _make_config(tmp_path, monkeypatch) -> Config:
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    return Config()


def test_defaults_keys_are_fully_partitioned_into_domains() -> None:
    assert_defaults_partitioned(DEFAULTS)
    assert "effect" in DOMAIN_KEYS[ConfigDomain.LIGHTING]
    assert "power_management_enabled" in DOMAIN_KEYS[ConfigDomain.POWER]
    assert "time_scheduler_enabled" in DOMAIN_KEYS[ConfigDomain.SCHEDULER]
    assert "physical_layout" in DOMAIN_KEYS[ConfigDomain.LAYOUT]
    assert "secondary_device_state" in DOMAIN_KEYS[ConfigDomain.SECONDARY]
    assert "controller_sleep_respect" in DOMAIN_KEYS[ConfigDomain.IDLE_DISPLAY]
    assert "tray_device_context" in DOMAIN_KEYS[ConfigDomain.APP]


def test_domain_for_key_and_projections_preserve_extras() -> None:
    values = {
        "effect": "wave",
        "power_management_enabled": True,
        "future_vendor_flag": 7,
        "secondary_device_state": {"lightbar": {"enabled": True}},
    }
    assert domain_for_key("effect") is ConfigDomain.LIGHTING
    assert domain_for_key("future_vendor_flag") is None
    assert project_domain(values, ConfigDomain.LIGHTING) == {"effect": "wave"}
    assert project_domain(values, ConfigDomain.POWER) == {"power_management_enabled": True}
    assert project_domain(values, ConfigDomain.SECONDARY) == {"secondary_device_state": {"lightbar": {"enabled": True}}}
    assert project_extras(values) == {"future_vendor_flag": 7}
    assert "future_vendor_flag" not in ALL_KNOWN_KEYS


def test_config_document_section_views_are_readonly(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["future_extension"] = {"ok": True}
    cfg.effect = "solid"

    document = cfg.document()
    assert isinstance(document, ConfigDocument)
    lighting = cfg.domain_view(ConfigDomain.LIGHTING)
    assert isinstance(lighting, MappingProxyType)
    assert lighting["effect"] == "solid"
    with pytest.raises(TypeError):
        lighting["effect"] = "wave"  # type: ignore[index]

    extras = cfg.extras_view()
    assert extras["future_extension"] == {"ok": True}
    with pytest.raises(TypeError):
        extras["future_extension"] = None  # type: ignore[index]


def test_config_settings_identity_and_domain_props_remain_stable(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    settings_id = id(cfg._settings)
    document_id = id(cfg.document().values)
    assert settings_id == document_id

    cfg.power_management_enabled = False
    cfg.time_scheduler_enabled = True
    cfg.physical_layout = "iso"
    cfg.software_effect_target = "keyboard"
    cfg.controller_sleep_respect = True

    assert cfg._settings is cfg.document().values
    assert cfg.domain_view("power")["power_management_enabled"] is False
    assert cfg.domain_view(ConfigDomain.SCHEDULER)["time_scheduler_enabled"] is True
    assert cfg.domain_view(ConfigDomain.LAYOUT)["physical_layout"] == "iso"
    assert cfg.domain_view(ConfigDomain.IDLE_DISPLAY)["controller_sleep_respect"] is True
    assert cfg.domain_view(ConfigDomain.LIGHTING)["software_effect_target"] == "keyboard"


def test_reload_replaces_document_values_and_keeps_facade(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg.effect = "wave"
    cfg._settings["vendor_preview"] = 1
    cfg._save()

    from src.core.config import Config as ConfigCls

    cfg2 = ConfigCls()
    assert cfg2.effect == "wave"
    assert cfg2.extras_view()["vendor_preview"] == 1
    assert cfg2.domain_view(ConfigDomain.LIGHTING)["effect"] == "wave"
