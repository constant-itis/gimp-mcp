# Packs — the modular tool layer

gimp-mcp is built like **mycelium + mycelium-tools**: a lean **core** (the substrate)
plus **packs** (add-ons you enable by usage). This keeps the tool surface light — which
matters, because every MCP tool's schema costs context tokens, especially for local /
context-limited models. Load only what you need.

## Choosing packs

Set `GIMP_MCP_PACKS`:

| value | loads | ~tools |
|-------|-------|--------|
| *(unset)* or `all` | core + every bundled pack | 72 |
| `core` | core only | 16 |
| `text,fx,recipes` | core + just those | varies |

Core is **always** loaded — with `gimp_eval` + `pdb_query`/`pdb_help` it already reaches
the *entire* GIMP PDB, so a capable model can do anything with core alone; packs are
ergonomics on top.

```bash
# lean, for a small local model:
GIMP_MCP_PACKS=core,text,select claude mcp add gimp -s user -- python3 "$(pwd)/server.py"
```

## The core (`_core.py`, ~16 tools)

Escape hatch + introspection (`gimp_eval`, `pdb_query`, `pdb_help`, `gimp_docs`), the
vision loop (`look`, `render_preview`, `describe`, `inspect`), image IO (`load_image`,
`list_images`, `new_image`, `export_image`), and safety/utility (`gimp_batch`,
`checkpoint`, `restore_checkpoint`). Also the shared infra packs build on — the wrapped
`bridge` (journaling + error hints), `_color`/`_drawable`/`_truthy`/`_flush`/`_place_layer`,
and `_render`.

## Bundled packs (`packs/`)

| pack | tools |
|------|-------|
| `layers` | list/new/add-from-file/set/merge/delete layers, save_xcf, export_layers, close_image |
| `text` | add_text, list_fonts, outline_text, text_with_shadow, arc_text, place |
| `transform` | scale_image, scale_to_fit, crop, autocrop, rotate, flip, resize_canvas |
| `color` | brightness_contrast, hue_saturation, desaturate, invert, auto_levels, curves_adjust |
| `fx` | gaussian_blur, sharpen, pixelize, drop_shadow, vignette, oilify, emboss, lens_flare, motion_blur, gradient_fill, add_border, overlay_blend |
| `select` | select, fill, draw_rect, select_by_color, feather_selection, grow_shrink_selection, color_to_alpha, trim_to_content |
| `recipes` | apply_recipe, list_recipes, show_recipe, save_recipe, delete_recipe |
| `journal` | journal (macro-recorder) |
| `watch` | show (watch in the GIMP window), suggest (context-aware next moves) |

## Writing your own pack

A pack is just a Python module that imports from `_core` and registers tools with
`@mcp.tool`. Drop it in `~/.config/gimp-mcp/packs/` (override with `$GIMP_MCP_PACKS_DIR`)
and it loads automatically — no core changes, no forking:

```python
# ~/.config/gimp-mcp/packs/mine.py
from _core import mcp, bridge, _color, _drawable, _flush

@mcp.tool
def redify(image_id: int, amount: int = 40) -> str:
    """Push the reds up on the active drawable."""
    d = _drawable(image_id)
    bridge.eval(f"(gimp-curves-spline {d} HISTOGRAM-RED 6 #(0 {amount} 128 {128+amount} 255 255))")
    _flush()
    return f"redified image {image_id}"
```

Importing the module registers the tool; that's the whole contract. What `_core`
exports for packs: `mcp, bridge, GimpError, MCPImage, _q, _color, _mode, _drawable,
_truthy, _flush, _place_layer, _render, _JOURNAL, _SUSPEND, _suspend, HERE, KNOWLEDGE_DIR`.

**Recipes vs packs:** a *recipe* is data (a JSON pipeline of existing ops — no code); a
*pack* is code (new tools). Reach for a recipe to save a technique, a pack to add a new
primitive.
