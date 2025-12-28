from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


def _step_cell(
    *,
    current_cell: Tuple[int, int],
    delta: int,
    rows: int,
    cols: int,
) -> Tuple[int, int]:
    r, c = current_cell
    idx = (r * cols + c + delta) % (rows * cols)
    return idx // cols, idx % cols


@dataclass
class CalibrationProbeState:
    rows: int
    cols: int
    current_cell: Tuple[int, int] = (0, 0)
    selected_key_id: Optional[str] = None

    def prev_cell(self) -> Tuple[int, int]:
        self.current_cell = _step_cell(
            current_cell=self.current_cell,
            delta=-1,
            rows=self.rows,
            cols=self.cols,
        )
        return self.current_cell

    def next_cell(self) -> Tuple[int, int]:
        self.current_cell = _step_cell(
            current_cell=self.current_cell,
            delta=1,
            rows=self.rows,
            cols=self.cols,
        )
        return self.current_cell

    def clear_selection(self) -> None:
        self.selected_key_id = None
