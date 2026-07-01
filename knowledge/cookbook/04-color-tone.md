# 04 — Color & Tone

## Mental model
- Color/tone ops act on a **drawable** (a layer/channel), not the image. Get it: `(car (gimp-image-get-active-drawable IMG))`. IMG and drawable are integer handles.
- Per-channel ops take a `channel` enum from the **HISTOGRAM-*** family (VALUE/RED/GREEN/BLUE/ALPHA/LUMINANCE/RGB). HISTOGRAM-VALUE = luminance composite; RED/GREEN/BLUE isolate a channel for color casts.
- GIMP 2.10 split every global into a `gimp-drawable-*` form. **Prefer `gimp-drawable-*`** (new, GEGL, float ranges). The bare `gimp-*` globals are deprecated but still work and use simpler **integer/0-255** ranges — handy for an agent. Both documented below.
- Colors are `'(R G B)` 0-255. Booleans `TRUE`/`FALSE`. Enums are bare constants. Wrap returns in `(car ...)` for the first value.
- Mutations are in-place on the drawable; no return value you need. Call `(gimp-displays-flush)` only if a GUI is attached (headless: skip).

## Core procedures
| Procedure | Signature (after drawable) | Use when | Note |
|---|---|---|---|
| `gimp-drawable-brightness-contrast` | `b -0.5..0.5  c -0.5..0.5` | brightness/contrast, new | **preferred** |
| `gimp-brightness-contrast` | `b -127..127  c -127..127` | same, integer args | deprecated |
| `gimp-drawable-curves-spline` | `channel num-pts #(x y …)` x,y 0.0..1.0 | smooth tone/color curve | **preferred**, float vec |
| `gimp-curves-spline` | `channel num-pts #(x y …)` x,y 0..255 | same, integer vec | deprecated, simpler |
| `gimp-drawable-curves-explicit` | `channel num-vals(256+) #(256 floats)` | full 256-entry LUT | **preferred** |
| `gimp-drawable-levels` | `channel lo-in hi-in clampIn gamma lo-out hi-out clampOut` floats 0..1 | precise levels/gamma | **preferred** |
| `gimp-levels` | `channel lo-in hi-in gamma lo-out hi-out` ints 0..255 | same, integer | deprecated |
| `gimp-drawable-levels-stretch` | *(no args)* | auto-stretch contrast | **preferred** (= Levels "Auto") |
| `gimp-levels-stretch` / `gimp-levels-auto` | *(no args)* | same | deprecated |
| `gimp-drawable-hue-saturation` | `hue-range hue-off light sat overlap` | hue/sat/light, optional overlap | **preferred** |
| `gimp-hue-saturation` | `hue-range hue-off light sat` | same, no overlap | deprecated |
| `gimp-drawable-color-balance` | `transfer-mode preserve-lum cr mg yb` (-100..100) | warm/cool by tonal range | **preferred** |
| `gimp-drawable-colorize-hsl` | `hue 0..360  sat 0..100  light -100..100` | tint/duotone (RGB only) | **preferred** |
| `gimp-colorize` | same args | same | deprecated |
| `gimp-drawable-desaturate` | `desaturate-mode` | RGB→gray-looking, stays RGB | **preferred** |
| `gimp-drawable-threshold` | `channel lo hi` floats 0..1 | 1-bit black/white | **preferred** |
| `gimp-threshold` | `lo hi` ints 0..255 | same | deprecated |
| `gimp-drawable-posterize` | `levels 2..255` | reduce shades | **preferred** |
| `gimp-drawable-invert` | `linear TRUE/FALSE` | negative | **preferred** |
| `gimp-drawable-histogram` | `channel start end` floats 0..1 → mean,std,median,pixels,count,percentile | read stats | **preferred** |

Convention below: `(define D (car (gimp-image-get-active-drawable IMG)))`.

## Recipes

### Brighten + add contrast (new form)
```scheme
; ranges -0.5..0.5; +0.15 brightness, +0.2 contrast
(gimp-drawable-brightness-contrast D 0.15 0.2)
```
Deprecated integer equivalent (-127..127):
```scheme
(gimp-brightness-contrast D 40 50)
```

### Warm up an image via curves (lift red, drop blue)
Curve points are a flat **vector** `#(x0 y0 x1 y1 …)`, monotonically increasing x, min 2 points (4 numbers). New form uses **0.0..1.0 floats**:
```scheme
; red: lift midtones; blue: lower midtones -> warm cast
(gimp-drawable-curves-spline D HISTOGRAM-RED  6 #(0.0 0.0 0.5 0.6 1.0 1.0))
(gimp-drawable-curves-spline D HISTOGRAM-BLUE 6 #(0.0 0.0 0.5 0.4 1.0 1.0))
```
Deprecated form, identical shape but **0..255 integers** (often easier to reason about):
```scheme
(gimp-curves-spline D HISTOGRAM-RED  6 #(0 0 128 165 255 255))
(gimp-curves-spline D HISTOGRAM-BLUE 6 #(0 0 128 100 255 255))
```
Both VERIFIED working. `num-points` = count of numbers in the vector (here 6 = 3 control points), NOT the point count.

### S-curve contrast on luminance
```scheme
(gimp-drawable-curves-spline D HISTOGRAM-VALUE 6 #(0.0 0.0 0.25 0.18 0.75 0.82))
; or add endpoints explicitly: #(0.0 0.0 0.25 0.18 0.75 0.82 1.0 1.0) -> num=8
```

### Auto-stretch contrast (one-liner, no params)
```scheme
(gimp-drawable-levels-stretch D)   ; == Levels tool "Auto" button
```

### Manual levels: clip black/white point + gamma (new, 0..1)
```scheme
; ch lo-in hi-in clamp-in gamma lo-out hi-out clamp-out
(gimp-drawable-levels D HISTOGRAM-VALUE 0.05 0.95 TRUE 1.1 0.0 1.0 TRUE)
```
Deprecated integer version (0..255, no clamp flags):
```scheme
(gimp-levels D HISTOGRAM-VALUE 13 242 1.1 0 255)
```

### Desaturate to B&W (stays RGB, pick formula)
```scheme
(gimp-drawable-desaturate D DESATURATE-LUMINANCE)  ; perceptual, best default
; modes: DESATURATE-LIGHTNESS LUMA AVERAGE LUMINANCE VALUE
```
True grayscale mode (drops color channels): `(gimp-image-convert-grayscale IMG)`.

### Boost / kill saturation
```scheme
; hue-range hue-offset lightness saturation overlap
(gimp-drawable-hue-saturation D HUE-RANGE-ALL 0 0 40 0)   ; +40 sat
(gimp-drawable-hue-saturation D HUE-RANGE-ALL 0 0 -100 0) ; fully desaturate
; shift only reds: (… HUE-RANGE-RED -20 0 30 0)
```

### Colorize / duotone (single-tone tint; RGB only)
```scheme
; hue 0..360, sat 0..100, lightness -100..100  -> sepia-ish
(gimp-drawable-colorize-hsl D 30 50 0)
; cyan duotone: (… 200 60 0)
```

### Warm/cool by tonal range (color balance)
```scheme
; transfer-mode preserve-lum  cyan-red  magenta-green  yellow-blue
(gimp-drawable-color-balance D TRANSFER-MIDTONES TRUE 20 0 -15)   ; warm mids
(gimp-drawable-color-balance D TRANSFER-SHADOWS  TRUE 0 0 15)     ; cool shadows
; +cr=toward red, +yb=toward blue; modes: TRANSFER-SHADOWS/MIDTONES/HIGHLIGHTS
```

### Threshold to 1-bit
```scheme
; channel low high, floats 0..1; pixels in [low,high] -> white, else black
(gimp-drawable-threshold D HISTOGRAM-VALUE 0.5 1.0)
```
Deprecated (0..255): `(gimp-threshold D 128 255)`

### Posterize (reduce shades)
```scheme
(gimp-drawable-posterize D 4)   ; 4 levels per channel; range 2..255
```

### Invert (negative)
```scheme
(gimp-drawable-invert D FALSE)  ; FALSE = perceptual; TRUE = linear space
; value-only invert (keeps hue/sat): (plug-in-vinvert RUN-NONINTERACTIVE IMG D)
```

### Read histogram stats (to drive decisions)
```scheme
; returns (mean std-dev median pixels count percentile), values 0..1 for 8-bit
(gimp-drawable-histogram D HISTOGRAM-VALUE 0.0 1.0)
(car (gimp-drawable-histogram D HISTOGRAM-VALUE 0.0 1.0))  ; mean only
```

## Gotchas & enums
- **Curve vector is `#(...)`** (a Scheme vector literal), flat `x0 y0 x1 y1 …`, x strictly increasing. `num-points` = element count (3 ctrl pts → 6). Passing a list `'(...)` or wrong count errors. VERIFIED: new=floats 0.0..1.0, deprecated=ints 0..255.
- **Value-range trap:** new `gimp-drawable-*` uses **0.0..1.0 floats** (and brightness/contrast **-0.5..0.5**); deprecated `gimp-*` uses **0..255 ints** (brightness/contrast **-127..127**). Mixing them silently clips or no-ops.
- `gimp-drawable-colorize-hsl` / `gimp-drawable-desaturate` are **RGB-only** — fail on grayscale/indexed images. Convert first if needed.
- `gimp-drawable-levels-stretch` and `gimp-drawable-invert` differ from deprecated by an arg: stretch takes none; invert adds the `linear` boolean.
- HISTOGRAM channels: `HISTOGRAM-VALUE 0  RED 1  GREEN 2  BLUE 3  ALPHA 4  LUMINANCE 5  RGB 6`.
- Desaturate modes: `DESATURATE-LIGHTNESS 0  LUMA 1  AVERAGE 2  LUMINANCE 3  VALUE 4`.
- Hue ranges: `HUE-RANGE-ALL 0  RED 1  YELLOW 2  GREEN 3  CYAN 4  BLUE 5  MAGENTA 6`. Use `HUE-RANGE-ALL` unless targeting one hue band.
- Color-balance transfer modes: `TRANSFER-SHADOWS 0  TRANSFER-MIDTONES 1  TRANSFER-HIGHLIGHTS 2`.
- `gimp-drawable-histogram` returns float stats 0..1 for 8-bit images, not 0..255. Deprecated `gimp-histogram` uses 0..255 ranges.

## See also
- **server.py MCP wrappers** (cross-reference these — they wrap the above): `brightness_contrast` (ints, deprecated form), `hue_saturation`, `desaturate` (mode by name), `invert`, `auto_levels` (= levels-stretch), `curves_adjust` (channel name + `"x,y x,y"` point string).
- To **limit scope** of any op, set a selection first (see selections cookbook) — color/tone ops only touch selected pixels.
- For blur/sharpen/noise/artistic filters see **filters-fx** cookbook.
- `render_preview` to dump a PNG and visually confirm a tone change.
