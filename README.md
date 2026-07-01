<p align="center">
  <img src="assets/crest.png" alt="gimp-mcp crest" width="300">
  <br>
  <sub><i>this crest was designed entirely by an agent driving gimp-mcp — shapes + arc-text + transparency, no human in the pixels</i></sub>
</p>

```
       _                                            
  __ _(_)_ __ ___  _ __        _ __ ___   ___ _ __  
 / _` | | '_ ` _ \| '_ \ _____| '_ ` _ \ / __| '_ \ 
| (_| | | | | | | | |_) |_____| | | | | | (__| |_) |
 \__, |_|_| |_| |_| .__/      |_| |_| |_|\___| .__/ 
 |___/            |_|                        |_|    
```

# gimp-mcp

[![ci](https://github.com/constant-itis/gimp-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/constant-itis/gimp-mcp/actions/workflows/ci.yml)

Drive **GIMP 2.10** from an AI agent. An [MCP](https://modelcontextprotocol.io)
server bridges tool calls to GIMP's built-in **Script-Fu** server, exposing the
*entire* GIMP procedure database (every filter, layer op, transform, exporter) —
plus a **vision feedback loop** so the model can actually *see* what it edits.

```
Agent ──MCP/stdio──▶ server.py ──TCP :10008──▶ GIMP Script-Fu server ──▶ GIMP PDB
```

Works with any MCP client. Examples below use [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## What makes it work: the model sees its own edits

The single most useful tool is `look` — it renders the current image and returns it
**inline** to the model as an image, so there's no blind editing. The loop is:

> **edit → `look` → judge → adjust**

Backed by `inspect` (region luminance/contrast + a text-placement hint — quantitative
eyes for "is this area dark enough for light text?") and `describe` (exact size / mode /
layers / dpi), the agent works the way a person does: make a change, look at the result,
correct. Everything else is in service of that loop.

`look` and `render_preview` take a `bg` argument — `auto` (default) shows a transparency
**checkerboard** when the image has alpha, so transparent/cut-out art is actually visible
instead of vanishing onto white. Use `bg=black`/`bg=white` to preview art as it'll sit on
a dark or light background (shirt, sticker, page), or `bg=none` to keep the alpha.

## Built for agents driving it (frontier *and* local models)

The tool surface is shaped around how an LLM actually works this, not how a human clicks:

- **See transparency, not white** — the vision loop composites alpha onto a checkerboard
  by default, so the model never edits blind on cut-out art.
- **No coordinate math** — `place` / `add_text(anchor=…)` position by gravity
  (`center`, `top-center`, `bottom-left`, …). One call instead of a
  measure → compute → set-offset round-trip that small models routinely get wrong.
- **Native transparency ops** — `color_to_alpha` (soft-key a background out) and
  `trim_to_content` (crop to the alpha bounding box) make print/sticker workflows one call.
- **Recoverable errors** — failures are translated into actionable hints ("font missing —
  call `list_fonts`", "stale image id — call `list_images`", "server down — run
  `start-gimp-server.sh`"). This matters most for local models (Hermes, Qwen, etc.) that
  otherwise stall on GIMP's opaque `"returned no return values"`.
- **Fewer round-trips** — `gimp_batch` runs many statements in one call with per-step
  error capture; wrappers return the ids/bboxes you'd otherwise have to re-query.

## Not just editing — drawing from scratch

<p align="center">
  <img src="assets/showcase.png" alt="a landscape drawn from scratch by an agent" width="620">
  <br>
  <sub><i>no source image — every shape here (sunburst, sun, layered mountains, stars) was
  drawn by an agent from the <code>generate</code> pack primitives, checking each move with <code>look</code></i></sub>
</p>

The `generate` pack (`draw_ellipse`/`draw_polygon`/`draw_star`/`draw_line`/`sunburst` +
procedural `render_plasma`/`render_noise`) turns the tool from an *editor* into a *canvas*:
an agent composes original vector/procedural art and iterates against the vision loop.

## Beyond one image — automation, vectors, motion

GIMP's real power isn't editing a single file; it's scale and range. Three packs open that up:

- **`batch`** — process whole *folders*: `batch_resize`, `batch_convert`, `batch_watermark`,
  `batch_recipe` (apply any saved recipe to every image), `contact_sheet`. The
  production-pipeline unlock: "watermark these 200 photos," "vintage the whole shoot."
- **`paths`** — `draw_curve`: real smooth bezier curves through anchor points (waves,
  ribbons, organic outlines) — proper vector illustration, not just rectangles and ellipses.
- **`animate`** — `frames_to_gif` (layers → animated GIF), `gif_from_folder` (a frame
  sequence → GIF), `spin_gif` (rotate a layer into a looping spinner). Motion graphics.

## Why a Script-Fu bridge (not a GIMP plugin)

On modern Linux, GIMP 2.10's **Python-Fu is effectively gone** — `gimp-python` was
dropped because it depended on Python 2 (EOL), so a Python plugin won't install.
But **Script-Fu (Scheme) is always built in**, and GIMP ships a Script-Fu *server*
that listens on TCP and runs any PDB command. This project bridges to that. **Nothing
is installed into GIMP itself** — it just talks to a socket.

## Requirements

- **GIMP 2.10** (2.10.30+ verified) on the `PATH` as `gimp`
- **Python 3.10+**
- **[`fastmcp`](https://github.com/jlowin/fastmcp)** — the only third-party dep (`pip install -r requirements.txt`)
- Linux/macOS (Windows should work via the Script-Fu server but is untested)

## Install

```bash
git clone https://github.com/constant-itis/gimp-mcp.git
cd gimp-mcp
pip install -r requirements.txt
```

Register the server with your MCP client. For Claude Code:

```bash
claude mcp add gimp -s user -- python3 "$(pwd)/server.py"
```

(For other clients, point them at `python3 /abs/path/to/server.py`, stdio transport.)

**Go lean if you want.** The tool surface is modular (core + opt-in packs). Load only
what you need with `GIMP_MCP_PACKS` — e.g. `GIMP_MCP_PACKS=core,text,select` gives ~24
tools instead of 72, which context-limited / local models appreciate. See [PACKS.md](PACKS.md).

## Quickstart

**Headless (fast, no window):**
```bash
./start-gimp-server.sh          # GIMP on 127.0.0.1:10008, idempotent
```
Then ask your agent — the `gimp` tools load automatically:
> "Load ~/pic.jpg, scale to 800px wide, bump the contrast, `look` at it, export a PNG."

The model composes the Scheme and checks its own work with `look`. No GIMP scripting
needed on your end.

## Watch it work — the designer workflow

The common case isn't "generate an image from scratch." It's: **you already have GIMP
open with your artwork** and you say *"hey, do X to this."* Because GIMP is
single-instance, you point the server at the window you already have open:

```bash
# 1. open GIMP with your image (normally)
# 2. attach the server to that same window:
./start-gimp-server.sh --gui      # (or in GIMP: Filters ▸ Script-Fu ▸ Start Server)
# 3. tell your agent: "work on the image I have open — do X"
```

The agent finds your open image (`list_images` / `suggest`), `show`s it, and edits it
**live in your window** — every tool flushes the display so you watch it happen. Ask to
"see it" any time and it opens/refreshes the view.

**House rules — [AGENTS.md](AGENTS.md).** A short convention set for *any* LLM driving
the tool: attach to the file you already have open, compose abilities (don't railroad),
**show a preview + offer options at each stage**, and **snapshot (`checkpoint`) before
any destructive/automated step** — GIMP 2.10 has no API undo, so the snapshot *is* the
undo. `suggest` gives the agent a context-aware menu of next moves to offer you.

## Recipes & journaling — the power-user layer

Techniques are **saved, parameterized, and reused**, not rebuilt each time:

- **`apply_recipe(name, image_id, params)`** runs a named, tunable pipeline on any image
  — e.g. `distressed-text` (grit dial), `vintage`, `sticker-outline`. Bundled recipes are
  just editable JSON in `recipes/`; your own live in `~/.config/gimp-mcp/recipes/`
  (`$GIMP_MCP_RECIPES`). `list_recipes` / `show_recipe` to browse.
- **`journal`** is a macro-recorder: `journal start` → do edits → `journal show` /
  `journal script` (a standalone replay `.py`) / `save_recipe(from_journal=True)` to turn
  what you just did into a reusable recipe. Pure queries and preview scratch are filtered
  out, so the log reads like the recipe you'd hand-write.

Recipes are **abilities, not baked-in behavior** — data you can read, edit, share, and
extend; nothing forces a workflow.

## Tools (16 core + 73 in packs = 89)

Modular: the **core** (~16, always on) reaches the whole PDB and drives the vision loop;
the rest live in opt-in **packs** ([PACKS.md](PACKS.md)). Listing below is the full set.

**The core three** make the whole PDB reachable — the rest are conveniences:

- `gimp_eval(scheme)` — raw escape hatch; runs any Scheme/PDB expression
- `pdb_query(keyword)` — search the PDB for procedure names
- `pdb_help(procedure)` — a procedure's blurb + typed argument list

**Vision & watch:** `look` (inline render — the feedback loop, transparency-aware `bg`),
`render_preview`, `describe` (metadata), `inspect` (region luminance/contrast + placement
hint), `show` (open it in the GIMP window to watch live), `suggest` (context-aware menu of
next moves)

**Recipes & journal:** `apply_recipe`, `list_recipes`, `show_recipe`, `save_recipe`,
`delete_recipe`, `journal` (record → replay script / new recipe)

**Editing:** layers (`new_layer`, `add_layer_from_file`, `set_layer`, `list_layers`,
`merge_visible`, `delete_layer`), text (`add_text`, `list_fonts`, `outline_text`,
`text_with_shadow`, `arc_text` — text on a circular arc, for seals/badges/mission
patches), transforms (`crop`, `autocrop`, `rotate`, `flip`, `resize_canvas`,
`scale_image`, `scale_to_fit`), color/tone (`brightness_contrast`, `hue_saturation`,
`desaturate`, `invert`, `auto_levels`, `curves_adjust`), filters (`gaussian_blur`,
`sharpen`, `pixelize`, `drop_shadow`, `vignette`, `oilify`, `emboss`, `lens_flare`,
`motion_blur`), selections (`select`, `select_by_color` — magic-wand/keying,
`feather_selection`, `grow_shrink_selection`), fills/shapes (`fill`, `draw_rect`,
`gradient_fill`, `add_border`, `overlay_blend`), placement & transparency
(`place` — anchor a layer by gravity, `color_to_alpha` — soft-key a bg to transparent,
`trim_to_content` — crop to the alpha bounds)

**Draw from scratch (`generate`):** `draw_ellipse`, `draw_polygon`, `draw_star`,
`draw_line`, `sunburst`, `render_plasma`, `render_noise` — vector + procedural primitives
an agent composes into original art, checking each move with `look`.

**Session & safety:** `load_image`, `list_images`, `new_image`, `export_image`,
`save_xcf`, `export_layers`, `close_image`, `checkpoint`/`restore_checkpoint`
(immutable snapshots — GIMP 2.10 has no undo over the PDB), `gimp_batch`
(multi-statement run with per-step error capture), `gimp_status`, `gimp_docs`

## Knowledge base (`knowledge/`)

An **AI-native, self-regenerating** GIMP reference — generated *from the installed GIMP
by introspection*, so it never drifts from what you can actually call:

- `pdb_full.json` — all ~1264 procedures with typed args (machine ground truth)
- `pdb_index.md` — categorized one-line index of everything
- `cookbook/00..11` — dense per-domain guides with working Scheme (read `00-overview` first)
- `recipes.md` — "I want to do X" → which tool / cookbook
- search it in-session with the `gimp_docs` tool; rebuild after a GIMP upgrade with `./build-knowledge.sh`

See `knowledge/README.md` for the full layout and regeneration story.

## Files

| file | role |
|------|------|
| `server.py`            | entry point — loads the core + enabled packs, serves over stdio |
| `_core.py`             | the lean substrate: eval/introspection, vision loop, IO, safety, shared infra |
| `packs/`               | opt-in tool bundles (layers, text, fx, recipes, watch, …) — see PACKS.md |
| `recipes/`             | bundled recipe pipelines (editable JSON) |
| `AGENTS.md` · `PACKS.md` | house rules for driving it · the pack system |
| `gimp_bridge.py`       | zero-dep socket client for the Script-Fu wire protocol |
| `start-gimp-server.sh` | launches GIMP (headless, or `--gui` to watch) with the Script-Fu server |
| `build_pdb_dump.py`    | introspects the live PDB → `knowledge/pdb_full.json` |
| `build_index.py`       | builds `knowledge/pdb_index.md` + per-domain `_slices/` |
| `build-knowledge.sh`   | one-shot regenerate of the machine-readable knowledge |
| `knowledge/`           | the AI-native GIMP reference (see `knowledge/README.md`) |

## Teaching a smaller model (`teach/`)

The Opus→Fable move: a strong model manufactures a **verified** corpus of worked
examples that teaches a small / local model (Hermes, a Qwen, a fine-tune) to drive
gimp-mcp. [`teach/factory.py`](teach/) executes JSON task specs against a live GIMP,
records the exact tool-call trace, renders + checks each, and emits `demos.jsonl`
(fine-tune ready), `fewshot.md` (prompt-ready examples), and a `contact-sheet.png`. The
bundled curriculum (36 verified design tasks) was authored by a seed pass + subagents;
the factory drops anything that doesn't actually run. See [teach/README.md](teach/README.md).

## Wire protocol (confirmed on GIMP 2.10.30)

- Request:  `'G'` + uint16_be(len) + scheme
- Response: `'G'` + err_byte(0 ok / 1 err) + uint16_be(len) + body
- `plug-in-script-fu-server` args: `run-mode, ip(STRING), port(INT), logfile(STRING)`

### Gotchas worth knowing

- **Don't launch GIMP with `-f`/`--no-fonts`** — `gimp-text-fontname` then silently
  returns `-1` and renders nothing. `start-gimp-server.sh` omits it deliberately.
- `script-fu-*` procedures take **no** run-mode arg; `plug-in-*` procedures **do**
  (`RUN-NONINTERACTIVE`).
- The Script-Fu interpreter is one long-lived process, so context (foreground color,
  brush, etc.) and `define`s persist across calls — use `gimp-context-push/pop`.
- `gimp-drawable-histogram` returns mean/std on a **0..255** scale on 2.10 (white =
  255.0), not 0..1.

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| **"cannot reach GIMP Script-Fu server"** / connection refused | The server isn't up. Run `./start-gimp-server.sh` (headless) or `--gui` (watchable). Check `gimp` is on your `PATH` and `gimp_status` reports OK. |
| **Text renders nothing / blank** | GIMP was launched with `-f`/`--no-fonts`, which makes `gimp-text-fontname` silently no-op. Use `start-gimp-server.sh` (it omits `-f`); don't add it. Also check the font name with `list_fonts`. |
| **New tools don't show up in your client** | The stdio MCP server loads tools at session start. **Restart the MCP session** (e.g. a new Claude Code session) after pulling changes or editing packs. |
| **Only *some* tools appear** | `GIMP_MCP_PACKS` is limiting them. Unset it (or set `all`) for the full 89; see [PACKS.md](PACKS.md). |
| **`"returned no return values"` error** | Usually a missing font (see above) or bad args. The tool's error text now appends a hint — follow it (`list_fonts`, `pdb_help`, etc.). |
| **Transparent art looks black or white** | For *viewing*: use `look(bg="checker")` (auto already does this when there's alpha). For *exporting*: `export_image` preserves alpha by default (PNG/WebP); pass `flatten=True` only if you want it composited. To *make* a transparent canvas use `new_image(transparent=True)` — `fill_white=False` alone leaves an opaque layer. |
| **Can't watch it work in a window** | Start with `./start-gimp-server.sh --gui`. GIMP is single-instance, so it attaches to a GIMP you already have open. Then `show <image_id>` pops it into the window; every tool flushes the display. |
| **Port already in use / multiple GIMPs** | Override with `GIMP_HOST` / `GIMP_PORT` env vars (both the launcher and the server read them). |
| **Edits go to the wrong image/layer** | State is by integer id. Re-check with `list_images` / `list_layers` / `describe`; ids are stale after `close_image` or a GIMP restart. |
| **A destructive step went wrong** | GIMP 2.10 has no API undo — take a `checkpoint` *before* risky/automated ops and `restore_checkpoint` to recover. |

## Path to GIMP 3.x

If you later install GIMP 3, Python 3 GI plugins come back *and* the Script-Fu server
still exists — this bridge keeps working; you'd just gain the option of richer
in-process plugins.

## Contributing

Contributions are welcome — most are additive (a new pack, a recipe, or a tool in an
existing pack) with no core changes. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup,
the test/dogfood loop, and the pack/recipe contracts. Bug reports and "this tool fought me
as an agent" friction reports are just as valuable as code.

## License

[AGPL-3.0](LICENSE).
