from __future__ import annotations


def launch_perkey_editor() -> None:
    from .editor import PerKeyEditor

    PerKeyEditor().run()


def main() -> None:
    launch_perkey_editor()
