# Contributing to KeyRGB

Thanks for your interest in contributing.

## What this project is

KeyRGB targets laptop keyboards driven by ITE 8291 / ITE8291R3-style controllers on Linux. The goal is a practical tray app + per-key editor with a calibration-based key mapping workflow.

## Development setup

- Python 3.8+
- A Linux desktop session (tray icon support)

Install editable + dev deps:

```bash
python3 -m pip install -e ".[dev]"
```

Run locally:

```bash
keyrgb
keyrgb-perkey
keyrgb-calibrate
```

## Tests

Run unit tests:

```bash
pytest
```

Some tests may be hardware-gated; do not assume CI has the device.

## Adding support for a new keyboard revision

KeyRGB is designed so that different laptop revisions can be supported without rewriting the app.

### 1) Add/adjust the visual layout

- Update the key rectangles and labels in `src/y15_pro_layout.py` (or add a new layout module if you want to avoid mixing revisions).
- The deck image coordinate space is `BASE_IMAGE_SIZE` (currently 1008×450).

### 2) Calibrate the mapping

- Run `keyrgb-calibrate`.
- Save the keymap.
- Verify per-key changes in `keyrgb-perkey`.

### 3) Validate profiles

If your revision differs only in key positions/labels, create a new profile and commit documentation (screenshots + notes). Profiles store:

- keymap
- global overlay alignment
- per-key overlay alignment
- per-key colors

### 4) Keep hardware ownership in mind

The tray app is intended to be the single USB owner. GUIs primarily write config; the tray applies changes.

## Style / PR guidance

- Keep changes small and focused.
- Prefer backwards-compatible config changes.
- Don’t add new UI complexity unless needed for correctness.
- If you change a workflow, update README.

## Reporting device info

When filing issues, include:

- Output of `lsusb | grep 048d` (or your device’s vendor/product)
- Distro + DE + kernel version
- Whether you are running other RGB tools (OpenRGB, vendor daemons)

## Tech debt / maintainability

We track maintainability hot spots and refactor ideas in `docs/genAI/tech-debt/`:

- `docs/genAI/tech-debt/README.md`
- `docs/genAI/tech-debt/hotspots.md`
- `docs/genAI/tech-debt/tracking.md`
