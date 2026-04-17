from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Protocol

from src.core.resources.layout import KeyDef

from . import _canvas_identity

_HitRect = tuple[float, float, float, float]


KEYDEF_BY_ID = _canvas_identity.KEYDEF_BY_ID
KEYDEF_BY_SLOT_ID = _canvas_identity.KEYDEF_BY_SLOT_ID


class _EditorBackedCanvas(Protocol):
    editor: object


class _LayoutTweaksEditor(Protocol):
    layout_tweaks: Mapping[str, object]
    per_key_layout_tweaks: Mapping[str, object]


class _HitTestCanvas(Protocol):
    editor: _LayoutTweaksEditor

    def _canvas_transform(self) -> object | None: ...


class _KeyBBoxCanvas(Protocol):
    def _key_bbox_canvas(self, key: KeyDef) -> tuple[float, float, float, float] | None: ...


class _KeyDefByIdentityLookup(Protocol):
    def __call__(self, identity: str) -> KeyDef | None: ...


class _KeyDefBySlotIdLookup(Protocol):
    def __call__(self, identity: str) -> KeyDef | None: ...


class _KeyDefByIdLookup(Protocol):
    def __call__(self, identity: str) -> KeyDef | None: ...


class _ResizeEdgesForPointLookup(Protocol):
    def __call__(self, *, x1: float, y1: float, x2: float, y2: float, cx: float, cy: float) -> str: ...


class _PointInBBoxLookup(Protocol):
    def __call__(self, *, x1: float, y1: float, x2: float, y2: float, cx: float, cy: float) -> bool: ...


class _PointNearBBoxLookup(Protocol):
    def __call__(self, *, x1: float, y1: float, x2: float, y2: float, cx: float, cy: float, pad: float) -> bool: ...


class _PointNearKeyBBoxLookup(Protocol):
    def __call__(self, identity: str, cx: float, cy: float, *, pad: float) -> bool: ...


class _HitTestSlotIdLookup(Protocol):
    def __call__(self, cx: float, cy: float) -> str | None: ...


def visible_layout_keys(
    editor: object,
    *,
    get_layout_keys: Callable[..., Iterable[KeyDef]],
) -> list[KeyDef]:
    return _canvas_identity.resolve_visible_layout_keys(editor, get_layout_keys=get_layout_keys)


def keydef_by_slot_id(
    canvas: _EditorBackedCanvas,
    slot_id: str,
    *,
    get_layout_keys: Callable[..., Iterable[KeyDef]],
    fallback_by_slot_id: Mapping[str, KeyDef],
) -> KeyDef | None:
    return _canvas_identity.lookup_keydef_by_slot_id(
        slot_id,
        visible_layout_keys=lambda: visible_layout_keys(canvas.editor, get_layout_keys=get_layout_keys),
        fallback_by_slot_id=fallback_by_slot_id,
    )


def keydef_by_id(
    canvas: _EditorBackedCanvas,
    key_id: str,
    *,
    get_layout_keys: Callable[..., Iterable[KeyDef]],
    fallback_by_id: Mapping[str, KeyDef],
) -> KeyDef | None:
    return _canvas_identity.lookup_keydef_by_id(
        key_id,
        visible_layout_keys=lambda: visible_layout_keys(canvas.editor, get_layout_keys=get_layout_keys),
        fallback_by_id=fallback_by_id,
    )


def keydef_by_identity(canvas: object, identity: str) -> KeyDef | None:
    return _canvas_identity.lookup_keydef_by_identity(
        identity,
        keydef_by_slot_id=lambda value: _canvas_identity.lookup_keydef_by_slot_id_or_none(canvas, value),
        keydef_by_id=lambda value: _canvas_identity.lookup_keydef_by_id_or_none(canvas, value),
    )


def resize_edges_for_point(
    canvas: _KeyBBoxCanvas,
    identity: str,
    cx: float,
    cy: float,
    *,
    keydef_by_identity: _KeyDefByIdentityLookup,
    resize_edges_for_point_in_bbox: _ResizeEdgesForPointLookup,
) -> str:
    return _canvas_identity.resize_edges_for_identity(
        identity,
        cx,
        cy,
        keydef_by_identity=keydef_by_identity,
        key_bbox_canvas=canvas._key_bbox_canvas,
        resize_edges_for_point_in_bbox=resize_edges_for_point_in_bbox,
    )


def point_in_key_bbox(
    canvas: _KeyBBoxCanvas,
    identity: str,
    cx: float,
    cy: float,
    *,
    keydef_by_identity: _KeyDefByIdentityLookup,
    point_in_bbox: _PointInBBoxLookup,
) -> bool:
    return _canvas_identity.point_in_identity_bbox(
        identity,
        cx,
        cy,
        keydef_by_identity=keydef_by_identity,
        key_bbox_canvas=canvas._key_bbox_canvas,
        point_in_bbox=point_in_bbox,
    )


def point_near_key_bbox(
    canvas: _KeyBBoxCanvas,
    identity: str,
    cx: float,
    cy: float,
    *,
    keydef_by_identity: _KeyDefByIdentityLookup,
    point_near_bbox: _PointNearBBoxLookup,
    pad: float,
) -> bool:
    return _canvas_identity.point_near_identity_bbox(
        identity,
        cx,
        cy,
        keydef_by_identity=keydef_by_identity,
        key_bbox_canvas=canvas._key_bbox_canvas,
        point_near_bbox=point_near_bbox,
        pad=pad,
    )


def hit_test_slot_id(
    canvas: _HitTestCanvas,
    cx: float,
    cy: float,
    *,
    get_layout_keys: Callable[..., Iterable[KeyDef]],
    key_canvas_hit_rects: Callable[..., Iterable[_HitRect]],
    image_size: tuple[int, int],
    point_in_bbox: _PointInBBoxLookup,
) -> str | None:
    return _canvas_identity.hit_test_slot_id(
        cx,
        cy,
        transform=canvas._canvas_transform(),
        visible_layout_keys=visible_layout_keys(canvas.editor, get_layout_keys=get_layout_keys),
        layout_tweaks=canvas.editor.layout_tweaks,
        per_key_layout_tweaks=canvas.editor.per_key_layout_tweaks,
        key_canvas_hit_rects=key_canvas_hit_rects,
        image_size=image_size,
        point_in_bbox=point_in_bbox,
    )


def hit_test_key_id(
    cx: float,
    cy: float,
    *,
    hit_test_slot_id: _HitTestSlotIdLookup,
    keydef_by_slot_id: _KeyDefBySlotIdLookup,
) -> str | None:
    return _canvas_identity.resolve_hit_test_key_id(
        hit_test_slot_id(cx, cy),
        keydef_by_slot_id=keydef_by_slot_id,
    )


def overlay_press_mode(
    *,
    selected_slot_id: str | None = None,
    selected_key_id: str | None = None,
    cx: float,
    cy: float,
    pad: float = 6.0,
    keydef_by_id: _KeyDefByIdLookup,
    resize_edges_for_point: Callable[[str, float, float], str],
    point_near_key_bbox: _PointNearKeyBBoxLookup,
    hit_test_slot_id: _HitTestSlotIdLookup,
) -> tuple[str, str] | None:
    return _canvas_identity.resolve_overlay_press_mode(
        selected_slot_id=selected_slot_id,
        selected_key_id=selected_key_id,
        cx=cx,
        cy=cy,
        pad=float(pad),
        keydef_by_id=keydef_by_id,
        resize_edges_for_point=resize_edges_for_point,
        point_near_key_bbox=point_near_key_bbox,
        hit_test_slot_id=hit_test_slot_id,
    )
