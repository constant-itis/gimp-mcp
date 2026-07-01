# 05 — Selections, Channels & Masks

## Mental model
- A **selection** is a single grayscale mask attached to the image (0=unselected, 255=fully selected, intermediate=partial/antialiased/feathered). It is **global to the image**, not per-layer — there is one selection at a time.
- Most edit ops (`gimp-edit-fill`, `gimp-edit-clear`, paint, filters, color ops) **only affect pixels inside the active selection**. No selection = whole drawable.
- Every `gimp-image-select-*` call takes a **CHANNEL-OP** combine mode saying how the new shape merges with the existing selection: REPLACE / ADD / SUBTRACT / INTERSECT.
- A **channel** is a saved, named, reusable mask. `gimp-selection-save` snapshots the live selection into a channel; `gimp-image-select-item` loads a channel (or layer/path) back as a selection. Selection ops (grow/shrink/feather/etc.) act on the live selection, not on saved channels.
- IDs are integers. Selection procs return nothing useful; query state with `gimp-selection-bounds` / `-is-empty` / `-value`.

## Core procedures
| Signature | Use when |
|---|---|
| `(gimp-image-select-rectangle img op x y w h)` | axis-aligned rect region |
| `(gimp-image-select-round-rectangle img op x y w h rx ry)` | rect with rounded corners |
| `(gimp-image-select-ellipse img op x y w h)` | circle/ellipse (x,y,w,h = bounding box) |
| `(gimp-image-select-polygon img op num-segs #(x1 y1 x2 y2 ...))` | arbitrary polygon; **num-segs = count of floats = 2×points** |
| `(gimp-image-select-color img op drawable '(r g b))` | all pixels near a color (whole drawable) |
| `(gimp-image-select-contiguous-color img op drawable x y)` | fuzzy/magic-wand: flood from a seed point |
| `(gimp-image-select-item img op item)` | load a channel / layer-alpha / path as selection |
| `(gimp-selection-all img)` / `(gimp-selection-none img)` | select everything / clear selection |
| `(gimp-selection-invert img)` | flip selected ↔ unselected |
| `(gimp-selection-grow img steps)` / `(gimp-selection-shrink img steps)` | expand/contract boundary by N px |
| `(gimp-selection-feather img radius)` | soften edges (gaussian, radius in px, FLOAT) |
| `(gimp-selection-border img radius)` | replace with a band of width `radius` around the edge |
| `(gimp-selection-sharpen img)` | remove antialias/feather → hard 0/255 mask |
| `(gimp-selection-flood img)` | fill interior holes left by fuzzy select |
| `(gimp-selection-save img)` → channel id | snapshot live selection to a new channel |
| `(gimp-selection-bounds img)` → `(non-empty x1 y1 x2 y2)` | get bbox; w=x2-x1, h=y2-y1 |
| `(gimp-selection-is-empty img)` → TRUE/FALSE | guard before an op |
| `(gimp-selection-value img x y)` → 0..255 | mask value at a pixel |
| `(gimp-channel-combine-masks ch1 ch2 op offx offy)` | boolean two saved channels into ch1 |
| `(gimp-image-insert-channel img ch parent pos)` | add a `gimp-channel-new` channel to the image |

## Recipes

### Select a rectangular region
```scheme
(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 40 40 200 120)
```

### Select an ellipse / circle
```scheme
; ellipse inside bbox (cx-50, cy-50) 100x100 = a 100px circle
(gimp-image-select-ellipse img CHANNEL-OP-REPLACE 60 60 100 100)
```

### Select a polygon (triangle)
```scheme
; num-segs = 6 floats (3 points). Pass the FLOATARRAY as a Scheme vector.
(gimp-image-select-polygon img CHANNEL-OP-REPLACE 6 #(10 10 200 30 60 180))
; building from a list: (list->vector (list 10 10 200 30 60 180))
```

### Select by color (everywhere in the drawable)
```scheme
(define draw (car (gimp-image-get-active-drawable img)))
(gimp-context-set-sample-threshold-int 30)   ; 0..255 tolerance
(gimp-image-select-color img CHANNEL-OP-REPLACE draw '(255 0 0))  ; all near-red pixels
```

### Fuzzy / contiguous select (magic wand from a seed point)
```scheme
(define draw (car (gimp-image-get-active-drawable img)))
(gimp-context-set-sample-threshold-int 50)
(gimp-context-set-sample-merged FALSE)        ; sample active drawable only
(gimp-image-select-contiguous-color img CHANNEL-OP-REPLACE draw 100 100)
(gimp-selection-flood img)                     ; optional: close interior holes
```

### Invert the selection (e.g. select background = everything but subject)
```scheme
(gimp-image-select-ellipse img CHANNEL-OP-REPLACE 80 80 240 240)
(gimp-selection-invert img)                    ; now everything OUTSIDE the ellipse
```

### Feather edges then delete to fade
```scheme
(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 50 50 300 200)
(gimp-selection-feather img 25)                ; 25px gaussian softness
(define draw (car (gimp-image-get-active-drawable img)))
(gimp-edit-clear draw)                          ; soft-edged hole (or fill instead)
(gimp-selection-none img)
```

### Grow / shrink a selection
```scheme
(gimp-image-select-ellipse img CHANNEL-OP-REPLACE 100 100 120 120)
(gimp-selection-grow img 10)                    ; +10px outward
; (gimp-selection-shrink img 10)                ; -10px inward
```

### Save selection to a channel, then restore it later
```scheme
(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 8 8 32 32)
(define ch (car (gimp-selection-save img)))     ; new channel, named "Selection Mask"
(gimp-item-set-name ch "subject")
(gimp-selection-none img)
; ... do other work ...
(gimp-image-select-item img CHANNEL-OP-REPLACE ch)  ; selection is back, bbox 8,8..40,40
```

### Combine two saved channels (boolean masks)
```scheme
; ch-a, ch-b created via gimp-selection-save. Result stored in ch-a.
(gimp-channel-combine-masks ch-a ch-b CHANNEL-OP-INTERSECT 0 0)
(gimp-image-select-item img CHANNEL-OP-REPLACE ch-a)
```

### Add a second shape to the current selection (multi-region)
```scheme
(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 20 20 80 80)
(gimp-image-select-ellipse   img CHANNEL-OP-ADD    140 20 80 80)  ; union of both
```

### Select all + clear the whole drawable
```scheme
(gimp-selection-all img)
(gimp-edit-clear (car (gimp-image-get-active-drawable img)))  ; transparent (or BG color)
(gimp-selection-none img)
```

### Mask a region, then apply a filter only there
```scheme
(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 0 0 256 384)  ; left half
(define draw (car (gimp-image-get-active-drawable img)))
(plug-in-gauss RUN-NONINTERACTIVE img draw 15 15 0)  ; blur confined to selection
(gimp-selection-none img)
(gimp-displays-flush)
```

## Gotchas & enums
- **CHANNEL-OP** values: `CHANNEL-OP-ADD` (0), `CHANNEL-OP-SUBTRACT` (1), `CHANNEL-OP-REPLACE` (2), `CHANNEL-OP-INTERSECT` (3). Use bare constants, not ints. Default mental model: REPLACE to start fresh, ADD/SUBTRACT to build compound regions.
- **Deprecated → replacement**: `gimp-rect-select`/`gimp-ellipse-select`/`gimp-fuzzy-select`/`gimp-by-color-select` → the `gimp-image-select-*` family. `gimp-selection-load`/`-combine`/`-layer-alpha` → `gimp-image-select-item`. `gimp-selection-clear` → `gimp-selection-none`. `gimp-channel-{get,set}-name/visible/tattoo` → `gimp-item-*`.
- **num-segs for polygon = number of floats (2×points)**, NOT the point count. A triangle is `6`, a quad is `8`. Wrong size → `FLOAT vector has size of N but expected size of M`. Pass the array as a Scheme **vector** (`#(...)` or `list->vector`), not a list.
- **Feather/grow/shrink/border radii are pixels** (feather radius is FLOAT, grow/shrink/border steps are INT). Feather happens at apply-time and softens; `gimp-selection-sharpen` undoes softness back to hard 0/255.
- **Color/contiguous select read context, not args** for tolerance: set `gimp-context-set-sample-threshold-int` (0–255) or `-sample-threshold` (0–1 FLOAT) first. Other knobs: `gimp-context-set-antialias TRUE/FALSE`, `gimp-context-set-feather` + `-feather-radius`, `gimp-context-set-sample-merged` (TRUE = sample all visible layers composited, drawable arg ignored; coords become image-relative).
- **`gimp-image-select-color` ignores x/y** — it scans the whole drawable. Use `gimp-image-select-contiguous-color` (seed x,y) when you want only the connected blob.
- **Empty selection ≠ whole image.** `gimp-selection-none` makes ops act on the *entire* drawable. If you only meant a region, never leave a stale selection — and **`gimp-selection-none` before save/export** so a leftover selection doesn't cause a partial flatten/op.
- `gimp-selection-bounds` returns `(non-empty x1 y1 x2 y2)`; the lower-right pixel is exclusive, so width = x2−x1, height = y2−y1.
- A channel from `gimp-selection-save` is auto-inserted; one from `gimp-channel-new` is **not** — call `gimp-image-insert-channel`. Saved channels show in the Channels dock and persist in the .xcf.
- Coordinates for `gimp-image-select-rectangle`/`-ellipse` are FLOAT but integers work fine.

## See also
- **server.py wrappers**: `select(image_id, shape, x, y, width, height)` — shape ∈ rectangle|ellipse|all|none, always REPLACE; `fill(image_id, color)` — fills current selection (or whole drawable if none) with foreground; `draw_rect(...)` selects+fills+deselects in one shot. Use raw PDB (this file) when you need ADD/SUBTRACT/INTERSECT, polygon/color/fuzzy, feather, or save-to-channel.
- **06-paint-draw** — `gimp-edit-fill`, `gimp-edit-clear`, brush strokes constrained by the active selection.
- **04-color-tone** — brightness/curves/hue ops that honor the selection for local adjustments.
- **07-filters-fx** — `plug-in-*` (e.g. `plug-in-gauss`) run only inside the selection; mask-a-region recipe above.
- **render_preview(image_id)** then Read the PNG to visually confirm a mask before committing destructive edits.
