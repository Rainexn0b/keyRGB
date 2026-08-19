# Tray view boundaries

Status: **Done**

## Purpose

Tray menu construction is presentation. It must render already-owned tray state
and must not acquire hardware or query OS power sysfs.

## Contract

`keyrgb/tray/controllers/view_snapshots.py` owns the presentation snapshots:

| Snapshot | Tray attribute | Observed when |
|---|---|---|
| System power mode | `system_power_status` | tray runtime start, after a power-mode apply |
| Effective secondary routes | `effective_secondary_routes` | tray runtime start |

Menu builders may only read those attributes (and other tray-owned presentation
fields such as `backend_probe.identifiers`, `device_discovery`, and
`engine.device_available`). They must not call:

- `keyrgb.core.power.system.get_status()`
- `iter_effective_secondary_routes()`
- backend `probe()` / `is_available()`
- engine `_ensure_device_available()`

Checked radio state is captured from the snapshot at build time. Applying a
system power mode is a runtime transition: it may observe OS state, store a
fresh snapshot, then request one coalesced menu rebuild that the runtime
coordinator executes after the transition completes — never mid-transition.
Other automatic AC/DC paths (brightness, on/off, idle, scheduler, hardware
poller) must not rebuild the live menu at all: rebuilding an open
AppIndicator/SNI menu can crash KDE plasmashell.

## Non-goals

- Aborting an in-flight cpufreq helper
- Live-refreshing the menu when another process changes the governor
- Changing public tray entrypoints
