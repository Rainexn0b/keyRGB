# Config domain model

Status: **Done**

## Purpose

Keep the on-disk config file as a flat JSON mapping for compatibility, while
giving runtime code an explicit ownership model so lighting, secondary devices,
power policy, idle/display sync, scheduler, layout, and app/session keys are not
one undifferentiated mutable bag.

## Owners

| Layer | Module | Responsibility |
|---|---|---|
| Public facade | `keyrgb/core/config/config.py` (`Config`) | Persistence, reload/save/batch, stable property API |
| Document | `keyrgb/core/config/document.py` (`ConfigDocument`) | Live settings identity + domain/extras projections |
| Domain registry | `keyrgb/core/config/domains.py` | Key partition and classification |
| Lighting accessors | `keyrgb/core/config/_lighting/` | Effect, brightness, reactive, per-key, secondary routes |
| Power accessors | `keyrgb/core/config/_power_accessors.py` | Lid/suspend and AC/battery lighting policy |
| Scheduler accessors | `keyrgb/core/config/_scheduler_accessors.py` | Idle/display dim sync and day/night schedule |
| App/layout accessors | `keyrgb/core/config/_app_accessors.py` | Autostart, experimental flags, physical layout, software target |
| Readonly snapshot | `keyrgb/core/config/_settings_view.py` | Typed scalar/map view for GUI/settings readers |
| Defaults | `keyrgb/core/config/defaults.py` | Authoritative default flat map |
| Storage | `keyrgb/core/config/file_storage.py` | Atomic load/merge/save |

## Domains

| Domain | Examples |
|---|---|
| `lighting` | `effect`, `speed`, brightness family, reactive, `per_key_colors`, `effect_speeds`, `software_effect_target` |
| `secondary` | `secondary_device_state`, legacy lightbar keys, ITE8258 chassis zone keys |
| `power` | lid/suspend toggles, battery saver, AC/battery lighting and power-mode prefs |
| `idle_display` | screen-dim sync, controller-sleep respect, idle debounce/fade |
| `scheduler` | day/night window and brightness targets |
| `layout` | `physical_layout`, `layout_legend_pack` |
| `app` | autostart flags, experimental backends, `tray_device_context` |

Unknown keys are **extras**. They are preserved through load/save for forward
compatibility and exposed through `Config.extras_view()`.

## Contracts

1. **Flat disk schema** remains the compatibility surface. Domain structure is
   runtime architecture, not a nested JSON migration.
2. **`Config._settings`** remains the live flat dict used by accessors and tests.
   It is the `ConfigDocument.values` identity, not a second copy.
3. **Domain views are readonly projections** (`MappingProxyType`) of present keys
   owned by one domain. Mutations go through `Config` properties or explicit
   settings writes that still persist via `_save()`.
4. **DEFAULTS must stay partitioned.** Every key in `defaults.DEFAULTS` belongs
   to exactly one domain. Unit tests enforce this.
5. **Public property facades stay stable.** Domain extraction must not rename or
   remove existing `Config` attributes.
6. Nested map boundaries already owned elsewhere stay authoritative for their
   shapes:
   - `EffectSpeedOverrides` for `effect_speeds`
   - secondary-device facade / snapshot helpers for `secondary_device_state`

## Consumer guidance

- Prefer `Config` properties or existing snapshot helpers for normal reads/writes.
- Use `config.domain_view(ConfigDomain.POWER)` (and siblings) when a caller needs
  a domain-scoped readonly slice without inventing ad-hoc key lists.
- Use `config.settings_view()` for broad typed scalar snapshots (settings UI).
- Do not treat raw `_settings` as a place to invent new cross-domain contracts;
  add the key to `domains.py` and the nearest accessor module instead.

## Non-goals

- Nested on-disk JSON sections
- Strict enums for every historical effect name in one pass
- Removing `_settings` compatibility access from tests
