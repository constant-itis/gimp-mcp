# 02 — Layers & Masks

## Mental model
- An image is a stack of layers. Position **0 = top**, increasing downward; bottom layer = highest index. `(gimp-image-get-layers IMG)` returns them top→bottom.
- All handles are **integers**: image, layer, channel (a mask is a CHANNEL), vectors.
- A **drawable** is the thing you paint/filter on — usually the active layer: `(car (gimp-image-get-active-drawable IMG))`. A layer mask is also a drawable. "Layer" is a specific kind of drawable.
- Creating a layer (`gimp-layer-new`, `gimp-layer-copy`, `gimp-layer-new-from-drawable`) does **not** add it to the image. You must call `gimp-image-insert-layer` explicitly.
- `gimp-image-insert-layer IMG LAYER PARENT POSITION`: `PARENT` = 0 for top-level stack, or a layer-group id to nest inside it. `POSITION` = index in stack/group (0 = top). `-1` with parent 0 = insert above active layer.
- A layer mask is created (`gimp-layer-create-mask`) then attached (`gimp-layer-add-mask`) — two steps, mask must match layer size.

## Core procedures
| Procedure | Signature | Use when |
|---|---|---|
| `gimp-layer-new` | `IMG W H TYPE NAME OPACITY MODE → layer` | Make a blank layer (not yet inserted) |
| `gimp-image-insert-layer` | `IMG LAYER PARENT POSITION` | Add a layer to the stack/group |
| `gimp-image-remove-layer` | `IMG LAYER` | Delete a layer from the image |
| `gimp-layer-copy` | `LAYER ADD-ALPHA → newlayer` | Duplicate a layer (still needs insert) |
| `gimp-layer-new-from-drawable` | `DRAWABLE DEST-IMG → layer` | Copy a drawable into (another) image |
| `gimp-layer-new-from-visible` | `SRC-IMG DEST-IMG NAME → layer` | Snapshot composited result as one layer |
| `gimp-layer-set-opacity` | `LAYER OPACITY(0-100)` | Change transparency |
| `gimp-layer-set-mode` | `LAYER MODE` | Set blend mode (LAYER-MODE-*) |
| `gimp-layer-set-offsets` | `LAYER OFFX OFFY` | Absolute position (relative to image origin) |
| `gimp-layer-translate` | `LAYER OFFX OFFY` | Relative move from current position |
| `gimp-image-set-active-layer` | `IMG LAYER` | Select which layer is active |
| `gimp-image-get-layers` | `IMG → (count #(ids…))` | List layer ids top→bottom |
| `gimp-image-get-layer-by-name` | `IMG NAME → layer` | Find a layer by name |
| `gimp-image-reorder-item` | `IMG ITEM PARENT POSITION` | Move a layer/group in the stack (item domain) |
| `gimp-layer-create-mask` | `LAYER MASK-TYPE → mask` | Build a mask channel (ADD-MASK-*) |
| `gimp-layer-add-mask` | `LAYER MASK` | Attach a created mask to the layer |
| `gimp-layer-remove-mask` | `LAYER MODE(0 apply/1 discard)` | Apply or drop the mask |
| `gimp-layer-set-apply-mask` | `LAYER TRUE/FALSE` | Toggle mask compositing |
| `gimp-layer-add-alpha` | `LAYER` | Add alpha channel (RGB→RGBA) |
| `gimp-layer-flatten` | `LAYER` | Strip alpha on one layer |
| `gimp-layer-group-new` | `IMG → group` | Create empty layer group (then insert) |
| `gimp-image-merge-visible-layers` | `IMG MERGE-TYPE → layer` | Flatten visible layers, keep invisibles |
| `gimp-image-merge-down` | `IMG LAYER MERGE-TYPE → layer` | Merge one layer with the one below |
| `gimp-image-merge-layer-group` | `IMG GROUP → layer` | Collapse a group to one layer |
| `gimp-image-flatten` | `IMG → layer` | Flatten all, discard invisibles & alpha |
| `gimp-item-set-visible` | `ITEM TRUE/FALSE` | Show/hide (non-deprecated; layers are items) |
| `gimp-item-get-name` / `gimp-item-set-name` | `ITEM [NAME]` | Read/rename a layer |

Note: most `gimp-layer-get/set-{name,visible,linked,tattoo}` and `gimp-image-{raise,lower}-layer*` are **deprecated** — use the `gimp-item-*` equivalents (`gimp-item-set-visible`, `gimp-item-set-name`, `gimp-image-raise-item`, `gimp-image-reorder-item`).

## Recipes

### Add a blank transparent layer at top
```scheme
(let* ((img (car (gimp-image-list)))
       (w   (car (gimp-image-width img)))
       (h   (car (gimp-image-height img)))
       (lyr (car (gimp-layer-new img w h RGBA-IMAGE "overlay" 100 LAYER-MODE-NORMAL))))
  (gimp-image-insert-layer img lyr 0 0)   ; parent 0 = top level, position 0 = top
  (gimp-image-set-active-layer img lyr)
  (gimp-displays-flush)
  lyr)
```

### Paste an image file as a new layer at (x,y)
```scheme
(let* ((img (car (gimp-image-list)))
       ;; load file, take its active drawable, copy into img
       (src (car (gimp-file-load RUN-NONINTERACTIVE "/tmp/logo.png" "logo.png")))
       (draw (car (gimp-image-get-active-drawable src)))
       (lyr  (car (gimp-layer-new-from-drawable draw img))))
  (gimp-image-insert-layer img lyr 0 0)
  (gimp-layer-set-offsets lyr 120 80)     ; absolute position in image
  (gimp-image-delete src)                 ; free the loader image
  (gimp-displays-flush))
```

### Set opacity + blend mode
```scheme
(let* ((img (car (gimp-image-list)))
       (lyr (car (gimp-image-get-active-layer img))))
  (gimp-layer-set-opacity lyr 65)             ; 0-100 float
  (gimp-layer-set-mode lyr LAYER-MODE-MULTIPLY)
  (gimp-displays-flush))
```

### Reposition a layer (absolute vs relative)
```scheme
(let* ((img (car (gimp-image-list)))
       (lyr (car (gimp-image-get-active-layer img))))
  (gimp-layer-set-offsets lyr 0 0)   ; snap to top-left
  (gimp-layer-translate   lyr 40 -10) ; then nudge +40x, -10y
  (gimp-displays-flush))
```

### Reorder a layer in the stack
```scheme
(let* ((img (car (gimp-image-list)))
       (lyr (car (gimp-image-get-active-layer img))))
  (gimp-image-reorder-item img lyr 0 0)        ; parent 0, position 0 → raise to top
  ;; or send to bottom: (gimp-image-reorder-item img lyr 0 (- (car (gimp-image-get-layers img)) 1))
  (gimp-displays-flush))
```

### Add and apply a white layer mask, then paint on it
```scheme
(let* ((img  (car (gimp-image-list)))
       (lyr  (car (gimp-image-get-active-layer img)))
       (mask (car (gimp-layer-create-mask lyr ADD-MASK-WHITE)))) ; white = fully visible
  (gimp-layer-add-mask lyr mask)
  ;; paint black on the mask to hide regions (mask IS a drawable):
  (gimp-image-set-active-layer img lyr)
  (gimp-context-set-foreground '(0 0 0))
  (gimp-image-select-rectangle img CHANNEL-OP-REPLACE 0 0 100 100)
  (gimp-edit-fill mask FILL-FOREGROUND)
  (gimp-selection-none img)
  (gimp-layer-remove-mask lyr MASK-APPLY)       ; 0 = bake mask into alpha (or MASK-DISCARD to drop)
  (gimp-displays-flush))
```

### Mask from the layer's own alpha
```scheme
(let* ((img  (car (gimp-image-list)))
       (lyr  (car (gimp-image-get-active-layer img)))
       (mask (car (gimp-layer-create-mask lyr ADD-MASK-ALPHA))))
  (gimp-layer-add-mask lyr mask)
  (gimp-displays-flush))
```

### Create a layer group and nest a layer inside it
```scheme
(let* ((img (car (gimp-image-list)))
       (grp (car (gimp-layer-group-new img))))
  (gimp-image-insert-layer img grp 0 0)         ; insert the group itself first
  (gimp-item-set-name grp "fx-group")
  (let ((lyr (car (gimp-layer-new img 200 200 RGBA-IMAGE "inner" 100 LAYER-MODE-NORMAL))))
    (gimp-image-insert-layer img lyr grp 0))     ; parent = group id → nested
  (gimp-displays-flush))
```

### Duplicate a layer
```scheme
(let* ((img (car (gimp-image-list)))
       (lyr (car (gimp-image-get-active-layer img)))
       (dup (car (gimp-layer-copy lyr FALSE))))  ; FALSE = don't force-add alpha
  (gimp-image-insert-layer img dup 0 0)          ; copy is NOT auto-inserted
  (gimp-item-set-name dup "copy")
  (gimp-displays-flush))
```

### Merge visible layers (keep hidden ones)
```scheme
(let ((img (car (gimp-image-list))))
  (gimp-image-merge-visible-layers img CLIP-TO-IMAGE)  ; 1 = clip to canvas
  (gimp-displays-flush))
```

### Merge a layer with the one below it
```scheme
(let* ((img (car (gimp-image-list)))
       (lyr (car (gimp-image-get-active-layer img))))
  (gimp-image-merge-down img lyr EXPAND-AS-NECESSARY)  ; 0 = grow to fit both
  (gimp-displays-flush))
```

### Flatten the whole image (drops alpha + invisible layers)
```scheme
(let ((img (car (gimp-image-list))))
  (gimp-image-flatten img)                ; returns the single resulting layer
  (gimp-displays-flush))
```

### Hide / show a layer
```scheme
(let* ((img (car (gimp-image-list)))
       (lyr (car (gimp-image-get-layer-by-name img "overlay"))))
  (gimp-item-set-visible lyr FALSE)       ; non-deprecated item API
  (gimp-displays-flush))
```

## Gotchas & enums
- **Insert is mandatory.** `gimp-layer-new` / `-copy` / `-new-from-drawable` return an orphan layer. Nothing appears until `gimp-image-insert-layer`.
- **Parent + position are required** on `gimp-image-insert-layer IMG LAYER PARENT POSITION`. `PARENT = 0` for top-level; a group id to nest. `POSITION = 0` is the top.
- **Position 0 = top of stack.** Bottom = `(- count 1)`.
- **Masks are 2-step:** `gimp-layer-create-mask` → `gimp-layer-add-mask`. Mask dimensions must equal layer dimensions; a fresh full-canvas layer is safest. The mask is a CHANNEL and a drawable — paint/fill on it directly.
- **`gimp-layer-set-offsets` is absolute** (relative to image origin); **`gimp-layer-translate` is relative** to current pos.
- **Need alpha to erase to transparency:** call `gimp-layer-add-alpha` (RGB→RGBA) first; otherwise erase paints background color.
- **Deprecated visibility/name/reorder:** use `gimp-item-set-visible`, `gimp-item-set-name`, `gimp-image-raise-item` / `gimp-image-lower-item` / `gimp-image-reorder-item` instead of the `gimp-layer-*` / `gimp-image-*-layer` versions.
- **Free loader images:** after `gimp-file-load` + `gimp-layer-new-from-drawable`, call `gimp-image-delete` on the loader image to avoid leaks.

### Layer types (`gimp-layer-new` TYPE)
`RGB-IMAGE(0) RGBA-IMAGE(1) GRAY-IMAGE(2) GRAYA-IMAGE(3) INDEXED-IMAGE(4) INDEXEDA-IMAGE(5)`. Must match image base type. Use the `*A*` variants for transparency.

### Blend modes (`gimp-layer-set-mode` / `gimp-layer-new` MODE)
Prefer the modern (non-`-LEGACY`) constants:
`LAYER-MODE-NORMAL(28) LAYER-MODE-DISSOLVE(1) LAYER-MODE-BEHIND(29) LAYER-MODE-MULTIPLY(30) LAYER-MODE-SCREEN(31) LAYER-MODE-OVERLAY(23) LAYER-MODE-DIFFERENCE(32) LAYER-MODE-ADDITION(33) LAYER-MODE-SUBTRACT(34) LAYER-MODE-DARKEN-ONLY(35) LAYER-MODE-LIGHTEN-ONLY(36) LAYER-MODE-HSV-HUE(37) LAYER-MODE-HSV-SATURATION(38) LAYER-MODE-HSL-COLOR(39) LAYER-MODE-HSV-VALUE(40) LAYER-MODE-DIVIDE(41) LAYER-MODE-DODGE(42) LAYER-MODE-BURN(43) LAYER-MODE-HARDLIGHT(44) LAYER-MODE-SOFTLIGHT(45) LAYER-MODE-GRAIN-EXTRACT(46) LAYER-MODE-GRAIN-MERGE(47) LAYER-MODE-VIVID-LIGHT(48) LAYER-MODE-PIN-LIGHT(49) LAYER-MODE-LINEAR-LIGHT(50) LAYER-MODE-HARD-MIX(51) LAYER-MODE-EXCLUSION(52) LAYER-MODE-LINEAR-BURN(53) LAYER-MODE-LUMA-DARKEN-ONLY(54) LAYER-MODE-LUMA-LIGHTEN-ONLY(55) LAYER-MODE-LUMINANCE(56) LAYER-MODE-EXCLUSION(52)`. Legacy variants `*-LEGACY` (0-22) reproduce GIMP 2.8 math; only use to match old files. `LAYER-MODE-PASS-THROUGH(61)` is valid **only on layer groups**.

### Mask types (`gimp-layer-create-mask` MASK-TYPE)
`ADD-MASK-WHITE(0)` full visible · `ADD-MASK-BLACK(1)` full transparent · `ADD-MASK-ALPHA(2)` from alpha (copy) · `ADD-MASK-ALPHA-TRANSFER(3)` move alpha into mask · `ADD-MASK-SELECTION(4)` current selection · `ADD-MASK-COPY(5)` grayscale of layer · `ADD-MASK-CHANNEL(6)` from active channel.

### Mask removal (`gimp-layer-remove-mask` MODE)
`MASK-APPLY(0)` bake mask into the layer's alpha · `MASK-DISCARD(1)` throw the mask away.

### Merge types (`merge-visible-layers` / `merge-down` MERGE-TYPE)
`EXPAND-AS-NECESSARY(0)` result grows to cover all merged layers · `CLIP-TO-IMAGE(1)` clip to canvas · `CLIP-TO-BOTTOM-LAYER(2)` clip to bottommost layer size. `gimp-image-flatten` always behaves like CLIP-TO-IMAGE.

## See also
- **MCP wrappers** (`./server.py`): `new_layer`, `add_layer_from_file`, `set_layer` (opacity/mode/offsets/visible), `list_layers`, `merge_visible`, `delete_layer` — thin wrappers over the procedures above; use them when an MCP tool call is cheaper than raw Scheme.
- **Related domains:** `01-images-io.md` (load/save/`gimp-image-list`/`gimp-image-delete`), `03-text-fonts.md` (`gimp-text-fontname` returns a layer you then position/mode), `04-paint-draw.md` (fill/paint on a layer or its mask, `gimp-edit-fill`, selection ops).
