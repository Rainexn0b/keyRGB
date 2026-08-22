from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..ui._profile_actions_support import _PerKeyProfileEditorProtocol
    from ..ui.backdrop import _BackdropEditorProtocol
    from ..ui.bulk_color import _BulkColorEditorProtocol
    from ..ui.calibrator import _CalibratorEditorProtocol
    from ..ui.full_map import _FullMapEditorProtocol
    from ..ui.wheel_apply import _WheelApplyEditorProtocol


def set_status(editor: object, message: str) -> None:
    from ..ui import status

    status.set_status(editor, message)


def no_keymap_found_initial() -> str:
    from ..ui import status

    return status.no_keymap_found_initial()


def save_layout_tweaks(editor: object, *, profiles: object) -> None:
    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.save_layout_tweaks(
        cast(editor_runtime._Editor, editor),
        profiles=cast(editor_runtime._ProfilesModule, profiles),
        status=cast(editor_runtime._StatusModule, status),
    )


def reset_layout_tweaks(editor: object) -> None:
    from keyrgb.core.resources.defaults import get_default_layout_tweaks

    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.reset_layout_tweaks(
        cast(editor_runtime._Editor, editor),
        get_default_layout_tweaks=get_default_layout_tweaks,
        status=cast(editor_runtime._StatusModule, status),
    )


def auto_sync_per_key_overlays(editor: object) -> None:
    from .. import overlay
    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.auto_sync_per_key_overlays(
        cast(editor_runtime._Editor, editor),
        overlay=cast(editor_runtime._OverlayModule, overlay),
        status=cast(editor_runtime._StatusModule, status),
    )


def run_calibrator(editor: _CalibratorEditorProtocol) -> None:
    from ..ui import calibrator

    calibrator.run_keymap_calibrator_ui(editor)


def reload_keymap(editor: object) -> None:
    from ..ui import keymap

    keymap.reload_keymap_ui(editor)


def commit(
    editor: object,
    *,
    force: bool,
    hardware: object,
    last_non_black_color_or: Callable[[object, object], object],
) -> None:
    from .. import color_utils, keyboard_apply
    from ..ui import status
    from . import runtime as editor_runtime

    editor_runtime.commit(
        cast(editor_runtime._Editor, editor),
        force=force,
        hardware=cast(editor_runtime._HardwareModule, hardware),
        color_utils=cast(editor_runtime._ColorUtilsModule, color_utils),
        keyboard_apply=cast(editor_runtime._KeyboardApplyModule, keyboard_apply),
        status=cast(editor_runtime._StatusModule, status),
        last_non_black_color_or=last_non_black_color_or,
    )


def on_wheel_color_change(
    editor: _WheelApplyEditorProtocol, r: int, g: int, b: int, *, num_rows: int, num_cols: int
) -> None:
    from ..ui import wheel_apply

    wheel_apply.on_wheel_color_change_ui(editor, r, g, b, num_rows=num_rows, num_cols=num_cols)


def on_wheel_color_release(
    editor: _WheelApplyEditorProtocol, r: int, g: int, b: int, *, num_rows: int, num_cols: int
) -> None:
    from ..ui import wheel_apply

    wheel_apply.on_wheel_color_release_ui(editor, r, g, b, num_rows=num_rows, num_cols=num_cols)


def set_backdrop(editor: _BackdropEditorProtocol) -> None:
    from ..ui import backdrop

    backdrop.set_backdrop_ui(editor)


def reset_backdrop(editor: _BackdropEditorProtocol) -> None:
    from ..ui import backdrop

    backdrop.reset_backdrop_ui(editor)


def fill_all(editor: _BulkColorEditorProtocol, *, num_rows: int, num_cols: int) -> None:
    from ..ui import bulk_color

    bulk_color.fill_all_ui(editor, num_rows=num_rows, num_cols=num_cols)


def ensure_full_map(editor: _FullMapEditorProtocol, *, num_rows: int, num_cols: int) -> None:
    from ..ui import full_map

    full_map.ensure_full_map_ui(editor, num_rows=num_rows, num_cols=num_cols)


def clear_all(editor: _BulkColorEditorProtocol, *, num_rows: int, num_cols: int) -> None:
    from ..ui import bulk_color

    bulk_color.clear_all_ui(editor, num_rows=num_rows, num_cols=num_cols)


def new_profile(editor: _PerKeyProfileEditorProtocol) -> None:
    from ..ui import _profile_actions_ui as profile_actions_ui

    profile_actions_ui.new_profile_ui(editor)


def activate_profile(editor: _PerKeyProfileEditorProtocol) -> None:
    from ..ui import _profile_actions_ui as profile_actions_ui

    profile_actions_ui.activate_profile_ui(editor)


def save_profile(editor: _PerKeyProfileEditorProtocol) -> None:
    from ..ui import _profile_actions_ui as profile_actions_ui

    profile_actions_ui.save_profile_ui(editor)


def delete_profile(editor: _PerKeyProfileEditorProtocol) -> None:
    from ..ui import _profile_actions_ui as profile_actions_ui

    profile_actions_ui.delete_profile_ui(editor)


def set_default_profile(editor: _PerKeyProfileEditorProtocol) -> None:
    from ..ui import _profile_actions_ui as profile_actions_ui

    profile_actions_ui.set_default_profile_ui(editor)


def save_power_source_profile_policy(editor: _PerKeyProfileEditorProtocol) -> None:
    from ..ui import _profile_actions_ui as profile_actions_ui

    profile_actions_ui.save_power_source_profile_policy_ui(editor)


def reset_layout_defaults(editor: _PerKeyProfileEditorProtocol) -> None:
    from ..ui import profile_actions

    profile_actions.reset_layout_defaults_ui(editor)


def load_keymap(
    editor: object,
    *,
    profiles: object,
    hardware: object,
) -> dict[str, tuple[tuple[int, int], ...]]:
    from .. import profile_management
    from . import runtime as editor_runtime

    return editor_runtime.load_keymap(
        cast(editor_runtime._Editor, editor),
        profiles=cast(editor_runtime._ProfilesModule, profiles),
        profile_management=cast(editor_runtime._ProfileManagementModule, profile_management),
        hardware=cast(editor_runtime._HardwareModule, hardware),
    )
