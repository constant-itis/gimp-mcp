# 08 — Filters & Effects (plug-in-* / script-fu-*)

The `filters-fx` slice is **209 procedures**. This file curates the ~30 you actually
reach for. For anything else: `pdb_query "blur"` / `pdb_query "distort"` then
`pdb_help "plug-in-NAME"` to get the **exact** typed arg list before calling.

## Mental model

- **`plug-in-*` calling convention:** `(plug-in-NAME RUN-NONINTERACTIVE image drawable ...params)`.
  First arg is **always** run-mode = `RUN-NONINTERACTIVE`. Then image, then drawable, then
  filter params **in registered order** — no keywords, position is everything.
- Most plug-ins take **both** image and drawable; a few ignore `image` (still pass it) and
  operate on `drawable` only. They mutate the drawable **in place** and return nothing useful.
- **`script-fu-*` are higher-level macros** (Scheme scripts, not C plug-ins). They build layers,
  selections, etc. **GOTCHA:** even though `pdb_help` lists `run-mode` as their first arg, you
  **call them WITHOUT run-mode** — `(script-fu-drop-shadow image drawable ...)`. Passing
  `RUN-NONINTERACTIVE` shifts every arg by one and throws cryptic errors (e.g.
  `Error: <: argument 1 must be: number`). Verified against `script-fu-drop-shadow`.
- Colors are `'(R G B)` 0–255. Booleans `TRUE`/`FALSE`. `(car ...)` for the first return value.
- After an in-place filter, `(gimp-displays-flush)` if a display is attached (the MCP server's
  `_flush()` does this for you).

## Core procedures

### Blur
| Signature | Use when |
|---|---|
| `(plug-in-gauss RUN-NONINTERACTIVE img drawable horiz vert method)` | General softening. `horiz`/`vert` 0–500 px radius; `method` IIR=0 (photos) / RLE=1 (synthetic). |
| `(plug-in-mblur RUN-NONINTERACTIVE img drawable type length angle center-x center-y)` | Motion. `type` LINEAR=0 / RADIAL=1 / ZOOM=2; `angle` 0–360. |
| `(plug-in-pixelize RUN-NONINTERACTIVE img drawable pixel-width)` | Censor / mosaic, square blocks. |
| `(plug-in-pixelize2 RUN-NONINTERACTIVE img drawable pixel-width pixel-height)` | Non-square blocks. |

### Sharpen
| Signature | Use when |
|---|---|
| `(plug-in-unsharp-mask RUN-NONINTERACTIVE img drawable radius amount threshold)` | **The** sharpener. `radius` ~1–5, `amount` ~0.5, `threshold` 0 INT32. |
| `(plug-in-sharpen RUN-NONINTERACTIVE img drawable percent)` | Quick/weaker. `percent` 1–99 INT32. |

### Distort
| Signature | Use when |
|---|---|
| `(plug-in-spread RUN-NONINTERACTIVE img drawable amount-x amount-y)` | Random pixel jitter / frosted glass. |
| `(plug-in-whirl-pinch RUN-NONINTERACTIVE img drawable whirl pinch radius)` | Swirl / bulge. `whirl` degrees, `pinch` -1..1, `radius` 0–2. |
| `(plug-in-lens-distortion RUN-NONINTERACTIVE img drawable offset-x offset-y main edge rescale brighten)` | Barrel/pincushion correction. |
| `(plug-in-applylens RUN-NONINTERACTIVE img drawable refraction keep-surroundings set-bg set-transparent)` | Magnifying-glass bubble. Last 3 are bool 0/1. |
| `(plug-in-displace RUN-NONINTERACTIVE img drawable amt-x amt-y do-x do-y map-x map-y type)` | Warp by a displacement-map drawable. Needs **real** map drawables. |

### Artistic
| Signature | Use when |
|---|---|
| `(plug-in-oilify RUN-NONINTERACTIVE img drawable mask-size mode)` | Oil-paint smear. `mask-size` 1–200; `mode` RGB=0 / INTENSITY=1. |
| `(plug-in-cartoon RUN-NONINTERACTIVE img drawable mask-radius pct-black)` | Inked-edge cartoon look. |
| `(plug-in-newsprint RUN-NONINTERACTIVE img drawable cell-width colorspace k-pullout gry-ang gry-spotfn red-ang red-spotfn grn-ang grn-spotfn blu-ang blu-spotfn oversample)` | Halftone dots. 13 params — copy from `pdb_help`. |

### Edge / Emboss
| Signature | Use when |
|---|---|
| `(plug-in-edge RUN-NONINTERACTIVE img drawable amount warpmode edgemode)` | Edge detect. `edgemode` SOBEL=0 PREWITT=1 GRADIENT=2 ROBERTS=3 DIFFERENTIAL=4 LAPLACE=5. |
| `(plug-in-emboss RUN-NONINTERACTIVE img drawable azimuth elevation depth emboss)` | Relief. `azimuth`/`elevation` degrees; `emboss` 1=emboss 0=bumpmap. |
| `(plug-in-bump-map RUN-NONINTERACTIVE img drawable bumpmap azimuth elevation depth xofs yofs waterlevel ambient compensate invert type)` | Light a surface by a bumpmap drawable. |

### Noise
| Signature | Use when |
|---|---|
| `(plug-in-hsv-noise RUN-NONINTERACTIVE img drawable holdness hue-dist sat-dist val-dist)` | Film-grain in HSV. |
| `(plug-in-rgb-noise RUN-NONINTERACTIVE img drawable independent correlated noise-1 noise-2 noise-3 noise-4)` | Per-channel RGBA noise. |

### Render (paint onto a drawable; ignore prior content)
| Signature | Use when |
|---|---|
| `(plug-in-plasma RUN-NONINTERACTIVE img drawable seed turbulence)` | Random plasma cloud texture. |
| `(plug-in-solid-noise RUN-NONINTERACTIVE img drawable tileable turbulent seed detail xsize ysize)` | Perlin clouds (tileable option). |
| `(plug-in-checkerboard RUN-NONINTERACTIVE img drawable check-mode check-size)` | Checkerboard. `mode` REGULAR=0 / PSYCHOBILY=1. |
| `(plug-in-grid RUN-NONINTERACTIVE img drawable hwidth hspace hoffset hcolor hopacity vwidth vspace voffset vcolor vopacity iwidth ispace ioffset icolor iopacity)` | Pixel grid overlay. Colors are `'(R G B)`. |
| `(plug-in-flarefx RUN-NONINTERACTIVE img drawable pos-x pos-y)` | Single lens flare at pixel (x,y). |
| `(plug-in-gflare RUN-NONINTERACTIVE img drawable ...)` | Gradient flare (many params — `pdb_help "plug-in-gflare"`). |
| `(plug-in-difference-clouds ...)` via `script-fu-difference-clouds` | Difference-clouds texture. |

### Decor (script-fu — **NO run-mode arg**, may add/resize layers)
| Signature | Use when |
|---|---|
| `(script-fu-drop-shadow img drawable offx offy blur color opacity allow-resize)` | Shadow behind alpha/selection. `color` `'(R G B)`, `opacity` 0–100, `allow-resize` TRUE/FALSE. **Adds a shadow layer.** |
| `(script-fu-add-bevel img drawable thickness work-on-copy keep-bump-layer)` | Beveled edge. `thickness` px, last two bool. |
| `(script-fu-round-corners img drawable radius add-shadow shadow-x shadow-y blur add-bg work-on-copy)` | Rounded corners (+optional shadow/bg). |
| `(script-fu-old-photo img drawable defocus border-size sepia mottle work-on-copy)` | Aged-photo composite. |

> No `script-fu-vignette` exists in this build. For a vignette, see the recipe below
> (radial selection + feather + darken), or use GEGL `gegl:vignette` via `plug-in-script-fu`.

## Recipes

### Gaussian blur (verified)
```scheme
(plug-in-gauss RUN-NONINTERACTIVE image drawable 8 8 0)   ; 8px IIR, both axes
(gimp-displays-flush)
```

### Motion blur (linear, horizontal streak)
```scheme
(plug-in-mblur RUN-NONINTERACTIVE image drawable 0 30 0 0 0)  ; LINEAR, len 30, angle 0
```

### Sharpen with unsharp mask (verified)
```scheme
(plug-in-unsharp-mask RUN-NONINTERACTIVE image drawable 5.0 0.5 0)  ; radius 5, amount .5, thresh 0
```

### Pixelize / censor a region (select → pixelize → deselect)
```scheme
(gimp-image-select-rectangle image CHANNEL-OP-REPLACE 120 80 200 120)
(plug-in-pixelize RUN-NONINTERACTIVE image drawable 12)  ; only the selection is mosaiced
(gimp-selection-none image)
```

### Oilify painterly (verified)
```scheme
(plug-in-oilify RUN-NONINTERACTIVE image drawable 7 0)   ; mask 7, RGB mode
```

### Drop shadow on a layer (verified — NO run-mode)
```scheme
(gimp-image-set-active-layer image layer)
(script-fu-drop-shadow image layer 8 8 15 '(0 0 0) 80 TRUE)  ; offx offy blur color opacity resize
; creates a new "Drop Shadow" layer below `layer`
```

### Add a bevel (script-fu — NO run-mode)
```scheme
(script-fu-add-bevel image drawable 10 FALSE FALSE)  ; thickness 10, work-in-place, drop bump layer
```

### Vignette (no script-fu-vignette — build it)
```scheme
(let* ((w (car (gimp-image-width image))) (h (car (gimp-image-height image))))
  (gimp-image-select-ellipse image CHANNEL-OP-REPLACE (* w -0.1) (* h -0.1) (* w 1.2) (* h 1.2))
  (gimp-selection-invert image)                       ; select the corners
  (gimp-selection-feather image (/ (min w h) 4))
  (gimp-curves-spline drawable HISTOGRAM-VALUE 6 #(0 0 128 64 255 180)) ; darken edges
  (gimp-selection-none image))
```

### Plasma render to a new layer (verified)
```scheme
(let ((lyr (car (gimp-layer-new image (car (gimp-image-width image))
                                (car (gimp-image-height image))
                                RGB-IMAGE "plasma" 100 LAYER-MODE-NORMAL))))
  (gimp-image-insert-layer image lyr 0 -1)
  (plug-in-plasma RUN-NONINTERACTIVE image lyr 42 2.0))  ; seed 42, turbulence 2.0
```

### Lens flare at a point
```scheme
(plug-in-flarefx RUN-NONINTERACTIVE image drawable 200 150)  ; flare centered at (200,150)
```

### Emboss (relief)
```scheme
(plug-in-emboss RUN-NONINTERACTIVE image drawable 30.0 45.0 20 1)  ; azimuth elev depth emboss=1
```

### Edge detect (Sobel)
```scheme
(plug-in-edge RUN-NONINTERACTIVE image drawable 2.0 0 0)  ; amount 2, warp NONE, SOBEL
```

## Gotchas & enums

- **`RUN-NONINTERACTIVE` on every `plug-in-*`** — forgetting it pops an interactive dialog
  (hangs headless) or misaligns args.
- **`script-fu-*` take NO run-mode** when called, even though `pdb_help` lists it first.
  Drop it. (Verified: passing it makes `script-fu-drop-shadow` throw
  `Error: <: argument 1 must be: number`.)
- **Arg order is the #1 failure.** Plug-in arg lists are unforgiving and undocumented inline —
  always `pdb_help "plug-in-NAME"` and copy types/order. INT32 vs FLOAT matters; pass `8` not
  `8.0` for INT32 width, `5.0` for FLOAT radius.
- **Some plug-ins need a real drawable, not `-1`.** Get one with `(car (gimp-image-get-active-drawable image))`.
  `displace`/`bump-map` additionally need real **map** drawables.
- **In-place mutation:** most filters return nothing; the change is on the drawable. Call
  `(gimp-displays-flush)` if a display is attached.
- **GEGL vs legacy:** GIMP 2.10 ships GEGL ports of many filters but the **PDB names are the
  legacy `plug-in-*`** — keep using them. GEGL-only ops (e.g. `gegl:vignette`) have no PDB
  wrapper; reach them via GEGL nodes, not here.
- **Enum quick ref:** gauss method IIR=0/RLE=1 · mblur type LINEAR=0/RADIAL=1/ZOOM=2 ·
  oilify mode RGB=0/INTENSITY=1 · edge mode SOBEL=0/PREWITT=1/GRADIENT=2/ROBERTS=3/DIFFERENTIAL=4/LAPLACE=5 ·
  checkerboard REGULAR=0/PSYCHOBILY=1 · newsprint colorspace GRAYSCALE=0/RGB=1/CMYK=2/LUMINANCE=3.

## See also

- **MCP wrappers** (`./server.py`): `gaussian_blur(image_id, radius)`,
  `sharpen(image_id, amount, radius)` → unsharp-mask, `pixelize(image_id, block)`,
  `drop_shadow(image_id, offset_x, offset_y, blur, color, opacity)`. These hide the run-mode/
  drawable/flush boilerplate — prefer them for the common path.
- **Scoping a filter:** combine with selections (`06-selections.*`): select a region, run the
  filter (it respects the selection), `(gimp-selection-none image)`.
- **Color/tone** (`07-color-tone.*`) for curves/levels used in the vignette recipe.
- Everything not curated here: `pdb_query "<term>"` over the 209-proc filters-fx slice.
