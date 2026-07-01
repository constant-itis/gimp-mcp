# 06 — Transforms & Canvas

Scaling, cropping, canvas resize, rotation, flip, and affine/perspective transforms via
Script-Fu PDB. All values are literal Scheme. Handles (image/item/drawable) are INTEGERS.
Booleans are `TRUE`/`FALSE`. Enums are bare constants (e.g. `ROTATE-90`). Grab the first
return value with `(car ...)`.

## Mental model

- **Scale** resamples content — pixels are interpolated, dimensions change, image looks the
  same but at a new resolution. **Resize** changes the *canvas* (the frame) and repositions
  layers by an offset; content pixels are untouched. **Crop** discards everything outside a
  rectangle.
- **Image-level** procs (`gimp-image-scale`, `-crop`, `-resize`, `-rotate`, `-flip`) act on
  the whole image: every layer, channel, and the selection mask move together.
- **Item-level** procs (`gimp-item-transform-*`) act on **one item** (layer/channel/path).
  They are affected by context: set `gimp-context-set-interpolation`,
  `gimp-context-set-transform-resize`, and `gimp-context-set-transform-direction` *before*
  the call to control quality and clipping.
- An item transform on a **drawable with an active selection** cuts the selected region into
  a **floating selection** and returns *its* ID — anchor it with `gimp-floating-sel-anchor`.
  With no selection it transforms the whole item and returns the item ID. Either way the
  return is a single drawable id you read with `(car ...)`.
- `gimp-image-scale` uses the interpolation set via `gimp-context-set-interpolation`
  (`gimp-image-scale-full` is deprecated — don't pass interpolation inline).

## Core procedures

| Procedure | Signature (args) | Use when |
|---|---|---|
| `gimp-image-scale` | `image new-width new-height` | Resample whole image to exact px size. |
| `gimp-image-crop` | `image new-width new-height offx offy` | Cut image to a rect; offx/offy = top-left of kept region. |
| `gimp-image-resize` | `image new-width new-height offx offy` | Change canvas size; shift layers by (offx,offy). Content kept. |
| `gimp-image-resize-to-layers` | `image` | Fit canvas to the bounding box of all layers. |
| `gimp-image-rotate` | `image rotate-type` | 90/180/270 whole-image rotation (`ROTATE-90/180/270`). |
| `gimp-image-flip` | `image flip-type` | Mirror whole image (`ORIENTATION-HORIZONTAL/VERTICAL`). |
| `plug-in-autocrop` | `RUN-NONINTERACTIVE image drawable` | Trim uniform-color borders off the image. |
| `gimp-item-transform-scale` | `item x0 y0 x1 y1` | Scale one layer to a new bounding box (corner coords). |
| `gimp-item-transform-rotate` | `item angle auto-center center-x center-y` | Rotate one item by arbitrary radians about a point. |
| `gimp-item-transform-rotate-simple` | `item rotate-type auto-center center-x center-y` | 90/180/270 rotate of one item. |
| `gimp-item-transform-flip-simple` | `item flip-type auto-center axis` | Mirror one item (H/V). |
| `gimp-item-transform-flip` | `item x0 y0 x1 y1` | Flip one item around an arbitrary axis line. |
| `gimp-item-transform-shear` | `item shear-type magnitude` | Shear one item H/V by magnitude px. |
| `gimp-item-transform-perspective` | `item x0 y0 x1 y1 x2 y2 x3 y3` | Remap 4 corners (perspective / keystone). |
| `gimp-item-transform-2d` | `item src-x src-y scale-x scale-y angle dest-x dest-y` | Combined scale+rotate+translate about a point. |
| `gimp-item-transform-matrix` | `item c00 c01 c02 c10 c11 c12 c20 c21 c22` | Raw 3x3 affine matrix. |
| `gimp-item-transform-translate` | `item off-x off-y` | Move one item by an offset (no resampling). |

Note: every `gimp-drawable-transform-*` proc is **deprecated** — use the `gimp-item-transform-*`
equivalent. Context setters live in `context-resources`; see also `08-context-resources.md`.

## Recipes

### Scale to fit a max dimension, preserving aspect
Compute the ratio in Python, round to ints, then one PDB call. Set interpolation first.
```python
import subprocess
def ev(e): return subprocess.run(["python3","gimp_bridge.py",e],
                                 capture_output=True,text=True).stdout.strip()
img = 1
w = int(ev(f"(car (gimp-image-width {img}))"))
h = int(ev(f"(car (gimp-image-height {img}))"))
MAX = 1024
r = min(MAX / w, MAX / h, 1.0)            # never upscale past original here
nw, nh = max(1, round(w * r)), max(1, round(h * r))
ev("(gimp-context-set-interpolation INTERPOLATION-CUBIC)")
ev(f"(gimp-image-scale {img} {nw} {nh})")
```

### Scale to fit, pure Scheme (no Python round-trip)
```scheme
(let* ((img 1)
       (w (car (gimp-image-width img)))
       (h (car (gimp-image-height img)))
       (maxd 1024.0)
       (r (min (/ maxd w) (/ maxd h)))
       (nw (max 1 (round (* w r))))
       (nh (max 1 (round (* h r)))))
  (gimp-context-set-interpolation INTERPOLATION-CUBIC)
  (gimp-image-scale img nw nh))
```

### Crop to a region (e.g. keep a 800x600 box at offset 100,50)
```scheme
(gimp-image-crop 1 800 600 100 50)   ; image new-w new-h offx offy
(gimp-displays-flush)
```

### Center-crop to a square
```scheme
(let* ((img 1)
       (w (car (gimp-image-width img)))
       (h (car (gimp-image-height img)))
       (s (min w h)))
  (gimp-image-crop img s s (quotient (- w s) 2) (quotient (- h s) 2)))
```

### Autocrop uniform borders
Needs a drawable; trims solid margins off the whole image.
```scheme
(let* ((img 1) (d (car (gimp-image-get-active-drawable img))))
  (plug-in-autocrop RUN-NONINTERACTIVE img d))
```

### Rotate the whole image 90° clockwise
```scheme
(gimp-image-rotate 1 ROTATE-90)   ; or ROTATE-180 / ROTATE-270
(gimp-displays-flush)
```

### Rotate one layer by an arbitrary angle about its center
Angle is **radians**. `auto-center TRUE` rotates about the item center (the center-x/-y args
are then ignored but must still be supplied). Set interpolation + resize policy first.
```scheme
(let* ((img 1)
       (layer (car (gimp-image-get-active-layer img)))
       (deg 12.5)
       (rad (* deg (/ 3.14159265358979 180))))
  (gimp-context-set-interpolation INTERPOLATION-CUBIC)
  (gimp-context-set-transform-resize TRANSFORM-RESIZE-ADJUST)  ; grow layer to fit
  (gimp-item-transform-rotate layer rad TRUE 0 0))
```

### Rotate about an explicit pivot point
```scheme
(gimp-context-set-interpolation INTERPOLATION-CUBIC)
(gimp-item-transform-rotate
   (car (gimp-image-get-active-layer 1))
   (/ 3.14159265358979 6)   ; 30° in radians
   FALSE 320 240)            ; auto-center FALSE -> pivot at (320,240)
```

### Flip the whole image, or just one layer
```scheme
(gimp-image-flip 1 ORIENTATION-HORIZONTAL)            ; whole image, mirror L<->R
; one layer, vertical, about its own center (axis arg ignored when auto-center TRUE):
(gimp-item-transform-flip-simple
   (car (gimp-image-get-active-layer 1)) ORIENTATION-VERTICAL TRUE 0)
```

### Scale one layer to a new bounding box (corner coords)
Double the active layer in place from its current top-left (0,0) to (2w,2h).
```scheme
(let* ((img 1) (l (car (gimp-image-get-active-layer img)))
       (w (car (gimp-drawable-width l))) (h (car (gimp-drawable-height l))))
  (gimp-context-set-interpolation INTERPOLATION-CUBIC)
  (gimp-item-transform-scale l 0 0 (* 2 w) (* 2 h)))
```

### Expand canvas and center the existing content
Resize canvas larger, offset layers to center, then flatten/clip nothing.
```scheme
(let* ((img 1)
       (w (car (gimp-image-width img))) (h (car (gimp-image-height img)))
       (nw (+ w 200)) (nh (+ h 200)))
  (gimp-image-resize img nw nh (quotient (- nw w) 2) (quotient (- nh h) 2))
  ; resize moves the canvas but not layer pixels; reposition the active layer too:
  (gimp-layer-set-offsets (car (gimp-image-get-active-layer img))
                          (quotient (- nw w) 2) (quotient (- nh h) 2)))
```

### Shrink canvas to the layers (auto-fit frame to content)
```scheme
(gimp-image-resize-to-layers 1)
(gimp-displays-flush)
```

### Perspective / keystone correction on a layer
Remap the 4 corners (upper-L, upper-R, lower-L, lower-R). Pull the top edge inward.
```scheme
(let* ((l (car (gimp-image-get-active-layer 1)))
       (w (car (gimp-drawable-width l))) (h (car (gimp-drawable-height l))))
  (gimp-context-set-interpolation INTERPOLATION-CUBIC)
  (gimp-context-set-transform-resize TRANSFORM-RESIZE-CLIP)
  (gimp-item-transform-perspective l
     (* 0.15 w) 0   (* 0.85 w) 0       ; top-left, top-right pulled in
     0 h            w h))              ; bottom-left, bottom-right
```

### Anchor a floating selection after an item transform
If a selection was active, the transform produced a floating sel — anchor it back down.
```scheme
(let ((fsel (car (gimp-item-transform-rotate
                   (car (gimp-image-get-active-layer 1))
                   0.1 TRUE 0 0))))
  (gimp-floating-sel-anchor fsel))   ; no-op error if it wasn't floating; guard with selection check
```

## Gotchas & enums

- **Rotation enums (90/180/270):** `ROTATE-90 (0)`, `ROTATE-180 (1)`, `ROTATE-270 (2)`. Used by
  `gimp-image-rotate` and `gimp-item-transform-rotate-simple`. Arbitrary angles use
  `gimp-item-transform-rotate` in **radians** (`deg * pi/180`).
- **Flip/shear orientation:** `ORIENTATION-HORIZONTAL (0)`, `ORIENTATION-VERTICAL (1)`.
  Horizontal flip mirrors left↔right; vertical mirrors top↔bottom.
- **Interpolation:** `INTERPOLATION-NONE (0)`, `-LINEAR (1)`, `-CUBIC (2)`, `-NOHALO (3)`,
  `-LOHALO (4)`. Set with `(gimp-context-set-interpolation INTERPOLATION-CUBIC)` before any
  scale/rotate for quality; `NONE` is nearest-neighbor (pixel art).
- **Transform resize (clip) policy:** `(gimp-context-set-transform-resize ...)` with
  `TRANSFORM-RESIZE-ADJUST (0)` grow layer to fit result, `-CLIP (1)` keep original size,
  `-CROP (2)`, `-CROP-WITH-ASPECT (3)`. Rotating with `ADJUST` enlarges the layer to hold the
  corners; `CLIP` cuts them off.
- **Transform direction:** `(gimp-context-set-transform-direction TRANSFORM-FORWARD)` (0) vs
  `TRANSFORM-BACKWARD (1)` (inverse map). Default FORWARD is what you want.
- **Floating selection:** item transforms on a drawable under an active selection return a
  *floating sel* id, not the item id. Read it with `(car ...)` and
  `(gimp-floating-sel-anchor id)` (or `gimp-floating-sel-to-layer`) before doing anything
  else, or later ops will operate on the wrong drawable.
- **resize ≠ moving pixels:** `gimp-image-resize` repositions layers by the offset but a
  single layer's pixels may still need `gimp-layer-set-offsets` to truly recenter; flatten if
  unsure.
- **auto-center TRUE:** the center-x/center-y (or axis) args are ignored but must still be
  passed — supply `0`.
- **Deprecated:** all `gimp-drawable-transform-*` and `gimp-image-scale-full` — use
  `gimp-item-transform-*` / `gimp-image-scale` + context interpolation.
- Always `(gimp-displays-flush)` after a batch of edits if a display is attached (headless
  server: harmless no-op).

## See also

- **server.py MCP tools** (`./server.py`): `scale_image(image_id,w,h)` →
  `gimp-image-scale`; `crop(image_id,w,h,x,y)` → `gimp-image-crop`; `autocrop(image_id)` →
  `plug-in-autocrop`; `rotate(image_id,degrees)` → `gimp-image-rotate` (90/180/270 only — use
  `gimp_eval` + `gimp-item-transform-rotate` for arbitrary angles); `flip(image_id,direction)`
  → `gimp-image-flip`; `resize_canvas(image_id,w,h,x,y)` → `gimp-image-resize`.
- **`05-images-io.md`** — creating/loading images, `gimp-image-width/height`, flatten, export.
- **`07-layers-masks.md`** — `gimp-image-get-active-layer`, `gimp-layer-set-offsets`,
  floating-sel anchor, layer creation.
- **`08-context-resources.md`** — `gimp-context-set-interpolation/-transform-resize/-direction`.
