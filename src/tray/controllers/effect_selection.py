from __future__ import annotations

try:
    # Module-level import so tests (and callers) can monkeypatch `profiles`.
    from src.core.profile import profiles
except Exception:  # pragma: no cover
    profiles = None


def _ensure_config_per_key_colors_loaded(config) -> None:
    """Ensure `config.per_key_colors` has a value, if possible.

    Used when switching into per-key effects so the keyboard isn't left blank.
    """

    try:
        existing = dict(getattr(config, "per_key_colors", {}) or {})
    except Exception:
        existing = {}

    if existing:
        return

    try:
        prof = profiles
        if prof is None:
            from src.core.profile import profiles as prof  # type: ignore[no-redef]

        active = prof.get_active_profile()
        colors = prof.load_per_key_colors(active)
        if colors:
            config.per_key_colors = colors
    except Exception:
        return


def apply_effect_selection(tray, *, effect_name: str) -> None:
    """Apply an effect selection coming from the tray menu.

    Expects `effect_name` to already be normalized (see `src.tray.menu.normalize_effect_label`).
    """

    caps = getattr(tray, "backend_caps", None)
    per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True

    if effect_name in {"none", "stop"}:
        tray.engine.stop()
        with tray.engine.kb_lock:
            tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
        tray.config.effect = "none"
        tray.is_off = False
        return

    # Block unsupported effect families early.
    if effect_name in {"rainbow", "breathing", "wave", "ripple", "marquee", "raindrop", "aurora", "fireworks"}:
        if not hw_effects_supported:
            tray.config.effect = "none"
            tray.engine.stop()
            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            tray.is_off = False
            return

    if effect_name in ("perkey", "perkey breathing", "perkey pulse"):
        if not per_key_supported:
            tray.config.effect = "none"
            tray.engine.stop()
            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            tray.is_off = False
            return
        _ensure_config_per_key_colors_loaded(tray.config)

    if effect_name in ("perkey breathing", "perkey pulse"):
        effect_name = effect_name.replace(" ", "_")
        tray.engine.per_key_colors = dict(getattr(tray.config, "per_key_colors", {}))

    tray.config.effect = effect_name
    tray._start_current_effect()
