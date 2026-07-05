# Initial device mapping (Tongfang-focused)

This file is an early, evolving mapping of USB IDs and chassis families.

Notes on sources:

- USB PID list for the ITE8291R3-style path is best taken from the upstream `ite8291r3-ctl` driver (`VENDOR_ID` + `PRODUCT_IDS`).
- Chassis ↔ brand mapping below includes information copied from a Gemini summary provided by a user; treat it as **unverified** until corroborated by real `keyrgb-diagnostics` reports.

## USB IDs (ITE via `ite8291r3-ctl`)

KeyRGB probes using vendor `0x048d` and the product IDs declared by the upstream driver.
If you see one of these in `keyrgb-diagnostics`, the ITE backend is a likely match.

| USB ID | Likely controller family | Notes |
|---|---|---|
| `048d:ce00` | ITE 8291 (rev 0.03) | Common in 2023–2025 units. |
| `048d:6004` | ITE 829x series | Reported in newer 16"/17" chassis (XMG). |
| `048d:6006` | ITE 829x series | Same family; Tuxedo Stellaris and similar high-end units. |
| `048d:6008` | ITE 8291 (Generic) | Generic RGB controller; protocol identical to 0x6004. |
| `048d:600a` | ITE 8291 (Tuxedo) | Tuxedo Stellaris / Polaris variants. |
| `048d:600b` | ITE 8291 (rev 0.03) variant | WootBook/Tongfang rebrands; 2023+ iterations. |

If you see `048d:....` with an unknown PID, it may still be ITE, but it might also be a different stack (e.g. sysfs `tuxedo_keyboard` style).

## Chassis mapping (UNVERIFIED; from Gemini summary)

| Tongfang chassis | Brand equivalents (examples) | Notes |
|---|---|---|
| `GM5HG0Y` | WootBook Y15 Pro G (2025) / Tuxedo InfinityBook Pro 15 Gen10 | Reported as Ryzen AI 9 / RTX 50xx generation. |
| `GX5` / `X5SP4` | Tuxedo Sirius 16 Gen2 / LaptopWithLinux GX5 | ITE 8291/8297-class controllers; often per-key RGB. |
| `GM6HG7Y` | WootBook Y16 / XMG Neo 16 (2025) | 16" chassis; sometimes “dock” marketed. |
| `GM7*` series | WootBook X17 / XMG Neo 17 | Often reported with ITE 8297-class controller (may need quirks later). |
| `PH4` / `PH6` | WootBook Slim / Tuxedo Pulse 14 | Often single-zone; sometimes exposed via sysfs LEDs (`tuxedo::kbd_backlight`). |

## Sysfs LED naming patterns to watch

Kernel/driver naming varies. Likely keyboard LED nodes include:

- `/sys/class/leds/tuxedo::kbd_backlight/`
- `/sys/class/leds/white:kbd_backlight/`
- `/sys/class/leds/ite_8291_lb:kbd_backlight/`

KeyRGB’s sysfs backend looks for LED names containing `kbd`/`keyboard`, which should match the above.
