from __future__ import annotations

from types import MappingProxyType

import pytest

from keyrgb.core.config import Config
from keyrgb.core.config.defaults import DEFAULTS
from keyrgb.core.config.document import ConfigDocument
from keyrgb.core.config.domains import (
    ALL_KNOWN_KEYS,
    DOMAIN_KEYS,
    ConfigDomain,
    project_domain,
    project_extras,
)


def _make_config(tmp_path, monkeypatch) -> Config:
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    return Config()


def test_defaults_keys_are_fully_partitioned_into_domains() -> None:
    # Coverage: every DEFAULTS key must be owned by a domain.
    missing = sorted(str(key) for key in DEFAULTS if key not in ALL_KNOWN_KEYS)
    assert not missing, f"DEFAULTS keys missing from config domains: {missing}"

    # No overlaps: a key must not be claimed by more than one domain.
    overlaps: list[str] = []
    seen: dict[str, ConfigDomain] = {}
    for domain, keys in DOMAIN_KEYS.items():
        for key in keys:
            prior = seen.get(key)
            if prior is not None and prior is not domain:
                overlaps.append(f"{key} ({prior.value} vs {domain.value})")
            seen[key] = domain
    assert not overlaps, f"config domain key overlaps: {overlaps}"

    # Known/unknown key evidence via domain ownership.
    assert "effect" in DOMAIN_KEYS[ConfigDomain.LIGHTING]
    assert "power_management_enabled" in DOMAIN_KEYS[ConfigDomain.POWER]
    assert "time_scheduler_enabled" in DOMAIN_KEYS[ConfigDomain.SCHEDULER]
    assert "physical_layout" in DOMAIN_KEYS[ConfigDomain.LAYOUT]
    assert "secondary_device_state" in DOMAIN_KEYS[ConfigDomain.SECONDARY]
    assert "controller_sleep_respect" in DOMAIN_KEYS[ConfigDomain.IDLE_DISPLAY]
    assert "tray_device_context" in DOMAIN_KEYS[ConfigDomain.APP]
    assert "future_vendor_flag" not in ALL_KNOWN_KEYS


def test_projections_preserve_extras() -> None:
    values = {
        "effect": "wave",
        "power_management_enabled": True,
        "future_vendor_flag": 7,
        "secondary_device_state": {"lightbar": {"enabled": True}},
    }
    assert "effect" in DOMAIN_KEYS[ConfigDomain.LIGHTING]
    assert "future_vendor_flag" not in ALL_KNOWN_KEYS
    assert project_domain(values, ConfigDomain.LIGHTING) == {"effect": "wave"}
    assert project_domain(values, ConfigDomain.POWER) == {"power_management_enabled": True}
    assert project_domain(values, ConfigDomain.SECONDARY) == {"secondary_device_state": {"lightbar": {"enabled": True}}}
    assert project_extras(values) == {"future_vendor_flag": 7}


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

    from keyrgb.core.config import Config as ConfigCls

    cfg2 = ConfigCls()
    assert cfg2.effect == "wave"
    assert cfg2.extras_view()["vendor_preview"] == 1
    assert cfg2.domain_view(ConfigDomain.LIGHTING)["effect"] == "wave"
