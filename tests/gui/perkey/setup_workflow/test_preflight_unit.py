from __future__ import annotations

import pytest

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS
from keyrgb.gui.perkey.setup_workflow import preflight
from keyrgb.gui.perkey.setup_workflow.preflight import (
    CalibrationPreflightEvidence,
    CalibrationPreflightResult,
    PreflightMode,
    PreflightReason,
    evaluate_calibration_preflight,
)


def _per_key_caps() -> BackendCapabilities:
    return BackendCapabilities(
        brightness=True,
        per_key=True,
        color=True,
        hardware_effects=False,
        palette=False,
    )


def _brightness_only_caps() -> BackendCapabilities:
    return BackendCapabilities(
        brightness=True,
        per_key=False,
        color=False,
        hardware_effects=False,
        palette=False,
    )


def _evidence(**overrides: object) -> CalibrationPreflightEvidence:
    base: dict[str, object] = {
        "selected_capabilities": _per_key_caps(),
        "backend_name": "Test Backend",
        "dimensions": (6, 18),
    }
    base.update(overrides)
    return CalibrationPreflightEvidence(**base)  # type: ignore[arg-type]


def test_live_preview_on_per_key_capabilities() -> None:
    result = evaluate_calibration_preflight(_evidence())

    assert result.mode is PreflightMode.LIVE_PREVIEW
    assert result.reason is PreflightReason.OK
    assert result.backend_name == "Test Backend"
    assert (result.rows, result.cols) == (6, 18)
    assert "Live calibration preview" in result.message
    assert result.offer_retry is False
    assert result.offer_continue_config_only is False
    assert result.offer_support is False


def test_live_preview_accepts_mapping_capabilities_through_normalizer() -> None:
    result = evaluate_calibration_preflight(
        _evidence(selected_capabilities={"brightness": True, "per_key": 1, "color": True}),
    )

    assert result.mode is PreflightMode.LIVE_PREVIEW
    assert result.reason is PreflightReason.OK


def test_live_preview_accepts_attribute_snapshot_capabilities() -> None:
    class Snapshot:
        brightness = True
        per_key = True
        color = True
        hardware_effects = False
        palette = False

    result = evaluate_calibration_preflight(_evidence(selected_capabilities=Snapshot()))

    assert result.mode is PreflightMode.LIVE_PREVIEW
    assert result.reason is PreflightReason.OK


@pytest.mark.parametrize("tray_managed", [False, True])
def test_tray_managed_live_only_when_caps_say_per_key(tray_managed: bool) -> None:
    live = evaluate_calibration_preflight(
        _evidence(tray_managed=tray_managed, selected_capabilities=_per_key_caps()),
    )
    degraded = evaluate_calibration_preflight(
        _evidence(tray_managed=tray_managed, selected_capabilities=_brightness_only_caps()),
    )

    assert live.mode is PreflightMode.LIVE_PREVIEW
    assert degraded.mode is PreflightMode.CONFIG_ONLY
    assert degraded.reason is PreflightReason.UNSUPPORTED_BACKEND


def test_brightness_only_caps_degrade_to_config_only() -> None:
    result = evaluate_calibration_preflight(_evidence(selected_capabilities=_brightness_only_caps()))

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.UNSUPPORTED_BACKEND
    assert result.offer_retry is False
    assert result.offer_continue_config_only is True
    assert result.offer_support is True
    assert "config-only" in result.message


@pytest.mark.parametrize(
    "caps",
    [
        {},
        {"brightness": True},
        {"per_key": False},
        {"per_key": "yes"},  # normalizer bool() coerces; documents truthy-mapping behavior
        "nope",
        42,
        object(),
    ],
)
def test_malformed_or_non_per_key_caps_never_go_live(caps: object) -> None:
    result = evaluate_calibration_preflight(_evidence(selected_capabilities=caps))

    truthy_per_key = isinstance(caps, dict) and bool(caps.get("per_key"))
    if truthy_per_key:
        assert result.mode is PreflightMode.LIVE_PREVIEW
    else:
        assert result.mode is PreflightMode.CONFIG_ONLY
        assert result.reason is PreflightReason.UNSUPPORTED_BACKEND


def test_missing_caps_degrades_to_config_only() -> None:
    result = evaluate_calibration_preflight(_evidence(selected_capabilities=None))

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.NO_BACKEND
    assert result.offer_retry is True
    assert result.offer_continue_config_only is True
    assert result.offer_support is True
    assert "live key flashing is unavailable" in result.message


@pytest.mark.parametrize(
    ("has_writer", "expected_mode", "expected_reason"),
    [
        (None, PreflightMode.LIVE_PREVIEW, PreflightReason.OK),
        (True, PreflightMode.LIVE_PREVIEW, PreflightReason.OK),
        (False, PreflightMode.CONFIG_ONLY, PreflightReason.UNSUPPORTED_BACKEND),
        (0, PreflightMode.CONFIG_ONLY, PreflightReason.UNSUPPORTED_BACKEND),
    ],
)
def test_per_key_writer_requirement_when_evidence_includes_it(
    has_writer: bool | None, expected_mode: PreflightMode, expected_reason: PreflightReason
) -> None:
    result = evaluate_calibration_preflight(
        _evidence(selected_capabilities=_per_key_caps(), has_per_key_writer=has_writer),
    )

    assert result.mode is expected_mode
    assert result.reason is expected_reason


def test_writer_evidence_cannot_upgrade_non_per_key_backend() -> None:
    result = evaluate_calibration_preflight(
        _evidence(selected_capabilities=_brightness_only_caps(), has_per_key_writer=True),
    )

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.UNSUPPORTED_BACKEND


@pytest.mark.parametrize(
    ("dimensions", "expected"),
    [
        ((6, 18), (6, 18)),
        ([6, 18], (6, 18)),
        (None, (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((7,), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((7, 18, 99), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((0, 18), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((-1, 18), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((6, 0), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((6, 9999), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((9999, 18), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        (("6", "18"), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((6.0, 18.0), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ((True, 18), (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        ("6x18", (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
        (42, (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)),
    ],
)
def test_dimensions_fallback_and_validation(dimensions: object, expected: tuple[int, int]) -> None:
    result = evaluate_calibration_preflight(_evidence(dimensions=dimensions))

    assert (result.rows, result.cols) == expected


@pytest.mark.parametrize(
    ("backend_name", "expected"),
    [
        ("Test Backend", "Test Backend"),
        ("  Padded Name  ", "Padded Name"),
        (None, "unknown backend"),
        ("", "unknown backend"),
        ("   ", "unknown backend"),
        (42, "unknown backend"),
    ],
)
def test_backend_name_normalization(backend_name: object, expected: str) -> None:
    result = evaluate_calibration_preflight(_evidence(backend_name=backend_name))

    assert result.backend_name == expected


@pytest.mark.parametrize(
    ("kwargs", "expected_reason", "expected_mode", "retry", "config_only", "support"),
    [
        ({"already_running": True}, PreflightReason.ALREADY_RUNNING, PreflightMode.CONFIG_ONLY, True, True, True),
        ({"config_writable": False}, PreflightReason.CONFIG_UNWRITABLE, PreflightMode.BLOCKED, True, False, True),
        ({"policy_disabled": True}, PreflightReason.POLICY_DISABLED, PreflightMode.BLOCKED, False, False, True),
        (
            {"selected_capabilities": None},
            PreflightReason.NO_BACKEND,
            PreflightMode.CONFIG_ONLY,
            True,
            True,
            True,
        ),
        ({"device_disconnected": True}, PreflightReason.DISCONNECTED, PreflightMode.CONFIG_ONLY, True, True, True),
        ({"permission_denied": True}, PreflightReason.PERMISSION, PreflightMode.CONFIG_ONLY, True, True, True),
        ({"device_busy": True}, PreflightReason.BUSY, PreflightMode.CONFIG_ONLY, True, True, True),
        (
            {"selected_capabilities": _brightness_only_caps()},
            PreflightReason.UNSUPPORTED_BACKEND,
            PreflightMode.CONFIG_ONLY,
            False,
            True,
            True,
        ),
        (
            {"selected_capabilities": _per_key_caps()},
            PreflightReason.OK,
            PreflightMode.LIVE_PREVIEW,
            False,
            False,
            False,
        ),
    ],
)
def test_reason_button_contract(
    kwargs: dict[str, object],
    expected_reason: PreflightReason,
    expected_mode: PreflightMode,
    retry: bool,
    config_only: bool,
    support: bool,
) -> None:
    result = evaluate_calibration_preflight(_evidence(**kwargs))

    assert result.reason is expected_reason
    assert result.mode is expected_mode
    assert result.offer_retry is retry
    assert result.offer_continue_config_only is config_only
    assert result.offer_support is support
    assert result.message.strip() != ""


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        (
            {
                "already_running": True,
                "config_writable": False,
                "policy_disabled": True,
                "selected_capabilities": None,
                "device_disconnected": True,
                "permission_denied": True,
                "device_busy": True,
            },
            PreflightReason.CONFIG_UNWRITABLE,
        ),
        (
            {
                "config_writable": False,
                "policy_disabled": True,
                "device_disconnected": True,
                "permission_denied": True,
                "device_busy": True,
            },
            PreflightReason.CONFIG_UNWRITABLE,
        ),
        (
            {
                "policy_disabled": True,
                "already_running": True,
                "device_disconnected": True,
                "permission_denied": True,
                "device_busy": True,
            },
            PreflightReason.POLICY_DISABLED,
        ),
        (
            {
                "already_running": True,
                "selected_capabilities": None,
                "device_disconnected": True,
                "permission_denied": True,
                "device_busy": True,
            },
            PreflightReason.ALREADY_RUNNING,
        ),
        (
            {
                "selected_capabilities": None,
                "device_disconnected": True,
                "permission_denied": True,
                "device_busy": True,
            },
            PreflightReason.NO_BACKEND,
        ),
        (
            {
                "device_disconnected": True,
                "permission_denied": True,
                "device_busy": True,
            },
            PreflightReason.DISCONNECTED,
        ),
        (
            {"permission_denied": True, "device_busy": True},
            PreflightReason.PERMISSION,
        ),
        (
            {"device_busy": True, "selected_capabilities": _brightness_only_caps()},
            PreflightReason.BUSY,
        ),
    ],
)
def test_reason_priority_order(kwargs: dict[str, object], expected_reason: PreflightReason) -> None:
    result = evaluate_calibration_preflight(_evidence(**kwargs))

    assert result.reason is expected_reason


def test_already_running_degrades_to_config_only_without_second_calibrator() -> None:
    result = evaluate_calibration_preflight(_evidence(already_running=True))

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.reason is PreflightReason.ALREADY_RUNNING
    assert result.offer_retry is True
    assert result.offer_continue_config_only is True
    assert result.offer_support is True
    assert "live key flashing is unavailable" in result.message
    assert "second calibrator cannot be launched" in result.message
    assert "Retry" in result.message


@pytest.mark.parametrize(
    "kwargs",
    [
        {"already_running": True},
        {"selected_capabilities": None},
        {"device_disconnected": True},
        {"permission_denied": True},
        {"device_busy": True},
        {"selected_capabilities": _brightness_only_caps()},
    ],
)
def test_every_config_only_result_warns_live_flashing_unavailable(kwargs: dict[str, object]) -> None:
    result = evaluate_calibration_preflight(_evidence(**kwargs))

    assert result.mode is PreflightMode.CONFIG_ONLY
    assert result.offer_continue_config_only is True
    assert "live key flashing is unavailable" in result.message


def test_evaluation_is_deterministic_and_env_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _evidence()
    first = evaluate_calibration_preflight(evidence)

    monkeypatch.setenv("KEYRGB_BACKEND", "nonsense-backend")
    monkeypatch.setenv("KEYRGB_TRAY_MANAGED_GUI", "1")
    second = evaluate_calibration_preflight(evidence)

    assert first == second
    assert isinstance(first, CalibrationPreflightResult)


def test_module_stays_off_hardware_tray_and_runtime_boundaries() -> None:
    import pathlib

    source = pathlib.Path(preflight.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "from keyrgb.tray",
        "import tray",
        "select_backend",
        "get_device",
        "is_available",
        "os.environ",
        "os.getenv",
        "open(",
    ):
        assert forbidden not in source
