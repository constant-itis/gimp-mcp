# GIMP 2.10 via Script-Fu — Agent Overview

This is the entry point. Read this first, then the domain cookbook you need.
The reader is an LLM driving GIMP 2.10.30 through its Script-Fu PDB over a socket
bridge (the repo root). Everything here is Scheme you can send verbatim.

## The execution model

```
you → MCP tool gimp_eval("(scheme …)") → server.py → TCP :10008 → GIMP Script-Fu server → PDB
```

- **Every GIMP operation is a PDB procedure call** written in Scheme (TinyScheme dialect).
- **Handles are integers.** `image`, `drawable`, `layer`, `channel`, `vectors` are all
  int ids. You pass them around. There is no object syntax.
- **A procedure returns a list**, even for one value. Take `(car …)`:
  `(car (gimp-image-width 1))` → the width.
- **The interpreter process is persistent and stateful.** Variables you `define`,
  and the global *context* (foreground color, brush, active image…), persist across
  separate `gimp_eval` calls because it's one long-lived GIMP process. This is a
  feature (set context once) and a trap (state leaks between unrelated operations).

## The five things that trip up an agent

1. **drawable ≠ layer (usually is, though).** Most edit ops act on a *drawable* —
   get it with `(car (gimp-image-get-active-drawable IMG))`. Set the active layer
   first if you mean a specific one.
2. **Plug-ins take `RUN-NONINTERACTIVE` as their first arg** (`plug-in-*`).
   **`script-fu-*` macros do NOT** — call them with their real args directly even
   though the PDB lists a run-mode. (Verified; see 08-filters-fx.)
3. **Colors are lists:** `'(255 128 0)`. Booleans are `TRUE`/`FALSE`. Enums are bare
   constants (`LAYER-MODE-MULTIPLY`, `HISTOGRAM-VALUE`, `ORIENTATION-HORIZONTAL`).
4. **Nothing is visible until you flush** in GUI mode: `(gimp-displays-flush)`.
   In headless mode it's harmless; include it.
5. **Errors come back as text with err-byte=1.** `gimp_eval` raises `GimpError` with
   GIMP's message. Read it — arg-count/type mismatches are the usual cause; fix with
   `pdb_help`.

## Work loop (use your eyes)

GIMP is visual. Don't fly blind:

```
load_image / new_image
  → make an edit (gimp_eval or a wrapper tool)
  → render_preview(img)         # exports a small PNG, returns path + scale
  → Read that PNG               # you can SEE it
  → judge, adjust, repeat
  → export_image / save_xcf
```

`render_preview` returns the scale factor so you can map what you see in the preview
back to full-res coordinates: `image_coord = preview_coord / scale`.

## How to find the right procedure

- **In a session:** call `pdb_query("keyword")` to find procedures, `pdb_help("name")`
  for the exact typed signature. These hit the *live* PDB — never stale.
- **Offline / browsing:** `../pdb_index.md` (all 1264, categorized, one-line each),
  `../pdb_full.json` (full machine reference), or the domain cookbooks here.
- **Recipes for "I want to do X":** the cookbook file for the domain, or `../../recipes.md`.

## Type codes (PDB arg types you'll see)

`INT32` (also used for bool/enum), `FLOAT`, `STRING`, `IMAGE`, `DRAWABLE`, `LAYER`,
`CHANNEL`, `ITEM`, `VECTORS`, `COLOR` (`'(r g b)`), `*ARRAY` (Scheme vector `#(…)`).

## Cookbook map

| file | domain |
|------|--------|
| 01-images-io | load / save / export / new / flatten / formats |
| 02-layers-masks | layer stack, modes, opacity, offsets, masks, groups |
| 03-text-fonts | text layers, fonts, styling (the `-f`/no-fonts trap) |
| 04-color-tone | curves, levels, brightness, hue, desaturate, threshold |
| 05-selections | rectangle/ellipse/color/fuzzy select, channels, masks |
| 06-transforms-canvas | scale vs resize vs crop, rotate, flip, canvas |
| 07-paint-draw | pencil/brush/bucket/gradient/stroke |
| 08-filters-fx | the `plug-in-*` / `script-fu-*` effect library |
| 09-vectors-paths | bezier paths, path↔selection, stroking |
| 10-context-resources | global context state, brushes/gradients/palettes |
| 11-automation | batch over files, scripting patterns, the bridge itself |
