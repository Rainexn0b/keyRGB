from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Protocol, cast

from src.core.resources.layout import REFERENCE_DEVICE_KEYS, KeyDef

_BBox = tuple[float, float, float, float]
_HitRect = tuple[float, float, float, float]


KEYDEF_BY_ID: dict[str, KeyDef] = {k.key_id: k for k in REFERENCE_DEVICE_KEYS}
KEYDEF_BY_SLOT_ID: dict[str, KeyDef] = {str(getattr(k, "slot_id", None) or k.key_id): k for k in REFERENCE_DEVICE_KEYS}


class _VisibleLayoutKeysGetter(Protocol):
    def __call__(self) -> Iterable[KeyDef]: ...


class _VisibleLayoutKeysSurface(Protocol):
    _get_visible_layout_keys: _VisibleLayoutKeysGetter


class _PhysicalLayoutSurface(Protocol):
    _physical_layout: str | None


class _ResolvedLayoutLegendPackIdGetter(Protocol):
    def __call__(self) -> str | None: ...


class _ResolvedLayoutLegendPackIdSurface(Protocol):
    _resolved_layout_legend_pack_id: _ResolvedLayoutLegendPackIdGetter


class _KeyDefBySlotIdLookup(Protocol):
    def __call__(self, identity: str) -> KeyDef | None: ...


class _KeyDefBySlotIdSurface(Protocol):
    _keydef_by_slot_id: _KeyDefBySlotIdLookup


class _KeyDefByIdLookup(Protocol):
    def __call__(self, identity: str) -> KeyDef | None: ...


class _KeyDefByIdSurface(Protocol):
    _keydef_by_id: _KeyDefByIdLookup


class _KeyDefByIdentityLookup(Protocol):
    def __call__(self, identity: str) -> KeyDef | None: ...


class _KeyBBoxCanvasLookup(Protocol):
    def __call__(self, key: KeyDef) -> _BBox | None: ...


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


def _visible_layout_keys_getter_or_none(editor: object) -> _VisibleLayoutKeysGetter | None:
    try:
        getter = cast(_VisibleLayoutKeysSurface, editor)._get_visible_layout_keys
    except AttributeError:
        return None
    return getter if callable(getter) else None


def _physical_layout_or_auto(editor: object) -> str:
    try:
        physical_layout = cast(_PhysicalLayoutSurface, editor)._physical_layout
    except AttributeError:
        return "auto"
    return physical_layout or "auto"


def _resolved_layout_legend_pack_id_or_none(editor: object) -> str | None:
    try:
        resolve_legend_pack = cast(_ResolvedLayoutLegendPackIdSurface, editor)._resolved_layout_legend_pack_id
    except AttributeError:
        return None
    if not callable(resolve_legend_pack):
        return None
    return resolve_legend_pack()


def lookup_keydef_by_slot_id_or_none(canvas: object, identity: str) -> KeyDef | None:
    try:
        slot_lookup = cast(_KeyDefBySlotIdSurface, canvas)._keydef_by_slot_id
    except AttributeError:
        return None
    return slot_lookup(identity) if callable(slot_lookup) else None


def lookup_keydef_by_id_or_none(canvas: object, identity: str) -> KeyDef | None:
    try:
        key_lookup = cast(_KeyDefByIdSurface, canvas)._keydef_by_id
    except AttributeError:
        return None
    return key_lookup(identity) if callable(key_lookup) else None


def resolve_visible_layout_keys(
    editor: object,
    *,
    get_layout_keys: Callable[..., Iterable[KeyDef]],
) -> list[KeyDef]:
    getter = _visible_layout_keys_getter_or_none(editor)
    if callable(getter):
        return list(getter())

    legend_pack_id = _resolved_layout_legend_pack_id_or_none(editor)
    return list(
        get_layout_keys(
            _physical_layout_or_auto(editor),
            legend_pack_id=legend_pack_id,
            slot_overrides=getattr(editor, "layout_slot_overrides", None),
        )
    )


def lookup_keydef_by_slot_id(
    slot_id: str,
    *,
    visible_layout_keys: Callable[[], Iterable[KeyDef]],
    fallback_by_slot_id: Mapping[str, KeyDef],
) -> KeyDef | None:
    slot_id_text = str(slot_id)
    for key in visible_layout_keys():
        if str(getattr(key, "slot_id", None) or key.key_id) == slot_id_text:
            return key
    return fallback_by_slot_id.get(slot_id_text)


def lookup_keydef_by_id(
    key_id: str,
    *,
    visible_layout_keys: Callable[[], Iterable[KeyDef]],
    fallback_by_id: Mapping[str, KeyDef],
) -> KeyDef | None:
    key_id_text = str(key_id)
    for key in visible_layout_keys():
        if key.key_id == key_id_text:
            return key
    return fallback_by_id.get(key_id_text)


def lookup_keydef_by_identity(
    identity: str,
    *,
    keydef_by_slot_id: _KeyDefBySlotIdLookup,
    keydef_by_id: _KeyDefByIdLookup,
) -> KeyDef | None:
    key = keydef_by_slot_id(identity)
    if key is not None:
        return key
    return keydef_by_id(identity)


def _identity_bbox(
    identity: str,
    *,
    keydef_by_identity: _KeyDefByIdentityLookup,
    key_bbox_canvas: _KeyBBoxCanvasLookup,
) -> _BBox | None:
    key = keydef_by_identity(identity)
    if key is None:
        return None
    return key_bbox_canvas(key)


def resize_edges_for_identity(
    identity: str,
    cx: float,
    cy: float,
    *,
    keydef_by_identity: _KeyDefByIdentityLookup,
    key_bbox_canvas: _KeyBBoxCanvasLookup,
    resize_edges_for_point_in_bbox: _ResizeEdgesForPointLookup,
) -> str:
    bbox = _identity_bbox(identity, keydef_by_identity=keydef_by_identity, key_bbox_canvas=key_bbox_canvas)
    if bbox is None:
        return ""
    x1, y1, x2, y2 = bbox
    return resize_edges_for_point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy)


def point_in_identity_bbox(
    identity: str,
    cx: float,
    cy: float,
    *,
    keydef_by_identity: _KeyDefByIdentityLookup,
    key_bbox_canvas: _KeyBBoxCanvasLookup,
    point_in_bbox: _PointInBBoxLookup,
) -> bool:
    bbox = _identity_bbox(identity, keydef_by_identity=keydef_by_identity, key_bbox_canvas=key_bbox_canvas)
    if bbox is None:
        return False
    x1, y1, x2, y2 = bbox
    return point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy)


def point_near_identity_bbox(
    identity: str,
    cx: float,
    cy: float,
    *,
    keydef_by_identity: _KeyDefByIdentityLookup,
    key_bbox_canvas: _KeyBBoxCanvasLookup,
    point_near_bbox: _PointNearBBoxLookup,
    pad: float,
) -> bool:
    bbox = _identity_bbox(identity, keydef_by_identity=keydef_by_identity, key_bbox_canvas=key_bbox_canvas)
    if bbox is None:
        return False
    x1, y1, x2, y2 = bbox
    return point_near_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy, pad=pad)


def hit_test_slot_id(
    cx: float,
    cy: float,
    *,
    transform: object | None,
    visible_layout_keys: Iterable[KeyDef],
    layout_tweaks: Mapping[str, object],
    per_key_layout_tweaks: Mapping[str, object],
    key_canvas_hit_rects: Callable[..., Iterable[_HitRect]],
    image_size: tuple[int, int],
    point_in_bbox: _PointInBBoxLookup,
) -> str | None:
    if transform is None:
        return None
    for key in visible_layout_keys:
        for x1, y1, x2, y2 in key_canvas_hit_rects(
            transform=transform,
            key=key,
            layout_tweaks=layout_tweaks,
            per_key_layout_tweaks=per_key_layout_tweaks,
            image_size=image_size,
        ):
            if point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy):
                return str(getattr(key, "slot_id", None) or key.key_id)
    return None


def resolve_hit_test_key_id(
    slot_id: str | None,
    *,
    keydef_by_slot_id: _KeyDefBySlotIdLookup,
) -> str | None:
    if slot_id is None:
        return None
    key = keydef_by_slot_id(slot_id)
    return str(key.key_id) if key is not None else str(slot_id)


def resolve_overlay_press_mode(
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
    selected_identity = str(selected_slot_id or "")
    if not selected_identity and selected_key_id:
        key = keydef_by_id(str(selected_key_id))
        if key is not None:
            selected_identity = str(getattr(key, "slot_id", None) or key.key_id)
        else:
            selected_identity = str(selected_key_id)
    if not selected_identity:
        return None

    edges = resize_edges_for_point(selected_identity, cx, cy)
    if edges:
        if not point_near_key_bbox(selected_identity, cx, cy, pad=float(pad)):
            return None
        return "resize", edges

    slot_id = hit_test_slot_id(cx, cy)
    if slot_id != selected_identity:
        return None
    return "move", ""
