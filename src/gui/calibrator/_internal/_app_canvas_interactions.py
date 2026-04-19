from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping, Protocol, TypeAlias

if TYPE_CHECKING:
    from PIL import Image

    from src.core.resources.layout import KeyDef

    from ._app_profile_layout import (
        KeyCells,
        Keymap,
        LayoutSlotOverrides,
        LayoutTweaks,
        PerKeyLayoutTweaks,
        PhysicalLayoutIdFn,
        _CalibratorAppLike,
        _DeckRenderCacheLike,
        _ProbeSelectedIdentityFn,
        _SelectedLayoutLegendPackFn,
        _VisibleLayoutKeysFn,
    )


ImageSize: TypeAlias = tuple[int, int]


class _KeymapCellsForFn(Protocol):
    def __call__(
        self,
        keymap: Mapping[str, object],
        key_id: str | None,
        *,
        slot_id: str | None = None,
        physical_layout: str | None = None,
    ) -> KeyCells: ...


class _RedrawCalibrationCanvasFn(Protocol):
    def __call__(
        self,
        *,
        canvas: object,
        deck_pil: Image.Image | None,
        deck_render_cache: _DeckRenderCacheLike,
        layout_tweaks: LayoutTweaks,
        per_key_layout_tweaks: PerKeyLayoutTweaks,
        keymap: Keymap,
        selected_slot_id: str | None = None,
        selected_key_id: str | None = None,
        physical_layout: str = "auto",
        legend_pack_id: str | None = None,
        slot_overrides: LayoutSlotOverrides | None = None,
    ) -> tuple[object, object | None]: ...


class _ClickEvent(Protocol):
    x: int
    y: int


class _HitTestByPointFn(Protocol):
    def __call__(self, x: int, y: int) -> KeyDef | None: ...


class _CanvasHitTestFn(Protocol):
    def __call__(
        self,
        *,
        transform: object,
        x: int,
        y: int,
        layout_tweaks: LayoutTweaks,
        per_key_layout_tweaks: PerKeyLayoutTweaks,
        keys: Iterable[KeyDef],
        image_size: ImageSize,
    ) -> KeyDef | None: ...


def redraw(
    app: _CalibratorAppLike,
    *,
    redraw_calibration_canvas: _RedrawCalibrationCanvasFn,
    probe_selected_slot_id_fn: _ProbeSelectedIdentityFn,
    probe_selected_key_id_fn: _ProbeSelectedIdentityFn,
    physical_layout_id_fn: PhysicalLayoutIdFn,
    selected_layout_legend_pack_fn: _SelectedLayoutLegendPackFn,
) -> None:
    physical_layout = physical_layout_id_fn(app)
    app._transform, app._deck_tk = redraw_calibration_canvas(
        canvas=app.canvas,
        deck_pil=app._deck_pil,
        deck_render_cache=app._deck_render_cache,
        layout_tweaks=app.layout_tweaks,
        per_key_layout_tweaks=app.per_key_layout_tweaks,
        keymap=app.keymap,
        selected_slot_id=probe_selected_slot_id_fn(app),
        selected_key_id=probe_selected_key_id_fn(app),
        physical_layout=physical_layout,
        legend_pack_id=selected_layout_legend_pack_fn(app.cfg, physical_layout=physical_layout),
        slot_overrides=app.layout_slot_overrides,
    )


def on_click(
    app: _CalibratorAppLike,
    event: _ClickEvent,
    *,
    hit_test_fn: _HitTestByPointFn,
    keymap_cells_for: _KeymapCellsForFn,
    physical_layout_id_fn: PhysicalLayoutIdFn,
) -> None:
    if app._transform is None:
        return
    hit = hit_test_fn(event.x, event.y)
    if hit is None:
        app.probe.clear_selection()
        app.lbl_status.configure(text="No key hit")
    else:
        app.probe.selected_slot_id = str(hit.slot_id or hit.key_id)
        app.probe.selected_key_id = str(hit.key_id)
        mapped = keymap_cells_for(
            app.keymap,
            hit.key_id,
            slot_id=app.probe.selected_slot_id,
            physical_layout=physical_layout_id_fn(app),
        )
        app.lbl_status.configure(text=f"Selected {hit.label}" + (f" (mapped {mapped})" if mapped else " (unmapped)"))
    app._redraw()


def hit_test_point(
    app: _CalibratorAppLike,
    x: int,
    y: int,
    *,
    hit_test: _CanvasHitTestFn,
    visible_layout_keys_fn: _VisibleLayoutKeysFn,
    image_size: ImageSize,
) -> KeyDef | None:
    if app._transform is None:
        return None

    return hit_test(
        transform=app._transform,
        x=x,
        y=y,
        layout_tweaks=app.layout_tweaks,
        per_key_layout_tweaks=app.per_key_layout_tweaks,
        keys=visible_layout_keys_fn(app),
        image_size=image_size,
    )
