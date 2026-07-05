# Support Tools and Backend Discovery

## Goal

Make the tray-first support flow the default path for diagnostics, safe device
discovery, support-bundle export, and issue drafting.

## Why this exists

Older support flows depended on Settings and ad-hoc manual commands. The current
design centralizes support work in a dedicated window so users can gather the
right evidence without needing maintainer-only knowledge first.

## Current owner modules

- `src/gui/windows/support.py`
- `src/tray/ui/menu.py`
- `src/core/diagnostics/device_discovery.py`
- `src/core/diagnostics/backend_speed_probe.py`
- `src/core/diagnostics/support_reports.py`
- `src/core/diagnostics/additional_evidence.py`

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

## Outputs

- diagnostics JSON
- discovery JSON
- combined support bundle
- generated issue draft and recommended template link
- optional deeper-evidence attachments when needed

## Testing

- Unit tests for discovery snapshots and formatting
- Unit tests for support-window actions and saved outputs
- Unit tests for backend-speed probe plans and support-report generation