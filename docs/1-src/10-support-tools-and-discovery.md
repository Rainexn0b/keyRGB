# Support Tools and Backend Discovery

## Goal

Make the tray-first support flow the default path for diagnostics, safe device
discovery, support-bundle export, and issue drafting.

## Why this exists

Older support flows depended on Settings and ad-hoc manual commands. The current
design centralizes support work in a dedicated window so users can gather the
right evidence without needing maintainer-only knowledge first.

## Current owner modules

- `keyrgb/gui/windows/support.py`
- `keyrgb/tray/ui/menu.py`
- `keyrgb/core/diagnostics/device_discovery.py`
- `keyrgb/core/diagnostics/secondary_devices.py`
- `keyrgb/core/diagnostics/backend_speed_probe.py`
- `keyrgb/core/diagnostics/support_reports.py`
- `keyrgb/core/diagnostics/additional_evidence.py`

## Current flow

1. Open `Support Tools…` from the tray.
2. Run diagnostics and or device discovery.
3. Review the support summary and suggested issue draft.
4. Save diagnostics JSON, discovery JSON, or a full support bundle.
5. Optionally collect deeper evidence only if the safe scan was not enough.

## Design rules

1. Discovery is read-only by default.

Safe discovery should not detach drivers or mutate hardware state.

2. Probe results should stay explainable.

Users and maintainers should be able to see not only the selected backend, but
also why other backends were unavailable, experimental-disabled, or dormant.

3. Support bundles should be issue-oriented.

The output should align with the repository's issue templates so the first
maintainer round-trip carries enough evidence to act on.

4. Guided backend probes belong here.

Targeted flows such as the `ite8910` speed probe should live in Support Tools,
not in hidden debug-only code paths.

5. Secondary-device state must be self-describing.

The discovery payload carries a `secondary_devices` section (see
`keyrgb/core/diagnostics/secondary_devices.py`) that reports, read-only, whether
auxiliary lighting devices and composite chassis zones (e.g. Legion Gen10
logo/neon/vent) are detected, whether their parent backend probe is available
(and the reason when it is not), which tray device-context rows would render,
the software-target state, and persisted per-zone brightness/color. This lets a
single support bundle confirm whether secondary-device controls are expected to
appear and work.

## Outputs

- diagnostics JSON
- discovery JSON (includes the `secondary_devices` section above)
- combined support bundle
- generated issue draft and recommended template link
- optional deeper-evidence attachments when needed

## Testing

- Unit tests for discovery snapshots and formatting
- Unit tests for support-window actions and saved outputs
- Unit tests for backend-speed probe plans and support-report generation