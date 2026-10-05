"""Small hardware-access setup window.

Work runs off the Tk event loop. Closing the window does not record dismissal
and does not record that setup succeeded.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from keyrgb.gui.hardware_access import HardwareAccessOutcome, HardwareAccessRequest, run_hardware_access
from keyrgb.gui.hardware_access_offer import (
    format_setup_result,
    remember_offer_dismissed,
    setup_explanation,
    user_in_video,
)
from keyrgb.gui.utils.tk_async import run_in_thread

_TK_ERRORS = (tk.TclError, OSError)


class HardwareAccessSetupController:
    """Duplicate-submission and dismissal state for the setup window."""

    def __init__(
        self,
        *,
        on_status: Callable[[str], None],
        remember_dismissal: Callable[[], bool] = remember_offer_dismissed,
        in_video: bool | None = None,
    ) -> None:
        self._on_status = on_status
        self._remember_dismissal = remember_dismissal
        self._in_video = in_video
        self._busy = False
        self.dismissed = False

    @property
    def busy(self) -> bool:
        return self._busy

    def start(self) -> bool:
        if self._busy:
            return False
        self._busy = True
        return True

    def complete(self, outcome: HardwareAccessOutcome) -> None:
        self._busy = False
        self._on_status(format_setup_result(outcome, in_video=self._in_video))

    def not_now(self) -> None:
        self.dismissed = self._remember_dismissal()
        if not self.dismissed:
            self._on_status("Could not remember Not now. Setup was not marked configured.")


def _video_membership() -> bool | None:
    try:
        import grp
        import os

        names = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
    except (ImportError, KeyError, OSError):
        return None
    return user_in_video(names)


def build_hardware_access_window(
    root: tk.Misc,
    *,
    runner: Callable[[HardwareAccessRequest], HardwareAccessOutcome] = run_hardware_access,
    controller: HardwareAccessSetupController | None = None,
) -> HardwareAccessSetupController:
    """Build the setup controls on ``root``. Returns the controller the buttons use."""

    explanation = ttk.Label(
        root,
        text=setup_explanation(),
        justify="left",
        wraplength=480,
    )
    explanation.pack(anchor="w", fill="x", padx=12, pady=(12, 8))

    defaults = HardwareAccessRequest()
    reactive = tk.BooleanVar(master=root, value=defaults.reactive_input)
    power = tk.BooleanVar(master=root, value=defaults.power_controls)
    ttk.Checkbutton(
        root,
        text="Reactive input (allows observing keypresses)",
        variable=reactive,
    ).pack(anchor="w", padx=12)
    ttk.Checkbutton(
        root,
        text="Power controls (included by default; not required for keyboard color)",
        variable=power,
    ).pack(anchor="w", padx=12, pady=(0, 8))

    status = ttk.Label(root, text="", justify="left", wraplength=480)
    status.pack(anchor="w", fill="x", padx=12, pady=(0, 8))

    def show(text: str) -> None:
        status.configure(text=text)

    owned = controller or HardwareAccessSetupController(on_status=show, in_video=_video_membership())
    buttons = ttk.Frame(root)
    buttons.pack(fill="x", padx=12, pady=(0, 12))
    setup_button = ttk.Button(buttons, text="Set up")
    not_now = ttk.Button(buttons, text="Not now")

    def on_not_now() -> None:
        owned.not_now()
        try:
            root.destroy()
        except _TK_ERRORS:
            return

    def on_done(outcome: HardwareAccessOutcome) -> None:
        owned.complete(outcome)
        try:
            setup_button.configure(state="normal")
        except _TK_ERRORS:
            return

    def on_setup() -> None:
        if not owned.start():
            return
        setup_button.configure(state="disabled")
        request = HardwareAccessRequest(
            reactive_input=bool(reactive.get()),
            power_controls=bool(power.get()),
        )
        run_in_thread(root, lambda: runner(request), on_done)

    setup_button.configure(command=on_setup)
    not_now.configure(command=on_not_now)
    setup_button.pack(side="left")
    not_now.pack(side="left", padx=(8, 0))
    return owned


def main() -> None:
    try:
        root = tk.Tk()
    except _TK_ERRORS:
        print(setup_explanation())
        print("Set up hardware access from a terminal: install.sh --hardware-access-only")
        return
    root.title("KeyRGB - Set up hardware access")
    build_hardware_access_window(root)
    root.mainloop()


if __name__ == "__main__":
    main()
