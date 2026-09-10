"""Tk page renderers and harvest helpers for the guided setup wizard."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import cast

from ..integration import SetupStep, calibration_skip_validation, legend_pack_choices
from ..preflight import PreflightMode
from .wizard_shared import (
    PreflightResolver,
    SlotStatesFactory,
    TkModule,
    TtkModule,
    WizardHost,
)

_TkErrors = tuple[type[BaseException], ...]


def _layout_labels() -> tuple[list[str], dict[str, str], dict[str, str]]:
    from keyrgb.core.resources.layouts import LAYOUT_CATALOG

    labels = [layout.label for layout in LAYOUT_CATALOG]
    id_to_label = {layout.layout_id: layout.label for layout in LAYOUT_CATALOG}
    label_to_id = {layout.label: layout.layout_id for layout in LAYOUT_CATALOG}
    return labels, id_to_label, label_to_id


def harvest_current_page(host: WizardHost) -> None:
    if host.controller.current_step is SetupStep.OPTIONAL_KEYS:
        host._harvest_optional_keys()
    if host.controller.current_step is SetupStep.OVERLAY:
        host._harvest_overlay()


def retry_preflight(host: WizardHost, *, resolve_fn: PreflightResolver) -> None:
    if host.controller.child_running:
        return
    result = resolve_fn(host.editor)
    host.controller.preflight = result
    host.controller.rows = result.rows
    host.controller.cols = result.cols
    host.controller.last_message = result.message
    host._render()


def render_preflight_page(host: WizardHost, *, ttk_module: object) -> None:
    ttk_mod = cast(TtkModule, ttk_module)
    preflight = host.controller.preflight
    ttk_mod.Label(host._body, text="Step 1: Check keyboard access").grid(row=0, column=0, sticky="w")
    ttk_mod.Label(host._body, text=preflight.message, wraplength=420).grid(row=1, column=0, sticky="w", pady=(8, 0))
    if preflight.mode is PreflightMode.CONFIG_ONLY:
        ttk_mod.Label(
            host._body,
            text="Config-only continuation: live key flashing is unavailable and unverified. "
            "Layout and optional-key edits still apply at Finish.",
            wraplength=420,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
    if preflight.offer_retry:
        ttk_mod.Button(host._body, text="Retry", command=host._retry_preflight).grid(
            row=3,
            column=0,
            sticky="w",
            pady=(12, 0),
        )


def render_layout_page(
    host: WizardHost,
    *,
    ttk_module: object,
    layout_labels: tuple[list[str], dict[str, str], dict[str, str]],
) -> None:
    ttk_mod = cast(TtkModule, ttk_module)
    labels, id_to_label, label_to_id = layout_labels
    draft = host.controller.draft
    ttk_mod.Label(host._body, text="Step 2: Layout & legends").grid(row=0, column=0, sticky="w")

    ttk_mod.Label(host._body, text="Physical layout").grid(row=1, column=0, sticky="w", pady=(8, 0))
    layout_combo = ttk_mod.Combobox(host._body, values=labels, state="readonly", width=30)
    layout_combo.set(id_to_label.get(draft.physical_layout, labels[0]))
    layout_combo.grid(row=2, column=0, sticky="ew", pady=(4, 0))

    ttk_mod.Label(host._body, text="Legend pack").grid(row=3, column=0, sticky="w", pady=(8, 0))
    legend_combo = ttk_mod.Combobox(host._body, state="readonly", width=30)
    legend_state: dict[str, list[tuple[str, str]]] = {}

    def refresh_legends(layout_id: str) -> None:
        choices = legend_pack_choices(layout_id)
        legend_state["choices"] = choices
        id_map = {pack_id: label for pack_id, label in choices}
        legend_combo.configure(values=[label for _, label in choices])
        legend_combo.set(id_map.get(draft.legend_pack, "Default legends"))

    refresh_legends(draft.physical_layout or "auto")

    def on_layout_select(_event: object = None) -> None:
        draft.set_physical_layout(label_to_id.get(layout_combo.get(), "auto"))
        refresh_legends(draft.physical_layout)

    def on_legend_select(_event: object = None) -> None:
        label_map = {label: pack_id for pack_id, label in legend_state.get("choices", [])}
        draft.set_legend_pack(label_map.get(legend_combo.get(), "auto"))

    layout_combo.bind("<<ComboboxSelected>>", on_layout_select)
    legend_combo.bind("<<ComboboxSelected>>", on_legend_select)


def render_optional_keys_page(
    host: WizardHost,
    *,
    ttk_module: object,
    tk_module: object,
    tk_errors: _TkErrors,
    states: list[object],
) -> None:
    ttk_mod = cast(TtkModule, ttk_module)
    tk_mod = cast(TkModule, tk_module)
    draft = host.controller.draft
    ttk_mod.Label(host._body, text="Step 3: Optional keys").grid(row=0, column=0, columnspan=2, sticky="w")
    if not states:
        ttk_mod.Label(host._body, text="No optional keys for this layout.").grid(row=1, column=0, sticky="w")
        return
    for index, state in enumerate(states, start=1):
        slot_id = str(getattr(state, "slot_id", ""))
        default_label = str(getattr(state, "default_label", slot_id))
        override = draft.slot_overrides.get(slot_id, {})
        visible = bool(override.get("visible", True))
        var = tk_mod.BooleanVar(value=visible)
        host._option_vars[slot_id] = var

        def _toggle(slot: str = slot_id, value: tk.BooleanVar = var) -> None:
            try:
                shown = bool(value.get())
            except tk_errors:
                return
            current = dict(draft.slot_overrides.get(slot, {}))
            if shown:
                current.pop("visible", None)
            else:
                current["visible"] = False
            if current:
                draft.put_slot_override(slot, current)
            else:
                draft.remove_slot_override(slot)

        check = ttk_mod.Checkbutton(host._body, text=default_label, variable=var, command=_toggle)
        check.grid(row=index, column=0, sticky="w")
        label_text = str(override.get("label", "")) if isinstance(override.get("label"), str) else ""
        entry = ttk_mod.Entry(host._body, width=20)
        entry.insert(0, label_text)
        entry.grid(row=index, column=1, sticky="ew", padx=(8, 0))

        def _relabel(
            _event: object = None,
            slot: str = slot_id,
            widget: ttk.Entry = entry,
            default: str = default_label,
        ) -> None:
            try:
                text = widget.get().strip()
            except tk_errors:
                return
            current = dict(draft.slot_overrides.get(slot, {}))
            if text and text != default:
                current["label"] = text
            else:
                current.pop("label", None)
            if current:
                try:
                    draft.put_slot_override(slot, current)
                except (TypeError, ValueError):
                    pass
            else:
                draft.remove_slot_override(slot)

        entry.bind("<FocusOut>", _relabel)
        entry.bind("<Return>", _relabel)
        host._option_labels[slot_id] = entry


def render_calibration_page(host: WizardHost, *, ttk_module: object, tk_errors: _TkErrors) -> None:
    ttk_mod = cast(TtkModule, ttk_module)
    draft = host.controller.draft
    ttk_mod.Label(host._body, text="Step 4: Keymap calibration").grid(row=0, column=0, sticky="w")
    validation = calibration_skip_validation(draft.keymap, rows=host.controller.rows, cols=host.controller.cols)
    if validation.valid:
        summary = f"Current keymap covers the matrix ({validation.entry_count} keys, {validation.cell_count} cells)."
    else:
        summary = f"Current keymap is not ready: {validation.reason}."
    ttk_mod.Label(host._body, text=summary, wraplength=420).grid(row=1, column=0, sticky="w", pady=(8, 0))
    if host.controller.config_only and not validation.valid:
        ttk_mod.Label(
            host._body,
            text="Config-only mode: live key flashing is unavailable and unverified. "
            "Retry with the keyboard connected, or run live calibration, before continuing.",
            wraplength=420,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
    elif host.controller.config_only:
        ttk_mod.Label(
            host._body,
            text="Config-only mode: the existing keymap validates, so you may explicitly skip "
            "live calibration and continue.",
            wraplength=420,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
    launch_button = ttk_mod.Button(host._body, text="Launch guided calibrator", command=host._on_launch_calibrator)
    launch_button.grid(row=3, column=0, sticky="ew", pady=(12, 0))
    if host.controller.child_running or not host.controller.live:
        try:
            launch_button.configure(state="disabled")
        except tk_errors:
            pass


def render_overlay_page(
    host: WizardHost,
    *,
    ttk_module: object,
    fields: tuple[tuple[str, str], ...],
    defaults: dict[str, float],
) -> None:
    ttk_mod = cast(TtkModule, ttk_module)
    draft = host.controller.draft
    ttk_mod.Label(host._body, text="Step 5 (optional): Overlay alignment").grid(
        row=0, column=0, columnspan=2, sticky="w"
    )
    ttk_mod.Label(
        host._body,
        text="Global overlay tweaks only; per-key payloads stay untouched.",
        wraplength=420,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
    for index, (name, caption) in enumerate(fields, start=2):
        ttk_mod.Label(host._body, text=caption).grid(row=index, column=0, sticky="w", pady=(4, 0))
        entry = ttk_mod.Entry(host._body, width=12)
        current = draft.layout_tweaks.get(name, defaults[name])
        entry.insert(0, str(current))
        entry.grid(row=index, column=1, sticky="ew", padx=(8, 0), pady=(4, 0))
        host._overlay_entries[name] = entry


def render_review_page(host: WizardHost, *, ttk_module: object) -> None:
    ttk_mod = cast(TtkModule, ttk_module)
    draft = host.controller.draft
    validation = calibration_skip_validation(draft.keymap, rows=host.controller.rows, cols=host.controller.cols)
    ttk_mod.Label(host._body, text="Step 6: Review & finish").grid(row=0, column=0, sticky="w")
    lines = [
        f"Layout: {draft.physical_layout or '(unset)'}",
        f"Legends: {draft.legend_pack or 'auto'}",
        f"Optional overrides: {len(draft.slot_overrides)}",
        (
            f"Keymap: {validation.entry_count} keys / {validation.cell_count} cells "
            f"({'valid' if validation.valid else 'invalid: ' + validation.reason})"
        ),
        f"Overlay tweaks: {dict(draft.layout_tweaks) or 'defaults'}",
        f"Mode: {'config-only (no hardware apply)' if host.controller.config_only else 'live'}",
    ]
    ttk_mod.Label(host._body, text="\n".join(lines), justify="left").grid(row=1, column=0, sticky="w", pady=(8, 0))
    ttk_mod.Label(
        host._body,
        text="Finish writes setup once; a failed Finish restores the original state and keeps this open.",
        wraplength=420,
    ).grid(row=2, column=0, sticky="w", pady=(8, 0))


def harvest_overlay_values(host: WizardHost, *, tk_errors: _TkErrors) -> None:
    draft = host.controller.draft
    for name, entry in host._overlay_entries.items():
        try:
            raw = entry.get().strip()
        except tk_errors:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if name == "inset":
            value = max(0.0, min(0.20, value))
        try:
            draft.set_layout_tweak(name, value)
        except (TypeError, ValueError):
            continue


def harvest_optional_values(host: WizardHost, *, tk_errors: _TkErrors, slot_states_fn: SlotStatesFactory) -> None:
    draft = host.controller.draft
    for slot_id, entry in host._option_labels.items():
        try:
            text = entry.get().strip()
        except tk_errors:
            continue
        current = dict(draft.slot_overrides.get(slot_id, {}))
        state = next(
            (item for item in slot_states_fn(draft) if str(getattr(item, "slot_id", "")) == slot_id),
            None,
        )
        default_label = str(getattr(state, "default_label", slot_id))
        if text and text != default_label:
            current["label"] = text
        else:
            current.pop("label", None)
        if current:
            draft.put_slot_override(slot_id, current)
        else:
            draft.remove_slot_override(slot_id)
