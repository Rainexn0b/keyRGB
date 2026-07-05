# Issue 4 — Initial report and first diagnosis

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/4

Date range: late March 2026

Reporter environment:

- KeyRGB `0.18.2`
- Linux Mint `22.3` / Cinnamon
- Clevo `X58xWNx`
- ITE 8910 (`0x048d:0x8910`) selected through `ite8910`

Reported symptoms:

1. The keymap calibrator showed an ANSI-style keyboard and could not assign
   ISO-only keys.
2. The per-key editor lit the wrong physical key, with a visible row inversion.
3. Software effects blinked on and off.
4. Hardware effect speed was reversed: lower UI values looked faster.

Maintainer notes:

- `ite8910` was being selected correctly, so the bug surface was not basic
  detection.
- The issue appeared to involve layout/calibrator wiring, tuple-to-LED
  translation, software-effect mode policy, and backend-specific speed mapping.
- The next step was a retest on `0.18.6` after an initial layout/catalog fix.
