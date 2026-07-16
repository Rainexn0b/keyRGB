from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import cast

from src.core.lighting_layers import render_effect_from_selected_effect


ColorTuple = tuple[int, int, int]

EffectNameResolver = Callable[[str], str]
BoolAttrReader = Callable[..., bool]
IntAttrReader = Callable[..., int]
StrAttrReader = Callable[..., str | None]
TupleAttrReader = Callable[..., ColorTuple]
PerkeySignatureReader = Callable[[object], tuple | None]
SoftwareEffectTargetNormalizer = Callable[[str], str]

# getattr/property + tuple coercion for config snapshots (no OS/I-O).
_CONFIG_FALLBACK_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError, OverflowError)
_REACTIVE_VISUAL_MODES = frozenset({"subtle", "vivid"})


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
        if len(per_key_colors) <= 0:  # type: ignore[arg-type]
            return None
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return None

    try:
        return tuple(sorted(per_key_colors.items()))
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return None


def _freeze_secondary_value(value: object) -> object:
    if isinstance(value, Mapping):
        pairs = [(str(key), _freeze_secondary_value(item)) for key, item in value.items()]
        return tuple(sorted(pairs, key=lambda pair: pair[0]))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_secondary_value(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_secondary_signature(config: object) -> tuple | None:
    """Return an ordering-independent immutable snapshot of secondary state."""
    try:
        snapshot_fn = getattr(config, "secondary_device_state_snapshot", None)
        if callable(snapshot_fn):
            raw_state = snapshot_fn()
        else:
            settings = vars(config).get("_settings")
            raw_state = settings.get("secondary_device_state") if isinstance(settings, Mapping) else None
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return None
    if raw_state is None:
        return None
    if not isinstance(raw_state, Mapping):
        return ()
    frozen = _freeze_secondary_value(raw_state)
    return cast(tuple, frozen)


@dataclass(frozen=True)
class ConfigApplyState:
    effect: str
    speed: int
    brightness: int
    color: ColorTuple
    perkey_sig: tuple | None
    reactive_use_manual: bool
    reactive_color: ColorTuple
    selected_effect: str | None = None
    reactive_brightness: int = 0
    reactive_trail_percent: int = 40
    reactive_visual_mode: str = "subtle"
    software_effect_target: str = "keyboard"
    secondary_sig: tuple | None = None

    def __post_init__(self) -> None:
        if self.selected_effect is None:
            object.__setattr__(self, "selected_effect", self.effect)


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
    read_secondary_signature: Callable[[object], tuple | None] = _safe_secondary_signature,
) -> ConfigApplyState:
    def _normalize_reactive_visual_mode(value: object, *, default: str = "subtle") -> str:
        try:
            normalized = str(value or default).strip().lower()
        except _CONFIG_FALLBACK_EXCEPTIONS:
            return default
        return normalized if normalized in _REACTIVE_VISUAL_MODES else default

    try:
        selected_effect = resolve_effect_name(read_str_attr(config, "effect", default="none") or "none")
    except _CONFIG_FALLBACK_EXCEPTIONS:
        selected_effect = "none"

    perkey_sig = read_perkey_signature(config)
    secondary_sig = read_secondary_signature(config)
    effect = render_effect_from_selected_effect(
        selected_effect=str(selected_effect),
        per_key_colors=perkey_sig,
    )

    reactive_use_manual = read_bool_attr(config, "reactive_use_manual_color", default=False)
    reactive_color = read_tuple_attr(config, "reactive_color", default=(255, 255, 255))

    base_brightness = read_int_attr(config, "brightness", default=0)
    reactive_brightness = 0
    reactive_trail_percent = 40
    reactive_visual_mode = "subtle"
    if effect in reactive_effects_set:
        reactive_brightness = read_int_attr(config, "reactive_brightness", default=base_brightness)
        reactive_trail_percent = read_int_attr(config, "reactive_trail_percent", default=40)
        reactive_visual_mode = _normalize_reactive_visual_mode(
            read_str_attr(config, "reactive_visual_mode", default="subtle") or "subtle"
        )

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
        selected_effect=str(selected_effect),
        software_effect_target=software_effect_target,
        reactive_use_manual=bool(reactive_use_manual),
        reactive_color=reactive_color,
        reactive_brightness=int(reactive_brightness),
        reactive_trail_percent=int(reactive_trail_percent),
        reactive_visual_mode=str(reactive_visual_mode),
        secondary_sig=secondary_sig,
    )
