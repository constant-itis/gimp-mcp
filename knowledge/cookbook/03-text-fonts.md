# 03 — Text & Fonts (Script-Fu / PDB)

## Mental model
- **Text is a layer.** `gimp-text-fontname` (or `gimp-text-layer-new`) returns a *layer id* (integer). It is NOT auto-added to nothing — `gimp-text-fontname` adds it to the image directly; `gimp-text-layer-new` does NOT (you must `gimp-image-insert-layer`).
- **Color** comes from the **foreground context** at draw time (`gimp-context-set-foreground '(r g b)`), OR is overridden afterward with `gimp-text-layer-set-color`. The setter is the reliable path — context color can surprise you.
- **`gimp-text-fontname` = one-shot create** (font/size/AA baked in at call). **`gimp-text-layer-set-*` = mutate an existing text layer** (font, size, color, justify, spacing…). Keep the layer editable; don't flatten until done.
- **Size units:** pass `UNIT-PIXEL` (enum value 0) for pixels or `UNIT-POINT` (1). `size-type` is *documented as ignored* by the PDB, but always pass `UNIT-PIXEL` and treat `size` as pixels — predictable across resolutions.
- Font name is a **Pango family+style string**: `"Sans Bold"`, `"Serif Italic"`, `"Monospace"`. Bare `"Sans"` = regular.

## ⚠️ THE #1 TRAP: `-f` / `--no-fonts`
If the headless GIMP server was launched with `-f` (`--no-fonts`), **`gimp-text-fontname` silently returns layer id `-1` and renders nothing.** No error, no exception. You get a -1 back and an empty canvas.
- **Fix:** launch WITHOUT `-f`. See `./start-gimp-server.sh` (it deliberately omits `-f`).
- Fonts take **~seconds to load** on startup — first text call after boot may lag; that's normal, not a hang.
- Sanity check: `(car (gimp-text-fontname img -1 0 0 "x" 0 TRUE 12 UNIT-PIXEL "Sans"))` → if it returns `-1`, fonts are off. Restart the server correctly.

## Core procedures
| Procedure | Signature (args in order) | Use when |
|---|---|---|
| `gimp-text-fontname` | `image drawable x y text border antialias size size-type fontname` → `(layer)` | Create text in one call. `drawable=-1` → new layer; `border=-1` auto-sizes layer to text; `border=0` = tight box. |
| `gimp-text-layer-new` | `image text fontname size unit` → `(layer)` | Create text layer object WITHOUT inserting (then `gimp-image-insert-layer`). |
| `gimp-text-get-extents-fontname` | `text size size-type fontname` → `(width height ascent descent)` | Measure BEFORE drawing — for centering / fitting. No image needed. |
| `gimp-text-layer-set-color` | `layer color` | Set text color reliably (overrides fg context). |
| `gimp-text-layer-set-font` | `layer font` | Change font of existing text layer. |
| `gimp-text-layer-set-font-size` | `layer font-size unit` | Resize existing text. |
| `gimp-text-layer-set-text` | `layer text` | Replace the string, keep styling. |
| `gimp-text-layer-set-justification` | `layer justify` | Multi-line alignment (`TEXT-JUSTIFY-*`). |
| `gimp-text-layer-set-letter-spacing` | `layer letter-spacing` | Tracking (float, ± px). |
| `gimp-text-layer-set-line-spacing` | `layer line-spacing` | Leading between lines (float, ± px). |
| `gimp-text-layer-set-base-direction` | `layer direction` | LTR/RTL/vertical (`TEXT-DIRECTION-*`). |
| `gimp-text-layer-set-antialias` | `layer antialias` | Toggle AA (TRUE/FALSE). |
| `gimp-text-layer-resize` | `layer width height` | Resize the *box* (wrapping) without rasterizing. |
| `gimp-text-layer-get-text` / `-get-font` / `-get-font-size` / `-get-color` | `layer` | Read back current properties. |
| `gimp-fonts-get-list` | `filter (regex)` → `(count #(names…))` | List/filter installed fonts. Pass `".*"` for all. |

`gimp-text-fontname` arg order, fully expanded:
```
(gimp-text-fontname  IMAGE  DRAWABLE  X  Y  TEXT  BORDER  ANTIALIAS  SIZE  SIZE-TYPE  FONTNAME)
;  e.g.              img    -1        20 20 "Hi"  0       TRUE       48    UNIT-PIXEL "Sans Bold"
```

## Recipes
All assume `img` is a valid image id. `(car …)` pulls the first return value (the layer id).

### Add a heading (one call), then color it
```scheme
(let* ((lay (car (gimp-text-fontname img -1 20 20 "Hello GIMP" 0 TRUE 48 UNIT-PIXEL "Sans Bold"))))
  (gimp-text-layer-set-color lay '(255 80 0))   ; orange, reliable override
  lay)
;; VERIFIED: returns layer id, extents 295x57 for this string at 48px Sans Bold
```

### Set color two ways
```scheme
;; (a) via foreground context BEFORE drawing
(gimp-context-set-foreground '(0 120 255))
(gimp-text-fontname img -1 10 10 "Blue via context" 0 TRUE 32 UNIT-PIXEL "Sans")

;; (b) via setter AFTER drawing — wins, and works on existing layers
(gimp-text-layer-set-color my-text-layer '(0 120 255))
```

### Centered text (measure with get-extents, then place)
```scheme
(let* ((txt "CENTERED") (size 64) (font "Sans Bold")
       (iw  (car (gimp-image-width  img)))
       (ext (gimp-text-get-extents-fontname txt size UNIT-PIXEL font)) ; (w h asc desc)
       (tw  (car ext))
       (x   (quotient (- iw tw) 2)))
  (gimp-text-fontname img -1 x 40 txt 0 TRUE size UNIT-PIXEL font))
```

### Multi-line text with centered justification + line spacing
```scheme
(let ((lay (car (gimp-text-fontname img -1 20 20
                  "line one\nline two\nthird line" 0 TRUE 28 UNIT-PIXEL "Sans"))))
  (gimp-text-layer-set-justification lay TEXT-JUSTIFY-CENTER)
  (gimp-text-layer-set-line-spacing  lay 6.0)   ; +6px leading
  lay)
```

### Change font + size of an EXISTING text layer
```scheme
(gimp-text-layer-set-font      my-layer "Serif Italic")
(gimp-text-layer-set-font-size my-layer 72 UNIT-PIXEL)
(gimp-text-layer-set-text      my-layer "new contents, same styling")
```

### Letter spacing (tracking)
```scheme
(gimp-text-layer-set-letter-spacing my-layer 8.0)   ; widen
(gimp-text-layer-set-letter-spacing my-layer -2.0)  ; tighten
```

### List / filter fonts (PDB regex)
```scheme
(gimp-fonts-get-list ".*")          ; → (N #("Sans" "Sans Bold" "Serif" ...))
(gimp-fonts-get-list "Mono")        ; substring/regex filter, case-sensitive
(car (gimp-fonts-get-list "Bold"))  ; → count of matches
```
Returns `(count vector)`; `(cadr …)` is the name vector. Prefer the MCP `list_fonts` wrapper for a clean, sorted, case-insensitive list.

### Outline / drop-shadow by duplicate trick
No native text-stroke. Duplicate the layer, recolor the copy, offset/grow it, stack behind:
```scheme
(let* ((fg (car (gimp-text-fontname img -1 20 20 "OUTLINE" 0 TRUE 60 UNIT-PIXEL "Sans Bold")))
       (bg (car (gimp-layer-copy fg FALSE))))
  (gimp-image-insert-layer img bg 0 -1)          ; insert copy
  (gimp-image-lower-item img bg)                 ; behind the original
  (gimp-text-layer-set-color bg '(0 0 0))        ; black "outline"/shadow
  (gimp-layer-set-offsets bg 22 22)              ; nudge for shadow, or grow+blur for outline
  (gimp-image-set-active-layer img fg)
  fg)
;; For a true outline: rasterize the copy, gimp-image-select-item + grow + bucket-fill,
;; then place behind. Keep the front layer as live text.
```

### Fit text into a box (wrapping)
```scheme
(let ((lay (car (gimp-text-layer-new img "long wrapping paragraph ..." "Sans" 24 UNIT-PIXEL))))
  (gimp-image-insert-layer img lay 0 -1)
  (gimp-text-layer-resize lay 300 150))   ; box 300x150, text wraps inside
```

## Gotchas & enums
- **`-f`/`--no-fonts` → layer id `-1`, blank render, no error.** (See trap section above. The single most common "my text didn't show up.")
- **Font strings are Pango family+style:** `"Sans Bold"`, `"Serif Bold Italic"`, `"Monospace"`. Wrong/unknown name → GIMP substitutes a default silently; verify with `(gimp-text-layer-get-font lay)`.
- **`border=-1` auto-sizes the layer to the text** (dynamic/fit). `border=0` = tight box at the text bounds. `border>0` = padding in px. Use `-1` unless you need a fixed wrapping box.
- **Deprecated — do NOT use:** `gimp-text` (old foundry/family/weight/slant arg soup) and `gimp-text-get-extents`. Use `gimp-text-fontname` and `gimp-text-get-extents-fontname`.
- **`get-extents-fontname` returns `(width height ascent descent)`** — 4 ints, descent is negative (e.g. `(295 57 45 -12)`). Layer height ≈ ascent + |descent|.
- **Justify enum:** `TEXT-JUSTIFY-LEFT 0`, `TEXT-JUSTIFY-RIGHT 1`, `TEXT-JUSTIFY-CENTER 2`, `TEXT-JUSTIFY-FILL 3`. Only meaningful for multi-line / boxed text.
- **Direction enum:** `TEXT-DIRECTION-LTR 0`, `TEXT-DIRECTION-RTL 1`, `TEXT-DIRECTION-TTB-RTL 2`, `TEXT-DIRECTION-TTB-RTL-UPRIGHT 3`, `TEXT-DIRECTION-TTB-LTR 4`, `TEXT-DIRECTION-TTB-LTR-UPRIGHT 5`.
- **Hint style enum (set-hint-style):** `TEXT-HINT-STYLE-NONE 0`, `SLIGHT 1`, `MEDIUM 2`, `FULL 3`. (`gimp-text-layer-set-hinting` is deprecated → use set-hint-style.)
- **Unit:** `UNIT-PIXEL 0`, `UNIT-POINT 1`. `size-type` is "currently ignored" per PDB help — to truly emulate points: `pixels = points / 72.0 * image-vertical-resolution`.
- **Colors are `'(R G B)` 0–255.** Booleans bare `TRUE`/`FALSE`. Enums bare constants (no quotes).
- **`gimp-text-layer-new` does NOT insert** — follow with `(gimp-image-insert-layer img lay 0 -1)` or it never appears.
- Setters need a **real text layer**; calling them on a rasterized/normal layer errors. Don't `gimp-image-flatten` before editing text.

## See also
- **MCP wrappers** (`./server.py`):
  - `add_text(image_id, text, x=20, y=20, size=48, color="0,0,0", font="Sans Bold")` — sets fg then `gimp-text-fontname … border=0 antialias=TRUE … UNIT-PIXEL`, returns the layer id. Color accepts `"#rrggbb"` or `"r,g,b"`.
  - `list_fonts(keyword="", limit=40)` — sorted, deduped, case-insensitive substring filter over `gimp-fonts-get-list`.
  - `render_preview` — render a PNG and Read it to *see* the placement/legibility, then nudge.
- **Cookbook:** `01-images-layers.md` / `02-*` for `gimp-image-insert-layer`, `gimp-layer-set-offsets`, `gimp-image-lower-item` (positioning text & the outline trick); color/tone slice for foreground context. Launch correctly via `start-gimp-server.sh` (no `-f`).
