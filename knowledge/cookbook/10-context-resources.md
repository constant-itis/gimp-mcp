# 10 — Context & Resources (Script-Fu / PDB)

## Mental model
- **Context is GLOBAL mutable state** living in the GIMP core: foreground/background color, active brush, brush size, opacity, paint mode, gradient, pattern, font, palette, dynamics, interpolation, antialias, feather, sampling. Paint/fill/select/transform ops **read** this state — many of them take NO color/brush/opacity args, so *setting context is how you parameterize them*.
- **Set context BEFORE the op.** `(gimp-context-set-foreground '(255 0 0))` then `(gimp-edit-fill drawable FILL-FOREGROUND)`.
- **It is STICKY and process-global.** It persists across socket calls in the same server process (see Gotchas — this is the #1 agent trap). Whatever the last caller set is still set.
- **Scope changes with `gimp-context-push` / `gimp-context-pop`.** Push saves the whole context, you mutate freely, pop restores. ALWAYS wrap reusable recipes in push/pop so they don't leak state to the next call.
- **Resources (brushes, gradients, patterns, palettes, fonts, dynamics) are referenced by exact NAME string** — e.g. `"2. Hardness 050"`, `"FG to BG (RGB)"`, `"Pine"`. List them, then pass the literal name to the matching `set`. Colors are `'(R G B)` 0–255; booleans `TRUE`/`FALSE`; opacity/threshold are **floats**.

## Core procedures

### (a) Context setters that matter
| Procedure | Signature → | Notes |
|---|---|---|
| `gimp-context-set-foreground` | `'(r g b)` | 0–255 ints. FG = primary fill/paint/text color. |
| `gimp-context-set-background` | `'(r g b)` | Used by FILL-BACKGROUND, FG→BG gradients. |
| `gimp-context-set-opacity` | `opacity` | **Float 0.0–100.0** (percent), not 0–1. |
| `gimp-context-set-paint-mode` | `paint-mode` | A `LAYER-MODE-*` enum (see below). |
| `gimp-context-set-brush` | `"name"` | Active brush by exact name string. |
| `gimp-context-set-brush-size` | `size` | Float px. Resizes active brush for paint ops. |
| `gimp-context-set-brush-hardness` | `hardness` | Float 0.0–1.0. |
| `gimp-context-set-gradient` | `"name"` | Active gradient by name (for blend/gradient ops). |
| `gimp-context-set-pattern` | `"name"` | Active pattern (for FILL-PATTERN / clone). |
| `gimp-context-set-palette` | `"name"` | Active palette. |
| `gimp-context-set-dynamics` | `"name"` | Active paint dynamics (`"Dynamics Off"` to disable). |
| `gimp-context-set-font` | `"name"` | Active font (Pango family, e.g. `"Sans Bold"`). |
| `gimp-context-set-interpolation` | `interpolation` | `INTERPOLATION-*` enum — quality of scale/rotate/transform. |
| `gimp-context-set-antialias` | `TRUE/FALSE` | AA for fills/selections/strokes. |
| `gimp-context-set-feather` | `TRUE/FALSE` | Toggle selection feathering. |
| `gimp-context-set-feather-radius` | `rx ry` | Two floats; feather amount when feather is on. |
| `gimp-context-set-sample-threshold` | `threshold` | Float 0.0–1.0 — fuzzy/by-color select & bucket tolerance. |
| `gimp-context-set-sample-criterion` | `criterion` | `SELECT-CRITERION-*` (which channel to compare). |
| `gimp-context-set-sample-merged` | `TRUE/FALSE` | Sample from composite vs active drawable. |
| `gimp-context-push` / `gimp-context-pop` | `()` | Save / restore the entire context. Pair them. |
| `gimp-context-set-defaults` | `()` | Reset ALL context to GIMP defaults in one call. |
| `gimp-context-get-foreground` | `() → ((r g b))` | Read back; `(car (gimp-context-get-foreground))` → `(r g b)`. Every setter has a `get-` twin. |

### (b) Resource listers — all take a regex `filter`, return `(count (list "name" …))`
| Procedure | Returns |
|---|---|
| `gimp-brushes-get-list` | `(count (names…))` brushes |
| `gimp-gradients-get-list` | `(count (names…))` gradients |
| `gimp-palettes-get-list` | `(count (names…))` palettes |
| `gimp-patterns-get-list` | `(count (names…))` patterns |
| `gimp-fonts-get-list` | `(count (names…))` fonts *(lives in text-fonts domain; same shape)* |
| `gimp-dynamics-get-list` | `(count (names…))` paint dynamics |

> **Access pattern:** `(cadr (gimp-brushes-get-list ".*"))` is a Scheme **list** of strings — use `(car (cadr …))`, `(list-ref names i)`, or `(map … names)`. (It is NOT a vector here; don't `vector-ref` it.) `(car …)` of the whole result is the integer count. Pass `".*"` for everything, or a regex like `"Hardness"` / `"^FG"` to filter.

There are ~220 procedures in this domain (ink, line-dash, transform-resize, brush-angle/aspect, gradient-blend-color-space, unit-* introspection, popup/refresh, per-resource get-data, etc.). The ~30 above cover normal agent work. For anything else: `pdb_query "gimp-context-set-line"` or `(gimp-procedural-db-query ...)`.

## Recipes
All assume a live server. `(car …)` pulls the first return value.

### Set foreground color, then fill
```scheme
(gimp-context-set-foreground '(255 80 0))      ; orange
(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 0 0 200 200)
(gimp-edit-fill drawable FILL-FOREGROUND)
(gimp-selection-none img)
;; VERIFIED: fg accepts '(r g b) 0-255; get-foreground returns ((r g b))
```

### Choose a brush by name and size (paint-mode + opacity too)
```scheme
(gimp-context-set-brush "2. Hardness 050")     ; exact name from get-list
(gimp-context-set-brush-size 40)               ; float px
(gimp-context-set-brush-hardness 0.7)
(gimp-context-set-opacity 75.0)                ; PERCENT 0-100, not 0-1
(gimp-context-set-paint-mode LAYER-MODE-NORMAL)
(gimp-pencil drawable 4 (list->vector '(10 10 200 200)))  ; reads all of the above
```

### Scope changes safely with push/pop (no state leak)
```scheme
(gimp-context-push)                            ; snapshot everything
(gimp-context-set-foreground '(0 0 0))
(gimp-context-set-opacity 100.0)
(gimp-context-set-brush "1. Pixel")
(gimp-edit-fill drawable FILL-FOREGROUND)
(gimp-context-pop)                             ; restore — caller's context untouched
;; VERIFIED: push/set/pop round-trips cleanly
```

### Pick a gradient by name (then blend)
```scheme
(gimp-context-set-gradient "FG to BG (RGB)")
(gimp-context-set-foreground '(20 20 90))
(gimp-context-set-background '(220 200 255))
(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 0 0 512 128)
(gimp-context-set-gradient-reverse FALSE)
(gimp-drawable-edit-gradient-fill drawable GRADIENT-LINEAR 0 FALSE 1 0 TRUE 0 0 512 0)
(gimp-selection-none img)
```

### List available brushes / gradients, filtered
```scheme
(gimp-brushes-get-list ".*")                   ; ALL brushes  → (58 ("Clipboard Image" …))
(cadr (gimp-brushes-get-list "Hardness"))      ; just the names list, filtered
(let ((g (gimp-gradients-get-list "^FG")))     ; gradients starting "FG"
  (list (car g) (cadr g)))
;; VERIFIED: filter is a regex; (car result)=count, (cadr result)=list of name strings
```

### Set interpolation for quality transforms
```scheme
(gimp-context-set-interpolation INTERPOLATION-LANCZOS)   ; sharpest for downscale
(gimp-item-transform-scale drawable 0 0 1024 768)        ; reads interpolation from context
;; INTERPOLATION-NONE(0) fast/blocky · LINEAR(1) · CUBIC(2) · NOHALO(3) · LANCZOS/LOHALO(3+)
```

### Tune selection sampling (fuzzy-select / by-color tolerance)
```scheme
(gimp-context-set-sample-threshold 0.15)       ; 0.0–1.0; lower = tighter match
(gimp-context-set-sample-criterion SELECT-CRITERION-COMPOSITE)
(gimp-context-set-antialias TRUE)
(gimp-context-set-feather TRUE)
(gimp-context-set-feather-radius 3 3)
(gimp-image-select-color img CHANNEL-OP-REPLACE drawable '(255 255 255))  ; reads threshold+criterion+feather
;; VERIFIED: gimp-context-set-sample-threshold accepts float 0.15
```

### Reset context to defaults
```scheme
(gimp-context-set-defaults)                    ; FG black, BG white, opacity 100, mode NORMAL, default brush…
;; Cheaper than tracking every change; do this at the start of a job for a known baseline.
```

### Set the active font (for subsequent text ops)
```scheme
(gimp-context-set-font "Sans Bold")            ; gimp-text-fontname can also take font inline; this is the default
(car (gimp-fonts-get-list ".*"))               ; how many fonts are loaded (0 ⇒ server started with -f, fonts off)
```

## Gotchas & enums
- **Context is sticky & process-global — THE agent trap.** The server is single-threaded and shared; context set by a previous socket call (even a previous task) is STILL ACTIVE. Never assume FG is black or opacity is 100. Either `(gimp-context-set-defaults)` first, OR wrap every reusable recipe in `gimp-context-push` … `gimp-context-pop`. *(Observed: get-foreground returned a color a prior call left behind.)*
- **ALWAYS pair push/pop.** A push with no pop grows the stack and leaks; a pop with no prior push errors. One in, one out.
- **Opacity is 0–100 (percent), threshold/hardness are 0.0–1.0.** Easy to swap; wrong scale silently misbehaves.
- **Resources are referenced by EXACT name string.** No fuzzy match. Get the literal from `*-get-list` and pass it verbatim; a typo throws "Invalid … name".
- **`*-get-list` returns `(count list-of-strings)` — `cadr` is a LIST, not a vector** in this server. Use `car`/`cadr`/`list-ref`/`map`, not `vector-ref`.
- **`gimp-context-set-paint-mode` takes a `LAYER-MODE-*` enum**, same family layers use: `LAYER-MODE-NORMAL`(28), `-MULTIPLY`(30), `-SCREEN`(31), `-OVERLAY`(23), `-DODGE`, `-BURN`, `-ADDITION`, `-DARKEN-ONLY`, `-LIGHTEN-ONLY`, `-HSL-COLOR`, `-DIFFERENCE`, `-GRAIN-MERGE`. (Legacy variants exist with `-LEGACY` suffix.)
- **Enums:** `INTERPOLATION-{NONE,LINEAR,CUBIC,NOHALO,LOHALO}`; `SELECT-CRITERION-{COMPOSITE,R,G,B,H,S,V,A,LCH-L,LCH-C,LCH-H}`; fill `FILL-{FOREGROUND,BACKGROUND,WHITE,TRANSPARENT,PATTERN}`.
- **`-f` / `--no-fonts` kills fonts:** `gimp-fonts-get-list` count near 0 and text renders nothing. Launch without `-f`.

## See also
- `server.py` wrappers: `set-foreground` is called inside fill/text wrappers (lines ~352, 538, 551); `set-background '(255 255 255)` baseline (~198); `(gimp-fonts-get-list ".*")` (~363).
- `04-color-tone.md` — FG/BG color and curves/levels that consume context color.
- `01-paint-draw.md` — brush/pencil/airbrush/blend ops that READ brush, size, opacity, paint-mode, gradient.
- `08-transforms-canvas.md` — scale/rotate/flip that READ `gimp-context-set-interpolation` & `transform-resize`.
- `03-text-fonts.md` — fonts (`gimp-context-set-font`, `gimp-fonts-get-list`) and text-layer color overrides.
- `pdb_query "gimp-context-"` — the other ~190 setters (ink, line-dash, brush-angle/aspect/force, gradient-blend-color-space, transform-direction/recursion, unit-* introspection).
