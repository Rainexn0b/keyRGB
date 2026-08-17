# A5 runtime effect geometry design gate

Date: 2026-08-11  
Status: approved and implemented; local validation complete  
Concern: A5 runtime effect geometry

## Confirmed problem

Software and reactive effects render on a fixed logical matrix:

- `src/core/effects/matrix_layout.py` hard-codes `NUM_ROWS=6`, `NUM_COLS=21`
- fades, software effects, reactive maps/buffers/ripples, and tray-icon mosaics
  import those constants
- the reactive effect API injects the same fixed dimensions into loop modules

Supported backends already expose different geometry through `dimensions()`:

| Backend | Dimensions |
|---|---|
| `ite8291r3_perkey` / `ite8291_perkey` | 6×21 |
| `ite8910_perkey` | 6×20 |
| `ite8258_perkey_chassis` | 7×20 |
| `ite8258_zones_lenovo_legion` | 4×6 |
| zone/uniform/lightbar backends | 1×N or 1×1 |
| `sysfs-leds` / `asusctl-aura` | reference fallback (currently 6×20) |

Tray bootstrap already captures backend dimensions as `_ite_rows/_ite_cols` and
uses them for config-poller per-key map fill. The effects engine does not. As a
result:

1. a selected 7×20 or 6×20 per-key backend still receives software/reactive
   frames built for 6×21;
2. out-of-range cells are dropped or clipped by device writers, and missing
   cells are never painted by the effect;
3. tray icon mosaics and effect buffers can disagree with the same backend
   geometry used by config apply;
4. profile/layout slot mapping still resolves to matrix cells, so a fixed grid
   also misaligns visual setup against hardware matrix ownership.

The preparatory contract already proves `build_full_color_grid()` honors
explicit dimensions. The remaining defect is that live software/reactive frame
construction still does not pass selected-backend geometry through one owner.

## Decision constraints

The solution must preserve current public facades and hardware-safe defaults. It
must not:

- make software effects import tray types or tray-private state;
- hold A2 coordinator ownership across frame rendering;
- rewrite physical layout/slot identity into LED matrix ownership;
- require every non-per-key backend to invent a fake keyboard matrix;
- break stored profiles that already use `(row, col)` keys for a device matrix;
- select hardware under pytest without explicit opt-in.

Physical layout variants (ANSI/ISO/…) remain independent. A5 owns LED/effect
matrix geometry only.

## Proposed owner

Make the effects engine the single runtime owner of effect-grid geometry.

### Geometry record

Add an immutable record near matrix layout ownership, for example:

```text
EffectGridGeometry {
  rows: int
  cols: int
  source: "backend" | "reference"
  backend_name: str | None
}
```

Reference geometry remains the documented fallback and is equal to today's
reference matrix defaults. Module-level `matrix_layout.NUM_ROWS/NUM_COLS` become
compatibility aliases for that reference fallback, not the live runtime owner.

### Ownership rules

1. `EffectsEngine` stores one `effect_geometry` snapshot.
2. Geometry is refreshed whenever backend ownership changes:
   - construction
   - `set_backend()`
   - device ensure/reacquire paths that already refresh backend capabilities
3. Geometry selection policy:
   - if backend capabilities declare `per_key=True` and `dimensions()` returns a
     positive finite pair, use those dimensions with `source="backend"`;
   - otherwise keep reference geometry with `source="reference"`.
4. Non-per-key backends continue to render uniform output. They may still build
   temporary logical frames on the reference grid for software math, then reduce
   to uniform RGB. They do not claim backend matrix ownership.
5. Tray `_ite_rows/_ite_cols` and config-poller map fill read the same geometry
   owner rather than a second independent bootstrap capture. Bootstrap may seed
   the engine, but the engine snapshot is authoritative after startup.

## Frame construction contract

Every software/reactive frame path that currently imports fixed
`matrix_layout.NUM_*` must obtain rows/cols from the active engine geometry:

- full-grid base maps
- reactive/software reusable buffers
- ripple/fade radius and bounds checks
- random cell selection inside effect loops
- tray-icon mosaic generation for software/reactive modes
- per-key fade/prime helpers

The already-dimensioned primitive `build_full_color_grid(..., num_rows, num_cols)`
remains the low-level grid builder. Callers stop hard-coding 6×21.

### Device write boundary

Per-key device writes receive only cells inside the active geometry. Backend
transports continue to validate their own matrix. A5 does not move protocol
packet layout ownership out of backend modules.

### Profile and slot data

Stored profile colors remain sparse `(row, col) -> rgb` maps.

- Cells inside the active geometry are applied.
- Cells outside the active geometry are ignored for rendering and must not crash
  the frame path.
- Sparse maps smaller than the geometry continue to fill from base color through
  `build_full_color_grid`.
- No automatic destructive rewrite of on-disk profiles is performed in A5.

Physical slot IDs still resolve to matrix cells through the existing layout
model. A5 only ensures the destination matrix matches the selected backend when
per-key output is active.

## Explicit non-goals

- redesigning physical layout catalogs or calibrator UX
- multi-device primary matrices in one effect engine
- per-frame geometry mutation while an effect thread is running without a
  generation boundary
- changing backend protocol row packing
- forcing zone/uniform devices to expose synthetic dense keyboard matrices as
  per-key surfaces

## Migration shape

1. Introduce `EffectGridGeometry` and reference helpers in effects matrix
   ownership.
2. Attach geometry to `EffectsEngine` beside `backend_caps`.
3. Thread geometry into software/reactive helpers and the reactive API binding
   surface. Prefer explicit parameters or engine-owned accessors over more
   module globals.
4. Point tray bootstrap/config-poller dimension consumers at the engine snapshot.
5. Keep reference constants as fallback/compatibility only.
6. Add regression tests for mismatched backend dimensions before changing
   production paths.

## Test contracts

Deterministic tests must prove:

1. selecting a 7×20 per-key backend makes software/reactive frames contain
   exactly 7×20 cells;
2. selecting a 6×20 per-key backend does not emit column 20;
3. a non-per-key backend keeps reference geometry for logical software math and
   still reduces to uniform output;
4. tray/config per-key fill uses the same geometry as the engine;
5. geometry refreshes with backend changes and device ensure, similar to
   capability refresh;
6. unexpected dimension lookup defects remain transparent; recoverable failures
   fall back to reference geometry with logging where the boundary already
   degrades;
7. existing 6×21 ITE paths remain behavior-compatible.

Hardware-safe unit tests inject fake backends/specs. No real device open is
required.

## Approval decision

Approve or revise these points before production work begins:

1. effects engine owns one immutable `EffectGridGeometry` snapshot;
2. per-key backends supply live rows/cols through `dimensions()`;
3. non-per-key backends keep reference geometry and uniform reduction;
4. software/reactive/tray-icon frame construction consumes the engine snapshot;
5. tray `_ite_rows/_ite_cols` become views of that same owner;
6. physical layout/slot identity remains outside A5;
7. no on-disk profile rewrite is required for A5.

## Implementation outcome

- Added immutable `EffectGridGeometry` and reference helpers in
  `src/core/effects/matrix_layout.py`.
- `EffectsEngine` owns `effect_geometry`, refreshed with backend capabilities on
  construction, `set_backend()`, and device ensure.
- Software/reactive/fade/tray-icon frame builders consume engine geometry.
- `build_full_color_grid()` ignores out-of-range profile cells.
- Tray bootstrap seeds `_ite_rows/_ite_cols` from the engine snapshot.
- Focused geometry contracts and full gates passed locally.
