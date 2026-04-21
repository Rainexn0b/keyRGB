"""Typed bootstrap state for the tray application facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from src.core.config import Config


class _TrayBootstrapWritable(Protocol):
    config: Config
    engine: object
    backend: object | None
    backend_probe: object | None
    backend_caps: object | None
    device_discovery: object | None
    selected_device_context: str
    _ite_rows: int
    _ite_cols: int


@dataclass(slots=True)
class TrayBootstrapState:
    config: Config
    engine: object
    power_manager_factory: object
    backend: object | None
    backend_probe: object | None
    backend_caps: object | None
    device_discovery: object | None
    selected_device_context: str
    ite_rows: int
    ite_cols: int

    def apply_to(self, tray: _TrayBootstrapWritable) -> None:
        tray.config = self.config
        tray.engine = self.engine
        tray.backend = self.backend
        tray.backend_probe = self.backend_probe
        tray.backend_caps = self.backend_caps
        tray.device_discovery = self.device_discovery
        tray.selected_device_context = self.selected_device_context
        tray._ite_rows = self.ite_rows
        tray._ite_cols = self.ite_cols