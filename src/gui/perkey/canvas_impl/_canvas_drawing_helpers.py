from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from tkinter import TclError
from typing import Protocol, SupportsFloat, SupportsIndex, TypeAlias, cast

from src.core.resources.layout import KeyDef


ShapeRect: TypeAlias = tuple[float, float, float, float]
FloatCoercible: TypeAlias = SupportsFloat | SupportsIndex | str | bytes | bytearray


class _ResolvedLegendPackFn(Protocol):
    def __call__(self) -> str | None: ...


class _VisibleLayoutKeysFn(Protocol):
    def __call__(self) -> Iterable[KeyDef]: ...


class _VisibleLayoutKeysSurface(Protocol):
    def _visible_layout_keys(self) -> Iterable[KeyDef]: ...


class _ValueGetterFn(Protocol):
    def __call__(self) -> object: ...


class _MeasuredFontProtocol(Protocol):
    def configure(self, *, size: int) -> None: ...

    def measure(self, text: str) -> int: ...


def _visible_layout_keys_or_none(canvas: object) -> list[KeyDef] | None:
    try:
        visible_keys_getter = cast(_VisibleLayoutKeysSurface, canvas)._visible_layout_keys
    except AttributeError:
        return None
    if not callable(visible_keys_getter):
        return None
    return list(cast(_VisibleLayoutKeysFn, visible_keys_getter)())


def _resolved_layout_legend_pack_id_or_none(editor: object) -> str | None:
    try:
        resolve_legend_pack = cast(_ResolvedLegendPackFn, editor)._resolved_layout_legend_pack_id
    except AttributeError:
        return None
    if not callable(resolve_legend_pack):
        return None
    return cast(_ResolvedLegendPackFn, resolve_legend_pack)()


def _fit_key_label(
    label: str,
    *,
    font_name: str,
    font_size: int,
    max_text_w: int,
    font_factory: Callable[..., _MeasuredFontProtocol],
    logger: logging.Logger,
) -> tuple[str, int]:
    try:
        font = font_factory(font=(font_name, font_size))
        while font_size > 6 and font.measure(label) > max_text_w:
            font_size -= 1
            font.configure(size=font_size)
        if font.measure(label) > max_text_w:
            ellipsis = "…"
            if font.measure(ellipsis) <= max_text_w:
                trimmed = label
                while trimmed and font.measure(trimmed + ellipsis) > max_text_w:
                    trimmed = trimmed[:-1]
                label = (trimmed + ellipsis) if trimmed else ellipsis
    except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
        logger.debug("Failed to measure key label %r; drawing without truncation.", label, exc_info=True)
    return label, font_size


def _coerce_backdrop_transparency(value: object, *, logger: logging.Logger) -> float:
    raw_value = value
    getter = getattr(raw_value, "get", None)
    if callable(getter):
        try:
            raw_value = cast(_ValueGetterFn, getter)()
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            logger.debug(
                "Failed to read backdrop transparency variable; falling back to default coercion.",
                exc_info=True,
            )
    try:
        coercion_input = cast(FloatCoercible, raw_value or 0)
        return max(0.0, min(100.0, float(coercion_input)))
    except (AttributeError, TypeError, ValueError, OverflowError):
        logger.debug("Failed to coerce backdrop transparency %r; defaulting to 0.", raw_value, exc_info=True)
        return 0.0


def _shape_polygon_points(shape_rects: Sequence[ShapeRect]) -> list[float]:
    if len(shape_rects) != 2:
        left = min(rect[0] for rect in shape_rects)
        top = min(rect[1] for rect in shape_rects)
        right = max(rect[2] for rect in shape_rects)
        bottom = max(rect[3] for rect in shape_rects)
        return [left, top, right, top, right, bottom, left, bottom]

    upper, lower = sorted(shape_rects, key=lambda rect: (rect[1], rect[0]))
    ux1, uy1, ux2, uy2 = upper
    lx1, _ly1, lx2, ly2 = lower
    return [ux1, uy1, ux2, uy1, ux2, uy2, lx2, uy2, lx2, ly2, lx1, ly2, lx1, uy2, ux1, uy2]
