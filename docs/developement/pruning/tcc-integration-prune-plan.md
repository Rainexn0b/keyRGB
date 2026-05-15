# TCC Integration Prune Plan

Date: 2026-05-16

## Decision

Prune the TUXEDO Control Center power-profile integration and keep KeyRGB's
canonical lightweight power mode controls.

Keep Tuxedo/Clevo kernel-driver guidance and diagnostics. The prune target is
the TCC application/profile integration, not `tuxedo-drivers`,
`tuxedo-keyboard`, `clevo-xsm-wmi`, or sysfs LED support.

## Why

The TCC integration was added early to provide power profile control before
KeyRGB had its own simpler implementation. It now creates two competing power
paths:

- KeyRGB lightweight Power Mode toggle, backed by `src.core.power.system` and
  the `keyrgb-power-helper` polkit helper.
- TUXEDO Control Center profiles, backed by the external `tccd` daemon, DBus,
  optional package install, and profile JSON editing.

The lightweight path is now the canonical product behavior. TCC support adds
installer branching, tray fallback logic, root-write profile editing, an extra
CLI command, and a large test surface for a legacy alternative.

## Current Surface

Installer and uninstall:

- `scripts/install_user.sh`
  - Mentions TCC in `--no-system-deps` help text.
  - Documents `KEYRGB_INSTALL_TUXEDO`.
  - Documents `KEYRGB_INSTALL_TCC_APP`.
  - Treats TCC package install as a reason to run system package changes.
  - Calls `install_tcc_app_best_effort`.
- `scripts/lib/user_prompts.sh`
  - Lets the user choose between lightweight Power Mode and TCC.
  - Sets `KEYRGB_INSTALL_TCC_APP`.
  - Handles `KEYRGB_INSTALL_TUXEDO` env override.
- `scripts/lib/optional_components.sh`
  - Defines `install_tcc_app_best_effort`.
  - Writes `~/.local/share/keyrgb/tcc-installed-by-keyrgb`.
- `scripts/uninstall.sh`
  - Previously defined `TCC_MARKER` and prompted to remove
    `tuxedo-control-center` if KeyRGB installed it.

Packaging and docs:

- `pyproject.toml`
  - `keyrgb-tcc-profiles = "src.gui.tcc.profiles:main"`
- `README.md`
  - Installer example uses `KEYRGB_INSTALL_TUXEDO=y` and
    `KEYRGB_INSTALL_TCC_APP=y`.
  - Command table lists `keyrgb-tcc-profiles`.
  - Env table lists `KEYRGB_TCCD_BIN`.
  - `--no-system-deps` row mentions TCC.

Runtime and tray:

- `src/core/power/tcc_profiles/`
  - DBus calls to `tccd`.
  - TCC profile parsing.
  - Custom profile create/update/delete.
  - Root apply path through `pkexec` or `sudo`.
- `src/gui/tcc/`
  - TCC profiles window.
  - Profile JSON editor.
  - Profile create/duplicate/rename/delete actions.
- `src/tray/ui/menu.py`
  - Imports `src.core.power.tcc_profiles`.
  - Builds `tcc_profiles_menu`.
  - Falls back to TCC when lightweight system power cannot apply.
- `src/tray/ui/menu_sections.py`
  - Imports `TccProfile`.
  - Exposes `_TccProfilesProviderProtocol`.
  - Exposes `_TccProfilesTrayProtocol`.
  - Exposes `build_tcc_profiles_menu`.
- `src/tray/ui/_menu_sections_profile_power.py`
  - Contains TCC profile menu construction and callback wrapper.
  - Also contains the lightweight system power and per-key profile builders.
- `src/tray/ui/gui_launch.py`
  - `launch_tcc_profiles_gui`.
- `src/tray/app/callbacks.py`
  - Imports TCC power profiles.
  - `on_tcc_profiles_gui_clicked`.
  - `on_tcc_profile_clicked`.
- `src/tray/app/_delegates.py`
  - `_on_tcc_profiles_gui_clicked`.
  - `_on_tcc_profile_clicked`.

Tests:

- `tests/core/power/tcc_profiles/`
- `tests/core/power/runtime/test_tcc_power_profiles_unit.py`
- `tests/gui/tcc/test_profile_actions_unit.py`
- `tests/gui/windows/test_tcc_profile_editor_unit.py`
- `tests/gui/windows/test_tcc_profiles_window_unit.py`
- TCC-specific tray callback/menu assertions in:
  - `tests/tray/app/test_tray_callbacks_unit.py`
  - `tests/tray/app/test_tray_application_unit.py`
  - `tests/tray/ui/menu/test_menu_sections_unit.py`
  - `tests/tray/ui/menu/test_tray_menu_capabilities_unit.py`

## Keep

Do not remove these during the TCC prune:

- `scripts/lib/optional_components.sh::install_kernel_drivers_best_effort`
- `KEYRGB_INSTALL_KERNEL_DRIVERS`
- Tuxedo/Clevo wording that refers to kernel drivers, sysfs LEDs, or hardware
  support.
- Diagnostics that mention `tuxedo_keyboard`, `tuxedo::kbd_backlight`,
  `tuxedo-drivers`, or `clevo-xsm-wmi`.
- README troubleshooting note that other tools such as TCC can fight KeyRGB.
  That is still useful even if KeyRGB no longer integrates with TCC.
- `src/core/backends/sysfs/common.py` Tuxedo LED name matching.

## Implementation Plan

1. Installer prompts and envs
   - Remove `KEYRGB_INSTALL_TUXEDO` from `scripts/install_user.sh` help.
   - Remove `KEYRGB_INSTALL_TCC_APP` from `scripts/install_user.sh` help.
   - In `scripts/lib/user_prompts.sh`, remove the TCC-vs-lightweight choice.
   - Default to `KEYRGB_INSTALL_POWER_HELPER=y` unless explicitly disabled.
   - Keep `KEYRGB_INSTALL_KERNEL_DRIVERS` prompts separate.
   - Update `--no-system-deps` copy to mention AppImage runtime, kernel
     drivers, and polkit, but not TCC.

2. Optional package install
   - Remove `install_tcc_app_best_effort`.
   - Remove the `KEYRGB_INSTALL_TCC_APP` check and call from
     `scripts/install_user.sh`.
   - Update `needs_system_package_changes` so TCC no longer triggers package
     manager work.

3. Uninstall compatibility
   - Remove the old `TCC_MARKER` cleanup block. KeyRGB no longer installs,
     tracks, or removes `tuxedo-control-center`.

4. Packaging
   - Remove `keyrgb-tcc-profiles` from `[project.scripts]` in `pyproject.toml`.
   - Confirm entrypoint consistency tests no longer expect it.

5. Runtime code
   - Delete `src/core/power/tcc_profiles/`.
   - Delete `src/gui/tcc/`.
   - Remove `launch_tcc_profiles_gui` from `src/tray/ui/gui_launch.py`.
   - Remove TCC imports and callbacks from `src/tray/app/callbacks.py`.
   - Remove TCC delegate methods from `src/tray/app/_delegates.py`.
   - Remove TCC protocol/callback references from `src/tray/ui/menu_sections.py`.
   - Remove TCC menu construction from
     `src/tray/ui/_menu_sections_profile_power.py`.
   - In `src/tray/ui/menu.py`, stop building `tcc_profiles_menu`; set the
     `Power Mode` menu from `build_system_power_mode_menu` only.

6. Menu behavior after prune
   - If lightweight system power status is supported, show `Power Mode`.
   - If system power is unsupported, hide `Power Mode`.
   - Do not fall back to any external TCC profile menu.
   - Keep per-key lighting profile menu behavior unchanged.

7. Tests
   - Delete TCC-only tests listed above.
   - Update tray menu tests so they assert:
     - no TCC provider is required,
     - system power menu is the only power menu,
     - unsupported system power means no power menu.
   - Update callback/delegate surface tests to remove TCC callback expectations.
   - Update entrypoint consistency tests for removed `keyrgb-tcc-profiles`.

8. Docs
   - Remove TCC install env vars from README examples.
   - Remove `keyrgb-tcc-profiles` from the command table.
   - Remove `KEYRGB_TCCD_BIN` from env vars.
   - Change `--no-system-deps` text to omit TCC.
   - Keep Tuxedo/Clevo kernel-driver support text.
   - Keep "other RGB tools/TCC may fight KeyRGB" troubleshooting language.

## Nuances

- TCC and tuxedo-drivers are not the same thing. TCC is an external user-facing
  app and daemon; tuxedo-drivers can expose useful sysfs LED nodes.
- Removing TCC should reduce collision risk because KeyRGB no longer encourages
  installing or controlling a second power/RGB tool.
- Removing the TCC provider from `menu.py` should also reduce menu refresh
  latency and error handling noise on systems without `tccd`.
- `src/tray/ui/_menu_sections_profile_power.py` currently mixes TCC, lightweight
  system power, and per-key lighting profiles. The prune is an opportunity to
  simplify naming after TCC removal, but keep that rename as a follow-up unless
  the edit is already straightforward.

## Validation

Run these after implementation:

```bash
bash -n install.sh uninstall.sh scripts/install_dev.sh scripts/install_user.sh scripts/uninstall.sh
.venv/bin/python -m pytest -q tests/buildpython/test_buildpython_import_probe_unit.py tests/core/runtime/test_entrypoint_consistency_unit.py
.venv/bin/python -m pytest -q tests/tray/app tests/tray/ui/menu tests/gui/settings tests/core/power
.venv/bin/python -m buildpython --run-steps="Import Scan,Repo Validation,File Size,Architecture Validation"
```

If the implementation deletes many tests, also run:

```bash
.venv/bin/python -m buildpython --run-steps="Compile,Pytest,Import Validation,Import Scan,Repo Validation"
```

## Expected Result

- Installer offers one canonical power integration: lightweight Power Mode.
- Optional kernel-driver guidance remains available for sysfs lighting support.
- TCC package installation is no longer offered or triggered.
- Tray no longer queries `tccd` or shows TCC profile fallback menus.
- `keyrgb-tcc-profiles` command is gone.
- Uninstall no longer tracks or removes TCC marker packages.

## Implementation Status

Implemented on 2026-05-16.

- Removed the TCC profile runtime package, TCC profile GUI package, TCC
  console entrypoint, tray TCC menu fallback, and tray TCC callbacks.
- Removed installer support for selecting or installing
  `tuxedo-control-center`.
- Kept Tuxedo/Clevo kernel-driver install guidance and sysfs support intact.
- Removed marker-based uninstall cleanup for older TCC installs.
- Updated README installer and command documentation to describe only the
  canonical lightweight Power Mode path.
