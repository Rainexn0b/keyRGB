# ITE 8910 protocol notes

Maintainer reference for future correction work on KeyRGB's experimental `ite8910` backend.

External references:

- Blog post: https://chocapikk.com/posts/2026/reverse-engineering-ite8910-keyboard-rgb/
- Reddit summary: https://www.reddit.com/r/XMG_gg/comments/1s509ps/reverseengineered_the_ite_8910_keyboard_rgb/

Key takeaways to verify against the current backend implementation:

- The controller is described as using 6-byte HID feature reports with report ID `0xCC`, not 7-byte packets.
- The protocol is described as distinct from the older ITE 8291 / 829x row-write model.
- Per-key writes are described as `[0xCC, 0x01, led_id, R, G, B]`.
- A clear/reset command is described as required before per-key updates: `[0xCC, 0x00, 0x0C]`.
- Brightness is described as a 0..10 device-scale command on `[0xCC, 0x09, brightness, speed, 0x00, 0x00]`.
- The LED ID encoding is described as `((row & 0x07) << 5) | (col & 0x1F)`.
- Linux `hidraw` writes are described as depending on the kernel HID stack having initialized the device first.

These notes are not a claim that KeyRGB is already aligned with that protocol. They are a starting point for validating and correcting the experimental backend.