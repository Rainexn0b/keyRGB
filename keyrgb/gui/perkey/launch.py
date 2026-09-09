from __future__ import annotations


def launch_perkey_editor() -> None:
    from .editor import PerKeyEditor

    PerKeyEditor().run()


def main() -> None:
    from keyrgb.gui import single_instance

    single_instance.acquire_gui_instance_or_exit("perkey")
    launch_perkey_editor()
