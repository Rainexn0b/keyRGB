# Diagnostics And Backend Discovery Roadmap

## Goal

Move diagnostics and backend-discovery tooling closer to the tray workflow so users can gather actionable support data without being walked through ad-hoc terminal commands.

This roadmap is intentionally staged. The end state is a tray-first support surface that can:

1. provide quick health checks for common failures
2. detect likely unsupported RGB controllers automatically
3. collect safe, read-only dumps for new hardware support requests
4. reduce maintainer back-and-forth for backend promotion work

## Problem Statement

The current UX has two issues:

1. diagnostics live inside Settings, which is too indirect for troubleshooting
2. keyboard layout also lives in Settings even though its real owner is the per-key editor / calibrator workflow

This creates a mixed-responsibility settings window and makes support workflows harder than they need to be.

## Product Direction

### Settings should own

- tray/runtime behavior
- power management
- dim/screen sync behavior
- autostart
- experimental-backend opt-in policy
- version and general app metadata

### Tray diagnostics should own

- quick health checks
- copy/export support reports
- backend probe visibility
- unsupported-device discovery
- safe guided dump collection for new hardware

### Per-key editor should own

- physical keyboard layout selection
- optional-key visibility and slot labels
- keymap calibration
- overlay alignment

## Safety Model

All automated discovery work should default to read-only, low-risk operations.

### Safe by default

- backend probing already present in keyRGB
- USB ID enumeration
- sysfs USB attribute reads
- hidraw enumeration via `/sys/class/hidraw`
- devnode permission checks
- process-holder detection via `/proc/*/fd`
- HID report descriptor reads via read-only ioctl helpers
- packaging the resulting data into JSON/text exports

### Explicitly out of scope until evidence exists

- speculative hidraw writes
- speculative feature reports
- USB control transfers that change device state
- auto-reset or rebind operations
- root-required probing flows as part of the normal support path

## Target UX

### Tray structure

Planned direction:

```text
Diagnostics
  Quick Health Check
  Copy Full Report
  Open Support Issue

Detect New Backends
  Scan For New Devices
  View Unrecognized RGB Controllers
  Export Safe Device Dump
```

The exact labels may change, but the split should stay:

- one section for diagnosing the current setup
- one section for discovering unsupported hardware

## Implementation Phases

### Phase 0: Ownership cleanup

Status: current session

Scope:

- document the roadmap
- remove Diagnostics from Settings
- remove Keyboard Layout from Settings
- keep physical layout in the per-key editor workflow only

Success criteria:

- Settings no longer contains mixed-responsibility support/setup sections
- no behavior regression for power-management settings

### Phase 1: Core discovery service

Scope:

- add a diagnostics/discovery service module under `src/core/diagnostics/`
- expose a structured API for:
  - current backend summary
  - supported backend probes
  - detected but unclaimed USB/hidraw RGB candidates
  - permission and busy-device hints
- add safe HID descriptor capture helpers

Suggested modules:

- `src/core/diagnostics/device_discovery.py`
- `src/core/diagnostics/hidraw_descriptor.py`

Success criteria:

- the tray can request discovery data without duplicating probe logic
- unrecognized ITE-class devices can be surfaced clearly

### Phase 2: Tray integration

Scope:

- add new tray menu sections for diagnostics and backend discovery
- add callbacks and launch points for the new flows
- keep the settings window focused on runtime/app settings only

Likely touch points:

- `src/tray/ui/menu.py`
- `src/tray/ui/menu_sections.py`
- `src/tray/app/callbacks.py`
- `src/tray/app/application.py`

Success criteria:

- users can run support flows directly from the tray
- current backend state and backend candidate state are visible without opening Settings

### Phase 3: Guided support windows

Scope:

- add a small support window for quick health checks
- add a discovery/export window for new backend reports
- support copy-to-clipboard and save-to-file workflows

Likely outputs:

- human-readable quick summary
- structured JSON export
- optional prefilled issue text or issue-template link

Success criteria:

- most support requests can be answered with a single exported file
- maintainers do not need to manually ask for the same first-round dumps repeatedly

### Phase 4: Backend-promotion workflow

Scope:

- connect discovery exports to dormant-backend promotion work
- add promotion criteria checklists for dormant backends like `ite8233`
- make the export format explicitly capture the minimum evidence needed for promotion

Examples:

- full USB descriptor snapshot
- HID report descriptor
- backend probe state
- permission state
- process holders
- user-supplied Windows traffic capture attachment guidance

Success criteria:

- dormant-to-experimental promotion becomes a smaller, mostly mechanical change

## Data Model Direction

The roadmap works best if diagnostics and discovery share a stable data shape.

Suggested top-level sections:

- `system`
- `app`
- `config`
- `backends`
- `usb_ids`
- `usb_devices`
- `hidraw_devices`
- `discovery`
- `warnings`
- `support_actions`

The `discovery` section should answer:

1. what devices keyRGB already supports
2. what devices keyRGB sees but does not claim
3. why a candidate backend was not selected
4. what safe next steps the user can take

## Near-Term Design Decisions

### Keep diagnostics and discovery separate in the UI

Diagnostics answers: "why is my current setup not working?"

Discovery answers: "what new hardware did keyRGB detect that it does not support yet?"

These are related but not identical workflows, and the tray should reflect that.

### Keep layout out of Settings

Physical layout changes affect the per-key editor, calibrator, and overlay setup. That makes the per-key editor the correct owner.

### Favor read-only automation over clever probing

The system should automate evidence gathering, not speculative control writes.

## Session Plan

### Session 1

- roadmap doc
- remove Diagnostics from Settings
- remove Keyboard Layout from Settings

### Session 2

- implement core discovery service
- add safe hidraw descriptor support
- add tests for supported/unrecognized-device classification

### Session 3

- wire tray menu sections and callbacks
- add quick summary actions

### Session 4

- add guided support/export windows
- define the exported dump format

### Session 5+

- iterate on dormant backend workflows like `ite8233`
- use collected dumps to promote backends safely

## Current Recommendation

Proceed incrementally.

The correct immediate move is to clean Settings ownership first, then build the tray-first support surface on top of the existing diagnostics collectors instead of replacing them.