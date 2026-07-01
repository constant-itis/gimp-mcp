# 09 — Vectors & Paths

## Mental model
- A **vectors** object (integer handle, also an ITEM) is a *path* — a container of one or more **strokes**.
- A **stroke** (integer `stroke-id`, 1-based per vectors object) is a bezier spline defined by **control points**.
- Control points are passed as a **flat float vector** of x,y pairs in the order `C A C  C A C …` — every **anchor (A)** is flanked by two **control handles (C)** (the bezier in/out tangents). One vertex = 3 points = 6 floats.
- A path is geometry only; it paints nothing until you either **stroke** it onto a drawable (`gimp-edit-stroke-vectors`) or convert it to a **selection** (`gimp-image-select-item`) and fill.
- A new vectors object is detached — you **must** `gimp-image-insert-vectors` before adding strokes or using it.
- `(car …)` for the first return value; ids are plain integers.

## Core procedures
| Procedure | Signature | Use when |
|---|---|---|
| `gimp-vectors-new` | `IMG NAME → vectors` | Create empty path object (not yet inserted) |
| `gimp-image-insert-vectors` | `IMG VECTORS PARENT POSITION` | Add path to image (PARENT 0, POSITION -1 = top). **Required before use** |
| `gimp-image-remove-vectors` | `IMG VECTORS` | Delete a path from the image |
| `gimp-vectors-copy` | `VECTORS → newvectors` | Duplicate a path (still needs insert) |
| `gimp-vectors-stroke-new-from-points` | `VECTORS TYPE NUM-POINTS #(floats) CLOSED → stroke-id` | Add a whole stroke from a flat control-point vector |
| `gimp-vectors-bezier-stroke-new-moveto` | `VECTORS X0 Y0 → stroke-id` | Start a stroke at a point, then extend it |
| `gimp-vectors-bezier-stroke-lineto` | `VECTORS SID X0 Y0` | Append a straight segment |
| `gimp-vectors-bezier-stroke-cubicto` | `VECTORS SID CX0 CY0 CX1 CY1 EX EY` | Append a cubic bezier (2 handles + endpoint) |
| `gimp-vectors-bezier-stroke-conicto` | `VECTORS SID CX CY EX EY` | Append a quadratic/conic segment (1 control) |
| `gimp-vectors-bezier-stroke-new-ellipse` | `VECTORS CX CY RX RY ANGLE → stroke-id` | Add a ready-made ellipse stroke |
| `gimp-vectors-stroke-close` | `VECTORS SID` | Close an open stroke (joins last→first) |
| `gimp-vectors-get-strokes` | `VECTORS → (count #(ids…))` | List stroke ids on a path |
| `gimp-vectors-stroke-get-points` | `VECTORS SID → (type num #(floats) closed)` | Read control points back |
| `gimp-vectors-stroke-get-length` | `VECTORS SID PRECISION → length` | Measure stroke length |
| `gimp-vectors-stroke-get-point-at-dist` | `VECTORS SID DIST PRECISION → (x y slope valid)` | Point along stroke (text-along-path) |
| `gimp-vectors-stroke-interpolate` | `VECTORS SID PRECISION → (#(coords) closed)` | Polygonal approximation of a stroke |
| `gimp-vectors-stroke-translate/scale/rotate/flip` | `VECTORS SID …` | Transform a single stroke |
| `gimp-image-select-item` | `IMG OP VECTORS` | **Path → selection** (replaces deprecated `gimp-vectors-to-selection`) |
| `gimp-edit-stroke-vectors` | `DRAWABLE VECTORS` | **Paint the path** onto a drawable with current brush/context |
| `gimp-image-insert-vectors` … | — | — |
| `gimp-vectors-new-from-text-layer` | `IMG LAYER → vectors` | Outline a text layer into a path |
| `gimp-vectors-import-from-string` | `IMG SVG-STR LEN MERGE SCALE → #(vectors)` | Build paths from an SVG string |
| `gimp-vectors-export-to-string` | `IMG VECTORS → svg-str` | Serialize path(s) to SVG (0 = all) |

Note: `gimp-vectors-{to-selection,get/set-name,get/set-visible,get/set-linked,get/set-tattoo,is-valid,parasite-*}` are **deprecated** → use `gimp-image-select-item` and the `gimp-item-*` equivalents. There is no path-specific server.py wrapper yet — drive all of these through **`gimp_eval`** / the bridge.

## Recipes

### Create a vectors object and add it to the image
```scheme
(let* ((img (car (gimp-image-list)))                ; or gimp-image-new
       (v   (car (gimp-vectors-new img "my-path"))))
  (gimp-image-insert-vectors img v 0 -1)            ; PARENT 0, POSITION -1 = top of stack
  v)                                                ; → integer vectors id
```

### Add a polygon stroke from corner points
A polygon = straight edges, so set each control handle **equal to its anchor** (zero-length tangents). Per vertex emit `Cx Cy  Ax Ay  Cx Cy` with C=A → 6 floats/vertex.
```scheme
(let* ((img (car (gimp-image-list)))
       (v   (car (gimp-vectors-new img "triangle"))))
  (gimp-image-insert-vectors img v 0 -1)
  ;; triangle (20,20)(180,20)(100,180): 3 verts × 3 pts × 2 = 18 floats, C=A everywhere
  (gimp-vectors-stroke-new-from-points
     v VECTORS-STROKE-TYPE-BEZIER 18
     (list->vector (list  20.0  20.0   20.0  20.0   20.0  20.0
                         180.0  20.0  180.0  20.0  180.0  20.0
                         100.0 180.0  100.0 180.0  100.0 180.0))
     TRUE))                                          ; CLOSED → join last→first
```
Helper: build it from a vertex list so you don't hand-triple coordinates.
```scheme
(define (poly-stroke v pts closed)        ; pts = ((x . y) ...)
  (gimp-vectors-stroke-new-from-points
     v VECTORS-STROKE-TYPE-BEZIER
     (* 6 (length pts))
     (list->vector
       (apply append
         (map (lambda (p) (let ((x (car p)) (y (cdr p)))
                            (list x y x y x y)))      ; C A C, all = anchor
              pts)))
     closed))
```

### Add a smooth bezier curve (explicit handles)
Here handles differ from anchors, giving curvature. Order is `C A C` per anchor.
```scheme
(let* ((img (car (gimp-image-list)))
       (v   (car (gimp-vectors-new img "curve"))))
  (gimp-image-insert-vectors img v 0 -1)
  ;; two anchors A1(20,100) A2(180,100), handles pull the curve into an arch
  (gimp-vectors-stroke-new-from-points
     v VECTORS-STROKE-TYPE-BEZIER 12
     (list->vector (list  20.0  40.0    20.0 100.0    60.0  40.0     ; in-A1-out
                         140.0  40.0   180.0 100.0   180.0  40.0))   ; in-A2-out
     FALSE))                                          ; open stroke
```

### Build a stroke incrementally (moveto / lineto / cubicto)
```scheme
(let* ((img (car (gimp-image-list)))
       (v   (car (gimp-vectors-new img "drawn"))))
  (gimp-image-insert-vectors img v 0 -1)
  (let ((sid (car (gimp-vectors-bezier-stroke-new-moveto v 20.0 20.0))))
    (gimp-vectors-bezier-stroke-lineto  v sid 180.0 20.0)
    (gimp-vectors-bezier-stroke-cubicto v sid 200.0 80.0 200.0 140.0 120.0 180.0)
    (gimp-vectors-stroke-close v sid)                 ; optional: close it
    sid))
```

### Convert a selection into a path
There is no direct PDB "selection→vectors" in this slice; use the registered plug-in `plug-in-sel2path` on the image's selection.
```scheme
(let ((img (car (gimp-image-list))))
  ;; assumes a non-empty selection already exists
  (plug-in-sel2path RUN-NONINTERACTIVE img)
  (car (gimp-image-get-active-vectors img)))          ; → the new vectors id
```

### Convert a path into a selection, then fill
```scheme
(let* ((img (car (gimp-image-list)))
       (v   (car (gimp-image-get-active-vectors img)))
       (drw (car (gimp-image-get-active-drawable img))))
  (gimp-image-select-item img CHANNEL-OP-REPLACE v)   ; path → selection
  (gimp-context-set-foreground '(255 0 0))
  (gimp-edit-fill drw FILL-FOREGROUND)
  (gimp-selection-none img)
  (gimp-displays-flush))
```
For antialias/feather control use the deprecated `gimp-vectors-to-selection v OP ANTIALIAS FEATHER FRX FRY`; `gimp-image-select-item` honors the context's antialias/feather settings instead.

### Stroke a path onto a drawable (current brush + color)
```scheme
(let* ((img (car (gimp-image-list)))
       (v   (car (gimp-image-get-active-vectors img)))
       (drw (car (gimp-image-get-active-drawable img))))
  (gimp-context-set-foreground '(0 0 0))
  (gimp-context-set-brush (car (gimp-brushes-get-brush)))
  (gimp-context-set-line-width 3)                     ; used when stroking by line, not paint tool
  (gimp-edit-stroke-vectors drw v)                    ; paints v onto drw with current context
  (gimp-displays-flush))
```

### Close an open stroke
```scheme
(gimp-vectors-stroke-close v sid)   ; sid from get-strokes / a *-new-* call
```

### Text-along-path helper (sample anchor points)
`gimp-vectors-stroke-get-point-at-dist` walks the curve; place glyphs/objects at each returned (x,y).
```scheme
(let* ((v   (car (gimp-image-get-active-vectors (car (gimp-image-list)))))
       (sid (vector-ref (cadr (gimp-vectors-get-strokes v)) 0))
       (len (car (gimp-vectors-stroke-get-length v sid 1.0))))
  (map (lambda (frac)
         (gimp-vectors-stroke-get-point-at-dist v sid (* frac len) 1.0)) ; → (x y slope valid)
       '(0.0 0.25 0.5 0.75 1.0)))
```

## Gotchas & enums
- **`gimp-image-insert-vectors` is mandatory** before adding strokes or stroking/selecting — a detached `gimp-vectors-new` result will error.
- **Stroke type enum:** only `VECTORS-STROKE-TYPE-BEZIER` (= `0`) exists. Pass the symbol, not a raw int, for readability.
- **Control-point layout (the hard part):** flat float vector, x,y pairs, grouped as `C A C  C A C …` per anchor. `NUM-POINTS` = number of *control points* × 2 (i.e. total floats), **not** the number of vertices. n vertices → `6n` floats.
- **Polygon trick:** straight segments = set both handles equal to the anchor (`x y  x y  x y`). Curvature comes from moving the C handles off the A.
- **`CLOSED` flag** (`TRUE`/`FALSE`) is on `stroke-new-from-points`; for incrementally built strokes call `gimp-vectors-stroke-close` instead. A closed stroke joins last anchor → first.
- **stroke-ids are per-vectors and 1-based**; `gimp-vectors-get-strokes` returns `(count #(ids…))` — pull ids with `(vector-ref (cadr …) i)`.
- **Selection ops enum:** `CHANNEL-OP-ADD 0`, `CHANNEL-OP-SUBTRACT 1`, `CHANNEL-OP-REPLACE 2`, `CHANNEL-OP-INTERSECT 3`.
- **Stroking ≠ filling:** `gimp-edit-stroke-vectors` outlines the path; to fill an enclosed shape go path→selection→`gimp-edit-fill`.
- Most `get/set` metadata procs on vectors are **deprecated** → use `gimp-item-*` (e.g. `gimp-item-set-name`, `gimp-item-set-visible`).
- Verified on GIMP 2.10.30: 6-float open polygon stroke → id `1`; 18-float closed triangle → `gimp-image-select-item` yields a non-empty selection.

## See also
- **07-selections** — `gimp-image-select-item`, `gimp-selection-none`, channel ops, feather/antialias context.
- **08-paint-draw** — `gimp-edit-stroke-vectors`, brush/foreground context, `gimp-edit-fill`, `gimp-pencil`/`gimp-paintbrush`.
- **02-layers-masks** — drawables you stroke/fill onto; `gimp-vectors-new-from-text-layer` ties paths to text layers.
