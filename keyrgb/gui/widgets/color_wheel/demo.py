from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .color_wheel import ColorWheel


def main() -> None:
    icon_fn: Callable[[tk.Misc], None] | None = None
    try:
        from keyrgb.gui.utils.window_icon import apply_keyrgb_window_icon

        icon_fn = apply_keyrgb_window_icon
    except ImportError:
        pass

    root = tk.Tk()
    root.title("Color Wheel Test")
    if icon_fn is not None:
        icon_fn(root)
    root.geometry("400x500")

    def on_color_change(red: int, green: int, blue: int) -> None:
        print(f"Color changed to RGB({red}, {green}, {blue})")

    wheel = ColorWheel(root, size=350, initial_color=(255, 0, 0), callback=on_color_change)
    wheel.pack(padx=20, pady=20)
    root.mainloop()


if __name__ == "__main__":
    main()
