# Hardware-access first-run setup — implementation tracker

- **Date:** 2026-10-05
- **Status:** steps 1–3 implemented; disposable-environment acceptance not started
- **Owners:** `scripts/` and `system/` for installation; `keyrgb/gui/settings/`
  for UI; `buildpython/steps/appimage/` for the bundled payload
- **Related:** [AppImage catalog compatibility investigation](../../D-debugging/appimage-catalog-compatibility-2026-10-05.md)

## Goal and scope rule

Let an AppImage user explicitly install the missing hardware-access files from a
first-run offer or **Settings → Set up hardware access**, without downloading or
running the full application installer. The normal application must continue to
run as the user, including when setup is skipped, cancelled, or unavailable.

**Extract a fail-closed hardware-write seam. Do not call today's install helpers,
and do not rebuild the installer or onboarding framework.**

The AppImage ABI/bundling patch is a separate dependency. Its local validation
does not mean these setup commands or the wizard already exist, or that either
change has been published.

## What this installs

| Selection | Payload | Default in the new mode |
|---|---|---|
| Keyboard access | [system/udev/99-ite8291-wootbook.rules](../../../system/udev/99-ite8291-wootbook.rules) and [system/udev/99-keyrgb-sysfs-leds.rules](../../../system/udev/99-keyrgb-sysfs-leds.rules) | On. Install the shipped file bytes unchanged, including hidraw and lightbar matches. |
| Reactive input | [system/udev/99-keyrgb-input-uaccess.rules](../../../system/udev/99-keyrgb-input-uaccess.rules) | Off. Explicit opt-in. This grants keyboard input-event observation, not lighting access. |
| Power controls | [system/bin/keyrgb-power-helper](../../../system/bin/keyrgb-power-helper), [system/polkit/90-keyrgb-power-helper.rules](../../../system/polkit/90-keyrgb-power-helper.rules), and [system/polkit/org.keyrgb.power-helper.policy](../../../system/polkit/org.keyrgb.power-helper.policy) | Off. Explicit opt-in. Not required for keyboard color. |

Out of scope, and must not be pulled in by the new mode:

- AppImage download or update, desktop files, autostart, icons, telemetry
- distro package managers and kernel-driver installation
- fuse2 / AppImage runtime packages (the AppImage is already running)
- adding the user to the `video` group, unless a later explicit decision says so
- a new polkit action, always-allow shell policy, or general privileged service
- backend selection, tray lighting, idle/power policy, or the per-key calibrator

## Do not call the current helpers

These functions are not a usable seam. They return success on failure, and the
GUI must not wrap them:

- `install_udev_rule_from_ref` returns 0 when `udevadm` is missing or the
  download fails, then falls back from the requested ref to `main`.
- `reload_udev_rules_best_effort` runs `sudo … || true` and still logs success.
- `install_privileged_helpers_local` / `install_privileged_helpers_from_ref`
  return 0 when polkit directories are missing. `install_user.sh` also wraps
  them in `|| true`.
- The input-rule caller logs "installed" after those best-effort returns.
- `should_install_power_helper` defaults to yes. The new mode must not call it.
- `require_not_root` in [scripts/lib/common_core.sh](../../../scripts/lib/common_core.sh)
  rejects a worker that is already root when called. Sourcing `common.sh` only
  defines that function; it does not execute the check. The privileged worker
  must not call it and should not load unrelated installer modules.

Leave those fallbacks on the full installer. Add a new fail-closed writer and
adapt only the immediate caller in `install_user.sh` so the full install and the
new mode share the write, not the old success-on-failure paths.

| Owner | Use |
|---|---|
| [install.sh](../../../install.sh) | Recognize `--hardware-access-only` in the dispatcher before any forward to `install_user.sh`. Preserve default, dev, and update modes. The no-arg interactive menu runs only when `$# -eq 0`; do not reorder that. |
| [scripts/install_user.sh](../../../scripts/install_user.sh) | Keep download, desktop integration, autostart, control flow, and existing defaults. Do not change its power-helper default. Its existing install helpers call the shared placer for the file write only. |
| [scripts/lib/uninstall_match.sh](../../../scripts/lib/uninstall_match.sh) | Reuse the managed-file markers and legacy header checks. Do not invent new installed names. |
| [system/udev/](../../../system/udev/), [system/bin/](../../../system/bin/), [system/polkit/](../../../system/polkit/) | Authoritative payloads. Copy bytes; do not generate rule text. |
| New `scripts/lib/hardware_access.sh` plus a thin `scripts/install_hardware_access.sh` | The only hardware entrypoint. Dispatcher and GUI both use it. Installation recipes live here, not in the GUI. |

USB and input rules are seat `uaccess` rules. The sysfs rule is not: it
`chgrp`s backlight attributes to `video` and group-writes them. Installing it
does not add the caller to `video`. Say that in the wizard and in the recheck.
Do not describe all three rules as seat ACLs.

The power helper stays `#!/usr/bin/env python3`. Do not retarget that shebang at
the AppImage mount or the bundled interpreter. The helper is a host script.

The polkit rule returns YES only for the local active user and only for
`/usr/local/bin/keyrgb-power-helper` (plus the matching action id). Do not point
it at a `/tmp` path, the AppImage mount, or a shell.

## Command contract

These commands do not exist yet:

```bash
./install.sh --hardware-access-only
./install.sh --hardware-access-only --reactive-input
./install.sh --hardware-access-only --power-controls
```

- Flags are explicit. Environment defaults from the full installer must not
  select reactive input or power controls in this mode.
- Repeated runs are idempotent. Byte-identical managed files need not be rewritten.
- A missing selected file is still installed. A managed file with different bytes
  is updated in place, including legacy KeyRGB copies recognized by
  `is_keyrgb_managed_*` in [scripts/lib/uninstall_match.sh](../../../scripts/lib/uninstall_match.sh).
- If the destination exists and is not a KeyRGB-managed file, do not overwrite it.
  Any conflict found in preflight stops the entire selected operation before
  writes. Report the conflicting file and let the user retry with different
  selections. If a conflict is discovered after a write, stop and report the
  partial result. Never delete the foreign file or silently install a subset.
- No arbitrary source or destination filenames, and no executable command argument.
- `--payload-dir` is an internal argument of the hardware module, not a public
  installer feature. It accepts only the directory the caller just staged. Reject
  `..`, symlinks, and any destination override.

`install.sh` must accept `--hardware-access-only` itself. Today an unknown flag
is forwarded to `install_user.sh`, which exits on unknown arguments. That is
safe only as a failure; it is not the implementation.

## Acquisition and writes are separate

One writer. Three ways to obtain the payload, chosen before the writer runs:

| Caller | Payload source | Network |
|---|---|---|
| GUI / Settings, AppImage | Files bundled in that AppImage, located via `APPDIR` | Never |
| GUI / Settings, checkout | Repo `system/` next to the source tree when `APPDIR` is unset | Never |
| `./install.sh` from a checkout | Local `system/` | No |
| curl-pipe `install.sh --hardware-access-only` | `bootstrap_and_run` fetches only the hardware entrypoint, its library, and `uninstall_match.sh`. The hardware module then downloads the selected `system/` files for the explicit ref and calls the same writer | Yes, ref only |

Rules:

- The GUI path must not be able to construct a GitHub URL. Test that the GUI
  module and the privileged command contain no `raw.githubusercontent.com`.
- The new mode does not fall back to `main` on a bad ref. A failed download is
  a failed run.
- Extend `bootstrap_and_run` so it fetches the new entrypoint, `hardware_access.sh`,
  and `uninstall_match.sh`. It must not grow a second downloader for `system/`
  files. The hardware module downloads those after it knows which components
  were selected. `install.sh` does not guess `--reactive-input` or `--power-controls`.
- The full installer keeps its old ref-to-`main` acquisition and its best-effort
  reload. Only the file write moves to the shared placer. Do not route full-install
  downloads through the new fail-closed fetcher, and do not make a `udevadm`
  failure abort desktop integration. The new mode's own reload is fail-closed.
- The privileged worker must not source [scripts/lib/user_integration.sh](../../../scripts/lib/user_integration.sh)
  or [scripts/common.sh](../../../scripts/common.sh). Those load unrelated
  installer definitions, including AppImage downloading and `require_not_root`;
  sourcing them does not itself download anything or invoke that check. Share
  only the new hardware library and narrowly required managed-file matching
  helpers. Every sourced library is part of the verified executable payload.

## Privilege boundary

```text
Unprivileged GUI or CLI
  → resolve payload (bundle, checkout, or explicit ref download)
  → hash each selected file
  → one authorization
  → fixed verifier copies the entrypoint and all sourced libraries into a
    root-owned temp and verifies every copy before executing any of that code
  → root worker copies each payload file once into a root-owned temp, hashes
    that copy, and installs only from the copy when the hash matches
  → direct udevadm reload/trigger (no sudo)
  → exit status and captured logs
  → unprivileged recheck and user-facing result
```

CLI and GUI do not authorize the same way:

- CLI: the user runs the hardware module. It may call `sudo` when not root.
  Keep that prompt. Do not `pkexec` the CLI path.
- GUI: `pkexec` only. Do not elevate Python, Tk, the AppImage, or `install.sh`.
  Do not fall back to `sudo` inside the GUI. If `pkexec` is missing, show that
  and point at the terminal command. Pass `--disable-internal-agent` so a missing
  graphical authentication agent cannot fall back to an invisible terminal prompt.

`pkexec` drops the environment, and root often cannot read the AppImage FUSE
mount. The unprivileged side therefore stages payload **data** to a private
`0700` directory before `pkexec`, then passes absolute paths, component flags,
and expected hashes as arguments. Do not rely on `APPDIR` or `KEYRGB_*` inside
the privileged process.

Do not `pkexec` a user-writable staged script. A swapped script skips whatever
checks it contains, and a swapped udev rule or power helper is root execution
(`RUN+=` in a rule; a YES polkit rule for `/usr/local/bin/keyrgb-power-helper`).

Required handoff:

- The authorized command is
  `pkexec --disable-internal-agent /bin/sh -c '<fixed verifier>' _ …args`.
  Do not add `--keep-cwd`. `pkexec` starts in root's home, so a relative `source`
  would not see the staged directory; making cwd the staged directory would
  re-open that path. Every executable path must be the absolute root-owned copy.
- Hash algorithm is `sha256sum` in both the GUI and the verifier. A hash is 64 hex
  characters. Do not accept a second algorithm.
- "Unexpected modes" means reject symlinks, setuid/setgid, and world-writable
  staged files. Do not require the staged mode to equal the installed mode.
  Umask may leave a staged copy at `0600` while the installed rule is `0644`
  and the helper is `0755`. Set the installed mode explicitly.
- The verifier body is a constant in the GUI, not a file from the staged directory.
  Paths and hashes are positional parameters, never interpolated into the script text.
- The verifier copies `scripts/install_hardware_access.sh` and **every library it
  sources**, including `scripts/lib/hardware_access.sh` and any reused matching
  helper, into a root-owned temp. Each copy must match its hash computed from the
  bundled source before the verifier execs the entrypoint. Preserve the small
  required directory layout; source code only from these verified root-owned
  copies, never from the staged directory, checkout, or AppImage mount. A library
  must not verify itself after being sourced. Then the worker does the same
  copy-once, hash, install-from-copy for each selected data/helper payload file.
- Refuse symlinks, unexpected modes, non-regular files, and destination overrides.
- The in-app explanation is the user-facing consent text. The polkit dialog will
  name `/bin/sh`, not KeyRGB. Do not install a policy just to change that caption.
- One authorization. The worker is already root, so it must not call `sudo`.
  This includes `udevadm`. Nested prompts are a step 1 failure, not a step 2 bug.
- Preflight selected payload files before prompting. As root, before the first
  write, preflight destination parents (`/etc/udev/rules.d`, and for power
  controls `/usr/local/bin`, `/etc/polkit-1/rules.d`, `/usr/share/polkit-1/actions`)
  and, for power controls only, system `python3`. If a selected component cannot
  be installed, write nothing and report that component. The user can retry
  without it. Do not claim rollback that was not implemented. A failure after
  the first successful write is a partial install and must be reported as such.
- Immutable `/usr` fails the power-controls option only. It must not block a
  later udev-only retry.
- The root worker must not probe devices and must not return success because
  root could open a node. Session ACLs are not root access.

Authorization outcomes belong to the GUI/process wrapper, not to a worker that
never started. `pkexec` exits 126 when the authentication dialog is dismissed
and the program is not run. Exit 127 is also what `pkexec` uses for denial or
launch failure, and what bash uses when a command is missing under `set -e`.
Do not treat every 127 with empty stdout as "the worker never started."

- 126 and no worker result line: `cancelled`. Nothing was written.
- 127 and no worker result line: `authorization-failed` only when stderr is
  `pkexec`'s own message (`Error executing command as another user`,
  `Not authorized`, or the no-agent text). Confirm the exact strings on the
  polkit versions under test, including a missing graphical agent with the
  internal agent disabled.
- Any other non-zero without a valid result line, including a worker exit 127:
  `failed`, with an unknown write state. Do not claim that nothing was written.
- If a worker result line exists, trust that outcome, not the exit-code class.
- The verifier and worker must not exit 126 or 127 on purpose. Normalize their
  failures to other statuses plus the result line. A missing graphical agent
  uses the same terminal-command fallback as a missing `pkexec`.

## Result contract

Exit 0 means only: every selected file was installed or already matched, and
reload was attempted without a swallowed error. It does not mean the session
user can use the hardware.

The verifier/worker reports installation outcomes in its exit status and a short
stable line on stdout. The GUI validates the line/status pair and synthesizes
pre-launch outcomes itself; a worker that never ran cannot emit them. The GUI
does not infer success from a closed dialog or a zero exit alone.

| Outcome | Meaning |
|---|---|
| `installed` | Selected files written or already current, and reload ran. |
| `cancelled` | GUI-synthesized. 126 and no worker result line. Nothing was written. |
| `authorization-failed` | GUI-synthesized. 127, no worker result line, and stderr is pkexec's own message. Not cancellation. A missing graphical agent also points at the terminal command. |
| `prerequisite` | GUI preflight for missing `pkexec`/payload, or verifier/worker preflight for missing `udevadm`, payload, system `python3` for power controls, or an unwritable destination. A known missing graphical agent is a GUI prerequisite failure. No installation writes occurred. |
| `conflict` | Worker preflight found a destination that is not KeyRGB-managed. Stop the entire selected operation with a nonzero result before writes; no foreign file is replaced. |
| `failed` | Verification, a write/reload, or execution failed; also the GUI fallback for a non-zero exit without a valid result line. Include `written=none` only when the worker knows it wrote nothing. If the write state is unknown, omit that claim. Allow a safe retry. |
| `reload-incomplete` | Not a shell success claim about access. Reserved for the unprivileged recheck, not for the root worker. |

Reload must fail the run if `udevadm` is missing or a reload/trigger command
fails. Do not use `|| true` on those commands in the new path.

## Recheck, stale rules, and group membership

After `pkexec` returns, the GUI rechecks as the user through existing read-only
probe / permission-denied classification and diagnostics devnode mode/ACL data.
Do not write lighting to test setup. Do not add a new detector.

Report incomplete activation instead of usable hardware when:

- rules were installed but the open is still denied (ACL not active until
  replug, re-login, or reboot)
- the sysfs rule is installed and the user is not in `video` — re-login will
  not fix that, because this task does not add the group

Stale rules are an offer, not incomplete activation. After a successful install
the bundled and installed bytes must match. If they still differ, the install
failed. Do not tell the user that activation is incomplete because the rules
are stale.

Also offer setup when the bundled rules differ from the installed managed
copies, even if the last probe did not fail. `--update-appimage` intentionally
skips udev, so a newer AppImage does not refresh new USB IDs by itself.
Unprivileged reads of `/etc/udev/rules.d` are enough for that compare. A missing
installed file is an offer, not an error.

No supported device, or an unsupported device, is not a permissions failure.
Do not prompt on catalog or test machines that have no matching hardware.

## Wizard

- One small setup window and a thin process wrapper. Reuse existing Tk
  subprocess and scheduling patterns. Do not extend
  `keyrgb/gui/perkey/setup_workflow/`; that first-run is calibration, not udev.
- Settings action lives on the existing About & Support surface next to Support
  Tools. Do not add a settings category for this.
- Callers for the offer: an existing probe or permission notification that
  already classified permission denied, a bundled-vs-installed rule mismatch,
  and the Settings action. Always allow the Settings action. Do not force a
  prompt when evidence is absent.
- Explain the selected files before authorization. Reactive input and power
  controls are separate unchecked choices. Copy for reactive input must say it
  allows observing keypresses. Copy for the sysfs rule must say the user needs
  to be in `video`. Copy must say skipping does not remove files already
  installed, and that removal is the existing uninstaller or manual deletion of
  the managed filenames. This wizard does not uninstall.
- Offer **Not now**. Remember dismissal in the existing config store. Do not
  persist "configured" because a dialog closed or a script returned 0. Permission
  checks must not consult the dismissal flag.
- If `pkexec` is missing, or the graphical agent is missing, say so and point
  at the terminal hardware-only command. Do not fall back to `sudo` in the GUI.
- Run work off the Tk event loop. Disable duplicate submissions. Surface logs
  and the result-contract line. Marshal completion back through existing UI
  scheduling.
- Checkout launches without `APPDIR` use the repo `system/` tree so the Settings
  action works from a source tree.

## Implementation tracker

Complete one bounded slice at a time. Record exact edited paths, commands, and
remaining limitations below. Implementation starts at the first unchecked row.

| Step | Status | Bounded work / exit condition |
|---|---|---|
| 0 — Plan | Complete | Reuse points, privilege handoff, result contract, and acceptance checks documented. No runtime changes. |
| 1 — Shell seam | Complete | Added `scripts/install_hardware_access.sh` and `scripts/lib/hardware_access.sh`. Dispatcher routes `--hardware-access-only` and bootstraps those scripts, not `system/` payloads. New mode is fail-closed, uses `sha256sum`, and does not fall back to `main`. CLI `sudo`s only when not root. Existing helpers call the shared placer for the file write; ref-to-`main` acquisition and best-effort reload stay. Sandbox tests cover keyboard-only, both explicit options, prerequisites, download failure, conflict with zero writes, partial write, and repeat. No host `/etc` writes. |
| 2 — Bundle + authorization | Complete | AppImage build copies the entrypoint, both sourced libraries, and the system payloads to `usr/lib/keyrgb/hardware-access`. `keyrgb/gui/hardware_access.py` resolves `APPDIR` or the checkout, stages data, and builds one `pkexec --disable-internal-agent /bin/sh -c` command. The verifier hashes root-owned copies before running them. Tests cover dismissal, pkexec denial, missing agent text, a worker result that must win over exit 127, missing `pkexec`/`python3`, and a udev-only retry after an unwritable power destination. No wizard yet. |
| 3 — Thin wizard | Complete | Added `keyrgb/gui/hardware_access_window.py` and the offer rules in `keyrgb/gui/hardware_access_offer.py`. About & Support has **Set up hardware access…** beside Support Tools. Automatic offers require permission-denied evidence or a stale managed rule, and Not now is stored in the existing config file. Tests cover copy, dismissal, duplicate submission, retry, and honest install results. Per-key setup was not changed. |
| 4 — Acceptance + docs | Not started | Validate merged paths and an actual AppImage setup in disposable environments. Document the terminal fallback, optional-access implications, and that removal is uninstall.sh or manual deletion of managed names. Publish or catalog-retest only when separately authorized. |

Any scope expansion, group-membership change, or new persistent privileged
component requires an explicit decision recorded here first.

## Acceptance and validation

- [ ] Hardware-only mode does not invoke release downloads except the explicit
  curl-pipe ref fetch, and never invokes package managers, desktop/autostart
  setup, telemetry, or profile writes.
- [ ] GUI and privileged command contain no `raw.githubusercontent.com` and cannot
  fall back to `main`.
- [ ] Full install, dev, update-only, bootstrap, and uninstall contracts remain
  intact. Full install still defaults power helper on; the new mode does not.
- [ ] USB and sysfs rules install by default. Reactive-input and power-control
  files install only when explicitly selected. Installed bytes match the shipped
  files. Managed names still match `uninstall_match.sh`, including legacy markers.
- [ ] Foreign files at those destinations are not overwritten; any preflight
  conflict stops the entire selected operation before installation writes.
- [ ] Offline AppImage setup works with no system Python and no repository
  checkout. Power controls are the exception: they require host `python3` and a
  writable `/usr`, and fail that option honestly when either is missing.
- [ ] GUI/root boundary covers FUSE staging, paths with spaces, symlink/mode
  rejection, hash mismatch, missing `pkexec`/`udevadm`, dismissed authorization,
  immutable `/usr`, partial failure, and repeated runs. No privileged GUI, no
  nested `sudo`, no root device probe reported as user access.
- [ ] Entrypoint and every sourced library are copied and hash-verified before
  executing any of that code. A substituted/missing library fails without
  execution or installation writes; no source path points back to staged code.
- [ ] GUI uses `--disable-internal-agent` and does not pass `--keep-cwd`.
  Missing `pkexec` and a missing graphical agent both point at the terminal
  command. 126 with no result line is cancellation. 127 is authorization-failed
  only when stderr is pkexec's own message. Any other missing result line is
  `failed` with an unknown write state. Verifier/worker failures do not reuse
  126/127. Hashes are `sha256sum` only.
- [ ] Skipping setup or having no supported hardware leaves launch and Settings
  usable. A successful write still rechecks as the user. Not being in `video`,
  stale rules, and ACLs that need replug/re-login are reported as incomplete,
  not as usable hardware.
- [ ] Wizard copy states that setup does not remove rules, and that removal is
  the existing uninstaller or manual deletion of the managed filenames.
- [ ] AppImage compatibility smoke still passes on Ubuntu 22.04 and 24.04.

Validation during implementation:

1. `bash -n` and targeted `shellcheck` on touched shell paths. Focused installer
   pytest with mocked privilege, network, and system commands. Never write host
   `/etc` from tests.
2. Focused GUI, process, and payload pytest, plus targeted Ruff and mypy on
   edited Python. Include a test that the GUI payload resolver has no network URL.
3. `.venv/bin/python -m buildpython --run-steps=19` when touching fallback or
   runtime boundaries, then `.venv/bin/python -m buildpython --profile=ci` after
   merging.
4. A portable AppImage build, plus setup and compatibility smoke in disposable
   Ubuntu LTS environments. Run the release profile before any authorized release.
   An unavailable authorization agent or missing hardware is a recorded
   limitation, not a passing acceptance result.

Do not install or reload rules on the developer's host just to validate this plan.

## Progress / decision log

- **2026-10-05:** Tracker created. Approach agreed: explicit first-run/Settings
  hardware setup through a narrow hardware-only command. Implementation,
  privileged host changes, version bump, commit/push, release, and catalog retest
  are not part of the doc-only step.
- **2026-10-05:** Amended after review, still doc-only. The new mode must not call
  the current success-on-failure helpers or inherit their `main` fallback.
  Privilege handoff is one fixed shell verifier with argv hashes and
  root-owned copy-then-hash; do not execute a staged script. Sysfs access still
  depends on `video` membership, which this task does not grant. Offers also
  cover stale bundled rules. Power controls require host Python and stay opt-in.
  Removal stays with the existing uninstaller.
- **2026-10-05:** Applied follow-up review: verify the entrypoint and all sourced
  libraries before execution; abort all selected writes on a preflight conflict;
  separate wrapper-owned authorization outcomes from worker results and disable
  pkexec's internal terminal agent. Corrected the distinction between sourcing
  `common.sh` and calling `require_not_root`. Implementation scope remains unchanged.
- **2026-10-05:** Final polish before implementation. 127 is authorization-failed
  only when stderr is pkexec's own message; any other missing result line is
  `failed` with an unknown write state. Stale rules are an offer, not incomplete
  activation. Hashes are `sha256sum` only. Do not pass `--keep-cwd` or require
  staged modes to match installed modes. Curl-pipe payload download stays in the
  hardware module. The full installer keeps ref-to-`main` acquisition and
  best-effort reload; only the file write moves to the shared placer.
- **2026-10-05:** Step 1 implemented. Commands: `bash -n` on the touched shell
  files; `shellcheck -x` on those files (exit 0); `.venv/bin/python -m pytest -q
  -o addopts= tests/installer` (123 passed); Ruff check and format on
  `tests/installer/test_hardware_access_unit.py`. Not done: AppImage payload
  bundling, the `pkexec` verifier, the wizard, and disposable-environment
  acceptance. The full installer still reloads udev best-effort.
- **2026-10-05:** Step 2 implemented. AppImage bundling and the unprivileged
  `pkexec` wrapper are in place. Commands: `.venv/bin/python -m pytest -q -o
  addopts= tests/gui/test_hardware_access_setup_unit.py
  tests/buildpython/test_buildpython_appimage_hardware_access_unit.py
  tests/installer/test_hardware_access_unit.py` (36 passed); Ruff check and
  format on the new Python. Not done: the Settings wizard, first-run offer,
  and disposable-environment acceptance. No host `/etc` writes and no real
  `pkexec` prompt.
- **2026-10-05:** Step 3 implemented. Settings can open the setup window, and the
  tray offers it only when permission-denied evidence or a stale managed rule
  is present and Not now has not been saved. Commands: `.venv/bin/python -m
  pytest -q -o addopts= tests/gui/test_hardware_access_window_unit.py
  tests/gui/settings/window/test_version_panel_unit.py
  tests/tray/app/test_tray_application_run_notify_unit.py` (64 passed); Ruff
  check and format on the new Python. Not done: disposable-environment
  acceptance and a real authorization prompt.
