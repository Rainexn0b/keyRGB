# Commands

This page documents KeyRGB’s installed entrypoints and common environment variables.

## Entry points

| Command | What it does |
| --- | --- |
| `keyrgb` | Start the tray app (background). |
| `./keyrgb` | Run the tray app attached to the terminal (dev mode, repo checkout). |
| `keyrgb-perkey` | Open the per-key editor. |
| `keyrgb-uniform` | Open the uniform-color GUI. |
| `keyrgb-calibrate` | Open the keymap calibrator UI (usually launched from per-key editor). |
| `keyrgb-diagnostics` | Print hardware diagnostics JSON (useful for bug reports). |

## Environment variables

| Variable | Usage |
| --- | --- |
| `KEYRGB_BACKEND` | Force backend: `auto` (default), `ite8291r3`, or `sysfs-leds`. |
| `KEYRGB_DEBUG=1` | Enable verbose debug logging. |
| `KEYRGB_TK_SCALING` | Float override for UI scaling (High-DPI / fractional scaling). |
| `KEYRGB_TCCD_BIN` | Override the `tccd` helper path for TCC integration. |

## Tray effects (names)

These are the effect names stored in `~/.config/keyrgb/config.json` under the `effect` key.

- Hardware (firmware) effects: `rainbow`, `breathing`, `wave`, `ripple`, `marquee`, `raindrop`, `aurora`, `fireworks`
- Software effects: `rainbow_wave`, `rainbow_swirl`, `spectrum_cycle`, `color_cycle`, `chase`, `twinkle`, `strobe`
- Reactive typing: `reactive_fade`, `reactive_ripple`
- Per-key static map: `perkey`

Notes:
