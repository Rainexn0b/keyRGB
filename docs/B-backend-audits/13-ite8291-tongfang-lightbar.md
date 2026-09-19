# Audit: `ite8291_none_chassis_lightbar_tongfang`

**Audit date:** 2026-09-16
**Stability:** `EXPERIMENTAL`
**Evidence level:** `REVERSE_ENGINEERED`
**Role:** auxiliary

## Hardware evidence

Issue #13's MEDION ERAZER Beast X30 support bundle reports two independent ITE
devices. The keyboard is `048d:ce00`, while the secondary controller is
`048d:6005` on its own writable hidraw node.

OpenRGB independently registers this exact secondary device as **Ionico Light
Bar**, matching VID/PID `048d:6005` and HID usage page/usage `ff03:01`:

- `Controllers/IonicoController/IonicoControllerDetect.cpp`
- `Controllers/IonicoController/IonicoController.h`
- `Controllers/IonicoController/IonicoController.cpp`
- `Controllers/IonicoController/RGBController_Ionico.cpp`

Source: https://github.com/CalcProgrammer1/OpenRGB/tree/master/Controllers/IonicoController

## Implemented protocol

Feature reports are nine bytes including report ID zero. Direct color uses mode
`0x33`, a begin feature report, one 65-byte output report in R/B/G order, and a
commit feature report. Brightness is the controller's native `0..50` field.
Off uses `00 09 02 00 00 00 00 00 00`.

OpenRGB also documents Breathing (`0x02`), lightbar Wave (`0x20`), and Raindrops
(`0x0A`) with seven feature-report color slots. KeyRGB implements those packet
builders but does not advertise hardware effects until live hardware validation.
The persistence report is deliberately not sent automatically.

## Safety boundaries

- Registered as `BackendRole.AUXILIARY`; it can never replace the keyboard
  backend during primary auto-selection.
- Requires the normal experimental-backend opt-in.
- Matches only `048d:6005`; it does not share the unrelated Clevo lightbar PID
  table or the `ce00` keyboard path.
- When multiple hidraw nodes share that VID/PID, prefer the OpenRGB application
  collection `ff03:01`. A single unmatched node is still accepted; multiple
  unmatched nodes fail closed.
- Uses a dedicated hidraw uaccess rule.
- Independent brightness is stored 0..100 on
  `ite8291_tongfang_lightbar_brightness` and scaled onto the 0..50 hardware
  field at write time.

## Known discrepancy

OpenRGB declares 22 LEDs but allocates and sends a 65-byte direct report. After
the report-ID byte, only 21 complete RGB triplets fit. Its source loop writes two
bytes beyond the local buffer for LED 22. KeyRGB does not reproduce that
overflow and does not send a partial final triplet: it writes 21 complete
triplets and leaves byte 64 zero. Real-hardware testing must confirm whether a
visible final segment remains stale or whether the declared LED count is wrong.

## Promotion requirements

Keep this backend experimental until hardware testing confirms uniform red,
green, blue, brightness, off/on, RGB order, every visible segment, relaunch, and
resume behavior. A HID descriptor dump and traffic capture remain useful for
resolving the 22-LED report-size discrepancy.
