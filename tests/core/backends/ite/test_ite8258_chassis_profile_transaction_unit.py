from __future__ import annotations

from collections.abc import Callable

from keyrgb.core.backends.ite8258_perkey_chassis import protocol
from keyrgb.core.backends.ite8258_perkey_chassis.device import (
    Ite8258ChassisKeyboardDevice,
    Ite8258ChassisZoneDevice,
)
from keyrgb.core.backends.ite8258_perkey_chassis.profile_coordinator import (
    Ite8258ChassisProfileCoordinator,
    ProfileCommitDisposition,
)


def test_output_transaction_batches_keyboard_and_zones_into_one_commit() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    keyboard = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)
    logo = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=coordinator,
    )
    neon = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="neon",
        led_ids=protocol.NEON_LED_IDS,
        profile_coordinator=coordinator,
    )
    vent = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="vent",
        led_ids=protocol.VENT_LED_IDS,
        profile_coordinator=coordinator,
    )

    with keyboard.output_transaction():
        keyboard.set_color((0x11, 0x22, 0x33), brightness=25)
        logo.set_color((0xAB, 0xCD, 0xEF), brightness=25)
        neon.set_color((0x10, 0x20, 0x30), brightness=25)
        vent.set_color((0x40, 0x50, 0x60), brightness=25)
        assert sent == []

    expected_groups = (
        *protocol.build_uniform_static_groups((0x11, 0x22, 0x33)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0xAB, 0xCD, 0xEF)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0x10, 0x20, 0x30)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0x40, 0x50, 0x60)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_nested_output_transactions_commit_once_at_outer_exit() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    keyboard = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)

    with keyboard.output_transaction():
        with keyboard.output_transaction():
            keyboard.set_color((0x11, 0x22, 0x33), brightness=25)
        assert sent == []

    expected_groups = (
        *protocol.build_uniform_static_groups((0x11, 0x22, 0x33)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0, 0, 0)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_profile_commit_dispositions_describe_wire_outcome() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    logo_groups = protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0xAA, 0xBB, 0xCC))

    assert (
        coordinator.apply_zone(
            sent.append,
            zone_name="logo",
            profile_id=protocol.DEFAULT_PROFILE_ID,
            groups=logo_groups,
        )
        is ProfileCommitDisposition.STAGED_NO_PRIMARY
    )
    assert sent == []

    assert (
        coordinator.apply_primary(
            sent.append,
            profile_id=protocol.DEFAULT_PROFILE_ID,
            groups=protocol.build_uniform_static_groups((0x11, 0x22, 0x33)),
            brightness=25,
        )
        is ProfileCommitDisposition.COMMITTED
    )
    sent.clear()

    coordinator.turn_off_all(sent.append, profile_id=protocol.DEFAULT_PROFILE_ID)
    sent.clear()
    assert (
        coordinator.turn_off_zone(
            sent.append,
            zone_name="logo",
            profile_id=protocol.DEFAULT_PROFILE_ID,
        )
        is ProfileCommitDisposition.STAGED_SUSPENDED
    )
    assert sent == []

    with coordinator.output_transaction(sent.append, profile_id=protocol.DEFAULT_PROFILE_ID):
        assert (
            coordinator.apply_zone(
                sent.append,
                zone_name="logo",
                profile_id=protocol.DEFAULT_PROFILE_ID,
                groups=logo_groups,
            )
            is ProfileCommitDisposition.STAGED_IN_TRANSACTION
        )
    assert sent == []


def test_output_transaction_staging_exception_restores_previous_desired_scene() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    keyboard = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)
    logo = Ite8258ChassisZoneDevice(
        sent.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=coordinator,
    )

    keyboard.set_color((0x12, 0x34, 0x56), brightness=25)
    logo.set_color((0xAB, 0xCD, 0xEF), brightness=25)
    sent.clear()

    try:
        with keyboard.output_transaction():
            keyboard.set_color((0x01, 0x02, 0x03), brightness=25)
            logo.set_color((0x99, 0x88, 0x77), brightness=25)
            raise RuntimeError("abort frame")
    except RuntimeError:
        pass

    assert sent == []
    keyboard.set_color((0x12, 0x34, 0x56), brightness=25)
    expected_groups = (
        *protocol.build_uniform_static_groups((0x12, 0x34, 0x56)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0xAB, 0xCD, 0xEF)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0, 0, 0)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_mid_commit_io_error_leaves_desired_scene_dirty_and_retryable() -> None:
    coordinator = Ite8258ChassisProfileCoordinator()
    bootstrap: list[bytes] = []
    keyboard = Ite8258ChassisKeyboardDevice(bootstrap.append, profile_coordinator=coordinator)
    logo = Ite8258ChassisZoneDevice(
        bootstrap.append,
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=coordinator,
    )
    keyboard.set_color((0x12, 0x34, 0x56), brightness=25)
    logo.set_color((0xAB, 0xCD, 0xEF), brightness=25)

    writes = 0

    def flaky_writer(report: bytes) -> None:
        nonlocal writes
        writes += 1
        if writes == 3:
            raise OSError("injected mid-commit failure")

    flaky_keyboard = Ite8258ChassisKeyboardDevice(flaky_writer, profile_coordinator=coordinator)
    try:
        flaky_keyboard.set_color((0x01, 0x02, 0x03), brightness=25)
    except OSError:
        pass

    assert coordinator.desired_dirty is True

    sent: list[bytes] = []
    keyboard_retry = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)
    keyboard_retry.set_color((0x01, 0x02, 0x03), brightness=25)
    expected_groups = (
        *protocol.build_uniform_static_groups((0x01, 0x02, 0x03)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0xAB, 0xCD, 0xEF)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0, 0, 0)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]
    assert coordinator.desired_dirty is False


def test_cold_positive_brightness_emits_switch_profile_then_brightness_only() -> None:
    sent: list[bytes] = []
    keyboard = Ite8258ChassisKeyboardDevice(
        sent.append,
        profile_coordinator=Ite8258ChassisProfileCoordinator(),
    )

    keyboard.set_brightness(25)

    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_composite_profile_transactions_do_not_interleave_between_surfaces() -> None:
    import threading
    import time

    coordinator = Ite8258ChassisProfileCoordinator()
    Ite8258ChassisKeyboardDevice(lambda _report: None, profile_coordinator=coordinator).set_color(
        (0x12, 0x34, 0x56),
        brightness=25,
    )

    writes: list[tuple[str, int]] = []
    errors: list[Exception] = []
    start = threading.Barrier(3)

    def writer(label: str) -> Callable[[bytes], None]:
        def _write(report: bytes) -> None:
            writes.append((label, report[1]))
            time.sleep(0.001)

        return _write

    keyboard = Ite8258ChassisKeyboardDevice(writer("keyboard"), profile_coordinator=coordinator)
    logo = Ite8258ChassisZoneDevice(
        writer("logo"),
        zone_name="logo",
        led_ids=protocol.LOGO_LED_IDS,
        profile_coordinator=coordinator,
    )

    def apply(action: Callable[[], None]) -> None:
        try:
            start.wait()
            action()
        except Exception as exc:  # noqa: BLE001 # pragma: no cover - surfaced by assertion
            errors.append(exc)

    keyboard_thread = threading.Thread(
        target=apply,
        args=(lambda: keyboard.set_color((0x01, 0x02, 0x03), brightness=25),),
    )
    logo_thread = threading.Thread(
        target=apply,
        args=(lambda: logo.set_color((0xAB, 0xCD, 0xEF), brightness=25),),
    )
    keyboard_thread.start()
    logo_thread.start()
    start.wait()
    keyboard_thread.join(timeout=2)
    logo_thread.join(timeout=2)

    assert not keyboard_thread.is_alive()
    assert not logo_thread.is_alive()
    assert errors == []
    labels = [label for label, _command in writes]
    assert labels in (
        ["keyboard"] * 4 + ["logo"] * 3,
        ["logo"] * 3 + ["keyboard"] * 4,
    )


def test_concurrent_output_transactions_are_serialized_not_coalesced() -> None:
    import threading

    coordinator = Ite8258ChassisProfileCoordinator()
    writes: list[tuple[str, int]] = []
    first_inside = threading.Event()
    second_attempting = threading.Event()
    release_first = threading.Event()
    errors: list[Exception] = []

    def run_first() -> None:
        keyboard = Ite8258ChassisKeyboardDevice(
            lambda report: writes.append(("first", report[1])),
            profile_coordinator=coordinator,
        )
        try:
            with keyboard.output_transaction():
                first_inside.set()
                if not release_first.wait(timeout=2):
                    raise TimeoutError("timed out waiting to release first transaction")
                keyboard.set_color((0x01, 0x02, 0x03), brightness=25)
        except Exception as exc:  # noqa: BLE001 # pragma: no cover - surfaced by assertion
            errors.append(exc)

    def run_second() -> None:
        if not first_inside.wait(timeout=2):
            errors.append(TimeoutError("first transaction did not start"))
            return
        keyboard = Ite8258ChassisKeyboardDevice(
            lambda report: writes.append(("second", report[1])),
            profile_coordinator=coordinator,
        )
        second_attempting.set()
        try:
            with keyboard.output_transaction():
                keyboard.set_color((0x04, 0x05, 0x06), brightness=25)
        except Exception as exc:  # noqa: BLE001 # pragma: no cover - surfaced by assertion
            errors.append(exc)

    first_thread = threading.Thread(target=run_first)
    second_thread = threading.Thread(target=run_second)
    first_thread.start()
    second_thread.start()
    assert second_attempting.wait(timeout=2)
    release_first.set()
    first_thread.join(timeout=2)
    second_thread.join(timeout=2)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert errors == []
    assert [label for label, _command in writes] == ["first"] * 4 + ["second"] * 4
