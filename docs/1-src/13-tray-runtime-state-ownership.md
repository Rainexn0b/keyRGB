# Tray runtime state ownership

Scope: inventory of mutable tray runtime state and who owns it after the 2026-07
bootstrap typing work. This is a map for debt paydown (D1), not a full redesign.

## Already typed containers

| Container | Module | Applied when | Holds |
|---|---|---|---|
| `TrayPreBootstrapState` | `src/tray/app/_application_state.py` | Before backend/engine wiring | Icon, off flags, dim-temp, brightness cache, event debounce map, permission notice, pending notifications, idle-power state object |
| `TrayBootstrapState` | same | After backend selection | Config, engine, backend/probe/caps, discovery, selected device context, ITE matrix dims |
| `TrayIdlePowerState` | `src/tray/idle_power_state.py` | Via pre-bootstrap | Idle/power dim policy runtime fields |
| `TrayIconState` | `src/tray/protocols.py` | Via pre-bootstrap | Icon color / mask presentation |

Bootstrap still **flattens** these containers onto `KeyRGBTray` attributes via
`apply_to()` so existing controllers/pollers can keep attribute access. The debt
is not "missing dataclasses" but **remaining flag sprawl and private-attr reach**.

## Ownership by concern

### Lighting / effect (controllers + config poller)

| Attribute / surface | Primary owner | Notes |
|---|---|---|
| `config` | Config + tray | Source of truth for desired lighting |
| `engine` | Effects engine | Runtime renderers / device writes |
| `backend`, `backend_probe`, `backend_caps` | Backend selection | Capability-driven UI |
| `selected_device_context` | Tray menu / secondary routing | Keyboard vs secondary route |
| `_ite_rows`, `_ite_cols` | Bootstrap | Matrix dims for per-key apply |
| `is_off` | Controllers + power paths | User/power/idle may force |

### Power / idle / dim

| Attribute / surface | Primary owner | Notes |
|---|---|---|
| `_power_forced_off` | Power manager / idle-power | Pre-bootstrap bag |
| `_user_forced_off` | Menu / callbacks | Pre-bootstrap bag |
| `_idle_forced_off` | Idle poller | Pre-bootstrap bag |
| `_dim_temp_*` | Dim-sync / brightness paths | Pre-bootstrap bag |
| `tray_idle_power_state` | Idle power subsystem | Prefer fields on this object over new tray flags |
| `_last_brightness` | Config apply + dim restore | Shared cache; treat carefully |
| `_last_resume_at` | Power restore | Debounce/resume |

### Secondary devices / composite

| Surface | Primary owner | Notes |
|---|---|---|
| Secondary routes | `src/core/secondary_device_routes.py` | Static route table |
| Profile secondary state | Config / profile | `secondary_device_state` |
| Composite coordinator | `ite8258_perkey_chassis.profile_coordinator` | Shared HID profile namespace |
| Software targets | Tray software-target controller | Fan-out for SW effects |

### UI / notifications

| Attribute / surface | Primary owner | Notes |
|---|---|---|
| `icon`, `tray_icon_state` | Icon modules + pollers | Presentation only |
| `_pending_notifications` | Startup / tray | Flushed when icon exists |
| `_permission_notice_sent` | Permission callback path | One-shot |
| `_event_last_at` | Event debounce | Multi-cause throttle |

### Serialized runtime transitions

`TrayRuntimeCoordinator` in `src/tray/controllers/runtime_coordinator.py` is the
single owner for low-frequency lighting transitions. Production creates it in
prebootstrap and starts it before power workers and pollers.

- Pystray callbacks, config apply, scheduler apply, idle actions, hardware
  observation apply, power-source iterations and power-event controller calls
  enter one FIFO command boundary.
- Existing tray/controller facades remain synchronous. Nested facade calls on
  the owner execute inline, avoiding self-deadlock and duplicate revisions.
- A revision is assigned when each root command is accepted. Hardware, idle and
  scheduler probes carry the revision captured before observation; stale results
  are discarded. Delayed power restores also require both the latest power-event
  generation and the active coordinator revision.
- Config reload/classification that participates in a transition executes on the
  owner. Sensor probing may remain outside when its result is revision-gated.
- Icon/menu requests made during a command are coalesced and flushed by the
  waiting caller after ownership is released. This prevents Xorg mainloop lock
  inversion and preserves non-animated hardware refresh requests.
- Menu rendering is read-only. It must not reload config, reconnect devices,
  query OS power sysfs, probe secondary backends, or persist fallback state.
  Power-mode and secondary-route labels come from
  `src/tray/controllers/view_snapshots.py`.
- High-frequency effect frames, render-local caches and backend-local I/O locks
  remain outside this owner.

Shutdown first stops pollers and power workers, then drains/verifies the
coordinator, then closes the effects engine and secondary targets. Quit starts
that sequence outside the pystray callback thread so native UI dispatch can
finish while pollers are joining.

### Pystray native-thread affinity

KeyRGB owns **refresh preparation and facade routing**; pystray owns dispatch to
its native event-loop thread. This distinction is part of the supported Linux
adapter contract:

- `Icon.run()` remains on the application main thread.
- KeyRGB mutations of the pystray image and menu are centralized in
  `src/tray/ui/refresh.py` and use only the public `Icon.icon` and `Icon.menu`
  properties. Pollers request those facades and must not access the pystray
  surface directly.
- In pystray 0.19.5, the GTK/AppIndicator implementations schedule native work
  with `GObject.idle_add`; the Xorg implementation rewrites update operations
  into messages handled by its mainloop thread. Current upstream retains those
  dispatch mechanisms.
- Do not hold a KeyRGB lock while invoking a pystray public mutation: Xorg may
  wait synchronously for its mainloop, so a callback taking the same lock can
  deadlock. Do not add a second generic UI dispatcher unless a supported
  backend is demonstrated to lack native dispatch.
- Direct access to pystray private/native backend fields remains prohibited. If
  a future backend changes this public-property contract, isolate that backend
  behind a tray UI adapter and add backend-specific integration evidence.

### Profile activation boundary

Core profile activation (`src/core/profile/runtime_activation.py`) applies profile
data to shared config through injected load/apply functions only. It does not
resolve private tray methods or tray-owned attributes by name.

Tray-owned runtime side effects are wired explicitly by callers:

- menu activation uses `src/tray/controllers/profile_activation.py`
- power-source profile switches supply duck-typed hooks from the tray object
  without importing tray packages into core

Order remains config apply first, then optional runtime lighting transition or
effect start, then icon/menu refresh.

## Rules for new state

1. Prefer extending `TrayIdlePowerState`, `TrayIconState`, or a new **named** bag
   over adding another `_private` flag on `KeyRGBTray`.
2. Controllers and pollers should take **narrow protocols** (see `src/tray/protocols.py`)
   rather than the full tray type.
3. Do not import tray modules from `src/core` (architecture rule).
4. Config apply classification stays pure (`ConfigApplyPlan`); execution stays in
   poller helpers.
5. Core profile activation must accept explicit hooks; do not reintroduce private
   tray method lookup from `src/core/profile/`.

## Write privileges

| State | Allowed writers | Readers should use |
|---|---|---|
| `user_forced_off` | User/menu power actions | `is_user_forced_off` |
| `power_forced_off` | Suspend/lid and power-source policy | `is_system_forced_off` |
| `idle_forced_off` | Idle-power action executor | `is_system_forced_off` |
| `dim_temp_active`, target | Screen-dim sync / idle-power actions | `is_dim_temp_active`, `dim_temp_target_brightness` |
| `last_brightness` | Brightness layer and config/power restore paths | `read_last_brightness` |
| `is_off` | Runtime coordinator through lighting/power/idle transitions | Controller protocol / explicit state |

New code must not write the legacy private attributes directly. Writers should
use `set_idle_power_state_field`, `set_last_brightness`, or a purpose-specific
state helper. Legacy attributes remain only as a compatibility bridge until all
external/test seams have migrated.

## Progress (2026-07-15)

- Preferred **read** API lives on `src/tray/idle_power_state.py`:
  - forced-off: `read_forced_off_flags`, `any_forced_off`, `is_user_forced_off`,
    `is_system_forced_off`
  - dim/resume: `is_dim_temp_active`, `dim_temp_target_brightness`, `read_last_resume_at`
  - brightness cache: `read_last_brightness` / `set_last_brightness` (owner field
    `TrayIdlePowerState.last_brightness`)
- Call sites migrated off direct private-attr / `vars(tray)` forced-off reads:
  - secondary static scene, software-target controller
  - power-policy brightness apply, time scheduler
  - config-poller forced-off skip path
  - hardware poller recovery + state apply
  - idle-power runtime logging and action classification inputs
  - restore / brightness-layer writers use `set_last_brightness` / `read_last_brightness`
- **KeyRGBTray owner-backed properties:** `_power_forced_off`, `_user_forced_off`,
  `_idle_forced_off`, `_dim_temp_*`, `_last_brightness`, `_last_resume_at` are
  properties that store only on `tray_idle_power_state`. Fakes/tests may still
  use plain instance attrs; helpers dual-write for that compatibility.
- **`set_idle_power_state_field`:** always updates the typed owner; dual-writes
  the legacy attr only when the tray type does **not** already define that name
  as a property (so production `KeyRGBTray` is owner-only on set).
- `ensure_idle_state` still bridges owner ↔ legacy attrs at poll start for
  duck-typed trays (including `_last_brightness`).

## Next migration slices (when paying D1)

1. Prefer `tests/tray/fakes.py` (`make_owner_backed_*`) for new tests; migrate
   remaining dual-write-only fakes when touched.
2. Stop dual-writing instance attrs in helpers once production paths and
   remaining fakes are owner-only.
3. Optionally drop legacy attributes from protocols once external seams are gone.

## Shutdown liveness contract

Tray pollers and power-monitor workers are runtime producers: they can still
read effect state or reach hardware while shutting down. Their owner must
therefore confirm worker liveness after every bounded join rather than treating
the join timeout as proof that a worker exited.

- `src/tray/app/lifecycle.py` owns the tray polling shutdown event and registered
  poller handles. `stop_all_polling()` returns a quiescence result and retains
  active or unverifiable handles so a later shutdown attempt can retry them.
- `PowerManager.stop_monitoring()` returns the corresponding aggregate result
  for its monitor, lid, and battery workers. A failed join does not prevent the
  remaining workers from receiving their own bounded join.
- `shutdown_tray_runtime_best_effort()` signals/stops both producer groups. If
  either group remains active or cannot be verified, it leaves the effects
  engine and secondary device cache open rather than racing worker activity
  against device teardown.
- A legacy/custom power manager returning `None` remains compatible and is
  treated as having honored its synchronous stop contract. Implementations that
  can time out should return an explicit boolean result.

## Related

- Debt plan: `docs/I-implementation-plans/2026-07-15/maintainability-debt-paydown-plan.md`
- Older note: `docs/Z-legacy/tech-debt/2026-03-31/tray-runtime-state.md`
