# Policy ownership

KeyRGB keeps policy code beside the subsystem that owns the decision. There is
no global `src/core/policies/` package: it would mix unrelated backend, power,
and tray-runtime decisions and make dependency direction less clear.

## Canonical owners

| Policy family | Canonical location |
| --- | --- |
| Backend selection, stability, and experimental evidence | `src/core/backends/policies/backend_selection.py` |
| Backend per-key mode initialization | `src/core/backends/policies/per_key_mode.py` |
| Backend controller-sleep signatures | `src/core/backends/policies/sleep_state.py` |
| Power events, power-source changes, and battery saver | `src/core/power/policies/` |
| Tray idle/blanking actions | `src/tray/pollers/idle_power/policy.py` |

Backend devices declare hardware-specific attributes such as
`keyrgb_per_key_mode_policy` and `keyrgb_sleep_state_policy`. The backend policy
modules own policy names, normalization, and classification; consumers should
not duplicate backend signatures or firmware assumptions.

## Import rule

Production code imports the exact canonical leaf module it needs, for example:

```python
from src.core.backends.policies.sleep_state import is_controller_sleep_state
from src.core.backends.policies.per_key_mode import per_key_mode_policy
```

Avoid broad imports from `src.core.backends.policies` in implementation code:
leaf imports make dependencies explicit and avoid importing unrelated policy
families.

KeyRGB is still in its beta/0.x compatibility window, so the former internal
facades (`src/core/backends/policy.py`, `src/core/backends/sleep_state.py`, and
the per-key policy re-exports from `perkey_animation.py`) were removed when the
canonical package was introduced. Policy imports therefore have one source of
truth and cannot drift back to historical paths.

## Adding a policy

1. Put the decision beside its owning subsystem.
2. Add a backend policy only with hardware diagnostics or capture evidence.
3. Keep firmware timing out of application policy where possible: classify the
   reported state instead of hardcoding a controller timeout.
4. Add focused normalization/classification tests before wiring the consumer.
