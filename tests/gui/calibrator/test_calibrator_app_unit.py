from __future__ import annotations

from src.gui.calibrator import app as calibrator_app
from src.gui.perkey import hardware as perkey_hardware


def test_calibrator_uses_backend_dimensions() -> None:
    assert calibrator_app.MATRIX_ROWS == perkey_hardware.NUM_ROWS
    assert calibrator_app.MATRIX_COLS == perkey_hardware.NUM_COLS
