from __future__ import annotations

from pathlib import Path
from typing import Any


def keymap_path_for_active_profile(*, get_active_profile_name: Any, keymap_path: Any) -> Path:
    return keymap_path(get_active_profile_name())


def save_keymap_for_active_profile(
    keymap: dict[str, tuple[tuple[int, int], ...]],
    *,
    physical_layout: str | None,
    get_active_profile_name: Any,
    save_keymap: Any,
) -> None:
    save_keymap(get_active_profile_name(), keymap, physical_layout=physical_layout)


def parse_default_keymap(
    layout_id: str,
    *,
    profiles: Any,
    get_default_keymap: Any,
    sanitize_keymap_cells: Any,
    num_rows: int,
    num_cols: int,
) -> dict[str, tuple[tuple[int, int], ...]]:
    return sanitize_keymap_cells(
        profiles.normalize_keymap(get_default_keymap(layout_id), physical_layout=layout_id),
        num_rows=num_rows,
        num_cols=num_cols,
    )


def resolved_layout_label(layout_id: str, *, resolve_layout_id: Any, layout_labels: dict[str, str]) -> str:
    resolved_layout = resolve_layout_id(layout_id)
    return layout_labels.get(resolved_layout, resolved_layout.upper())


def load_profile_state(
    profile_name: str,
    *,
    physical_layout: str,
    load_keymap: Any,
    load_layout_global: Any,
    load_layout_per_key: Any,
    load_layout_slots: Any,
    sanitize_keymap_cells: Any,
    num_rows: int,
    num_cols: int,
) -> tuple[
    dict[str, tuple[tuple[int, int], ...]],
    dict[str, float],
    dict[str, dict[str, float]],
    dict[str, dict[str, object]],
]:
    keymap = sanitize_keymap_cells(
        load_keymap(profile_name, physical_layout=physical_layout),
        num_rows=num_rows,
        num_cols=num_cols,
    )
    layout_tweaks = load_layout_global(profile_name, physical_layout=physical_layout)
    per_key_layout_tweaks = load_layout_per_key(profile_name, physical_layout=physical_layout)
    layout_slot_overrides = load_layout_slots(profile_name, physical_layout)
    return keymap, layout_tweaks, per_key_layout_tweaks, layout_slot_overrides


def selected_layout_legend_pack(cfg: object, *, physical_layout: str, load_layout_legend_pack: Any) -> str | None:
    requested = str(getattr(cfg, "layout_legend_pack", "auto") or "auto").strip().lower()
    if not requested or requested == "auto":
        return None

    pack = load_layout_legend_pack(requested)
    if not pack:
        return None

    resolved_pack_layout = str(pack.get("layout_id") or physical_layout).strip().lower()
    return requested if resolved_pack_layout == str(physical_layout or "auto").strip().lower() else None


def physical_layout_id(app: Any) -> str:
    cfg = getattr(app, "cfg", None)
    return str(getattr(cfg, "physical_layout", "auto") or "auto")


def visible_layout_keys(
    app: Any,
    *,
    get_layout_keys: Any,
    selected_layout_legend_pack_fn: Any,
    physical_layout_id_fn: Any,
) -> list[Any]:
    physical_layout = physical_layout_id_fn(app)
    cfg = getattr(app, "cfg", None)
    return list(
        get_layout_keys(
            physical_layout,
            legend_pack_id=selected_layout_legend_pack_fn(cfg, physical_layout=physical_layout)
            if cfg is not None
            else None,
            slot_overrides=getattr(app, "layout_slot_overrides", None),
        )
    )


def visible_key_for_slot_id(app: Any, slot_id: str | None, *, visible_layout_keys_fn: Any) -> Any | None:
    normalized_slot_id = str(slot_id or "").strip()
    if not normalized_slot_id:
        return None

    for key in visible_layout_keys_fn(app):
        if str(getattr(key, "slot_id", None) or key.key_id) == normalized_slot_id:
            return key
    return None


def probe_selected_slot_id(app: Any, *, visible_layout_keys_fn: Any) -> str | None:
    probe = getattr(app, "probe", None)
    selected_slot_id = str(getattr(probe, "selected_slot_id", "") or "").strip()
    if selected_slot_id:
        return selected_slot_id

    selected_key_id = str(getattr(probe, "selected_key_id", "") or "").strip()
    if not selected_key_id:
        return None

    for key in visible_layout_keys_fn(app):
        if str(key.key_id) == selected_key_id:
            return str(getattr(key, "slot_id", None) or key.key_id)
    return selected_key_id


def probe_selected_key_id(
    app: Any,
    *,
    probe_selected_slot_id_fn: Any,
    visible_key_for_slot_id_fn: Any,
) -> str | None:
    slot_id = probe_selected_slot_id_fn(app)
    key = visible_key_for_slot_id_fn(app, slot_id)
    if key is not None:
        return str(key.key_id)

    probe = getattr(app, "probe", None)
    selected_key_id = str(getattr(probe, "selected_key_id", "") or "").strip()
    return selected_key_id or None


def set_backdrop(
    app: Any,
    *,
    askopenfilename: Any,
    save_backdrop_image: Any,
    save_backdrop_mode: Any,
    update_errors: tuple[type[BaseException], ...],
) -> None:
    path = askopenfilename(
        title="Select keyboard backdrop image",
        filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All files", "*.*")],
    )
    if not path:
        return
    try:
        save_backdrop_image(profile_name=app.profile_name, source_path=path)
        save_backdrop_mode("custom", app.profile_name)
        app._backdrop_mode_var.set("custom")
        app._backdrop_mode_combo.set("Custom image")
        app._load_deck_image()
        app._redraw()
        app.lbl_status.configure(text="Backdrop updated")
    except update_errors:
        app.lbl_status.configure(text="Failed to set backdrop")


def reset_backdrop(
    app: Any, *, reset_backdrop_image: Any, save_backdrop_mode: Any, update_errors: tuple[type[BaseException], ...]
) -> None:
    try:
        reset_backdrop_image(app.profile_name)
        save_backdrop_mode("builtin", app.profile_name)
        app._backdrop_mode_var.set("builtin")
        app._backdrop_mode_combo.set("Built-in seed")
        app._load_deck_image()
        app._redraw()
        app.lbl_status.configure(text="Backdrop reset")
    except update_errors:
        app.lbl_status.configure(text="Failed to reset backdrop")


def on_backdrop_mode_changed(
    app: Any,
    *,
    backdrop_mode_labels: dict[str, str],
    save_backdrop_mode: Any,
    update_errors: tuple[type[BaseException], ...],
) -> None:
    label = app._backdrop_mode_combo.get()
    for mode, mode_label in backdrop_mode_labels.items():
        if mode_label == label:
            app._backdrop_mode_var.set(mode)
            break
    else:
        app._backdrop_mode_var.set("builtin")

    try:
        save_backdrop_mode(app._backdrop_mode_var.get(), app.profile_name)
        app._load_deck_image()
        app._redraw()
    except update_errors:
        app.lbl_status.configure(text="Failed to update backdrop mode")


def reset_keymap_defaults(
    app: Any,
    *,
    parse_default_keymap_fn: Any,
    sanitize_keymap_cells: Any,
    num_rows: int,
    num_cols: int,
    physical_layout_id_fn: Any,
    resolved_layout_label_fn: Any,
) -> None:
    physical_layout = physical_layout_id_fn(app)
    app.keymap = sanitize_keymap_cells(parse_default_keymap_fn(physical_layout), num_rows=num_rows, num_cols=num_cols)
    app._redraw()
    app.lbl_status.configure(text=f"Reset keymap to {resolved_layout_label_fn(physical_layout)} defaults")


def restore_original_config(app: Any) -> None:
    app.preview.restore()


def on_close(app: Any) -> None:
    app._restore_original_config()
    app.destroy()


def load_deck_image(app: Any, *, load_backdrop_image: Any) -> None:
    app._deck_pil = load_backdrop_image(app.profile_name)
    app._deck_render_cache.clear()


def apply_current_probe(app: Any) -> None:
    row, col = app.probe.current_cell
    app.lbl_cell.configure(text=f"Probing matrix cell: ({row}, {col})")
    app.preview.apply_probe_cell(row, col)
    app.after(50, lambda: None)


def prev_cell(app: Any) -> None:
    app.probe.prev_cell()
    app._apply_current_probe()


def next_cell(app: Any) -> None:
    app.probe.next_cell()
    app._apply_current_probe()


def skip_cell(app: Any) -> None:
    app.probe.clear_selection()
    app.lbl_status.configure(text="Skipped. Move to next cell.")
    app._next()


def assign_current_cell(
    app: Any,
    *,
    probe_selected_slot_id_fn: Any,
    probe_selected_key_id_fn: Any,
    keymap_cells_for: Any,
    physical_layout_id_fn: Any,
) -> None:
    slot_id = probe_selected_slot_id_fn(app)
    key_id = probe_selected_key_id_fn(app)
    if not slot_id and not key_id:
        app.lbl_status.configure(text="Select a key on the image first")
        return
    key_identity = str(slot_id or key_id)
    display_key_id = str(key_id or key_identity)
    cells = list(
        keymap_cells_for(app.keymap, display_key_id, slot_id=slot_id, physical_layout=physical_layout_id_fn(app))
    )
    if app.probe.current_cell not in cells:
        cells.append(app.probe.current_cell)
    app.keymap[key_identity] = tuple(cells)
    app.lbl_status.configure(text=f"Assigned {display_key_id} -> {app.probe.current_cell} ({len(cells)} cell(s))")
    app._redraw()
    app._next()


def save_current_keymap(app: Any, *, save_keymap_fn: Any, keymap_path_fn: Any, physical_layout_id_fn: Any) -> None:
    save_keymap_fn(app.keymap, physical_layout=physical_layout_id_fn(app))
    app.lbl_status.configure(text=f"Saved to {str(keymap_path_fn())}")


def save_and_close(app: Any) -> None:
    app._save()
    app._restore_original_config()
    app.destroy()


def redraw(
    app: Any,
    *,
    redraw_calibration_canvas: Any,
    probe_selected_slot_id_fn: Any,
    probe_selected_key_id_fn: Any,
    physical_layout_id_fn: Any,
    selected_layout_legend_pack_fn: Any,
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
    app: Any,
    event: Any,
    *,
    hit_test_fn: Any,
    keymap_cells_for: Any,
    physical_layout_id_fn: Any,
) -> None:
    if app._transform is None:
        return
    hit = hit_test_fn(event.x, event.y)
    if hit is None:
        app.probe.clear_selection()
        app.lbl_status.configure(text="No key hit")
    else:
        app.probe.selected_slot_id = str(getattr(hit, "slot_id", None) or hit.key_id)
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
    app: Any,
    x: int,
    y: int,
    *,
    hit_test: Any,
    visible_layout_keys_fn: Any,
    image_size: tuple[int, int],
) -> Any | None:
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
