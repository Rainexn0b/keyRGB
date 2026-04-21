#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class _GeometryRoot(Protocol):
    def update_idletasks(self) -> None: ...

    def geometry(self, value: str) -> None: ...


class _MainFrame(Protocol):
    def winfo_reqheight(self) -> int: ...

    def winfo_reqwidth(self) -> int: ...


def apply_window_geometry(
    *,
    root: _GeometryRoot,
    main_frame: _MainFrame,
    compute_centered_window_geometry: Callable[..., str],
    geometry_apply_errors: tuple[type[BaseException], ...],
) -> None:
    try:
        root.update_idletasks()
        geometry = compute_centered_window_geometry(
            root,
            content_height_px=int(main_frame.winfo_reqheight()),
            content_width_px=int(main_frame.winfo_reqwidth()),
            footer_height_px=0,
            chrome_padding_px=48,
            default_w=1240,
            default_h=920,
            screen_ratio_cap=0.95,
        )
        root.geometry(geometry)
    except geometry_apply_errors:
        return