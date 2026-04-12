"""Safe attribute access helpers.

Provides type-safe alternatives to legacy inline attribute-to-number coercion,
where each call site mixed attribute lookup, fallback handling, and conversion.

The helpers centralize that behavior and avoid subtle falsy-value bugs such as
treating 0 like a missing value.

Migration:
    from src.core.utils.safe_attrs import safe_int_attr
    brightness = safe_int_attr(tray.config, "brightness", default=0)
"""

from __future__ import annotations

from typing import Optional, overload


_SAFE_ATTR_ACCESS_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_SAFE_NUMERIC_FALLBACK_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _safe_getattr_or_none(obj: object, name: str) -> object | None:
    try:
        return getattr(obj, name, None)
    except _SAFE_ATTR_ACCESS_ERRORS:
        return None


@overload
def _coerce_int_like(raw: object, *, default: int) -> int: ...


@overload
def _coerce_int_like(raw: object, *, default: None) -> Optional[int]: ...


def _coerce_int_like(raw: object, *, default: Optional[int]) -> Optional[int]:
    _raw = raw
    try:
        return int(_raw)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        try:
            return int(float(_raw))  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            return default
        except _SAFE_NUMERIC_FALLBACK_ERRORS:
            return default


def safe_int_attr(
    obj: object, name: str, *, default: int = 0, min_v: Optional[int] = None, max_v: Optional[int] = None
) -> int:
    """Safely get an integer attribute with explicit default.

    Handles:
    - Missing attribute (returns default)
    - None value (returns default)
    - String values that look like ints (attempts conversion)
    - Out-of-range values (clamps if min_v/max_v provided)

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute missing or None
        min_v: Optional minimum value (clamps)
        max_v: Optional maximum value (clamps)

    Returns:
        Integer value, clamped to [min_v, max_v] if specified
    """
    raw = _safe_getattr_or_none(obj, name)

    if raw is None:
        val = default
    else:
        val = _coerce_int_like(raw, default=default)

    if min_v is not None and val < min_v:
        val = min_v
    if max_v is not None and val > max_v:
        val = max_v

    return val


def safe_bool_attr(obj: object, name: str, *, default: bool = False) -> bool:
    """Safely get a boolean attribute with explicit default.

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute missing or None

    Returns:
        Boolean value
    """
    raw = _safe_getattr_or_none(obj, name)

    if raw is None:
        return default

    return bool(raw)


def safe_float_attr(
    obj: object, name: str, *, default: float = 0.0, min_v: Optional[float] = None, max_v: Optional[float] = None
) -> float:
    """Safely get a float attribute with explicit default.

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute missing or None
        min_v: Optional minimum value (clamps)
        max_v: Optional maximum value (clamps)

    Returns:
        Float value, clamped to [min_v, max_v] if specified
    """
    raw = _safe_getattr_or_none(obj, name)

    if raw is None:
        val = default
    else:
        try:
            val = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            val = default

    if min_v is not None and val < min_v:
        val = min_v
    if max_v is not None and val > max_v:
        val = max_v

    return val


def safe_str_attr(obj: object, name: str, *, default: str = "") -> str:
    """Safely get a string attribute with explicit default.

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute missing or None

    Returns:
        String value
    """
    raw = _safe_getattr_or_none(obj, name)

    if raw is None:
        return default

    return str(raw)


def safe_optional_int_attr(
    obj: object, name: str, *, min_v: Optional[int] = None, max_v: Optional[int] = None
) -> Optional[int]:
    """Safely get an optional integer attribute (preserves None).

    Unlike safe_int_attr, this returns None when the attribute is None or missing,
    rather than a default value. Useful for config values where None means "not set".

    Args:
        obj: Object to get attribute from
        name: Attribute name
        min_v: Optional minimum value (clamps if not None)
        max_v: Optional maximum value (clamps if not None)

    Returns:
        Integer value or None
    """
    raw = _safe_getattr_or_none(obj, name)

    if raw is None:
        return None

    val = _coerce_int_like(raw, default=None)
    if val is None:
        return None

    if min_v is not None and val < min_v:
        val = min_v
    if max_v is not None and val > max_v:
        val = max_v

    return val
