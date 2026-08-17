# A2 tray runtime coordinator design gate

Date: 2026-08-11  
Status: approved and implemented; local validation complete  
Concern: A2 serialized tray runtime ownership

## Confirmed problem

`KeyRGBTray` is one mutable runtime aggregate, but complete lighting transitions
have no serialization owner. Config, hardware, idle-power and scheduler pollers,
three power-monitor workers, pystray callbacks and effect-control facades can
concurrently change `is_off`, forced-off/dim state, shared `Config`, effects
engine lifecycle, non-frame hardware output and transition timestamps.

Existing synchronization is resource-local:

- `engine.kb_lock` serializes selected keyboard I/O, not the state transition
  that planned the I/O;
- config file locks protect replacement/merge, not one shared in-memory
  `Config` instance;
- effect generations protect stale worker cleanup, not concurrent starts/stops;
- shutdown and debounce state do not serialize operational transitions.

Concrete reproducible candidates are:

1. a hardware poll applies a captured zero/off observation after a newer manual
   turn-on;
2. config apply passes its forced-off guard before a user turn-off, then starts
   an effect after that newer off command;
3. scheduler brightness passes forced-off guards before user turn-off, then
   relights per-key output and sets `is_off=False`; and
4. an older delayed resume executes after a newer suspend or lid-close event.

## Decision constraints

The solution must preserve current controller, callback and poller facades. It
must not:

- hold an aggregate lock across USB/sysfs I/O, effect-thread joins, config I/O
  or pystray calls;
- route high-frequency effect frames through tray coordination;
- absorb A5 effect geometry or A6 profile layering;
- import tray coordination into `src/core`; or
- make existing synchronous public controller calls silently asynchronous.

### Pystray deadlock constraint

Pystray Xorg public mutations may synchronously wait for its mainloop. A pystray
callback also runs on that mainloop. Therefore this sequence must be impossible:

1. mainloop callback waits for a serialized tray transition;
2. transition invokes `_refresh_ui()` from the coordinator worker;
3. pystray mutation waits for the blocked mainloop.

A queue without deferred UI handling is not an acceptable implementation.

## Proposed owner

Add `TrayRuntimeCoordinator` under `src/tray/controllers/`. One instance is
created during tray prebootstrap and started before power monitoring or pollers.

The coordinator owns:

- FIFO execution of low-frequency tray transitions;
- one monotonically increasing transition revision;
- reentrant execution when an existing transition invokes another stable tray
  facade;
- deferred icon/menu refresh requests; and
- drain/stop liveness before effects-engine and device teardown.

It does **not** own effect frame rendering, render-local caches, pystray native
dispatch, sensor probing or backend selection.

## Command contract

The coordinator exposes a narrow generic boundary rather than a command class
per feature:

- `run(action)`: execute one complete transition on the owner thread and return
  its result or re-raise its exception;
- `capture_revision()`: snapshot the accepted-transition revision before a
  sensor probe;
- `run_if_current(revision, action)`: reject a stale observation if another
  transition was accepted after its probe began;
- `request_ui(icon=..., menu=...)`: accumulate presentation requests while the
  owner executes; and
- `stop_and_drain(timeout=...)`: stop accepting work, drain accepted commands,
  join the owner and report liveness.

Calls made from the owner thread execute inline without opening a nested command
or incrementing the revision. This preserves existing nested controller calls
without queue deadlock.

## Deferred UI contract

Existing `_update_icon`, `_update_menu` and `_refresh_ui` facades remain public.
While a transition is executing, they record refresh intent instead of touching
pystray. After the root command completes, the waiting caller performs the
coalesced refresh with no coordinator ownership held:

- a pystray callback refreshes on its mainloop after the transition returns;
- a poller refreshes through pystray's supported backend dispatcher; and
- repeated requests inside one transition coalesce to one icon/menu refresh.

This retains synchronous state/hardware completion semantics while preventing
Xorg lock inversion.

## Migration boundary

### Stable adapters retained

- `src/tray/app/_delegates.py`
- `src/tray/app/callbacks.py`
- `src/tray/controllers/lighting_controller.py`
- existing poller start and iteration facades
- `PowerManager` calls to the tray controller protocol

### Root transition entrypoints migrated

1. Full pystray callback actions, including their config mutation and controller
   invocation, run as one command.
2. One config-apply iteration runs as one command so forced-off classification
   and execution cannot be split by another transition.
3. Scheduler brightness execution runs as one command.
4. Idle-power sensor collection/planning remains outside; the selected action
   and its state commit run as one command.
5. Hardware probing remains outside and captures a revision; polled-state apply
   uses `run_if_current`.
6. Power-source, suspend/resume and lid intents enter through existing tray
   facades. Resume delay becomes generation/revision-aware so an older resume
   cannot overtake a newer off event.
7. Direct effect selection, turn-off/on, restore and brightness-policy facades
   execute inline when already inside a root command.

## Startup and shutdown

Startup order:

1. create/start coordinator;
2. construct and prime power manager through coordinated tray facades;
3. autostart effect through the coordinator;
4. start pollers.

Shutdown order extends A4:

1. signal and join pollers;
2. stop and verify power-monitor workers;
3. drain, stop and verify the runtime coordinator;
4. close the effects engine;
5. close secondary target/device caches.

If producers or the coordinator remain alive, later device teardown remains
suppressed.

## Deterministic test plan

Use `threading.Event` barriers; no timing-dependent race assertions.

1. Coordinator FIFO, exception propagation, reentrancy and stop/drain tests.
2. Deferred UI coalescing test proving pystray mutation occurs on the waiting
   caller after command completion, never on the owner worker.
3. Config apply versus user turn-off: newer serialized user intent wins and no
   effect starts after forced-off state commits.
4. Scheduler versus user turn-off: scheduler cannot relight after the newer off
   transition.
5. Hardware stale observation: a revision captured before manual turn-on is
   rejected after the turn-on commits.
6. Delayed resume versus newer suspend/lid-close: stale resume is discarded.
7. Shutdown ordering and liveness tests include the coordinator before engine
   teardown.
8. Existing sequential facade tests remain unchanged or use coordinator-free
   fakes, proving compatibility outside production bootstrap.

## Implementation slices after approval

1. Coordinator primitive, owner state and unit tests.
2. Deferred UI request/flush seam and deadlock regression tests.
3. Startup/shutdown ownership integration.
4. Callback and lighting-controller root adapters.
5. Config, scheduler and idle action migration.
6. Hardware observation revisions and stale-result tests.
7. Power-event ordering and stale-resume tests.
8. Full repository, architecture and exception-transparency validation.

All slices belong to A2 and must land as one completed campaign item; the slices
exist to keep review and local verification bounded, not to declare partial A2
completion.

## Approval decision

Approved on 2026-08-11:

1. one tray-owned FIFO coordinator instead of an aggregate `RLock`;
2. synchronous public transition semantics;
3. deferred/coalesced UI refresh outside coordinator ownership;
4. revision rejection for stale sensor observations; and
5. exclusion of effect frames, backend selection, A5 geometry and A6 profile
   layering from this owner.

## Implementation outcome

- `TrayRuntimeCoordinator` is created during prebootstrap and explicitly started
  before power workers and pollers.
- Config, scheduler, idle, hardware, power-source and pystray callback roots use
  the owner; nested controller calls execute inline.
- Hardware, idle, scheduler and delayed power observations use accepted-command
  revisions or event generations to reject stale work.
- Icon/menu requests defer and coalesce, including non-animated icon intent.
- Menu rendering is read-only: config reload, device ensure and selected-context
  persistence were removed from view construction.
- Quit returns from the pystray callback before producer joins, then performs
  shutdown and icon stop on a dedicated shutdown worker.
- A4 shutdown now drains and verifies the coordinator before engine/device
  teardown.
