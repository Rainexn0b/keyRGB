from __future__ import annotations

from dataclasses import dataclass


def _step_cell(
    *,
    current_cell: tuple[int, int],
    delta: int,
    rows: int,
    cols: int,
) -> tuple[int, int]:
    r, c = current_cell
    idx = (r * cols + c + delta) % (rows * cols)
    return idx // cols, idx % cols


@dataclass
class CalibrationProbeState:
    rows: int
    cols: int
    current_cell: tuple[int, int] = (0, 0)
    selected_key_id: str | None = None
    selected_slot_id: str | None = None

    def prev_cell(self) -> tuple[int, int]:
        self.current_cell = _step_cell(
            current_cell=self.current_cell,
            delta=-1,
            rows=self.rows,
            cols=self.cols,
        )
        return self.current_cell

    def next_cell(self) -> tuple[int, int]:
        self.current_cell = _step_cell(
            current_cell=self.current_cell,
            delta=1,
            rows=self.rows,
            cols=self.cols,
        )
        return self.current_cell

    def clear_selection(self) -> None:
        self.selected_key_id = None
        self.selected_slot_id = None
