# Effect runtime contracts

Status: **Done**

## Purpose

Effect execution crosses four extension boundaries: software/reactive
registration, the composed effects engine, reactive render loops, and backend
hardware-effect payload builders. These boundaries must declare their
dependencies directly; closure internals, mutated module globals, and
exception message text are not contracts.

## Software and reactive registration

`keyrgb/core/effects/effect_contract.py` owns `EffectRegistration`. Implementation
modules export `EFFECT_REGISTRATION` or `EFFECT_REGISTRATIONS`.
`keyrgb/core/effects/registry.py` discovers those markers and is the source of
truth for selectable software and reactive names, titles, menu order, start
colours, and engine runners.

`catalog.py` derives `SOFTWARE_EFFECTS`, `REACTIVE_EFFECTS`, and `SW_EFFECTS`
from that registry. `HW_EFFECTS` remains a static firmware-name fallback;
live hardware effects are backend-owned.

Adding a selectable software/reactive effect is: implement `run_<name>`, export
the marker, add a test. Do not edit `catalog.py` or engine start dispatch.
Unmarked runners are not selectable. See `keyrgb/core/effects/README.md`.

## Engine support contract

`keyrgb/core/effects/engine_support/_contracts.py` defines the state and operations
shared by `_EngineCore`, `_EngineBrightness`, and `_EngineStart`.
`EffectsEngine` validates this contract at construction, so a missing mixin
dependency fails immediately with its member name rather than during a later
effect transition. Optional permission-error handling is initialized explicitly
to `None` by the core owner.

The public `EffectsEngine` methods and mixin composition remain stable.

## Reactive loop dependency contract

`ReactiveApiFacade` in `keyrgb/core/effects/reactive/_effects_api.py` is a frozen,
slot-backed dependency object. `effects.py` constructs concrete fade and ripple
facades and passes them directly to the loop functions.

Reactive code must not:

- inject dependencies through `globals().update()`;
- recover an API from `sys.modules`; or
- cast a module object to a loop protocol.

Tests can replace a facade with `dataclasses.replace()` and inject only the
dependencies relevant to the test.

## Hardware-effect builder contract

`keyrgb/core/backends/effect_contract.py` owns hardware payload builder metadata:

- `HardwareEffectBuilder.accepted_kwargs` declares supported payload fields;
- `UnsupportedHardwareEffectArgument` carries the rejected field as structured
  data while retaining the historical `ValueError` message for compatibility;
- `hardware_effect_builder()` creates the immutable callable wrapper.

`build_hw_effect_payload()` filters explicitly declared builders before calling
them. It does not inspect `__code__` / `__closure__`, and it does not parse
`ValueError` text. Legacy or plugin callables without metadata still receive the
historical common fields, but new in-tree hardware-effect builders must publish
the explicit contract.

The current in-tree hardware-effect backends with builders all publish metadata:

- ITE 8291r3 per-key
- ITE 8910 per-key
- ITE 8258 per-key chassis
- ITE 8258 Lenovo Legion zones
- ITE 8295 Lenovo IdeaPad zones

## Extension guidance

1. New software or reactive effects export `EFFECT_REGISTRATION` from their
   implementation module; catalog and engine start follow the marker.
2. New reactive loops receive a concrete dependency facade; do not use module
   mutation as dependency injection.
3. New hardware-effect builders use `hardware_effect_builder()` and list every
   accepted field.
4. Rejected builder fields use `UnsupportedHardwareEffectArgument`; callers
   must not infer behavior from exception strings.
5. Any new cross-mixin engine dependency is added to `EngineSupportContract` and
   its construction-time validation list.
