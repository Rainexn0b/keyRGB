# Contributing to KeyRGB

Thanks for your interest in contributing. KeyRGB is a Linux-first tray app plus GUI toolkit for laptop keyboard lighting, with most of the complexity split across backend/device support, layout and calibration data, and tray/runtime orchestration.

## Good contribution candidates

- New user-facing features
- New backend implementations or expanded device support
- Layout or calibration improvements
- Diagnostics, installer, or support-tool improvements
- Tests, docs, or maintainability work

## Before you start

- If you are changing architecture, backend policy, or install behavior, open an issue or draft PR early so the direction can be reviewed before the implementation gets large.
- If you are adding device support, collect evidence first:

```bash
keyrgb-diagnostics
lsusb
```

Also note your distro, kernel, desktop session, and whether other RGB tools or vendor daemons are running.

## Development setup

Requirements:

- Python 3.10+
- A Linux desktop session if you need to exercise the tray or Tk windows

Quick setup:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Alternative:

```bash
./install.sh --dev
```

Useful local entrypoints:

```bash
./keyrgb
keyrgb-settings
keyrgb-perkey
keyrgb-uniform
keyrgb-reactive-color
keyrgb-calibrate
keyrgb-diagnostics
```

## Project map

- `src/core/backends/`: backend contracts, probing, device opens, protocol helpers, backend policy, and registration
- `src/core/diagnostics/`: diagnostics JSON, hardware discovery, support/evidence helpers
- `src/core/effects/`: software and reactive effect engine code
- `src/core/resources/`: visual layout specs, layout catalog, legend packs, starter keymaps, and reference defaults
- `src/core/config/` and `src/core/profile/`: persisted settings, profile storage, defaults, and migrations
- `src/gui/`: settings, calibrator, per-key editor, reusable widgets, and standalone windows
- `src/tray/`: startup, lifecycle, controllers, menu building, runtime polling, and tray icon behavior
- `scripts/` and `system/`: installer, desktop integration, udev, polkit, and AppImage plumbing
- `tests/`: mirrors runtime ownership closely; add tests in the nearest relevant slice

## Project rules that matter for contributors

- Prefer sysfs or kernel-backed integrations before adding a direct USB or HID backend.
- Keep behavior capability-driven. Use `BackendCapabilities` and `backend_caps` instead of backend-name special cases where possible.
- Preserve public script entrypoints in `pyproject.toml` unless the change intentionally alters the user-facing command surface.
- Keep tray/runtime orchestration in `src/tray/`; avoid duplicating long-running hardware-control logic inside GUI windows.
- Unit tests must stay hardware-safe by default. Normal `pytest` runs intentionally avoid scanning real USB devices or touching real `/sys` lighting state.
- Do not edit generated output in `buildlog/` or `htmlcov/`.

## Contributing a feature

- Put code in the nearest owner first. Backend logic belongs in `src/core/backends/`, tray lifecycle and polling in `src/tray/`, windows in `src/gui/`, and installer/system integration in `scripts/` or `system/`.
- Keep changes small and focused. If a feature also changes config shape, docs, or startup behavior, update those in the same PR.
- Add or update targeted tests near the touched area before reaching for broad repo-wide refactors.
- If a feature changes what users can do or how they enable it, update `README.md`.

## Contributing a layout or calibration improvement

If you are supporting another keyboard revision, first decide whether it is:

- an existing physical family with different calibration or default data
- a genuinely new visual layout family

For existing layout families:

- layout IDs and UI labels live in `src/core/resources/layouts/catalog.py`
- starter keymaps and tweak data live in `src/core/resources/reference_defaults_specs/`
- per-key overlay and default tweak files live in `src/core/resources/reference_defaults_specs/per_key_tweaks/`
- legend-pack overrides live in `src/core/resources/layout_legend_specs.json`

For new visual families:

- declarative visual layout specs live in `src/core/resources/layout_specs.json`
- rendering and layout-build logic lives in `src/core/resources/layout.py`
- the reference deck image coordinate space is `BASE_IMAGE_SIZE` in `src/core/resources/layout.py` (currently `1008x450`)

Validation for layout work:

```bash
keyrgb-calibrate
keyrgb-perkey
.venv/bin/python -m pytest tests/core/resources tests/gui/calibrator tests/gui/perkey -q -o addopts=
```

## Contributing a backend or new device support

1. Confirm whether a kernel or sysfs path already exists. If Linux already exposes the keyboard through `/sys/class/leds`, extend that path before adding a new direct controller implementation.
2. Gather evidence before writing code: `keyrgb-diagnostics`, `lsusb`, relevant `hidraw` or sysfs paths, permission behavior, and any protocol notes or captures you are relying on.
3. Add the backend under `src/core/backends/<backend_name>/`. Most backends split into a `backend.py`, `device.py`, and protocol/helper modules.
4. Implement the backend surface defined in `src/core/backends/base.py`: metadata (`name`, `priority`, `stability`, `experimental_evidence`) plus `probe()`, `capabilities()`, `get_device()`, `dimensions()`, `effects()`, and `colors()`.
5. Register the backend in `src/core/backends/registry.py`.
6. Start new or weakly proven backends as `experimental` unless there is strong real-hardware validation. Use the evidence tag so diagnostics can distinguish research-backed work from speculative work.
7. Do not add USB IDs to an existing ITE backend unless protocol compatibility is actually established. Detection similarity is not enough.
8. Translate permission, busy-device, disconnect, and transport failures into the backend exception types rather than letting raw library errors leak to users.
9. Add targeted tests in `tests/core/backends/` and update `README.md` if the support matrix, environment variables, or troubleshooting steps changed.
10. If the backend needs new permissions or helper plumbing, update the matching files under `system/` and `scripts/` in the same PR.

## Validation

Focused validation is preferred while you iterate:

```bash
.venv/bin/python -m pytest <target> -q -o addopts=
```

Full test suite:

```bash
.venv/bin/python -m pytest -q -o addopts=
```

Hardware tests are opt-in only:

```bash
KEYRGB_HW_TESTS=1 .venv/bin/python -m pytest -q -o addopts=
```

Repo gate discovery:

```bash
.venv/bin/python -m buildpython --list-profiles
.venv/bin/python -m buildpython --list-steps
```

Common gate runs:

```bash
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --profile=full --with-black
.venv/bin/python -m buildpython --profile=release
```

If you use numeric step selectors, list steps first. Step numbers can move as the pipeline changes.

## Pull request expectations

- Keep PRs narrow enough that the motivation, changed ownership area, and validation are easy to review.
- Include the exact commands you ran.
- State clearly whether the change was validated on real hardware, mocked tests only, or both.
- For backend or device-support work, include diagnostics output, USB IDs, and any permission or udev requirements.
- Update `README.md`, `CONTRIBUTING.md`, or deeper docs when the user-facing workflow, support matrix, install behavior, or contributor workflow changes.
- For GUI changes, screenshots are helpful when the change is materially visual.

## Useful references

- `README.md`
- `docs/usage/01-build_runner.md`
- `docs/usage/04-hardware_tests.md`
- `docs/developement/backends/`
- `tests/conftest.py` for hardware-safety assumptions in normal test runs

## Reporting issues

When filing an issue, include:

- `keyrgb-diagnostics`
- `lsusb` output for the relevant controller
- distro, kernel, desktop environment, and Wayland or X11 session details
- whether other RGB tools or vendor daemons are running
- steps to reproduce and what you expected instead
