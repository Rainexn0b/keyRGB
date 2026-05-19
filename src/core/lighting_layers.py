from __future__ import annotations

from collections.abc import Callable


_LAYER_STATE_EXCEPTIONS = (AttributeError, LookupError, RuntimeError, TypeError, ValueError)


def has_nonempty_per_key_base(per_key_colors: object | None) -> bool:
    """Return True when a usable saved per-key base map exists."""

    if per_key_colors is None:
        return False

    try:
        return len(per_key_colors) > 0  # type: ignore[arg-type]
    except _LAYER_STATE_EXCEPTIONS:
        return False


def render_effect_from_selected_effect(*, selected_effect: str, per_key_colors: object | None) -> str:
    """Map the selected effect layer to the runtime render effect.

    The canonical lighting stack is:
    - selected effect layer
    - brightness layer
    - base per-key color layer

    When no tertiary effect is selected, a non-empty base map should render as
    static per-key output instead of falling back to uniform hardware color.
    """

    effect = str(selected_effect or "none") or "none"
    if effect == "none" and has_nonempty_per_key_base(per_key_colors):
        return "perkey"
    return effect


def resolve_render_effect(
    *,
    selected_effect: str | None,
    per_key_colors: object | None,
    resolve_effect_name_fn: Callable[[str], str],
) -> str:
    """Resolve the selected effect first, then apply base-layer fallback rules."""

    resolved_selected = resolve_effect_name_fn(str(selected_effect or "none")) or "none"
    return render_effect_from_selected_effect(
        selected_effect=resolved_selected,
        per_key_colors=per_key_colors,
    )
