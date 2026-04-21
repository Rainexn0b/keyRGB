from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import cast


ColorTuple = tuple[int, int, int]

EffectNameResolver = Callable[[str], str]
BoolAttrReader = Callable[..., bool]
IntAttrReader = Callable[..., int]
StrAttrReader = Callable[..., str | None]
TupleAttrReader = Callable[..., ColorTuple]
PerkeySignatureReader = Callable[[object], tuple | None]
SoftwareEffectTargetNormalizer = Callable[[str], str]

_CONFIG_FALLBACK_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)


def _safe_tuple_attr(config: object, name: str, *, default: ColorTuple) -> ColorTuple:
    try:
        raw = getattr(config, name, default)
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return default

    if not isinstance(raw, Iterable):
        return default

    try:
        value = tuple(raw)
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return default

    if len(value) != 3:
        return default

    return cast(ColorTuple, value)


def _safe_perkey_signature(config: object) -> tuple | None:
    try:
        per_key_colors = getattr(config, "per_key_colors", None)
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return None

    if per_key_colors is None:
        return None

    try:
        return tuple(sorted(per_key_colors.items()))
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return None


@dataclass(frozen=True)
class ConfigApplyState:
    effect: str
    speed: int
    brightness: int
    color: ColorTuple
    perkey_sig: tuple | None
    reactive_use_manual: bool
    reactive_color: ColorTuple
    reactive_brightness: int = 0
    reactive_trail_percent: int = 50
    software_effect_target: str = "keyboard"


def build_config_apply_state(
    config: object,
    *,
    resolve_effect_name: EffectNameResolver,
    read_bool_attr: BoolAttrReader,
    read_int_attr: IntAttrReader,
    read_str_attr: StrAttrReader,
    read_tuple_attr: TupleAttrReader,
    read_perkey_signature: PerkeySignatureReader,
    normalize_software_effect_target_fn: SoftwareEffectTargetNormalizer,
    reactive_effects_set: set[str] | frozenset[str],
) -> ConfigApplyState:
    try:
        effect = resolve_effect_name(read_str_attr(config, "effect", default="none") or "none")
    except _CONFIG_FALLBACK_EXCEPTIONS:
        effect = "none"

    perkey_sig = None
    if effect == "perkey":
        perkey_sig = read_perkey_signature(config)

    reactive_use_manual = read_bool_attr(config, "reactive_use_manual_color", default=False)
    reactive_color = read_tuple_attr(config, "reactive_color", default=(255, 255, 255))

    base_brightness = read_int_attr(config, "brightness", default=0)
    reactive_brightness = 0
    reactive_trail_percent = 50
    if effect in reactive_effects_set:
        reactive_brightness = read_int_attr(config, "reactive_brightness", default=base_brightness)
        reactive_trail_percent = read_int_attr(config, "reactive_trail_percent", default=50)

    color = read_tuple_attr(config, "color", default=(255, 255, 255))
    software_effect_target = normalize_software_effect_target_fn(
        read_str_attr(config, "software_effect_target", default="keyboard") or "keyboard"
    )

    return ConfigApplyState(
        effect=str(effect),
        speed=read_int_attr(config, "speed", default=0),
        brightness=base_brightness,
        color=color,
        perkey_sig=perkey_sig,
        software_effect_target=software_effect_target,
        reactive_use_manual=bool(reactive_use_manual),
        reactive_color=reactive_color,
        reactive_brightness=int(reactive_brightness),
        reactive_trail_percent=int(reactive_trail_percent),
    )