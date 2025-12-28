from __future__ import annotations


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
        from src.core import profiles

        active = profiles.get_active_profile()
        colors = profiles.load_per_key_colors(active)
        if colors:
            config.per_key_colors = colors
    except Exception:
        return


def apply_effect_selection(tray, *, effect_name: str) -> None:
    """Apply an effect selection coming from the tray menu.

    Expects `effect_name` to already be normalized (see `src.tray.menu.normalize_effect_label`).
    """

    if effect_name in {"none", "stop"}:
        tray.engine.stop()
        with tray.engine.kb_lock:
            tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
        tray.config.effect = "none"
        tray.is_off = False
        return

    if effect_name in ("perkey", "perkey breathing", "perkey pulse"):
        _ensure_config_per_key_colors_loaded(tray.config)

    if effect_name in ("perkey breathing", "perkey pulse"):
        effect_name = effect_name.replace(" ", "_")
        tray.engine.per_key_colors = dict(getattr(tray.config, "per_key_colors", {}))

    tray.config.effect = effect_name
    tray._start_current_effect()
