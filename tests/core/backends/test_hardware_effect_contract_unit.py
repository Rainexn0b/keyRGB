from __future__ import annotations

import pytest

from keyrgb.core.backends.effect_contract import (
    UnsupportedHardwareEffectArgument,
    hardware_effect_builder,
)


def test_hardware_effect_builder_exposes_immutable_accepted_fields() -> None:
    builder = hardware_effect_builder(
        lambda **kwargs: dict(kwargs),
        accepted_kwargs=("speed", "brightness"),
    )

    assert builder.accepted_kwargs == frozenset({"speed", "brightness"})
    assert builder(speed=4) == {"speed": 4}


def test_hardware_effect_builder_rejects_unknown_field_with_typed_error() -> None:
    builder = hardware_effect_builder(lambda **kwargs: kwargs, accepted_kwargs=("speed",))

    with pytest.raises(UnsupportedHardwareEffectArgument) as caught:
        builder(brightness=25)

    assert caught.value.argument == "brightness"
    assert str(caught.value) == "'brightness' attr is not needed by effect"


def test_internal_hardware_backends_publish_builder_metadata() -> None:
    from keyrgb.core.backends.ite8258_perkey_chassis.backend import _effect_builder as ite8258_perkey_builder
    from keyrgb.core.backends.ite8258_zones_lenovo_legion.backend import _effect_builder as ite8258_zones_builder
    from keyrgb.core.backends.ite8291r3_perkey.protocol import effect as ite8291r3_builder
    from keyrgb.core.backends.ite8295_zones_lenovo_ideapad.backend import _effect_builder as ite8295_zones_builder
    from keyrgb.core.backends.ite8910_perkey.backend import _effect_builder as ite8910_builder

    builders = (
        ite8258_perkey_builder("wave", extra=("direction",)),
        ite8258_zones_builder("wave", extra=("direction",)),
        ite8291r3_builder(3, {"speed": (1, 5), "brightness": (2, 25)}),
        ite8295_zones_builder("wave", extra=("direction",)),
        ite8910_builder("wave", extra=("direction",)),
    )

    for builder in builders:
        assert isinstance(builder.accepted_kwargs, frozenset)
        assert "speed" in builder.accepted_kwargs
