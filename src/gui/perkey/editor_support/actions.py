from __future__ import annotations


def set_status(editor: object, message: str) -> None:
    from ..ui import status

    status.set_status(editor, message)


def no_keymap_found_initial() -> str:
    from ..ui import status

    return status.no_keymap_found_initial()


def save_layout_tweaks(editor: object, *, profiles: object) -> None:
    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.save_layout_tweaks(editor, profiles=profiles, status=status)


def reset_layout_tweaks(editor: object) -> None:
    from src.core.resources.defaults import get_default_layout_tweaks

    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.reset_layout_tweaks(
        editor,
        get_default_layout_tweaks=get_default_layout_tweaks,
        status=status,
    )


def auto_sync_per_key_overlays(editor: object) -> None:
    from .. import overlay
    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.auto_sync_per_key_overlays(editor, overlay=overlay, status=status)


def run_calibrator(editor: object) -> None:
    from ..ui import calibrator

    calibrator.run_keymap_calibrator_ui(editor)


def reload_keymap(editor: object) -> None:
    from ..ui import keymap

    keymap.reload_keymap_ui(editor)


def commit(editor: object, *, force: bool, hardware: object, last_non_black_color_or: object) -> None:
    from .. import color_utils, keyboard_apply
    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.commit(
        editor,
        force=force,
        hardware=hardware,
        color_utils=color_utils,
        keyboard_apply=keyboard_apply,
        status=status,
        last_non_black_color_or=last_non_black_color_or,
    )


def on_wheel_color_change(editor: object, r: int, g: int, b: int, *, num_rows: int, num_cols: int) -> None:
    from ..ui import wheel_apply

    wheel_apply.on_wheel_color_change_ui(editor, r, g, b, num_rows=num_rows, num_cols=num_cols)


def on_wheel_color_release(editor: object, r: int, g: int, b: int, *, num_rows: int, num_cols: int) -> None:
    from ..ui import wheel_apply

    wheel_apply.on_wheel_color_release_ui(editor, r, g, b, num_rows=num_rows, num_cols=num_cols)


def set_backdrop(editor: object) -> None:
    from ..ui import backdrop

    backdrop.set_backdrop_ui(editor)


def reset_backdrop(editor: object) -> None:
    from ..ui import backdrop

    backdrop.reset_backdrop_ui(editor)


def fill_all(editor: object, *, num_rows: int, num_cols: int) -> None:
    from ..ui import bulk_color

    bulk_color.fill_all_ui(editor, num_rows=num_rows, num_cols=num_cols)


def ensure_full_map(editor: object, *, num_rows: int, num_cols: int) -> None:
    from ..ui import full_map

    full_map.ensure_full_map_ui(editor, num_rows=num_rows, num_cols=num_cols)


def clear_all(editor: object, *, num_rows: int, num_cols: int) -> None:
    from ..ui import bulk_color

    bulk_color.clear_all_ui(editor, num_rows=num_rows, num_cols=num_cols)


def new_profile(editor: object) -> None:
    from ..ui import profile_actions

    profile_actions.new_profile_ui(editor)


def activate_profile(editor: object) -> None:
    from ..ui import profile_actions

    profile_actions.activate_profile_ui(editor)


def save_profile(editor: object) -> None:
    from ..ui import profile_actions

    profile_actions.save_profile_ui(editor)


def delete_profile(editor: object) -> None:
    from ..ui import profile_actions

    profile_actions.delete_profile_ui(editor)


def set_default_profile(editor: object) -> None:
    from ..ui import profile_actions

    profile_actions.set_default_profile_ui(editor)


def reset_layout_defaults(editor: object) -> None:
    from ..ui import profile_actions

    profile_actions.reset_layout_defaults_ui(editor)


def load_keymap(editor: object, *, profiles: object, hardware: object) -> dict[str, tuple[tuple[int, int], ...]]:
    from .. import profile_management
    from . import runtime as editor_runtime

    return editor_runtime.load_keymap(
        editor,
        profiles=profiles,
        profile_management=profile_management,
        hardware=hardware,
    )
