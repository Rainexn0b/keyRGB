"""Tests confirming that Diagnostics snapshot instances are appropriately immutable."""

from __future__ import annotations

import pytest

from src.core.diagnostics.model import Diagnostics, DiagnosticsConfigSnapshot


def test_diagnostics_dict_fields_are_readonly_through_snapshot() -> None:
    """Confirm that dict fields cannot be mutated through the snapshot."""
    diag = Diagnostics(
        dmi={"sys_vendor": "Tongfang"},
        leds=[],
        sysfs_leds=[],
        usb_ids=[],
        env={"HOME": "/home/user"},
        virt={},
        system={"platform": "linux"},
        hints={"test": "value"},
        app={"version": "1.0"},
        power_supply={},
        backends={"selected": "ite8291r3"},
        usb_devices=[],
        config={},
        process={"pid": 123},
    )

    # All dict fields should be wrapped in MappingProxyType, preventing mutation through snapshot.
    with pytest.raises(TypeError):
        diag.dmi["sys_vendor"] = "NewValue"  # type: ignore[index]

    with pytest.raises(TypeError):
        diag.env["HOME"] = "/tmp"  # type: ignore[index]

    with pytest.raises(TypeError):
        diag.system["platform"] = "windows"  # type: ignore[index]

    with pytest.raises(TypeError):
        diag.hints["test"] = "new"  # type: ignore[index]

    with pytest.raises(TypeError):
        diag.backends["selected"] = "sysfs-leds"  # type: ignore[index]

    with pytest.raises(TypeError):
        diag.process["pid"] = 456  # type: ignore[index]


def test_diagnostics_list_fields_are_readonly_through_snapshot() -> None:
    """Confirm that list fields are tuples and cannot be mutated."""
    diag = Diagnostics(
        dmi={},
        leds=[{"name": "led1"}, {"name": "led2"}],
        sysfs_leds=[{"name": "sled1"}],
        usb_ids=["048d:ce00"],
        env={},
        virt={},
        system={},
        hints={},
        app={},
        power_supply={},
        backends={},
        usb_devices=[{"idVendor": "0x048d"}],
        config=DiagnosticsConfigSnapshot(),
        process={},
    )

    # All list fields should be tuples, preventing mutation.
    assert isinstance(diag.leds, tuple)
    assert isinstance(diag.sysfs_leds, tuple)
    assert isinstance(diag.usb_ids, tuple)
    assert isinstance(diag.usb_devices, tuple)

    with pytest.raises(AttributeError):
        diag.leds.append({"name": "led3"})  # type: ignore[attr-defined]

    with pytest.raises(AttributeError):
        diag.usb_ids.append("048d:8910")  # type: ignore[attr-defined]

    with pytest.raises(TypeError):
        diag.leds[0] = {"name": "modified"}  # type: ignore[index]


def test_diagnostics_to_dict_preserves_shape_with_immutable_fields() -> None:
    """Confirm that to_dict() serializes correctly even with immutable fields."""
    original_dmi = {"sys_vendor": "Tongfang", "product_name": "GM5"}
    original_leds = [{"name": "led1", "path": "/sys/leds/led1"}]
    original_usb_ids = ["048d:ce00", "048d:8910"]

    diag = Diagnostics(
        dmi=original_dmi,
        leds=original_leds,
        sysfs_leds=original_leds,
        usb_ids=original_usb_ids,
        env={},
        virt={},
        system={},
        hints={},
        app={},
        power_supply={},
        backends={},
        usb_devices=[],
        config=DiagnosticsConfigSnapshot(
            present=True,
            mtime=123,
            settings={"brightness": "50"},
        ),
        process={},
    )

    output = diag.to_dict()

    # Serialized output should match the original data structure (as dicts and lists).
    assert output["dmi"] == original_dmi
    assert output["leds"] == original_leds
    assert output["sysfs_leds"] == original_leds
    assert output["usb_ids"] == original_usb_ids
    assert isinstance(output["dmi"], dict)
    assert isinstance(output["leds"], list)
    assert isinstance(output["usb_ids"], list)


def test_diagnostics_mapping_config_is_readonly_but_keeps_caller_mapping_values() -> None:
    """Confirm that plain mapping config is readonly through snapshot but reflects caller mutations."""
    config_mapping = {"backend": "auto", "effect": "wave"}

    diag = Diagnostics(
        dmi={},
        leds=[],
        sysfs_leds=[],
        usb_ids=[],
        env={},
        virt={},
        system={},
        hints={},
        app={},
        power_supply={},
        backends={},
        usb_devices=[],
        config=config_mapping,
        process={},
    )

    # Cannot mutate through the snapshot (wrapped in MappingProxyType).
    with pytest.raises(TypeError):
        diag.config["backend"] = "ite8291r3"  # type: ignore[index]

    # But if caller still has the original reference and mutates it, snapshot reflects the change.
    config_mapping["backend"] = "ite8291r3"
    assert diag.to_dict()["config"] == {"backend": "ite8291r3", "effect": "wave"}


def test_diagnostics_config_snapshot_is_immutable() -> None:
    """Confirm that DiagnosticsConfigSnapshot config field is properly immutable."""
    diag = Diagnostics(
        dmi={},
        leds=[],
        sysfs_leds=[],
        usb_ids=[],
        env={},
        virt={},
        system={},
        hints={},
        app={},
        power_supply={},
        backends={},
        usb_devices=[],
        config=DiagnosticsConfigSnapshot(
            present=True,
            mtime=123,
            settings={"brightness": "50", "effect": "wave"},
        ),
        process={},
    )

    # The snapshot itself is immutable (frozen=True).
    with pytest.raises(AttributeError):
        diag.config.present = False  # type: ignore[misc]

    # Its settings view is also readonly.
    with pytest.raises(TypeError):
        diag.config.settings["brightness"] = "100"  # type: ignore[index]
