# gimp-mcp

Drive GIMP 2.10 from Claude prompts. MCP server → GIMP's built-in Script-Fu TCP
server → the full GIMP PDB (every filter, layer op, exporter).

## Why this design (not a "real" GIMP plugin)

On Pop!_OS 22.04, GIMP's **Python-Fu is gone** — `gimp-python` was dropped because
it needed Python 2 (EOL). So a Python plugin won't install. **Script-Fu (Scheme)
is always built in**, and GIMP ships a Script-Fu *server* that listens on TCP and
runs any PDB command. We bridge to that. Nothing is installed into GIMP itself.

```
Claude ──MCP/stdio──▶ server.py ──TCP :10008──▶ GIMP Script-Fu server ──▶ GIMP PDB
```

## Files

| file | role |
|------|------|
| `gimp_bridge.py`       | zero-dep socket client for the Script-Fu wire protocol |
| `server.py`            | fastmcp server exposing 53 tools (see below) |
| `start-gimp-server.sh` | launches GIMP headless with the Script-Fu server (idempotent) |
| `build_pdb_dump.py`    | introspects the live PDB → `knowledge/pdb_full.json` |
| `build_index.py`       | builds `knowledge/pdb_index.md` + per-domain `_slices/` |
| `build-knowledge.sh`   | one-shot regenerate of the machine-readable knowledge |
| `knowledge/`           | the AI-native GIMP reference (see `knowledge/README.md`) |

## Usage

1. **Start GIMP's server** (once per session):
   ```bash
   ./start-gimp-server.sh
   ```
   Headless on `127.0.0.1:10008`. To drive a GIMP you're *looking at* instead,
   open the GUI and use `Filters ▸ Script-Fu ▸ Start Server` (same port) — then
   edits appear live in the window.

2. **The MCP server is already registered** (`claude mcp add gimp`, user scope).
   In a Claude session the `gimp` tools appear automatically.

3. **Ask Claude.** e.g. "load ~/pic.jpg, scale to 800px wide, bump contrast, export PNG".

## Tools

- `gimp_eval(scheme)` — raw escape hatch; runs any Scheme/PDB expression
- `gimp_status()` — server reachable? version + open images
- `pdb_query(keyword)` — search the PDB for procedure names
- `pdb_help(procedure)` — a procedure's blurb + typed argument list
- `load_image`, `list_images`, `new_image`, `scale_image`,
  `brightness_contrast`, `gaussian_blur`, `export_image`

The first three are the point: `gimp_eval` + the two `pdb_*` introspection tools
mean the *entire* PDB is reachable from prompts — the wrappers are just shortcuts
for the common ops.

**Power tools (the high-leverage layer):** `look` (renders + returns the image
**inline** — auto-vision, no Read step), `describe` (structured metadata), `inspect`
(region luminance/contrast + text-placement hint — quantitative eyes), `gimp_batch`
(multi-statement run with per-step error capture), `checkpoint`/`restore_checkpoint`
(immutable snapshots for safe experimentation), `scale_to_fit`, `add_border`,
`gradient_fill`, `vignette`, `outline_text`, `text_with_shadow`, `overlay_blend`.

Full set (53): vision (`look`, `render_preview`), layers
(`new_layer`, `add_layer_from_file`, `set_layer`, `list_layers`, `merge_visible`,
`delete_layer`), text (`add_text`, `list_fonts`), transforms (`crop`, `autocrop`,
`rotate`, `flip`, `resize_canvas`, `scale_image`), color/tone (`brightness_contrast`,
`hue_saturation`, `desaturate`, `invert`, `auto_levels`, `curves_adjust`), filters
(`gaussian_blur`, `sharpen`, `pixelize`, `drop_shadow`), selection/fill/shapes
(`select`, `fill`, `draw_rect`), file/session (`load_image`, `list_images`,
`new_image`, `export_image`, `save_xcf`, `export_layers`, `close_image`), and docs
(`gimp_docs`).

## Knowledge base (`knowledge/`)

An **AI-native, self-regenerating** GIMP reference — generated from the installed
GIMP by introspection, so it never drifts from what you can actually call:

- `pdb_full.json` — all 1264 procedures with typed args (machine ground truth)
- `pdb_index.md` — categorized one-line index of everything
- `cookbook/00..11` — dense per-domain guides with working Scheme (read `00-overview` first)
- `recipes.md` — "I want to do X" → tool/cookbook
- search it in-session with the `gimp_docs` tool; rebuild with `./build-knowledge.sh`

See `knowledge/README.md` for the full layout and regeneration story.

## Wire protocol (confirmed on GIMP 2.10.30)

- Request:  `'G'` + uint16_be(len) + scheme
- Response: `'G'` + err_byte(0 ok / 1 err) + uint16_be(len) + body
- `plug-in-script-fu-server` args: `run-mode, ip(STRING), port(INT), logfile(STRING)`

## Path to GIMP 3.x

If you later install GIMP 3 (Flatpak or build), you get Python 3 GI plugins back
*and* the Script-Fu server still exists — this bridge keeps working, you'd just
gain the option of richer in-process plugins.
