from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeAlias

from src.core.resources.layout import BASE_IMAGE_SIZE, KeyDef

from ._canvas_drawing_helpers import ShapeRect


CanvasItemId: TypeAlias = int
KeyCell: TypeAlias = tuple[int, int]
RGBColor: TypeAlias = tuple[int, int, int]
LayoutTweaks: TypeAlias = dict[str, float]
PerKeyLayoutTweaks: TypeAlias = dict[str, dict[str, float]]
LayoutSlotOverrides: TypeAlias = dict[str, dict[str, object]]


class _CanvasTransformProtocol(Protocol):
    def to_canvas(self, rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]: ...


class _InsetPixelsProtocol(Protocol):
    def __call__(self, width_px: float, height_px: float, inset_value: float) -> float: ...


class _CanvasCreatePolygonProtocol(Protocol):
    def __call__(self, points: Sequence[float], **kwargs: object) -> CanvasItemId: ...


class _CanvasCreateRectangleProtocol(Protocol):
    def __call__(self, x1: float, y1: float, x2: float, y2: float, **kwargs: object) -> CanvasItemId: ...


class _CanvasCreateTextProtocol(Protocol):
    def __call__(self, x: float, y: float, **kwargs: object) -> CanvasItemId: ...


class _CanvasTagBindProtocol(Protocol):
    def __call__(self, tag_or_id: str, event: str, callback: Callable[[object], None]) -> None: ...


class _KeyCanvasRectProtocol(Protocol):
    def __call__(
        self,
        *,
        transform: object,
        key: KeyDef,
        layout_tweaks: LayoutTweaks,
        per_key_layout_tweaks: PerKeyLayoutTweaks,
        image_size: tuple[int, int],
    ) -> tuple[float, float, float, float, float]: ...


class _KeyCanvasHitRectsProtocol(Protocol):
    def __call__(
        self,
        *,
        transform: object,
        key: KeyDef,
        layout_tweaks: LayoutTweaks,
        per_key_layout_tweaks: PerKeyLayoutTweaks,
        image_size: tuple[int, int],
    ) -> Sequence[ShapeRect]: ...


class _KeyDrawStyleProtocol(Protocol):
    fill: str
    stipple: str | None
    outline: str
    width: int
    dash: tuple[int, ...]
    text_fill: str


class _KeyDrawStyleFactoryProtocol(Protocol):
    def __call__(self, *, mapped: bool, selected: bool, color: RGBColor | None) -> _KeyDrawStyleProtocol: ...


class _KeymapCellsForProtocol(Protocol):
    def __call__(
        self,
        keymap: Mapping[str, object],
        key_id: str,
        *,
        slot_id: str,
        physical_layout: str,
    ) -> Sequence[KeyCell]: ...


class _RepresentativeCellProtocol(Protocol):
    def __call__(self, cells: Sequence[KeyCell], *, colors: Mapping[KeyCell, RGBColor]) -> KeyCell | None: ...


class _ShapePolygonPointsProtocol(Protocol):
    def __call__(self, shape_rects: Sequence[ShapeRect]) -> list[float]: ...


class _FitKeyLabelProtocol(Protocol):
    def __call__(
        self,
        label: str,
        *,
        font_name: str,
        font_size: int,
        max_text_w: int,
    ) -> tuple[str, int]: ...


class _VisibleLayoutKeysOrNoneProtocol(Protocol):
    def __call__(self, canvas: object) -> list[KeyDef] | None: ...


class _ResolvedLayoutLegendPackIdOrNoneProtocol(Protocol):
    def __call__(self, editor: object) -> str | None: ...


class _GetLayoutKeysProtocol(Protocol):
    def __call__(
        self,
        physical_layout: str,
        *,
        legend_pack_id: str | None,
        slot_overrides: LayoutSlotOverrides | None,
    ) -> Sequence[KeyDef]: ...


class _PerKeyCanvasEditorProtocol(Protocol):
    layout_slot_overrides: LayoutSlotOverrides | None
    layout_tweaks: LayoutTweaks
    per_key_layout_tweaks: PerKeyLayoutTweaks
    keymap: Mapping[str, object]
    colors: Mapping[KeyCell, RGBColor]
    selected_slot_id: str | None

    def on_slot_clicked(self, slot_id: str) -> None: ...


class _CanvasRenderSurfaceProtocol(Protocol):
    editor: _PerKeyCanvasEditorProtocol
    _inset_pixels: _InsetPixelsProtocol
    create_polygon: _CanvasCreatePolygonProtocol
    create_rectangle: _CanvasCreateRectangleProtocol
    create_text: _CanvasCreateTextProtocol
    tag_bind: _CanvasTagBindProtocol
    key_rects: dict[str, CanvasItemId]
    key_texts: dict[str, CanvasItemId]


def resolve_visible_keys(
    *,
    canvas: object,
    editor: object,
    physical_layout: str,
    visible_layout_keys_or_none: _VisibleLayoutKeysOrNoneProtocol,
    resolved_layout_legend_pack_id_or_none: _ResolvedLayoutLegendPackIdOrNoneProtocol,
    get_layout_keys: _GetLayoutKeysProtocol,
) -> list[KeyDef]:
    visible_keys = visible_layout_keys_or_none(canvas)
    if visible_keys is not None:
        return list(visible_keys)

    legend_pack_id = resolved_layout_legend_pack_id_or_none(editor)
    return list(
        get_layout_keys(
            physical_layout,
            legend_pack_id=legend_pack_id,
            slot_overrides=getattr(editor, "layout_slot_overrides", None),
        )
    )


def render_visible_keys(
    *,
    canvas: _CanvasRenderSurfaceProtocol,
    transform: _CanvasTransformProtocol | object,
    visible_keys: Sequence[KeyDef],
    physical_layout: str,
    key_canvas_rect: _KeyCanvasRectProtocol,
    key_canvas_hit_rects: _KeyCanvasHitRectsProtocol,
    key_draw_style: _KeyDrawStyleFactoryProtocol,
    keymap_cells_for: _KeymapCellsForProtocol,
    representative_cell: _RepresentativeCellProtocol,
    shape_polygon_points: _ShapePolygonPointsProtocol,
    fit_key_label: _FitKeyLabelProtocol,
) -> None:
    editor = canvas.editor
    for key in visible_keys:
        slot_id = str(getattr(key, "slot_id", None) or key.key_id)
        x1, y1, x2, y2, inset_value = key_canvas_rect(
            transform=transform,
            key=key,
            layout_tweaks=editor.layout_tweaks,
            per_key_layout_tweaks=editor.per_key_layout_tweaks,
            image_size=BASE_IMAGE_SIZE,
        )

        inset = canvas._inset_pixels(x2 - x1, y2 - y1, inset_value)
        x1 += inset
        y1 += inset
        x2 -= inset
        y2 -= inset

        mapped_cells = keymap_cells_for(
            editor.keymap,
            key.key_id,
            slot_id=slot_id,
            physical_layout=physical_layout,
        )
        mapped = bool(mapped_cells)
        mapped_cell = representative_cell(mapped_cells, colors=editor.colors)
        color = editor.colors.get(mapped_cell) if mapped_cell is not None else None
        style = key_draw_style(
            mapped=mapped,
            selected=getattr(editor, "selected_slot_id", None) == slot_id,
            color=color,
        )

        tags = (f"pslot_{slot_id}", f"pkey_{key.key_id}", "pkey")
        shape_rects = list(
            key_canvas_hit_rects(
                transform=transform,
                key=key,
                layout_tweaks=editor.layout_tweaks,
                per_key_layout_tweaks=editor.per_key_layout_tweaks,
                image_size=BASE_IMAGE_SIZE,
            )
        )
        if len(shape_rects) == 1:
            sx1, sy1, sx2, sy2 = shape_rects[0]
            rect_id = canvas.create_rectangle(
                sx1,
                sy1,
                sx2,
                sy2,
                fill=style.fill,
                stipple=style.stipple,
                outline=style.outline,
                width=style.width,
                dash=style.dash,
                tags=tags,
            )
        else:
            rect_id = canvas.create_polygon(
                shape_polygon_points(shape_rects),
                fill=style.fill,
                stipple=style.stipple,
                outline=style.outline,
                width=style.width,
                dash=style.dash,
                joinstyle="miter",
                tags=tags,
            )
        canvas.key_rects[key.key_id] = rect_id
        canvas.key_rects[slot_id] = rect_id

        key_w = max(1, int(x2 - x1))
        key_h = max(1, int(y2 - y1))
        font_name = "TkDefaultFont"
        font_size = max(7, min(11, int(min(key_w, key_h) * 0.30)))
        max_text_w = max(1, key_w - 6)

        label, font_size = fit_key_label(
            key.label,
            font_name=font_name,
            font_size=font_size,
            max_text_w=max_text_w,
        )
        text_id = canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=label,
            fill=style.text_fill,
            font=(font_name, font_size),
            tags=tags,
        )
        canvas.key_texts[key.key_id] = text_id
        canvas.key_texts[slot_id] = text_id

        canvas.tag_bind(
            f"pslot_{slot_id}",
            "<Button-1>",
            lambda _e, sid=slot_id: editor.on_slot_clicked(sid),
        )
