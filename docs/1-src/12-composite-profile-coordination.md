# Composite Controller Profile Coordination

## Status

- **Classification:** implemented backend-local reference implementation
- **Canonical implementation:**
  `src/core/backends/ite8258_perkey_chassis_logo_neon_vent_lenovo_legion/profile_coordinator.py`
- **First consumer:** Lenovo Legion Pro 7 Gen10 composite ITE 8258 controller
  (`0x048d:0xc197`)
- **API status:** not a shared backend API and not ready to move unchanged into a
  generic module
- **Validation status:** focused unit, cross-layer, transaction-concurrency, and
  deferred-disconnect contracts are covered; Issue #7 reporter hardware
  revalidation remains pending

This document marks `Ite8258ChassisProfileCoordinator` as KeyRGB's reference
implementation for a specific hardware shape: several logical lighting routes
share one physical controller and partial writes replace a common profile rather
than patching one route.

It is a reference for the architecture and invariants. It is not evidence that
the current c197 class is protocol-neutral or that every multi-device backend
should use it.

## The problem shape

The pattern applies when all of the following are true:

1. One physical controller is exposed as a primary device plus logical child
   routes.
2. Those routes share one hardware profile or command namespace.
3. A child write is destructive outside the context of the complete scene.
4. More than one facade can update the controller, possibly from different
   runtime paths.
5. The controller's complete scene can be reconstructed from retained protocol
   state.

The c197 path exposes Keyboard, Logo, Neon Strip, and Vents as separate KeyRGB
surfaces. The UI and profile system need those independent logical routes, while
the firmware needs one ordered `SAVE_PROFILE` group list.

```text
keyboard facade ----\
logo facade ---------\
neon facade ----------> retained desired scene -> complete profile reports
vent facade ---------/                                  |
                                                        v
                                          shared hidraw transport
                                                        |
                                                        v
                                          one physical controller
```

Independent devices such as a separate USB lightbar or sysfs mouse do not fit
this pattern. Neither does a controller with a proven zone-local patch command.

## Reference invariants

### 1. Logical routing stays independent

`SecondaryDeviceRoute` remains the UI, profile, diagnostics, simulation, and
software-target addressing surface. Tray code should not learn c197 packet
layout or group ordering.

The backend translates those independent logical operations into complete
physical-controller commits.

### 2. Every physical commit is a complete scene

Once primary state exists, a production profile write must contain the retained
primary groups and every registered child group in deterministic order. A child
operation must never restart the shared group namespace with a child-only group
list.

"Transaction" in this document means that reports from two coordinator-managed
operations cannot interleave. It does not mean the firmware provides rollback
if I/O fails after some reports have already been sent.

### 3. Child-first updates are staged

A child route can be edited before the keyboard has supplied a primary scene.
The desired child state is retained, but no incomplete hardware profile is
emitted. The next primary update commits the combined scene.

### 4. Desired scene state does not own a transport

The coordinator retains protocol data, not a `HidrawTransportProxy`. A newly
acquired proxy can therefore replay desired state after the previous facade has
closed and the shared transport has reopened.

### 5. One lock covers the complete report sequence

The shared transport manager serializes one report at a time. The coordinator
adds the larger boundary required by the controller: profile selection,
direct-mode disable, every `SAVE_PROFILE` packet, and optional brightness are
serialized as one full-scene operation.

### 6. Shared brightness stays primary-owned

Logo, Neon, and Vents do not have independent brightness. Their logical profile
contract is `enabled + color`; the primary keyboard owns the controller-wide
brightness command.

### 7. Global output state and desired scene state are different concepts

Turning the controller output off suspends wire output and preserves the desired
scene for resume. Editing a child while output is suspended updates desired state
without writing the wire (positive colour or black/off). Transient global-power
cleanup must not call child `turn_off()` for routes whose primary owns global
off (`primary_owns_global_off`); those routes skip secondary global-off fan-out.

### 8. Optional nested output transactions batch one logical frame

Primary devices may expose `output_transaction()`. Effects and config apply wrap
keyboard + secondary fan-out in `optional_output_transaction()` so composite
controllers emit one full-scene commit per logical frame. Non-composite backends
no-op.

## Responsibility boundaries

| Owner | Responsibility | Must not own |
|---|---|---|
| `SecondaryDeviceRoute` | Logical identity and capabilities | Packet or group ordering |
| Keyboard/zone device facades | Validate public device calls and build protocol groups | Cross-surface scene policy |
| Profile coordinator | Desired scene, readiness, output state, full-commit serialization | Transport lifetime or tray/profile semantics |
| Protocol module | Packet bytes, group encoding, LED IDs, brightness conversion | Runtime state or device lifetime |
| `SharedHidrawTransportManager` | File-descriptor lifetime, proxies, per-report serialization | Composite scene reconstruction |
| Tray/profile controllers | User intent, persisted enabled/color state, power policy | Controller-specific profile composition |

## Current c197 commit lifecycle

1. A facade translates a keyboard or zone operation into ITE 8258 groups.
2. The coordinator updates retained desired state under an `RLock`.
3. If primary state is unavailable, a child update remains staged.
4. Otherwise the coordinator combines Keyboard, Logo, Neon, and Vent groups.
5. It sends profile selection and direct-mode disable.
6. It emits all complete-profile reports in group order.
7. A primary operation optionally emits controller brightness.
8. Facades release their transport proxy without deleting desired scene state.

## Known limitations of the reference implementation

These are recorded so future backends copy the invariants rather than the
accidental constraints:

1. The coordinator and transport manager are process-wide package singletons.
   This is bounded by the current one-c197-controller support contract. A future
   multi-controller implementation must key state by physical controller identity
   and hardware profile.
2. `profile_id` is supplied to individual calls while retained state is not
   partitioned by profile. Production currently uses the default profile only.
3. Child on/off while output is suspended both update desired state; global
   power-off paths must skip parent-shared routes rather than misuse child
   `turn_off` as cleanup.
4. A staged zone facade reports accepted logical state, not observed hardware
   state. KeyRGB cannot read back whether a staged scene is physically visible.
5. Cold positive brightness without retained primary groups sends profile
   selection followed by controller brightness; it does not invent primary
   groups. Packet sequence is covered by unit tests; reporter observation is
   still the gate for visible semantics.
6. Desired revision advances on mutation; applied revision advances only after a
   complete report sequence succeeds. Mid-commit I/O failure leaves
   `desired_dirty` set for retry.
7. Software and static apply paths wrap keyboard + secondary fan-out in an
   optional output transaction so one logical frame produces one physical
   full-scene commit on c197.
8. Zone names, LED IDs, black-as-off representation, group types, profile
   preparation, and brightness packets are c197-specific policy.

## Reuse and extraction rule

Reuse the pattern now; extract shared code only when a second real composite
backend needs the same retained-scene contract.

A future protocol-neutral coordinator may own:

- ordered component state and defaults;
- primary-readiness and staged updates;
- desired and applied scene revisions;
- output suspend/resume state;
- nested transaction locking;
- explicit staged/committed/deferred outcomes.

Each backend adapter must continue to own:

- component names and physical ordering;
- protocol state and packet types;
- off representation;
- profile preparation and commit packets;
- brightness ownership and conversion;
- physical-controller identity.

Extraction is justified when another backend exposes multiple logical routes on
one physical profile and would otherwise duplicate the state machine. Similar
packet names or a shared ITE family are not sufficient evidence by themselves.

## Output batching extension point

The next reusable seam is an optional output transaction around one logical
render operation:

```python
with optional_output_transaction(primary_device):
    primary_device.set_key_colors(...)
    logo.set_color(...)
    neon.set_color(...)
    vent.set_color(...)
```

For ordinary backends this is a no-op. For c197, facade calls stage mutations
and the outermost successful exit emits one complete profile. The transaction
belongs at the effects/backend boundary; it must not introduce c197-specific
logic into tray policy.

## Review checklist for another backend

Before adopting this pattern, prove:

- partial child writes overwrite or invalidate a shared scene;
- all logical surfaces resolve to the same physical controller identity;
- the complete scene has a deterministic order and bounded size;
- off, resume, and brightness ownership are known from evidence;
- staged state can be represented without owning an open transport;
- a full commit can be serialized across every facade;
- device close/reopen does not discard required desired state;
- tests cover child-first staging, sibling preservation, global off/resume,
  concurrency, I/O failure, and complete report composition;
- real hardware validates the packet sequence before stable promotion.

## Related documents

- [Multi-device routing and targets](11-multi-device-routing-and-targets.md)
- [Issue #7 second review](../D-bug-reports/issue-7/01-second-review-0.29.1-regression-2026-07-15.md)
- [Issue #7 hardening and validation plan](../I-implementation-plans/issue-7-composite-profile-hardening-and-validation-plan.md)
- [ITE 8258 chassis backend audit](../B-backend-audits/06-ite8258-chassis.md)
