```
       _                                            
  __ _(_)_ __ ___  _ __        _ __ ___   ___ _ __  
 / _` | | '_ ` _ \| '_ \ _____| '_ ` _ \ / __| '_ \ 
| (_| | | | | | | | |_) |_____| | | | | | (__| |_) |
 \__, |_|_| |_| |_| .__/      |_| |_| |_|\___| .__/ 
 |___/            |_|                        |_|    
```

# gimp-mcp

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

## Quickstart

1. **Start GIMP's Script-Fu server** (once per session):
   ```bash
   ./start-gimp-server.sh
   ```
   Launches GIMP headless on `127.0.0.1:10008` (idempotent — no-op if already up).
   To drive a GIMP window you can *watch*, open the GUI and use
   `Filters ▸ Script-Fu ▸ Start Server` on the same port instead — edits then appear
   live in the window.

2. **Ask your agent.** The `gimp` tools load automatically. For example:
   > "Load ~/pic.jpg, scale to 800px wide, bump the contrast, then `look` at it and export a PNG."

That's it — no GIMP scripting knowledge required on your end; the model composes the
Scheme and checks its work with `look`.

## Tools (53)

**The core three** make the whole PDB reachable — the rest are conveniences:

- `gimp_eval(scheme)` — raw escape hatch; runs any Scheme/PDB expression
- `pdb_query(keyword)` — search the PDB for procedure names
- `pdb_help(procedure)` — a procedure's blurb + typed argument list

**Vision:** `look` (inline render — the feedback loop), `render_preview`, `describe`
(metadata), `inspect` (region luminance/contrast + placement hint)

**Editing:** layers (`new_layer`, `add_layer_from_file`, `set_layer`, `list_layers`,
`merge_visible`, `delete_layer`), text (`add_text`, `list_fonts`, `outline_text`,
`text_with_shadow`), transforms (`crop`, `autocrop`, `rotate`, `flip`, `resize_canvas`,
`scale_image`, `scale_to_fit`), color/tone (`brightness_contrast`, `hue_saturation`,
`desaturate`, `invert`, `auto_levels`, `curves_adjust`), filters (`gaussian_blur`,
`sharpen`, `pixelize`, `drop_shadow`, `vignette`), fills/shapes (`select`, `fill`,
`draw_rect`, `gradient_fill`, `add_border`, `overlay_blend`)

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
| `server.py`            | MCP server exposing the 53 tools |
| `gimp_bridge.py`       | zero-dep socket client for the Script-Fu wire protocol |
| `start-gimp-server.sh` | launches GIMP headless with the Script-Fu server (idempotent) |
| `build_pdb_dump.py`    | introspects the live PDB → `knowledge/pdb_full.json` |
| `build_index.py`       | builds `knowledge/pdb_index.md` + per-domain `_slices/` |
| `build-knowledge.sh`   | one-shot regenerate of the machine-readable knowledge |
| `knowledge/`           | the AI-native GIMP reference (see `knowledge/README.md`) |

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

## Path to GIMP 3.x

If you later install GIMP 3, Python 3 GI plugins come back *and* the Script-Fu server
still exists — this bridge keeps working; you'd just gain the option of richer
in-process plugins.

## License

[AGPL-3.0](LICENSE).
