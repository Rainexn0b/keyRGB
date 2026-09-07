from __future__ import annotations

import pytest

from buildpython.steps.architecture_validation import scan_architecture
from tests.buildpython._architecture_validation_helpers import (
    REPO_ROOT,
    production_architecture_rules,
    scan_configured_rule,
    scan_configured_secondary_device_rule,
)


@pytest.mark.parametrize(
    ("receiver", "method"),
    [
        ("tray.engine.kb", "set_brightness"),
        ("tray.engine.kb", "set_color"),
        ("tray.engine.kb", "set_key_colors"),
        ("tray.engine.kb", "enable_user_mode"),
        ("tray.engine.kb", "turn_off"),
        ("tray.engine.kb", "set_effect"),
        ("tray.engine", "set_brightness"),
        ("tray.engine", "turn_off"),
        ("tray.engine", "start_effect"),
        ("tray.engine", "stop"),
        ("self.tray.engine.kb", "turn_off"),
        ("self.tray.engine", "stop"),
    ],
)
def test_configured_secondary_device_rule_forbids_each_primary_receiver_category(
    tmp_path, receiver: str, method: str
) -> None:
    result = scan_configured_secondary_device_rule(
        tmp_path,
        f"{receiver}.{method}()\n",
        relative_path="keyrgb/tray/controllers/example_secondary.py",
    )

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "secondary-device-no-primary-keyboard-mutations"
    assert result.findings[0].regex == f"call:{receiver}.{method}"


def test_configured_secondary_device_rule_allows_secondary_receivers(tmp_path) -> None:
    result = scan_configured_secondary_device_rule(
        tmp_path,
        """target.device.set_color((1, 2, 3), brightness=5)
selected.device.turn_off()
secondary.engine.turn_off()
engine.set_brightness(5)
""",
        relative_path="keyrgb/tray/controllers/example_secondary.py",
    )

    assert result.findings == ()


def test_configured_secondary_device_rule_uses_only_its_corpus(tmp_path) -> None:
    root = tmp_path / "repo"
    matching = root / "keyrgb/tray/controllers/example_secondary.py"
    explicit = root / "keyrgb/tray/controllers/_software_target_auxiliary.py"
    auxiliary = root / "keyrgb/tray/controllers/example_auxiliary.py"
    unrelated = root / "keyrgb/tray/controllers/ordinary.py"
    matching.parent.mkdir(parents=True)
    matching.write_text("tray.engine.turn_off()\n", encoding="utf-8")
    explicit.write_text("tray.engine.kb.turn_off()\n", encoding="utf-8")
    auxiliary.write_text("self.tray.engine.stop()\n", encoding="utf-8")
    unrelated.write_text("tray.engine.turn_off()\n", encoding="utf-8")
    rules = [
        rule
        for rule in production_architecture_rules()
        if rule.rule_id == "secondary-device-no-primary-keyboard-mutations"
    ]
    result = scan_architecture(root, rules)

    assert [(finding.path, finding.regex) for finding in result.findings] == [
        ("keyrgb/tray/controllers/_software_target_auxiliary.py", "call:tray.engine.kb.turn_off"),
        ("keyrgb/tray/controllers/example_auxiliary.py", "call:self.tray.engine.stop"),
        ("keyrgb/tray/controllers/example_secondary.py", "call:tray.engine.turn_off"),
    ]


@pytest.mark.parametrize(
    ("source", "finding_token"),
    [
        (
            "from keyrgb.core.power.system import get_status\n",
            "import:keyrgb.core.power.system.get_status",
        ),
        (
            "from keyrgb.core.secondary_device_runtime import iter_effective_secondary_routes\n",
            "import:keyrgb.core.secondary_device_runtime.iter_effective_secondary_routes",
        ),
        (
            "import keyrgb.core.power.system as power_system\npower_system.get_status()\n",
            "call:keyrgb.core.power.system.get_status",
        ),
        (
            "import keyrgb.core.secondary_device_runtime as runtime\nruntime.iter_effective_secondary_routes()\n",
            "call:keyrgb.core.secondary_device_runtime.iter_effective_secondary_routes",
        ),
        (
            "tray.backend.probe()\n",
            "call:tray.backend.probe",
        ),
        (
            "backend.is_available()\n",
            "call:backend.is_available",
        ),
        (
            "engine._ensure_device_available()\n",
            "attribute:_ensure_device_available",
        ),
    ],
)
def test_configured_tray_ui_view_boundary_forbids_live_observation(tmp_path, source: str, finding_token: str) -> None:
    result = scan_configured_rule(
        tmp_path,
        source,
        rule_id="tray-ui-no-live-observation",
        relative_path="keyrgb/tray/ui/menu.py",
    )

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "tray-ui-no-live-observation"
    assert result.findings[0].regex == finding_token


def test_configured_tray_ui_view_boundary_allows_snapshot_reads(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        """from keyrgb.core.power.system import PowerMode, set_mode
from keyrgb.tray.controllers.view_snapshots import (
    read_effective_secondary_routes,
    read_system_power_status,
)

def render(tray):
    status = read_system_power_status(tray)
    routes = read_effective_secondary_routes(tray)
    available = tray.engine.device_available
    probe = tray.backend_probe.identifiers
    set_mode(PowerMode.BALANCED)
    return status, routes, available, probe
""",
        rule_id="tray-ui-no-live-observation",
        relative_path="keyrgb/tray/ui/menu_sections.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    "source",
    [
        "from keyrgb.core.config.config import Config\n",
        "from keyrgb.core.config import Config\n",
    ],
)
def test_configured_diagnostics_rule_forbids_live_config(tmp_path, source: str) -> None:
    result = scan_configured_rule(
        tmp_path,
        source,
        rule_id="diagnostics-no-live-config",
        relative_path="keyrgb/core/diagnostics/secondary_devices.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"diagnostics-no-live-config"}


def test_configured_diagnostics_rule_allows_readonly_settings_load(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        """from keyrgb.core.config._settings_view import ConfigSettingsView
from keyrgb.core.config.defaults import DEFAULTS
from keyrgb.core.config.file_storage import load_config_settings
from keyrgb.core.config.paths import config_file_path
""",
        rule_id="diagnostics-no-live-config",
        relative_path="keyrgb/core/diagnostics/secondary_devices.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    ("source", "relative_path"),
    [
        ("tray._update_menu()\n", "keyrgb/tray/pollers/hardware_polling.py"),
        ("tray._refresh_ui(refresh_menu=True)\n", "keyrgb/tray/pollers/idle_power/_actions.py"),
        ("tray._refresh_ui(animate_icon=False, refresh_menu = True)\n", "keyrgb/core/power/management/manager.py"),
    ],
)
def test_configured_automatic_power_paths_cannot_rebuild_live_menu(tmp_path, source: str, relative_path: str) -> None:
    result = scan_configured_rule(
        tmp_path,
        source,
        rule_id="automatic-power-paths-no-live-menu-rebuild",
        relative_path=relative_path,
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"automatic-power-paths-no-live-menu-rebuild"}


def test_configured_automatic_power_paths_allow_icon_refresh_without_menu(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        """tray._update_icon()
tray._refresh_ui(animate_icon=False, refresh_menu=False)
""",
        rule_id="automatic-power-paths-no-live-menu-rebuild",
        relative_path="keyrgb/tray/pollers/time_scheduler.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    "source",
    [
        "from keyrgb.core.backends.policy import per_key_mode_policy\n",
        "from keyrgb.core.backends.sleep_state import is_controller_sleep_state\n",
        "from keyrgb.core.backends.policies import sleep_state\n",
        "import keyrgb.core.backends.policies as policies\n",
    ],
)
def test_configured_policy_import_rule_forbids_historical_and_package_root_imports(tmp_path, source: str) -> None:
    result = scan_configured_rule(
        tmp_path,
        source,
        rule_id="canonical-backend-policy-imports",
        relative_path="keyrgb/tray/pollers/hardware/_controller_sleep.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"canonical-backend-policy-imports"}


def test_configured_policy_import_rule_allows_canonical_leaf_imports(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        """from keyrgb.core.backends.policies.sleep_state import is_controller_sleep_state
from keyrgb.core.backends.policies.per_key_mode import per_key_mode_policy
from keyrgb.core.backends.policies.backend_selection import stability_for_backend
""",
        rule_id="canonical-backend-policy-imports",
        relative_path="keyrgb/tray/pollers/hardware/_controller_sleep.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    "source",
    [
        "globals().update({'render': render})\n",
        "api = sys.modules[__name__]\n",
    ],
)
def test_configured_reactive_rule_forbids_module_global_injection(tmp_path, source: str) -> None:
    result = scan_configured_rule(
        tmp_path,
        source,
        rule_id="reactive-no-module-global-injection",
        relative_path="keyrgb/core/effects/reactive/effects.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"reactive-no-module-global-injection"}


def test_configured_reactive_rule_allows_explicit_facade_construction(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        """# Build immutable API facades (replaces globals().update + sys.modules cast)
from keyrgb.core.effects.reactive._effects_api import build_reactive_api

_fade_api = build_reactive_api()
""",
        rule_id="reactive-no-module-global-injection",
        relative_path="keyrgb/core/effects/reactive/effects.py",
    )

    assert result.findings == ()


def test_configured_gui_async_rule_forbids_direct_worker_threads(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        "from threading import Thread\nThread(target=work, daemon=True).start()\n",
        rule_id="gui-background-work-uses-tk-async",
        relative_path="keyrgb/gui/windows/uniform.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"gui-background-work-uses-tk-async"}


def test_configured_gui_async_rule_allows_tk_async_owner_and_helpers(tmp_path) -> None:
    owner = scan_configured_rule(
        tmp_path,
        "Thread(target=worker, daemon=True).start()\n",
        rule_id="gui-background-work-uses-tk-async",
        relative_path="keyrgb/gui/utils/tk_async.py",
    )
    helper = scan_configured_rule(
        tmp_path,
        """from keyrgb.gui.utils.tk_async import TkAsyncCoordinator, submit_gui_work

self.tk_jobs = TkAsyncCoordinator()
submit_gui_work(self, self.root, work, on_done)
""",
        rule_id="gui-background-work-uses-tk-async",
        relative_path="keyrgb/gui/windows/power_mode.py",
    )

    assert owner.findings == ()
    assert helper.findings == ()


def test_configured_composite_coordinator_rule_forbids_unrelated_imports(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        "from keyrgb.core.backends.ite8258_perkey_chassis.profile_coordinator import Ite8258ChassisProfileCoordinator\n",
        rule_id="composite-coordinator-stays-backend-local",
        relative_path="keyrgb/tray/controllers/secondary_device_controller.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"composite-coordinator-stays-backend-local"}


def test_configured_composite_coordinator_rule_allows_owning_package(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        "from .profile_coordinator import Ite8258ChassisProfileCoordinator\nfrom .protocol import SAVE_PROFILE\n",
        rule_id="composite-coordinator-stays-backend-local",
        relative_path="keyrgb/core/backends/ite8258_perkey_chassis/device.py",
    )

    assert result.findings == ()


def test_configured_poller_pystray_rule_forbids_direct_imports(tmp_path) -> None:
    imported = scan_configured_rule(
        tmp_path,
        "import pystray\n",
        rule_id="pollers-no-direct-pystray",
        relative_path="keyrgb/tray/pollers/icon_color_polling.py",
    )
    loaded = scan_configured_rule(
        tmp_path,
        "import_module('pystray')\n",
        rule_id="pollers-no-direct-pystray",
        relative_path="keyrgb/tray/pollers/idle_power/polling.py",
    )

    assert {finding.rule_id for finding in imported.findings} == {"pollers-no-direct-pystray"}
    assert {finding.rule_id for finding in loaded.findings} == {"pollers-no-direct-pystray"}


def test_configured_core_profile_rule_forbids_tray_imports_and_private_getattr(tmp_path) -> None:
    imported = scan_configured_rule(
        tmp_path,
        "from keyrgb.tray.app.application import KeyRGBTray\n",
        rule_id="core-profile-no-private-tray-lookup",
        relative_path="keyrgb/core/profile/runtime_activation.py",
    )
    private = scan_configured_rule(
        tmp_path,
        'getattr(tray, "_start_effect")\n',
        rule_id="core-profile-no-private-tray-lookup",
        relative_path="keyrgb/core/profile/runtime_activation.py",
    )

    assert {finding.rule_id for finding in imported.findings} == {"core-profile-no-private-tray-lookup"}
    assert {finding.rule_id for finding in private.findings} == {"core-profile-no-private-tray-lookup"}


def test_configured_hardware_effect_rule_forbids_code_introspection(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        "accepted = builder.__code__.co_varnames\n",
        rule_id="hardware-effect-builders-no-introspection",
        relative_path="keyrgb/core/effects/device/hw_payloads.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"hardware-effect-builders-no-introspection"}


def test_current_repo_has_no_architecture_findings() -> None:
    assert scan_architecture(REPO_ROOT, production_architecture_rules()).findings == ()


def test_configured_hardware_assignment_rule_is_scoped_and_keeps_is_off_allowed(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb/tray/pollers/hardware/nested").mkdir(parents=True)
    (root / "keyrgb/tray/pollers/hardware/nested/example.py").write_text(
        "tray.config.brightness = 25\ntray._power_forced_off = True\ntray.is_off = True\n",
        encoding="utf-8",
    )
    (root / "keyrgb/tray/pollers/hardware_polling.py").write_text(
        "tray.config.effect = 'none'\ntray.idle_forced_off = True\n",
        encoding="utf-8",
    )
    (root / "keyrgb/tray/other.py").parent.mkdir(parents=True, exist_ok=True)
    (root / "keyrgb/tray/other.py").write_text("tray.config.brightness = 25\n", encoding="utf-8")
    findings = scan_architecture(root, production_architecture_rules()).findings

    assignment_findings = [
        finding for finding in findings if finding.rule_id == "hardware-observation-no-desired-state-assignments"
    ]
    assert [(finding.path, finding.line, finding.regex) for finding in assignment_findings] == [
        ("keyrgb/tray/pollers/hardware/nested/example.py", 1, "assignment:tray.config.brightness"),
        ("keyrgb/tray/pollers/hardware/nested/example.py", 2, "assignment:tray._power_forced_off"),
        ("keyrgb/tray/pollers/hardware_polling.py", 1, "assignment:tray.config.effect"),
        ("keyrgb/tray/pollers/hardware_polling.py", 2, "assignment:tray.idle_forced_off"),
    ]
