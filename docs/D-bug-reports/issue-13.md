## Issue 13: MEDION ERAZER Beast X30 (`048d:6005` / `048d:ce00`)

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/13

Status as of 2026-09-16:

- The reporter confirmed the traditional 4-zone keyboard and attached a full
  KeyRGB 0.35.0 support bundle.
- The bundle identifies `048d:ce00`, `bcdDevice 0x0002`, on `/dev/hidraw5` with
  read/write access. The reporter then tested `ite8291_zones_clevo`: all four
  zones, RGB channel order, brightness, and off/on work without flicker.
- The separate `048d:6005` controller appears on `/dev/hidraw4` with read/write
  access. OpenRGB's dedicated `IonicoController` independently identifies this
  exact VID/PID and expected HID usage `0xFF03:0x01` as the **Ionico Light Bar**.
- KeyRGB now has a separate opt-in auxiliary backend,
  `ite8291_none_chassis_lightbar_tongfang`. It does not alter or participate in
  selection of the `ce00` keyboard backend.

## Controller split

The two ITE devices use separate roles and protocol paths:

- `048d:ce00`, `bcdDevice 0x0002`: four-zone keyboard through
  `ite8291_zones_clevo`.
- The four-zone backend now advertises zoned spatial output separately from
  per-key control. Software and reactive effects render across the four logical
  zones, while per-key profiles and calibration remain unavailable as intended.
- `048d:ce00`, `bcdDevice 0x0003`: validated per-key keyboard through
  `ite8291r3_perkey`.
- `048d:6005`: independent Tongfang / Ionico front lightbar through
  `ite8291_none_chassis_lightbar_tongfang`.

The lightbar implementation is based on OpenRGB's current
`Controllers/IonicoController` source, not on the unrelated
`ite8233_none_chassis_lightbar_clevo` PID table. It is registered as an
experimental auxiliary backend and has its own hidraw uaccess rule.

## Known lightbar evidence gap

OpenRGB declares 22 lightbar LEDs but sends a 65-byte direct report containing
one report-ID byte. Only 21 complete RGB triplets fit. Its C++ loop writes two
bytes beyond that local buffer for LED 22, although only 65 bytes are sent.
KeyRGB does not reproduce the overflow or send a partial RGB triplet: it writes
only the 21 complete triplets and leaves the final report byte zero.

The backend also avoids the documented persistence command by default. Hardware
effects remain unadvertised until direct color, brightness, off/on, RGB ordering,
and the visible treatment of the final lightbar segment are tested on this
machine.

## Next validation step

Provide an AppImage or build containing the new backend, then ask the reporter
to enable experimental backends, restart KeyRGB, select **Front Lightbar**, and
test low-brightness red, green, blue, brightness, and off/on with all competing
RGB software closed. Record whether every visible segment changes uniformly,
especially the final segment, and attach a fresh full support bundle from
**Settings → About & Support → Support Tools**.

Additional static evidence remains useful:

```bash
lsusb -v -d 048d:6005
sudo usbhid-dump -d 048d:6005 -e descriptor
```

Do not force either backend to the other controller's hidraw node.

## v0.36.2 reporter feedback (2026-09-17)

- Hardware effects: PASS (reporter wording; `ite8291_zones_clevo` advertises
  `hardware_effects=False`, so this likely means static hardware output).
- Software effects: PASS.
- 4 keyboard zones: PASS.
- Lightbar behaviour: PASS.
- Brightness control: PASS.
- Lighting off/on: FAIL.
- Flicker occurs only after the laptop is unused for a while.
- Screenshot shows Software Effects > Rainbow Wave active with
  `Include enabled lighting areas` checked; reporter says
  “I somehow cannot use 1 color anymore.”

Triage:

- A saved single lightbar color is temporarily owned by the running software
  effect while `Include enabled lighting areas` is checked. Unchecking that
  toggle (or stopping the software effect) restores the saved static color.
  This is expected routing ownership, not a lightbar protocol failure.
- Auxiliary Front Lightbar off/on/brightness had a verified fresh-device bug:
  nonzero brightness and Turn On called `set_brightness()` on a newly acquired
  device whose cached color defaults to white, losing the saved color. State
  was also persisted before hardware success, and restore could fall back to
  25 instead of preserved profile brightness. Fixed in the worktree by doing
  hardware I/O first, applying the persisted route color with
  `set_color(color, brightness=...)`, and preferring the active-profile
  brightness on restore.
- No deterministic failure was found in the explicit primary keyboard
  Turn Off/On path. The generic `Lighting off/on: FAIL` remains ambiguous
  (bottom Turn Off/On versus Turn Off/On Front Lightbar; keyboard versus
  lightbar; Off fails versus On restores wrong color; static versus software
  effect).
- Idle-only flicker is separate from the immediate toggle. Candidates are
  controller-native inactivity sleep (the 4-zone backend reports cached
  brightness/off state and cannot observe autonomous firmware darkening),
  desktop screen-idle sync issuing off/restore, or per-frame zone-enable
  traffic (KeyRGB sends enable + colors + commit per frame; upstream TUXEDO
  enables once at probe/resume, then sends colors + commit). No zone-protocol
  change was made pending hardware evidence.
- Both backends remain experimental; do not promote to validated yet.

Next evidence needed: exact menu label clicked, affected device, active effect,
static versus software-effect behavior, screen on/dimmed/blanked/locked state,
delay after last keypress, whether keypress stops it, screen-idle sync and
controller-sleep settings, competing RGB tools, `/sys/class/leds`, and a
`keyrgb --diagnostic-session` capture spanning the event.
