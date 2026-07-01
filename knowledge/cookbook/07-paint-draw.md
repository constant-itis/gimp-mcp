# 07 — Painting, Drawing & Filling

## Mental model
- Paint tools mutate a **drawable** (`(car (gimp-image-get-active-drawable IMG))`) using the **current context**: foreground/background color, active brush, brush size, opacity, paint mode. Set context FIRST — paint procs take no color/brush args, they read context.
- Stroke procs (`gimp-pencil`, `gimp-paintbrush`, `gimp-airbrush`, `gimp-eraser`, `gimp-smudge`, `gimp-clone`) take `num-strokes` (= total count of x/y values, i.e. 2× the number of points, NOT the number of points) plus a **flat float vector** `#(x1 y1 x2 y2 ...)`. A single point still needs `num-strokes 2` and `#(x y)`.
- Three ways to lay down color: **bucket fill** (seed-fill a contiguous color region or a selection), **edit-fill** (fill the active selection / whole drawable with FG/BG/pattern), **gradient fill** (interpolate between two points). All respect the active selection.
- After any paint op, call `(gimp-displays-flush)` so an open display repaints (no-op headless, harmless).

## Core procedures
| Procedure | Signature (types) | Use when |
|---|---|---|
| `gimp-context-set-foreground` | `(color '(R G B))` | Set FG color before painting/filling |
| `gimp-context-set-background` | `(color '(R G B))` | Set BG color (eraser w/o alpha, BG fills) |
| `gimp-context-set-brush` | `(brush "name")` | Pick brush (e.g. `"2. Hardness 050"`) |
| `gimp-context-set-brush-size` | `(size FLOAT)` | Brush diameter in px |
| `gimp-context-set-opacity` | `(opacity 0-100)` | Paint/fill opacity |
| `gimp-context-set-paint-mode` | `(mode LAYER-MODE-*)` | Blend mode for paint |
| `gimp-context-set-gradient` | `(name "Incandescent")` | Select gradient before gradient-fill |
| `gimp-pencil` | `(draw num-strokes #(x y ...))` | Hard-edge polyline, no AA |
| `gimp-paintbrush-default` | `(draw num-strokes #(x y ...))` | Soft brush stroke, options from dialog |
| `gimp-paintbrush` | `(draw fade-out num-strokes #(...) method grad-len)` | Brush stroke with fade-out / gradient pull |
| `gimp-airbrush` | `(draw pressure num-strokes #(...))` | Time-pressure spray (0-100) |
| `gimp-eraser` | `(draw num-strokes #(...) hardness method)` | Erase to transparent/BG |
| `gimp-smudge` | `(draw pressure num-strokes #(...))` | Smear existing pixels |
| `gimp-clone` | `(draw src-draw clone-type src-x src-y num-strokes #(...))` | Copy from source/pattern |
| `gimp-drawable-edit-fill` | `(draw fill-type)` | Fill selection/drawable w/ FG/BG/pattern |
| `gimp-drawable-edit-bucket-fill` | `(draw fill-type x y)` | Seed-fill contiguous region at x,y |
| `gimp-drawable-edit-gradient-fill` | `(draw grad-type offset supersample smax sthresh dither x1 y1 x2 y2)` | Gradient between two points |
| `gimp-drawable-edit-stroke-selection` | `(draw)` | Paint along selection boundary |
| `gimp-image-select-color` | `(img op draw '(R G B))` | Build a selection from a color, then fill |

> Each stroke proc returns `TRUE`; wrap calls in `(car ...)` only where you need a return value. The `-default` variants pull tool options from their dialogs — prefer them unless you need the extra args.

## Recipes

### Set foreground color and fill the whole layer
```scheme
(let* ((img (car (gimp-image-new 400 300 RGB)))
       (lay (car (gimp-layer-new img 400 300 RGB-IMAGE "bg" 100 LAYER-MODE-NORMAL))))
  (gimp-image-insert-layer img lay 0 -1)
  (gimp-context-set-foreground '(30 30 40))
  (gimp-image-select-rectangle img CHANNEL-OP-REPLACE 0 0 400 300)
  (gimp-drawable-edit-fill lay FILL-FOREGROUND)
  (gimp-selection-none img)
  (gimp-displays-flush))
```

### Draw a hard-edge polyline with the pencil
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-foreground '(255 80 80))
  (gimp-context-set-brush "1. Pixel")
  (gimp-context-set-brush-size 3)
  ;; 4 points = 8 values -> num-strokes 8
  (gimp-pencil d 8 #(20 20 120 60 200 30 300 140))
  (gimp-displays-flush))
```

### Soft brush stroke (paintbrush)
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-foreground '(60 160 255))
  (gimp-context-set-brush "2. Hardness 050")
  (gimp-context-set-brush-size 40)
  (gimp-context-set-opacity 80)
  (gimp-paintbrush-default d 6 #(40 250 200 200 360 260))
  (gimp-displays-flush))
```

### Airbrush spray with pressure
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-foreground '(255 230 120))
  (gimp-context-set-brush-size 60)
  (gimp-airbrush d 50 2 #(200 150))   ; pressure 50, single point
  (gimp-displays-flush))
```

### Fill the active selection with the foreground color
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-image-select-ellipse img CHANNEL-OP-REPLACE 100 80 160 120)
  (gimp-context-set-foreground '(120 220 120))
  (gimp-drawable-edit-fill d FILL-FOREGROUND)   ; only fills inside selection
  (gimp-selection-none img)
  (gimp-displays-flush))
```

### Bucket fill a contiguous color region (seed fill by similarity)
```scheme
;; No selection -> seed fills outward from (x,y) within threshold.
;; Threshold/sample-merged come from context, not args, on the edit-* proc.
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-foreground '(200 40 40))
  (gimp-context-set-sample-threshold-int 40)   ; 0-255 color similarity
  (gimp-drawable-edit-bucket-fill d FILL-FOREGROUND 200.0 150.0)
  (gimp-displays-flush))
```

### Select by color, then fill (region = every matching pixel, not just contiguous)
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-sample-threshold-int 30)
  (gimp-image-select-color img CHANNEL-OP-REPLACE d '(30 30 40)) ; pick the bg color
  (gimp-context-set-foreground '(10 80 10))
  (gimp-drawable-edit-fill d FILL-FOREGROUND)
  (gimp-selection-none img)
  (gimp-displays-flush))
```

### Linear gradient between two points
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-foreground '(255 0 0))
  (gimp-context-set-background '(0 0 255))
  (gimp-context-set-gradient "FG to BG (RGB)")
  ;; type offset supersample max-depth threshold dither x1 y1 x2 y2
  (gimp-drawable-edit-gradient-fill d GRADIENT-LINEAR 0 FALSE 3 0.2 FALSE
                                    0 0 400 300)
  (gimp-displays-flush))
```

### Radial gradient (center -> edge)
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-gradient "Incandescent")
  (gimp-drawable-edit-gradient-fill d GRADIENT-RADIAL 0 FALSE 3 0.2 FALSE
                                    200 150 200 0)  ; from center to top edge
  (gimp-displays-flush))
```

### Stroke a selection outline (rectangle border)
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-image-select-rectangle img CHANNEL-OP-REPLACE 50 50 300 200)
  (gimp-context-set-foreground '(255 255 255))
  (gimp-context-set-brush "2. Hardness 100")
  (gimp-context-set-brush-size 6)
  (gimp-drawable-edit-stroke-selection d)  ; paints along the boundary
  (gimp-selection-none img)
  (gimp-displays-flush))
```

### Draw a filled circle
```scheme
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-image-select-ellipse img CHANNEL-OP-REPLACE 150 100 100 100) ; x,y,w,h (square=circle)
  (gimp-context-set-foreground '(255 180 0))
  (gimp-drawable-edit-fill d FILL-FOREGROUND)
  (gimp-selection-none img)
  (gimp-displays-flush))
```

### Erase to transparency
```scheme
;; Layer must have alpha or eraser writes the BG color instead.
(let ((d (car (gimp-image-get-active-drawable img))))
  (gimp-image-set-active-layer img (car (gimp-image-get-active-layer img)))
  (gimp-layer-add-alpha (car (gimp-image-get-active-layer img)))
  (gimp-context-set-brush-size 30)
  (gimp-eraser d 4 #(80 80 240 200) BRUSH-HARD PAINT-CONSTANT)
  (gimp-displays-flush))
```

## Gotchas & enums
- **Context before paint.** Color/brush/size/opacity/paint-mode/gradient are NOT args to paint procs — set them via `gimp-context-set-*` first. Forgetting leaves you with stale defaults (often a black FG + tiny brush).
- **`num-strokes` is the value count, not the point count.** N points → `num-strokes = 2N`, vector has 2N floats. Mismatch errors or paints garbage. A dot = `2 #(x y)`.
- **Flat vector only.** Strokes are `#(x1 y1 x2 y2 ...)` (Scheme vector literal). Not a list, not nested pairs.
- **Selection scopes the fill.** `gimp-drawable-edit-fill` / `-bucket-fill` / `-gradient-fill` only affect inside the active selection. With no selection, edit-fill paints the whole drawable, bucket-fill seed-fills from (x,y). Use `gimp-drawable-fill` (not in this slice) to ignore selection entirely.
- **Bucket threshold lives in context** for the modern `gimp-drawable-edit-bucket-fill`: set `gimp-context-set-sample-threshold-int` (0-255) / `gimp-context-set-sample-merged` first. The deprecated `gimp-edit-bucket-fill[-full]` take threshold/x/y as args instead.
- **Fill-type enum:** `FILL-FOREGROUND (0)`, `FILL-BACKGROUND (1)`, `FILL-WHITE (2)`, `FILL-TRANSPARENT (3)`, `FILL-PATTERN (4)`. Bucket *legacy* fill-mode enum differs: `BUCKET-FILL-FG (0)`, `BUCKET-FILL-BG (1)`, `BUCKET-FILL-PATTERN (2)`.
- **Gradient-type enum:** `GRADIENT-LINEAR (0)`, `GRADIENT-BILINEAR (1)`, `GRADIENT-RADIAL (2)`, `GRADIENT-SQUARE (3)`, `GRADIENT-CONICAL-SYMMETRIC (4)`, `GRADIENT-CONICAL-ASYMMETRIC (5)`, shapebursts `(6-8)`, spirals `(9-10)`.
- **Use `gimp-drawable-edit-gradient-fill`, not `gimp-blend`/`gimp-edit-blend`.** Both `gimp-blend` and `gimp-edit-blend` are deprecated; the edit-gradient-fill proc pulls blend/paint mode + opacity from context instead of a long arg list.
- **Likewise prefer the `gimp-drawable-edit-*` family** over `gimp-edit-fill`, `gimp-edit-bucket-fill`, `gimp-edit-stroke`, `gimp-edit-stroke-vectors`, `gimp-bucket-fill` — all deprecated aliases.
- **Eraser needs alpha** to erase to transparency; without an alpha channel it stamps the background color. `hardness` = `BRUSH-HARD (0)`/`BRUSH-SOFT (1)`; `method` = `PAINT-CONSTANT (0)`/`PAINT-INCREMENTAL (1)`.
- **Paint-mode** is a `LAYER-MODE-*` enum; default is `LAYER-MODE-NORMAL (28)`. The `*-LEGACY` variants reproduce GIMP 2.8 math.
- **Coords are floats** in stroke/gradient/bucket vectors; integers auto-coerce but write `200.0` where the arg type is FLOAT to avoid surprises.

## See also
- **server.py wrappers** (`./server.py`): `fill(image_id, color="R,G,B")` → selects-all + `gimp-edit-fill` shortcut; `draw_rect(image_id, x, y, w, h, ...)` → select-rectangle + fill. Use these MCP tools for the common cases; drop to raw PDB for brushes/gradients/strokes.
- **Selections** (`gimp-image-select-rectangle/ellipse/color`, `CHANNEL-OP-REPLACE/ADD/SUBTRACT/INTERSECT`, `gimp-selection-none`) — every fill/stroke recipe here depends on the selection slice.
- **Context & resources** — `gimp-context-set-brush/gradient/pattern`, brush/gradient enumeration (`gimp-brushes-get-list`, `gimp-gradients-get-list`); needed to know valid brush/gradient names.
- **Color & tone** — for adjusting painted pixels after the fact (curves/levels/hue).
- **Gradient editing** — `gimp-gradient-new` + `gimp-gradient-segment-set-left/right-color` to build a custom gradient before `gimp-context-set-gradient`.
