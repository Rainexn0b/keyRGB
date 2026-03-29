# ITE 8910 protocol notes

Protocol reference for KeyRGB's `ite8910` backend.

External references:

- Blog post: https://chocapikk.com/posts/2026/reverse-engineering-ite8910-keyboard-rgb/
- Reddit summary: https://www.reddit.com/r/XMG_gg/comments/1s509ps/reverseengineered_the_ite_8910_keyboard_rgb/

## Packet format

6-byte HID feature reports with report ID `0xCC`: `[0xCC, cmd, d0, d1, d2, d3]`

No 7th byte. The HID descriptor is malformed (declares 3-bit fields) but the firmware reads 6 bytes.

## Commands

| Command | Packet | Description |
| --- | --- | --- |
| Set Key Color | `[CC, 01, led_id, R, G, B]` | Per-key color |
| Brightness/Speed | `[CC, 09, brightness, speed, 00, 00]` | Brightness `0x00-0x0A`, speed `0x00-0x0A` |
| Animation Mode | `[CC, 00, mode_id, 00, 00, 00]` | Select firmware animation |
| Breathing Random | `[CC, 0A, 00, 00, 00, 00]` | Breathing with random colors |
| Breathing Color | `[CC, 0A, AA, R, G, B]` | Breathing with custom color |
| Flashing Random | `[CC, 0B, 00, 00, 00, 00]` | Flashing with random colors |
| Flashing Color | `[CC, 0B, AA, R, G, B]` | Flashing with custom color |
| Random Color | `[CC, 18, A1, R, G, B]` | Random with custom color |
| Wave Direction | `[CC, 15, slot, 00, 00, 00]` | Preset direction (rainbow) |
| Wave Color | `[CC, 15, slot, R, G, B]` | Custom direction + color |
| Snake Direction | `[CC, 16, slot, 00, 00, 00]` | Preset direction (multicolor) |
| Snake Color | `[CC, 16, slot, R, G, B]` | Custom direction + color |
| Scan Color 1 | `[CC, 17, A1, R, G, B]` | First band color |
| Scan Color 2 | `[CC, 17, A2, R, G, B]` | Second band color |

## Animation mode IDs

| ID | Mode |
| --- | --- |
| `0x02` | Spectrum Cycle |
| `0x04` | Rainbow Wave |
| `0x09` | Random |
| `0x0A` | Scan |
| `0x0B` | Snake |
| `0x0C` | Clear (required before per-key) |

## Wave direction slots

Preset (rainbow, direction only) and custom (color + direction) slots share the same direction mapping:

| Preset | Custom | Direction |
| --- | --- | --- |
| `0x71` | `0xA1` | Up-Left |
| `0x72` | `0xA2` | Up-Right |
| `0x73` | `0xA3` | Down-Left |
| `0x74` | `0xA4` | Down-Right |
| `0x75` | `0xA5` | Up |
| `0x76` | `0xA6` | Down |
| `0x77` | `0xA7` | Left |
| `0x78` | `0xA8` | Right |

Only the last slot sent is active. Preset and custom cannot be combined.

## Snake direction slots

4 diagonal directions only:

| Preset | Custom | Direction |
| --- | --- | --- |
| `0x71` | `0xA1` | Up-Left |
| `0x72` | `0xA2` | Up-Right |
| `0x73` | `0xA3` | Down-Left |
| `0x74` | `0xA4` | Down-Right |

## LED ID encoding

`((row & 0x07) << 5) | (col & 0x1F)` for the 6x20 LED matrix.

## Command sequence

Animation modes:

1. `[CC, 00, mode_id, 00, 00, 00]` to activate the mode
2. `[CC, 15/16/17/18, slot, R, G, B]` for direction or custom colors when applicable
3. `[CC, 09, brightness, speed, 00, 00]` to set brightness and speed

Per-key direct mode:

1. `[CC, 00, 0C, 00, 00, 00]` to clear the deck
2. `[CC, 09, brightness, speed, 00, 00]` to set brightness
3. `[CC, 01, led_id, R, G, B]` for each key

## Notes

- The Uniwill Control Center (`LedKeyboardSetting.exe`, rebranded by XMG/TUXEDO/Eluktronics) replaces black `(0, 0, 0)` with red `(255, 0, 0)` as a default color for custom-color modes. That is a software choice, not a firmware limitation.
- ClearColor (`0x0C`) stops the active animation but LEDs retain their last color. Send black to all LEDs after clear for a full reset.
- Brightness max is `0x0A` and the firmware clamps internally.
- Resending the animation mode command restarts the animation. Only send it when the mode actually changes, not on every color or speed update.
- Resending brightness/speed when unchanged can cause firmware timing issues. Track the current values and only send them when they change.