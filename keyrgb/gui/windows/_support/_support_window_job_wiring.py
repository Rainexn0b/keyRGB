from __future__ import annotations

from collections.abc import Callable


def auto_run_backend_speed_probe_via_tray_config(
    plan: dict[str, object],
    *,
    config_cls: object,
    sleep_fn: Callable[[float], None],
    auto_run_backend_speed_probe_fn: Callable[..., dict[str, object]],
    probe_config_snapshot_fn: Callable[..., object],
    restore_probe_config_fn: Callable[..., None],
) -> dict[str, object]:
    return auto_run_backend_speed_probe_fn(
        plan,
        **build_auto_run_backend_speed_probe_kwargs(
            config_cls=config_cls,
            sleep_fn=sleep_fn,
            auto_run_backend_speed_probe_fn=auto_run_backend_speed_probe_fn,
            probe_config_snapshot_fn=probe_config_snapshot_fn,
            restore_probe_config_fn=restore_probe_config_fn,
        ),
    )


def build_auto_run_backend_speed_probe_kwargs(
    *,
    config_cls: object,
    sleep_fn: Callable[[float], None],
    auto_run_backend_speed_probe_fn: Callable[..., dict[str, object]],
    probe_config_snapshot_fn: Callable[..., object],
    restore_probe_config_fn: Callable[..., None],
) -> dict[str, object]:
    _ = auto_run_backend_speed_probe_fn
    return {
        "config_cls": config_cls,
        "sleep_fn": sleep_fn,
        "probe_config_snapshot_fn": probe_config_snapshot_fn,
        "restore_probe_config_fn": restore_probe_config_fn,
    }


def build_backend_speed_probe_run_kwargs(
    *,
    prompt: bool,
    current_backend_speed_probe_plan_fn: Callable[[], object],
    tk_runtime_errors: tuple[type[BaseException], ...],
    run_in_thread: Callable[..., object],
    config_cls: object,
    tray_pid: str,
    sleep_fn: Callable[[float], None],
    auto_run_backend_speed_probe_fn: Callable[..., dict[str, object]],
    complete_backend_speed_probe_fn: Callable[..., None],
    show_probe_message_dialog: Callable[..., object],
    ask_probe_choice_dialog: Callable[..., object],
    ask_probe_notes_dialog: Callable[..., object],
    format_probe_speed_list_fn: Callable[..., str],
    tray_process_alive_fn: Callable[[str], bool],
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "current_backend_speed_probe_plan_fn": current_backend_speed_probe_plan_fn,
        "tk_runtime_errors": tk_runtime_errors,
        "run_in_thread": run_in_thread,
        "config_cls": config_cls,
        "tray_pid": tray_pid,
        "sleep_fn": sleep_fn,
        "format_probe_speed_list_fn": format_probe_speed_list_fn,
        "tray_process_alive_fn": tray_process_alive_fn,
        "auto_run_backend_speed_probe_fn": auto_run_backend_speed_probe_fn,
        "complete_backend_speed_probe_fn": complete_backend_speed_probe_fn,
        "show_probe_message_dialog": show_probe_message_dialog,
        "ask_probe_choice_dialog": ask_probe_choice_dialog,
        "ask_probe_notes_dialog": ask_probe_notes_dialog,
        "tk": tk,
        "ttk": ttk,
        "scrolledtext": scrolledtext,
    }
