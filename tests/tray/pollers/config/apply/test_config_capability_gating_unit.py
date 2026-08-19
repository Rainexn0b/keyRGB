from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from keyrgb.tray.pollers.config_polling_internal._post_fast_path_apply import apply_post_fast_path_execution


def test_persisted_perkey_config_falls_back_to_uniform_without_capability() -> None:
    tray = MagicMock()
    tray.backend_caps = None
    tray.config = SimpleNamespace(effect="perkey")
    tray.is_off = False
    current = SimpleNamespace(effect="perkey", brightness=25)
    apply_perkey = MagicMock()
    apply_uniform = MagicMock()

    result = apply_post_fast_path_execution(
        tray,
        current=current,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="config changed",
        last_apply_warn_at=0.0,
        monotonic_fn=lambda: 1.0,
        is_device_disconnected_fn=lambda _exc: False,
        sync_reactive_fn=MagicMock(),
        apply_perkey_fn=apply_perkey,
        apply_uniform_fn=apply_uniform,
        apply_effect_fn=MagicMock(),
        runtime_boundary_exceptions=(RuntimeError,),
    )

    assert result == 0.0
    assert tray.config.effect == "none"
    apply_perkey.assert_not_called()
    apply_uniform.assert_called_once_with(tray, current, cause="config changed: per-key unsupported")
