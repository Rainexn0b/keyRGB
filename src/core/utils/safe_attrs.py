"""Safe attribute access helpers.

Provides type-safe alternatives to defensive patterns like:
    int(getattr(obj, "attr", 0) or 0)

The issue with the above pattern:
1. Redundant - getattr already has a default
2. The `or 0` handles None but also treats 0 as falsy (bug risk)
3. Nested int() calls are wasteful

Migration:
    # Before
    brightness = int(getattr(tray.config, "brightness", 0) or 0)

    # After
    from src.core.utils.safe_attrs import safe_int_attr
    brightness = safe_int_attr(tray.config, "brightness", default=0)
"""

from __future__ import annotations

from typing import Any, Optional


def safe_int_attr(
    obj: Any, name: str, *, default: int = 0, min_v: Optional[int] = None, max_v: Optional[int] = None
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
    try:
        raw = getattr(obj, name, None)
    except Exception:
        raw = None

    if raw is None:
        val = default
    else:
        try:
            val = int(raw)
        except (TypeError, ValueError):
            try:
                val = int(float(raw))
            except Exception:
                val = default

    if min_v is not None and val < min_v:
        val = min_v
    if max_v is not None and val > max_v:
        val = max_v

    return val


def safe_bool_attr(obj: Any, name: str, *, default: bool = False) -> bool:
    """Safely get a boolean attribute with explicit default.

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute missing or None

    Returns:
        Boolean value
    """
    try:
        raw = getattr(obj, name, None)
    except Exception:
        raw = None

    if raw is None:
        return default

    return bool(raw)


def safe_float_attr(
    obj: Any, name: str, *, default: float = 0.0, min_v: Optional[float] = None, max_v: Optional[float] = None
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
    try:
        raw = getattr(obj, name, None)
    except Exception:
        raw = None

    if raw is None:
        val = default
    else:
        try:
            val = float(raw)
        except (TypeError, ValueError):
            val = default

    if min_v is not None and val < min_v:
        val = min_v
    if max_v is not None and val > max_v:
        val = max_v

    return val


def safe_str_attr(obj: Any, name: str, *, default: str = "") -> str:
    """Safely get a string attribute with explicit default.

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute missing or None

    Returns:
        String value
    """
    try:
        raw = getattr(obj, name, None)
    except Exception:
        raw = None

    if raw is None:
        return default

    return str(raw)


def safe_optional_int_attr(
    obj: Any, name: str, *, min_v: Optional[int] = None, max_v: Optional[int] = None
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
    try:
        raw = getattr(obj, name, None)
    except Exception:
        return None

    if raw is None:
        return None

    try:
        val = int(raw)
    except (TypeError, ValueError):
        try:
            val = int(float(raw))
        except Exception:
            return None

    if min_v is not None and val < min_v:
        val = min_v
    if max_v is not None and val > max_v:
        val = max_v

    return val
