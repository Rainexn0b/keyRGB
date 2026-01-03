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

    try:
        effect_name = str(effect_name).strip().lower()
    except Exception:
        effect_name = "none"

    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            log_event("menu", "select_effect", old=str(prev_effect), new=str(effect_name))
        except Exception:
            pass

    # Backward compatibility: these legacy per-key software animations were removed.
    # Treat any selection or persisted value as plain per-key mode.
    perkey_aliases = {"perkey breathing", "perkey pulse", "perkey_breathing", "perkey_pulse"}
    if effect_name in perkey_aliases:
        effect_name = "perkey"

    # If the user is currently in a per-key mode and temporarily starts a non-per-key
    # effect, remember that we should restore per-key lighting when they stop the effect.
    try:
        prev_effect = getattr(tray.config, "effect", "none")
    except Exception:
        prev_effect = "none"

    if effect_name in {"none", "stop"}:
        restore_effect = getattr(tray.config, "return_effect_after_effect", None)

        if restore_effect in perkey_aliases:
            restore_effect = "perkey"

        tray.engine.stop()
        if restore_effect == "perkey" and per_key_supported:
            tray.config.return_effect_after_effect = None
            tray.config.effect = restore_effect
            _ensure_config_per_key_colors_loaded(tray.config)
            try:
                tray.engine.per_key_colors = dict(getattr(tray.config, "per_key_colors", {}) or {})
            except Exception:
                pass
            tray._start_current_effect()
            tray.is_off = False
            return

        # Clear any stale persisted restore target if we can't honor it.
        try:
            tray.config.return_effect_after_effect = None
        except Exception:
            pass

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

    if effect_name == "perkey":
        if not per_key_supported:
            tray.config.effect = "none"
            tray.engine.stop()
            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            tray.is_off = False
            return
        _ensure_config_per_key_colors_loaded(tray.config)

        try:
            tray.engine.per_key_colors = dict(getattr(tray.config, "per_key_colors", {}) or {})
        except Exception:
            pass

        # Explicit per-key selection overrides any pending restore state.
        tray.config.return_effect_after_effect = None

    # When starting a non-per-key effect from a per-key state, remember we should
    # restore per-key when the user stops the effect.
    if effect_name not in {"none", "stop", "perkey"}:
        prev_norm = prev_effect
        if prev_norm in perkey_aliases:
            prev_norm = "perkey"
        if prev_norm == "perkey":
            tray.config.return_effect_after_effect = "perkey"
            try:
                _ensure_config_per_key_colors_loaded(tray.config)
                tray.engine.per_key_colors = dict(getattr(tray.config, "per_key_colors", {}) or {})
            except Exception:
                pass
        else:
            # If we previously started an effect from per-key mode, keep the
            # restore target sticky while the user cycles through other effects.
            existing_restore = getattr(tray.config, "return_effect_after_effect", None)
            if existing_restore != "perkey":
                tray.config.return_effect_after_effect = None
                # Explicitly clear any stale per-key snapshot so software effects
                # render in uniform mode unless the user was actually in per-key.
                try:
                    tray.engine.per_key_colors = None
                except Exception:
                    pass

    tray.config.effect = effect_name
    tray._start_current_effect()
