from __future__ import annotations

import tkinter as tk

from .color_wheel import ColorWheel


def main() -> None:
    try:
        from src.gui.utils.window_icon import apply_keyrgb_window_icon
    except Exception:  # @quality-exception exception-transparency: window icon import is optional; demo runs without it
        apply_keyrgb_window_icon = None  # type: ignore[assignment]

    root = tk.Tk()
    root.title("Color Wheel Test")
    if apply_keyrgb_window_icon is not None:
        apply_keyrgb_window_icon(root)
    root.geometry("400x500")

    def on_color_change(r: int, g: int, b: int) -> None:
        print(f"Color changed to RGB({r}, {g}, {b})")

    wheel = ColorWheel(root, size=350, initial_color=(255, 0, 0), callback=on_color_change)
    wheel.pack(padx=20, pady=20)
    root.mainloop()


if __name__ == "__main__":
    main()
