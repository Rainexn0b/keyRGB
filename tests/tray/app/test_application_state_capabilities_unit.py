from __future__ import annotations

from types import SimpleNamespace

from src.core.backends.base import BackendCapabilities
from src.tray.app._application_state import TrayBootstrapState


def _caps(*, color: bool) -> BackendCapabilities:
    return BackendCapabilities(
        brightness=True,
        per_key=False,
        color=color,
        hardware_effects=False,
        palette=False,
    )


def test_bootstrap_keeps_tray_capabilities_synchronized_with_engine_refreshes() -> None:
    class PublishingEngine:
        def __init__(self) -> None:
            self.callback = None

        def set_backend_capabilities_changed_callback(self, callback) -> None:
            self.callback = callback
            callback(_caps(color=False))

    engine = PublishingEngine()
    state = TrayBootstrapState(
        config=object(),  # type: ignore[arg-type]
        engine=engine,
        power_manager_factory=object(),
        backend=object(),
        backend_probe=None,
        backend_caps=_caps(color=True),
        device_discovery=None,
        selected_device_context="keyboard",
        ite_rows=6,
        ite_cols=21,
    )
    tray = SimpleNamespace()

    state.apply_to(tray)
    assert tray.backend_caps == _caps(color=False)

    assert engine.callback is not None
    engine.callback(_caps(color=True))
    assert tray.backend_caps == _caps(color=True)
