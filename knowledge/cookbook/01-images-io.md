# 01 — Images & File I/O (Script-Fu)

## Mental model
- Everything is a PDB call returning a list; take `(car ...)` for the value. Handles (image, layer, drawable, channel) are plain **integers**.
- An **image** is a container; you never paint on it directly. You paint on a **drawable** — almost always the active layer: `(car (gimp-image-get-active-drawable img))`.
- Load/save plug-ins are `file-*` / `gimp-file-*` procs whose first arg is a run-mode — always pass `RUN-NONINTERACTIVE`.
- `gimp-file-save` picks the format by **filename extension**. The per-format `file-*-save` procs give you quality/compression knobs but require all their args.
- Loading and saving do not touch the GUI display; you don't need `gimp-displays-flush` in headless batch. Always `gimp-image-delete` scratch images to free memory.

## Core procedures
| Procedure | Signature | Use when |
|---|---|---|
| `gimp-file-load` | `run-mode filename raw-filename` → image | Open any format by extension (png/jpg/tif/webp/xcf/...). |
| `gimp-file-save` | `run-mode image drawable filename raw-filename` | Save by extension, default options. Simplest export. |
| `file-png-save` | `run-mode image drawable filename raw raw interlace compression bkgd gama offs phys time` | PNG with explicit compression (0–9). |
| `file-jpeg-save` | `run-mode image drawable filename raw quality smoothing optimize progressive comment subsmp baseline restart dct` | JPEG with quality 0.0–1.0. |
| `file-webp-save` | `run-mode image drawable filename raw preset lossless quality alpha-quality animation anim-loop minimize-size kf-distance exif iptc xmp delay force-delay` | WebP lossy/lossless. |
| `file-tiff-save` | `run-mode image drawable filename raw compression` | TIFF with compression enum. |
| `file-heif-save` | `run-mode image drawable uri raw-uri quality lossless` | HEIF/AVIF (quality is **INT** 0–100 here). |
| `file-gif-save` | `run-mode image drawable uri raw interlace loop default-delay default-dispose` | GIF (image must be INDEXED first). |
| `gimp-image-new` | `width height type` → image | Make a blank image; `type` = RGB / GRAY / INDEXED. |
| `gimp-image-new-with-precision` | `width height type precision` → image | New image at non-8-bit precision. |
| `gimp-image-duplicate` | `image` → image | Deep copy (all layers) before destructive ops. |
| `gimp-image-flatten` | `image` → layer | Merge all layers, drop alpha → single layer. Do before JPEG. |
| `gimp-image-merge-visible-layers` | `image merge-type` → layer | Merge visible only, keep alpha. |
| `gimp-image-scale` | `image new-width new-height` | **Resample content** to a new pixel size. |
| `gimp-image-resize` | `image new-width new-height offx offy` | **Change canvas** only; layers/content unchanged, offset placement. |
| `gimp-image-get-active-drawable` | `image` → drawable | Get the thing you paint on / pass to savers. |
| `gimp-image-get-active-layer` | `image` → layer | Active layer handle specifically. |
| `gimp-image-set-filename` | `image filename` | Set the associated path (also sets XCF default). |
| `gimp-image-get-filename` | `image` → string | Read associated path. |
| `gimp-image-width` / `gimp-image-height` | `image` → int | Query dimensions. |
| `gimp-image-base-type` | `image` → int | 0=RGB, 1=GRAY, 2=INDEXED. |
| `gimp-image-convert-rgb` / `-grayscale` | `image` | Change color mode. |
| `gimp-image-convert-indexed` | `image dither-type palette-type num-cols alpha-dither remove-unused palette` | Reduce to palette (needed for GIF). |
| `gimp-image-convert-precision` | `image precision` | Switch to 16/32-bit int or float. |
| `gimp-image-get-precision` | `image` → int | Query precision enum. |
| `gimp-image-delete` | `image` | Free a scratch/loaded image. Always do this. |

> ~356 procs exist in this domain (every `file-*-save`/load for ps, pdf, dds, exr, psd, ico, bmp, tga, dicom, raw, etc.). Discover any with `pdb_query("file-")` / `pdb_help("file-psd-save")`.

## Recipes

### Load JPEG, flatten, save PNG
```scheme
(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.jpg" "in.jpg"))))
  (gimp-image-flatten img)
  (let ((d (car (gimp-image-get-active-drawable img))))
    (file-png-save RUN-NONINTERACTIVE img d "/path/out.png" "out.png"
                   0 9 1 1 1 1 1))   ; interlace=0, compression=9
  (gimp-image-delete img))
```

### Save by extension (let GIMP choose the handler)
```scheme
(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.png" "in.png")))
       (d   (car (gimp-image-get-active-drawable img))))
  (gimp-file-save RUN-NONINTERACTIVE img d "/path/out.tiff" "out.tiff")
  (gimp-image-delete img))
```

### Export JPEG at a given quality
```scheme
(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.png" "in.png"))))
  (gimp-image-flatten img)                       ; JPEG has no alpha
  (let ((d (car (gimp-image-get-active-drawable img))))
    ;; quality 0.0-1.0, smoothing, optimize, progressive, comment,
    ;; subsmp(0=4:2:0..2=4:4:4 best), baseline, restart, dct(0=int)
    (file-jpeg-save RUN-NONINTERACTIVE img d "/path/out.jpg" "out.jpg"
                    0.85 0.0 1 1 "" 2 1 0 0))
  (gimp-image-delete img))
```

### Export WebP (lossy and lossless)
```scheme
(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.png" "in.png")))
       (d   (car (gimp-image-get-active-drawable img))))
  ;; preset=0, lossless=0, quality=80, alpha-quality=100, then anim/meta flags 0
  (file-webp-save RUN-NONINTERACTIVE img d "/path/lossy.webp" "lossy.webp"
                  0 0 80.0 100.0 0 0 0 0 0 0 0 0 0)
  ;; lossless: set lossless=1 (quality ignored)
  (file-webp-save RUN-NONINTERACTIVE img d "/path/lossless.webp" "lossless.webp"
                  0 1 100.0 100.0 0 0 0 0 0 0 0 0 0)
  (gimp-image-delete img))
```

### New transparent RGBA image
```scheme
(let* ((img (car (gimp-image-new 1200 630 RGB)))
       (lay (car (gimp-layer-new img 1200 630 RGBA-IMAGE "bg" 100 LAYER-MODE-NORMAL))))
  (gimp-image-insert-layer img lay 0 -1)         ; parent=0(none) pos=-1(top)
  (gimp-image-set-active-layer img lay)
  (gimp-drawable-fill lay FILL-TRANSPARENT)
  ;; ... draw here ...
  (let ((d (car (gimp-image-get-active-drawable img))))
    (file-png-save RUN-NONINTERACTIVE img d "/path/out.png" "out.png" 0 9 1 1 1 1 1))
  (gimp-image-delete img))
```

### Scale (resample) vs resize-canvas
```scheme
(let ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.png" "in.png"))))
  (gimp-image-scale img 800 600)                 ; resamples pixels to 800x600
  ;; vs. enlarge canvas to 1000x800, placing old content at offset 100,100,
  ;; transparent margin around it (content NOT resampled):
  (gimp-image-resize img 1000 800 100 100)
  (gimp-layer-resize-to-image-size (car (gimp-image-get-active-layer img)))
  (gimp-image-flatten img)
  (gimp-image-delete img))
```

### Thumbnail with aspect ratio preserved
```scheme
(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.jpg" "in.jpg")))
       (w (car (gimp-image-width img)))
       (h (car (gimp-image-height img)))
       (max 256)
       (s (min (/ max w) (/ max h))))
  (gimp-image-scale img (round (* w s)) (round (* h s)))
  (gimp-image-flatten img)
  (let ((d (car (gimp-image-get-active-drawable img))))
    (file-png-save RUN-NONINTERACTIVE img d "/path/thumb.png" "thumb.png" 0 9 1 1 1 1 1))
  (gimp-image-delete img))
```

### Duplicate before destructive edits
```scheme
(let* ((src  (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.png" "in.png")))
       (work (car (gimp-image-duplicate src))))           ; src stays pristine
  (gimp-image-scale work 400 400)
  (gimp-image-flatten work)
  (let ((d (car (gimp-image-get-active-drawable work))))
    (gimp-file-save RUN-NONINTERACTIVE work d "/path/small.png" "small.png"))
  (gimp-image-delete work)
  (gimp-image-delete src))
```

### Convert to indexed, save GIF
```scheme
(let ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.png" "in.png"))))
  (gimp-image-flatten img)
  ;; dither NONE, palette GENERATE, 256 colors, no alpha-dither, remove-unused, no custom palette
  (gimp-image-convert-indexed img CONVERT-DITHER-NONE CONVERT-PALETTE-GENERATE 256 FALSE TRUE "")
  (let ((d (car (gimp-image-get-active-drawable img))))
    (file-gif-save RUN-NONINTERACTIVE img d "/path/out.gif" "out.gif" 0 0 0 0))
  (gimp-image-delete img))
```

### Convert to grayscale and export
```scheme
(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "/path/in.png" "in.png"))))
  (gimp-image-convert-grayscale img)
  (gimp-image-flatten img)
  (let ((d (car (gimp-image-get-active-drawable img))))
    (gimp-file-save RUN-NONINTERACTIVE img d "/path/gray.png" "gray.png"))
  (gimp-image-delete img))
```

### 16-bit precision round trip
```scheme
(let ((img (car (gimp-image-new-with-precision
                  512 512 RGB GIMP-PRECISION-U16-NON-LINEAR))))
  ;; or convert an existing 8-bit image:
  ;; (gimp-image-convert-precision img GIMP-PRECISION-U16-NON-LINEAR)
  (gimp-image-get-precision img)                 ; -> (150) enum value
  (gimp-image-delete img))
```

### Batch resize every PNG in a directory
```scheme
(let loop ((files (cadr (gimp-version))))         ; placeholder; build your own list
  #t)
;; Practical pattern — iterate an explicit list:
(for-each
  (lambda (path)
    (let ((img (car (gimp-file-load RUN-NONINTERACTIVE path path))))
      (gimp-image-scale img 1024 768)
      (gimp-image-flatten img)
      (let ((d (car (gimp-image-get-active-drawable img))))
        (gimp-file-save RUN-NONINTERACTIVE img d
          (string-append path ".1024.png") "out.png"))
      (gimp-image-delete img)))
  (list "/path/a.png" "/path/b.png" "/path/c.png"))
```

## Gotchas & enums
- **`gimp-file-save` dispatches by extension.** `out.jpg` → JPEG, `out.webp` → WebP. Wrong/unknown extension throws. Per-format `file-*-save` ignore the extension but demand every arg.
- **JPEG/BMP/GIF have no alpha.** `gimp-image-flatten` first or transparency goes black/white. PNG/WebP/TIFF keep alpha — flatten only if you intend to.
- **HEIF quality is INT 0–100**, but **JPEG/WebP quality is FLOAT** (`0.85`, `80.0`). Mixing the type errors out.
- **`file-*-save` return `(#t)`**, not a handle. Don't `(car ...)` it expecting an id.
- **`raw-filename` arg**: just pass the basename string; it's cosmetic for noninteractive.
- **Image types (`gimp-image-new`):** `RGB`(0) `GRAY`(1) `INDEXED`(2). **Layer types (`gimp-layer-new`):** `RGB-IMAGE` `RGBA-IMAGE` `GRAY-IMAGE` `GRAYA-IMAGE` `INDEXED-IMAGE` `INDEXEDA-IMAGE`. Layer type must match image base type.
- **scale vs resize vs resize-to-layers:** `gimp-image-scale` resamples content (changes how things look); `gimp-image-resize` only moves the canvas border (offx/offy place existing content, may clip or add transparent margin) — follow it with `gimp-layer-resize-to-image-size` so a flatten captures the new canvas; `gimp-image-resize-to-layers` shrink-wraps canvas to layer bounds.
- **Fill modes (`gimp-drawable-fill`):** `FILL-FOREGROUND` `FILL-BACKGROUND` `FILL-WHITE` `FILL-TRANSPARENT` `FILL-PATTERN`.
- **Precision enums:** `GIMP-PRECISION-U8-NON-LINEAR` (default 8-bit), `-U16-NON-LINEAR`, `-U32-LINEAR`, `-FLOAT-LINEAR`, etc. `gimp-image-get-precision` returns the int enum value, not a name.
- **Indexed conversion enums:** dither `CONVERT-DITHER-NONE|-FS|-FS-LOWBLEED|-FIXED`; palette `CONVERT-PALETTE-GENERATE|-WEB|-MONO|-CUSTOM`.
- **Headless:** no display, so `gimp-displays-flush` is a no-op you can skip. Never launch the server with `-f` (fonts break, unrelated to I/O but it's the shared server).
- **Always `gimp-image-delete`** loaded/scratch images — the shared server leaks them otherwise.

## See also
- **server.py MCP tools:** `load_image`, `export_image`, `new_image`, `scale_image`, `resize_canvas`, `save_xcf`, `export_layers`, `close_image`, `list_images`, `render_preview` (renders a PNG so the agent can *see* the result — Read the file), `pdb_query` / `pdb_help` (discover the other ~330 file procs).
- **Cookbook domains:** `02-layers-masks` (layer create/insert/merge, `gimp-layer-new`, masks), `03-transforms-canvas` (`gimp-image-scale`/`-resize`/crop/rotate/flip), `04-paint-draw` (fills, selections, edit-fill).
