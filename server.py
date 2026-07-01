#!/usr/bin/env python3
"""
gimp-mcp — MCP server that lets Claude drive GIMP 2.10 from prompts.

Bridges MCP tool calls to GIMP's Script-Fu TCP server (see gimp_bridge.py).
Design: one raw `gimp_eval` escape hatch + PDB introspection tools so the
*entire* GIMP procedure database is reachable, plus a few high-level
convenience wrappers for the common image ops.

Run:   python3 server.py            (stdio transport, for `claude mcp add`)
Needs: the Script-Fu server running — ./start-gimp-server.sh
"""

import os
import sys
import re
import json
import glob
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP
from fastmcp.utilities.types import Image as MCPImage
from gimp_bridge import GimpBridge, GimpError

HOST = os.environ.get("GIMP_HOST", "127.0.0.1")
PORT = int(os.environ.get("GIMP_PORT", "10008"))

mcp = FastMCP("gimp")
bridge = GimpBridge(HOST, PORT)


def _q(path: str) -> str:
    """Escape a string for embedding inside a Scheme double-quoted literal."""
    return path.replace("\\", "\\\\").replace('"', '\\"')


# ── error hints: turn opaque GIMP failures into actionable guidance ────────────
# Small/local models (Hermes, Qwen, etc.) recover poorly from raw GIMP errors;
# every tool routes through bridge.eval, so we translate failures in ONE place.
_ERROR_HINTS = [
    ("no return values",   "the proc failed — often a missing font, or GIMP was launched with -f/--no-fonts (text renders nothing). Call list_fonts; if fonts are truly gone, restart with start-gimp-server.sh."),
    ("invalid image",      "that image id is stale or closed — call list_images to see live ids."),
    ("invalid drawable",   "that layer/drawable id is stale — call list_layers <image_id>."),
    ("invalid item",       "that item id is stale — re-fetch it (list_layers / describe)."),
    ("not found",          "no such PDB procedure — search names with pdb_query, then pdb_help."),
    ("wrong number",       "wrong argument count — check the exact signature with pdb_help <procedure>."),
]


def _hint(msg: str) -> str:
    low = msg.lower()
    for needle, tip in _ERROR_HINTS:
        if needle in low:
            return "\n  hint: " + tip
    return ""


# ── journaling: record the design ops as they happen (macro-recorder) ─────────
# Every tool routes through bridge.eval, so this one hook captures a replayable
# log. Pure reads and preview/export scratch work are filtered out so the journal
# reads like the recipe you'd hand-write, not socket noise.
_JOURNAL = {"on": False, "label": "", "ops": []}
_SUSPEND = {"n": 0}                       # reentrant: >0 = don't record (previews/exports)
_READ_RE = re.compile(
    r"gimp-(image-(width|height|base-type|get-layers|get-resolution|get-filename|"
    r"get-active-(drawable|layer))|drawable-(width|height|offsets|has-alpha|histogram|"
    r"get-pixel)|item-get-(name|visible)|layer-get-opacity|selection-bounds|image-list|"
    r"version)|gimp-procedural-db|gimp-fonts-get-list|gimp-displays-flush"
)
_WRITE_RE = re.compile(
    r"plug-in-|script-fu-|-set-|-fill|-insert|-add-|-remove|-delete|threshold|levels|"
    r"curves|transform|gradient|-select|merge|create-mask|anchor|-scale|-crop|-rotate|"
    r"-flip|desaturate|invert|brightness|hue-saturation|colortoalpha|text-fontname|edit-|"
    r"floating|convert|set-offsets|set-opacity|set-mode"
)


def _journal_add(scheme: str):
    if not _JOURNAL["on"] or _SUSPEND["n"] > 0:
        return
    s = scheme.strip()
    if s.startswith(";"):
        _JOURNAL["ops"].append(s)          # explicit marker (e.g. apply_recipe)
        return
    if _READ_RE.search(s) and not _WRITE_RE.search(s):
        return                             # pure query — not a design op
    _JOURNAL["ops"].append(s)


class _suspend:
    """`with _suspend():` — don't journal scratch work (previews, exports, snapshots)."""
    def __enter__(self): _SUSPEND["n"] += 1
    def __exit__(self, *a): _SUSPEND["n"] -= 1


_raw_eval = bridge.eval


def _smart_eval(scheme: str) -> str:
    """bridge.eval + journaling + actionable error text. Applied globally."""
    try:
        out = _raw_eval(scheme)
        _journal_add(scheme)
        return out
    except ConnectionError as e:
        raise ConnectionError(
            f"{e}\n  hint: Script-Fu server unreachable — run ./start-gimp-server.sh "
            f"(headless), or in the GUI use Filters ▸ Script-Fu ▸ Start Server on :10008."
        ) from None
    except GimpError as e:
        raise GimpError(f"{e}{_hint(str(e))}") from None


bridge.eval = _smart_eval


# ── core: raw eval + introspection ───────────────────────────────────────────

@mcp.tool
def gimp_eval(scheme: str) -> str:
    """Evaluate a raw Script-Fu (Scheme) expression against GIMP's full PDB.

    This is the escape hatch — any GIMP operation can be done here. Returns the
    printed result, or raises with GIMP's error text. Image/drawable handles are
    integers. Example: '(gimp-image-width 1)' or
    '(gimp-image-scale 1 800 600)'.
    """
    return bridge.eval(scheme)


@mcp.tool
def gimp_status() -> str:
    """Check that the Script-Fu server is reachable and report GIMP version."""
    try:
        ver = bridge.eval("(car (gimp-version))")
        imgs = bridge.eval("(vector->list (cadr (gimp-image-list)))")
        return f"OK — GIMP {ver.strip(chr(34))}, open images: {imgs}"
    except (ConnectionError, GimpError) as e:
        return f"NOT READY — {e}"


@mcp.tool
def pdb_query(keyword: str = "", limit: int = 60) -> str:
    """Search GIMP's procedure database for procedures whose name matches keyword.

    Use this to discover the right PDB procedure before calling it via gimp_eval.
    Empty keyword lists the first `limit` procedures. Matching is a substring on
    the procedure name (GIMP wants '*kw*' glob — handled here).
    """
    kw = "*" + keyword.replace("*", "") + "*" if keyword else "*"
    raw = bridge.eval(
        f'(cadr (gimp-procedural-db-query "{_q(kw)}" ".*" ".*" ".*" ".*" ".*" ".*"))'
    )
    names = raw.strip().strip("()").split()
    names = [n.strip('"') for n in names if n.strip()]
    names.sort()
    shown = names[:limit]
    more = "" if len(names) <= limit else f"\n… (+{len(names)-limit} more, narrow the keyword)"
    return f"{len(names)} match(es):\n" + "\n".join(shown) + more


@mcp.tool
def pdb_help(procedure: str) -> str:
    """Show a PDB procedure's blurb and full argument list (name + type each).

    Run this before calling an unfamiliar procedure so you pass the right args.
    """
    info = bridge.eval(f'(gimp-procedural-db-proc-info "{_q(procedure)}")')
    # info = (blurb help author copyright date proc-type num-args num-values)
    nargs = bridge.eval(f'(list-ref (gimp-procedural-db-proc-info "{_q(procedure)}") 6)')
    try:
        n = int(nargs.strip())
    except ValueError:
        n = 0
    type_names = {
        "0": "INT32", "1": "INT16", "2": "INT8", "3": "FLOAT", "4": "STRING",
        "5": "INT32ARRAY", "6": "INT16ARRAY", "7": "INT8ARRAY", "8": "FLOATARRAY",
        "9": "STRINGARRAY", "10": "COLOR", "11": "ITEM", "12": "DISPLAY",
        "13": "IMAGE", "14": "LAYER", "15": "CHANNEL", "16": "DRAWABLE",
        "17": "SELECTION", "18": "COLORARRAY", "19": "VECTORS", "20": "PARASITE",
    }
    lines = [f"=== {procedure} ===", info.strip(), "", "Arguments:"]
    for i in range(n):
        arg = bridge.eval(
            f'(let ((a (gimp-procedural-db-proc-arg "{_q(procedure)}" {i}))) '
            f'(string-append (number->string (car a)) "|" (cadr a) "|" (caddr a)))'
        ).strip().strip('"')
        parts = arg.split("|")
        t = type_names.get(parts[0], parts[0])
        name = parts[1] if len(parts) > 1 else "?"
        desc = parts[2] if len(parts) > 2 else ""
        lines.append(f"  {i}: {name} ({t}) — {desc}")
    return "\n".join(lines)


# ── convenience wrappers for the common ops ──────────────────────────────────

@mcp.tool
def load_image(path: str) -> str:
    """Load an image file into GIMP. Returns the image id (an integer handle)."""
    img = bridge.eval(
        f'(car (gimp-file-load RUN-NONINTERACTIVE "{_q(path)}" "{_q(os.path.basename(path))}"))'
    )
    return f"loaded image id={img.strip()} from {path}"


@mcp.tool
def list_images() -> str:
    """List open image ids with their filename, width, and height."""
    ids = bridge.eval("(vector->list (cadr (gimp-image-list)))").strip().strip("()").split()
    if not ids:
        return "no images open"
    out = []
    for i in ids:
        try:
            w = bridge.eval(f"(car (gimp-image-width {i}))").strip()
            h = bridge.eval(f"(car (gimp-image-height {i}))").strip()
            name = bridge.eval(f"(car (gimp-image-get-filename {i}))").strip()
            out.append(f"id={i}  {w}x{h}  {name}")
        except GimpError:
            out.append(f"id={i}  (info unavailable)")
    return "\n".join(out)


@mcp.tool
def scale_image(image_id: int, width: int, height: int) -> str:
    """Resize an image to width x height pixels (in place)."""
    bridge.eval(f"(gimp-image-scale {int(image_id)} {int(width)} {int(height)})")
    bridge.eval("(gimp-displays-flush)")
    return f"scaled image {image_id} to {width}x{height}"


@mcp.tool
def brightness_contrast(image_id: int, brightness: int = 0, contrast: int = 0) -> str:
    """Adjust brightness and contrast (-127..127 each) on the active drawable."""
    d = bridge.eval(f"(car (gimp-image-get-active-drawable {int(image_id)}))").strip()
    bridge.eval(
        f"(gimp-brightness-contrast {d} {int(brightness)} {int(contrast)})"
    )
    bridge.eval("(gimp-displays-flush)")
    return f"applied brightness={brightness} contrast={contrast} to image {image_id}"


@mcp.tool
def gaussian_blur(image_id: int, radius: float = 5.0) -> str:
    """Apply a Gaussian blur of the given radius (px) to the active drawable."""
    d = bridge.eval(f"(car (gimp-image-get-active-drawable {int(image_id)}))").strip()
    bridge.eval(f"(plug-in-gauss RUN-NONINTERACTIVE {int(image_id)} {d} {float(radius)} {float(radius)} 0)")
    bridge.eval("(gimp-displays-flush)")
    return f"blurred image {image_id} radius={radius}"


@mcp.tool
def export_image(image_id: int, path: str) -> str:
    """Flatten a copy of the image and export it to `path`.

    Format is chosen from the file extension (.png/.jpg/.webp/.tiff/...).
    The original in-memory image is left unflattened.
    """
    dup = bridge.eval(f"(car (gimp-image-duplicate {int(image_id)}))").strip()
    try:
        bridge.eval(f"(gimp-image-flatten {dup})")
        d = bridge.eval(f"(car (gimp-image-get-active-drawable {dup}))").strip()
        bridge.eval(
            f'(gimp-file-save RUN-NONINTERACTIVE {dup} {d} "{_q(path)}" "{_q(os.path.basename(path))}")'
        )
    finally:
        bridge.eval(f"(gimp-image-delete {dup})")
    return f"exported image {image_id} -> {path}"


@mcp.tool
def new_image(width: int = 1024, height: int = 1024, fill_white: bool = True) -> str:
    """Create a new RGB image. Returns the new image id."""
    img = bridge.eval(f"(car (gimp-image-new {int(width)} {int(height)} RGB))").strip()
    layer = bridge.eval(
        f'(car (gimp-layer-new {img} {int(width)} {int(height)} RGB-IMAGE "bg" 100 LAYER-MODE-NORMAL))'
    ).strip()
    bridge.eval(f"(gimp-image-insert-layer {img} {layer} 0 -1)")
    if fill_white:
        bridge.eval("(gimp-context-set-background '(255 255 255))")
        bridge.eval(f"(gimp-image-set-active-layer {img} {layer})")
        bridge.eval(f"(gimp-drawable-fill {layer} FILL-BACKGROUND)")
    return f"created image id={img} ({width}x{height})"


# ── helpers for the extended tool set ────────────────────────────────────────

def _color(c) -> str:
    """Accept '#rrggbb', 'r,g,b', or 'r g b' → Scheme color literal '(r g b)."""
    s = str(c).strip().lstrip("#")
    if len(s) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in s):
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    else:
        parts = s.replace(",", " ").split()
        r, g, b = (int(float(p)) for p in parts[:3])
    return f"'({r} {g} {b})"


def _mode(name: str) -> str:
    """Map a friendly blend-mode name to a GIMP LAYER-MODE-* constant."""
    return "LAYER-MODE-" + str(name).strip().upper().replace("_", "-").replace(" ", "-")


def _drawable(image_id) -> str:
    return bridge.eval(f"(car (gimp-image-get-active-drawable {int(image_id)}))").strip()


def _truthy(scheme: str) -> bool:
    """Eval a predicate and interpret the result. GIMP booleans come back over the
    bridge as '1'/'0' (NOT 'TRUE'/'FALSE') — this normalizes both."""
    return bridge.eval(scheme).strip().upper() in ("1", "TRUE", "#T", "YES")


def _flush():
    bridge.eval("(gimp-displays-flush)")


def _place_layer(iid: int, lid, anchor: str, dx: int = 0, dy: int = 0, margin: int = 0):
    """Move layer `lid` to a canvas gravity anchor (+ optional offset). Shared by
    `place` and `add_text`. anchor keywords: center/top/bottom/left/right and the
    corner/edge combos (top-left, bottom-center, …). Returns (x, y)."""
    W = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    H = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    lw = int(bridge.eval(f"(car (gimp-drawable-width {lid}))").strip())
    lh = int(bridge.eval(f"(car (gimp-drawable-height {lid}))").strip())
    a = str(anchor).lower().replace("_", "-").replace(" ", "-")
    m = int(margin)
    if "left" in a:    x = m
    elif "right" in a: x = W - lw - m
    else:              x = (W - lw) // 2
    if "top" in a:     y = m
    elif "bottom" in a:y = H - lh - m
    else:              y = (H - lh) // 2
    x += int(dx); y += int(dy)
    bridge.eval(f"(gimp-layer-set-offsets {lid} {x} {y})")
    return x, y


# ── VISION: the keystone preview loop ────────────────────────────────────────

def _render(iid: int, max_dim: int, bg: str, path: str):
    """Duplicate → composite a background → flatten → downscale → save PNG.

    bg controls how transparency is shown (transparent art is INVISIBLE when
    flattened onto white — this is the whole reason the loop needs a background):
      auto    → checker if the image has alpha, else a plain flatten
      checker → grey transparency checkerboard (see the alpha like an editor does)
      black / white → solid backdrop (judge art as it'll sit on a dark/light shirt)
      none    → keep the alpha channel in the PNG (no backdrop)
    Returns (w, h, pw, ph, scale, mode).
    """
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    scale = min(1.0, max_dim / max(w, h))
    pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
    _SUSPEND["n"] += 1                      # scratch work — keep it out of the journal
    dup = bridge.eval(f"(car (gimp-image-duplicate {iid}))").strip()
    try:
        mode = str(bg).lower()
        if mode == "auto":
            d0 = bridge.eval(f"(car (gimp-image-get-active-drawable {dup}))").strip()
            has_alpha = _truthy(f"(car (gimp-drawable-has-alpha {d0}))")
            mode = "checker" if has_alpha else "flat"
        if mode in ("checker", "black", "white"):
            bl = bridge.eval(f'(car (gimp-layer-new {dup} {w} {h} RGB-IMAGE "bg" 100 LAYER-MODE-NORMAL))').strip()
            bridge.eval(f"(gimp-image-insert-layer {dup} {bl} 0 -1)")
            bridge.eval(f"(gimp-image-lower-item-to-bottom {dup} {bl})")
            bridge.eval(f"(gimp-image-set-active-layer {dup} {bl})")
            if mode == "checker":
                bridge.eval("(gimp-context-set-foreground '(153 153 153))")
                bridge.eval("(gimp-context-set-background '(102 102 102))")
                bridge.eval(f"(plug-in-checkerboard RUN-NONINTERACTIVE {dup} {bl} 0 {max(6, min(w, h)//24)})")
            else:
                bridge.eval(f"(gimp-context-set-foreground {_color('#ffffff' if mode == 'white' else '#000000')})")
                bridge.eval(f"(gimp-image-set-active-layer {dup} {bl})")
                bridge.eval(f"(gimp-drawable-fill {bl} FILL-FOREGROUND)")
        if mode != "none":
            bridge.eval(f"(gimp-image-flatten {dup})")
        if scale < 1.0:
            bridge.eval(f"(gimp-image-scale {dup} {pw} {ph})")
        d = bridge.eval(f"(car (gimp-image-get-active-drawable {dup}))").strip()
        bridge.eval(f'(file-png-save RUN-NONINTERACTIVE {dup} {d} "{_q(path)}" "l" 0 9 1 1 1 1 1)')
    finally:
        bridge.eval(f"(gimp-image-delete {dup})")
        _SUSPEND["n"] -= 1
    return w, h, pw, ph, scale, mode


@mcp.tool
def render_preview(image_id: int, max_dim: int = 640, bg: str = "auto") -> str:
    """Export a downscaled PNG of the image so Claude can SEE it, then Read the path.

    Returns the file path, preview dimensions, and the scale factor preview->original
    (image_coord = preview_coord / scale). `bg` controls how transparency is shown:
    auto | checker | black | white | none (see `look`). Prefer `look` for inline view.
    """
    iid = int(image_id)
    path = f"/tmp/gimp-preview-{iid}.png"
    w, h, pw, ph, scale, mode = _render(iid, max_dim, bg, path)
    return (f"{path}\norig={w}x{h}  preview={pw}x{ph}  scale={scale:.4f}  bg={mode}\n"
            f"(image_coord = preview_coord / {scale:.4f}) — Read the path to view it.")


_SHOWN = set()


@mcp.tool
def show(image_id: int) -> str:
    """Open this image in the GIMP WINDOW so a human can WATCH edits happen live.

    Only meaningful when the server was started with `--gui`
    (`./start-gimp-server.sh --gui`). First call opens a window; later calls just
    refresh it. In headless mode there is no display — this reports that and is
    otherwise harmless. Your own visual checks should still use `look` (works in
    both modes); `show` is for the human watching the GUI.
    """
    iid = int(image_id)
    try:
        with _suspend():
            if iid not in _SHOWN:
                bridge.eval(f"(gimp-display-new {iid})")
                _SHOWN.add(iid)
            bridge.eval("(gimp-displays-flush)")
        return f"image {iid} is live in the GIMP window — watch it update as tools run."
    except GimpError:
        return ("no display — you're running headless. Restart the server with "
                "`./start-gimp-server.sh --gui` to watch in a window. (`look` still works headless.)")


@mcp.tool
def suggest(image_id: int = -1) -> str:
    """Read the current image state and propose relevant next moves — the menu to
    show the user at each stage (see AGENTS.md). Advisory only; picks nothing.

    Pass an image id, or omit to use the first open image (e.g. the one the designer
    already has open in GIMP). Great for local models that don't know what's possible.
    """
    ids = bridge.eval("(vector->list (cadr (gimp-image-list)))").strip().strip("()").split()
    if not ids:
        return ("no images open.\n"
                "  · already working in GIMP? start the server in it (./start-gimp-server.sh --gui) "
                "and your open image shows up here\n"
                "  · or load_image(path) / new_image(w, h)")
    iid = int(image_id) if int(image_id) >= 0 else int(ids[0])
    with _suspend():
        w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
        h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
        nlayers = int(bridge.eval(f"(car (gimp-image-get-layers {iid}))").strip())
        d = _drawable(iid)
        alpha = _truthy(f"(car (gimp-drawable-has-alpha {d}))")
        fname = bridge.eval(f"(car (gimp-image-get-filename {iid}))").strip().strip('"')
        try:
            dpi = round(float(bridge.eval(f"(car (gimp-image-get-resolution {iid}))").strip()))
        except (GimpError, ValueError):
            dpi = 0
        tight = False
        if alpha:
            bridge.eval(f"(gimp-image-select-item {iid} CHANNEL-OP-REPLACE {d})")
            b = bridge.eval(f"(gimp-selection-bounds {iid})").strip().strip("()").split()
            bridge.eval(f"(gimp-selection-none {iid})")
            if b and b[0].upper() not in ("FALSE", "0", "#F"):
                tight = (int(b[3]) - int(b[1]) < w) or (int(b[4]) - int(b[2]) < h)

    tips = []
    if len(ids) > 1:
        tips.append(f"{len(ids)} images open — this is #{iid}; pass image_id to target another")
    tips.append("see it: `look` (checker/black/white bg) — or `show` to watch live in the GIMP window")
    if alpha and tight:
        tips.append("transparent margins around the art → `trim_to_content` before export")
    if alpha:
        tips.append("die-cut edge → apply_recipe('sticker-outline'); keep a hard bg out with `color_to_alpha`")
    if not alpha:
        tips.append("solid background → `color_to_alpha` to knock it out to transparency")
        tips.append("age it → apply_recipe('vintage'); grit text/art → apply_recipe('distressed-text')")
    tips.append("add a title → add_text(anchor='top-center') / place; badge arc → arc_text")
    if nlayers > 1:
        tips.append(f"{nlayers} layers → `merge_visible`, or `export_layers` to split them out")
    if not fname:
        tips.append("unsaved → `save_xcf` (keep layers) and/or `export_image` (flatten to PNG)")
    if dpi and dpi < 150 and max(w, h) < 2000:
        tips.append(f"low res for print ({w}x{h}@{dpi}dpi) → upscale (LoHalo) before a print export")
    tips.append("before any destructive/automated step: `checkpoint` first (it's the undo) — see AGENTS.md")
    head = f"image {iid}: {w}x{h}  layers={nlayers}  alpha={'yes' if alpha else 'no'}  {dpi or '?'}dpi  {'unsaved' if not fname else fname}"
    return head + "\noptions:\n" + "\n".join(f"  · {t}" for t in tips)


# ── LAYERS ───────────────────────────────────────────────────────────────────

@mcp.tool
def list_layers(image_id: int) -> str:
    """List the image's layers top→bottom with id, name, opacity, mode, position, visibility."""
    iid = int(image_id)
    ids = bridge.eval(f"(vector->list (cadr (gimp-image-get-layers {iid})))").strip().strip("()").split()
    if not ids:
        return "no layers"
    out = []
    for lid in ids:
        name = bridge.eval(f"(car (gimp-item-get-name {lid}))").strip().strip('"')
        op = bridge.eval(f"(car (gimp-layer-get-opacity {lid}))").strip()
        off = bridge.eval(f"(let ((o (gimp-drawable-offsets {lid}))) (string-append (number->string (car o)) \",\" (number->string (cadr o))))").strip().strip('"')
        vis = bridge.eval(f"(car (gimp-item-get-visible {lid}))").strip()
        out.append(f"id={lid}  '{name}'  opacity={op}%  pos=({off})  visible={vis}")
    return "\n".join(out)


@mcp.tool
def new_layer(image_id: int, name: str = "layer", opacity: float = 100.0,
              mode: str = "normal", transparent: bool = True) -> str:
    """Add a new (transparent by default) layer on top. Returns the layer id."""
    iid = int(image_id)
    w = bridge.eval(f"(car (gimp-image-width {iid}))").strip()
    h = bridge.eval(f"(car (gimp-image-height {iid}))").strip()
    fill = "RGBA-IMAGE" if transparent else "RGB-IMAGE"
    lid = bridge.eval(
        f'(car (gimp-layer-new {iid} {w} {h} {fill} "{_q(name)}" {float(opacity)} {_mode(mode)}))'
    ).strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {lid} 0 -1)")
    if transparent:
        bridge.eval(f"(gimp-image-set-active-layer {iid} {lid})")
        bridge.eval(f"(gimp-drawable-fill {lid} FILL-TRANSPARENT)")
    _flush()
    return f"added layer id={lid} ('{name}') to image {iid}"


@mcp.tool
def add_layer_from_file(image_id: int, path: str, x: int = 0, y: int = 0) -> str:
    """Load an image file as a new layer (a logo/photo on top) at offset (x,y). Returns layer id."""
    iid = int(image_id)
    lid = bridge.eval(f'(car (gimp-file-load-layer RUN-NONINTERACTIVE {iid} "{_q(path)}"))').strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {lid} 0 -1)")
    bridge.eval(f"(gimp-layer-set-offsets {lid} {int(x)} {int(y)})")
    _flush()
    return f"added layer id={lid} from {path} at ({x},{y})"


@mcp.tool
def set_layer(image_id: int, layer_id: int, opacity: float = None, mode: str = None,
              x: int = None, y: int = None, visible: bool = None) -> str:
    """Tune a layer: opacity (0-100), blend mode, position (x,y offsets), visibility. Omit to leave unchanged."""
    lid = int(layer_id)
    if opacity is not None:
        bridge.eval(f"(gimp-layer-set-opacity {lid} {float(opacity)})")
    if mode is not None:
        bridge.eval(f"(gimp-layer-set-mode {lid} {_mode(mode)})")
    if x is not None and y is not None:
        bridge.eval(f"(gimp-layer-set-offsets {lid} {int(x)} {int(y)})")
    if visible is not None:
        bridge.eval(f"(gimp-item-set-visible {lid} {'TRUE' if visible else 'FALSE'})")
    _flush()
    return f"updated layer {lid}"


@mcp.tool
def merge_visible(image_id: int) -> str:
    """Merge all visible layers into one (CLIP-TO-IMAGE). Returns the merged layer id."""
    lid = bridge.eval(f"(car (gimp-image-merge-visible-layers {int(image_id)} CLIP-TO-IMAGE))").strip()
    _flush()
    return f"merged visible layers of image {image_id} -> layer {lid}"


@mcp.tool
def delete_layer(image_id: int, layer_id: int) -> str:
    """Remove a layer from the image."""
    bridge.eval(f"(gimp-image-remove-layer {int(image_id)} {int(layer_id)})")
    _flush()
    return f"removed layer {layer_id}"


# ── TEXT ─────────────────────────────────────────────────────────────────────

@mcp.tool
def add_text(image_id: int, text: str, x: int = 20, y: int = 20, size: float = 48,
             color: str = "0,0,0", font: str = "Sans Bold", anchor: str = "") -> str:
    """Add a text layer. color is '#rrggbb' or 'r,g,b'. Returns the layer id + final bbox.

    Pass `anchor` (center | top-center | bottom-center | top-left | ... , same names as
    `place`) to auto-position the rendered text and ignore x/y — no need to measure the
    text first. Returns 'layer=<id> bbox=x,y,WxH' so you know exactly where it landed.
    """
    iid = int(image_id)
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    lid = bridge.eval(
        f'(car (gimp-text-fontname {iid} -1 {int(x)} {int(y)} "{_q(text)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
    ).strip()
    if anchor:
        _place_layer(iid, lid, anchor)
    lw = int(bridge.eval(f"(car (gimp-drawable-width {lid}))").strip())
    lh = int(bridge.eval(f"(car (gimp-drawable-height {lid}))").strip())
    off = bridge.eval(f"(gimp-drawable-offsets {lid})").strip().strip("()").split()
    _flush()
    return f"layer={lid} bbox={off[0]},{off[1]},{lw}x{lh}  '{text}'"


@mcp.tool
def list_fonts(keyword: str = "", limit: int = 40) -> str:
    """List available font names, optionally filtered by a case-insensitive substring."""
    raw = bridge.eval('(gimp-fonts-get-list ".*")')
    # returns (count #("Font A" "Font B" ...)) — pull quoted names
    import re
    names = re.findall(r'"([^"]*)"', raw)
    if keyword:
        names = [n for n in names if keyword.lower() in n.lower()]
    names = sorted(set(names))
    more = "" if len(names) <= limit else f"\n… (+{len(names)-limit} more)"
    return f"{len(names)} font(s):\n" + "\n".join(names[:limit]) + more


# ── TRANSFORMS ───────────────────────────────────────────────────────────────

@mcp.tool
def crop(image_id: int, width: int, height: int, x: int = 0, y: int = 0) -> str:
    """Crop the image to width x height starting at offset (x,y)."""
    bridge.eval(f"(gimp-image-crop {int(image_id)} {int(width)} {int(height)} {int(x)} {int(y)})")
    _flush()
    return f"cropped image {image_id} to {width}x{height} @ ({x},{y})"


@mcp.tool
def autocrop(image_id: int) -> str:
    """Auto-crop uniform borders off the image (e.g. trim solid-color margins)."""
    d = _drawable(image_id)
    bridge.eval(f"(plug-in-autocrop RUN-NONINTERACTIVE {int(image_id)} {d})")
    _flush()
    return f"autocropped image {image_id}"


@mcp.tool
def rotate(image_id: int, degrees: int) -> str:
    """Rotate the whole image. degrees must be 90, 180, or 270 (clockwise)."""
    m = {90: "ROTATE-90", 180: "ROTATE-180", 270: "ROTATE-270"}
    if int(degrees) not in m:
        return "degrees must be 90, 180, or 270 (use gimp_eval + gimp-item-transform-rotate for arbitrary angles)"
    bridge.eval(f"(gimp-image-rotate {int(image_id)} {m[int(degrees)]})")
    _flush()
    return f"rotated image {image_id} {degrees}°"


@mcp.tool
def flip(image_id: int, direction: str = "horizontal") -> str:
    """Flip the image 'horizontal' or 'vertical'."""
    o = "ORIENTATION-VERTICAL" if direction.lower().startswith("v") else "ORIENTATION-HORIZONTAL"
    bridge.eval(f"(gimp-image-flip {int(image_id)} {o})")
    _flush()
    return f"flipped image {image_id} {direction}"


@mcp.tool
def resize_canvas(image_id: int, width: int, height: int, x: int = 0, y: int = 0) -> str:
    """Resize the canvas (not the content) to width x height, offsetting existing layers by (x,y)."""
    bridge.eval(f"(gimp-image-resize {int(image_id)} {int(width)} {int(height)} {int(x)} {int(y)})")
    _flush()
    return f"resized canvas of image {image_id} to {width}x{height}"


# ── TONE / COLOR ─────────────────────────────────────────────────────────────

@mcp.tool
def hue_saturation(image_id: int, hue: float = 0, saturation: float = 0, lightness: float = 0) -> str:
    """Shift hue (-180..180), saturation (-100..100), lightness (-100..100) on the active drawable."""
    d = _drawable(image_id)
    bridge.eval(f"(gimp-drawable-hue-saturation {d} HUE-RANGE-ALL {float(hue)} {float(lightness)} {float(saturation)} 0)")
    _flush()
    return f"hue/sat adjusted image {image_id}"


@mcp.tool
def desaturate(image_id: int, mode: str = "luminosity") -> str:
    """Convert the active drawable to grayscale-in-RGB. mode: lightness|luma|average|luminosity|value."""
    d = _drawable(image_id)
    m = {"lightness": "DESATURATE-LIGHTNESS", "luma": "DESATURATE-LUMA",
         "average": "DESATURATE-AVERAGE", "luminosity": "DESATURATE-LUMINOSITY",
         "value": "DESATURATE-VALUE"}.get(mode.lower(), "DESATURATE-LUMINOSITY")
    bridge.eval(f"(gimp-drawable-desaturate {d} {m})")
    _flush()
    return f"desaturated image {image_id} ({mode})"


@mcp.tool
def invert(image_id: int) -> str:
    """Invert the colors of the active drawable."""
    bridge.eval(f"(gimp-drawable-invert {_drawable(image_id)} FALSE)")
    _flush()
    return f"inverted image {image_id}"


@mcp.tool
def auto_levels(image_id: int) -> str:
    """Auto-stretch contrast (white-balance-ish) on the active drawable."""
    d = _drawable(image_id)
    bridge.eval(f"(gimp-levels-stretch {d})")
    _flush()
    return f"auto-leveled image {image_id}"


@mcp.tool
def curves_adjust(image_id: int, channel: str = "value", points: str = "0,0 255,255") -> str:
    """Apply a curves adjustment. channel: value|red|green|blue|alpha. points: 'x,y x,y ...' (0-255).

    Example to brighten mids: '0,0 128,160 255,255'.
    """
    d = _drawable(image_id)
    ch = {"value": "HISTOGRAM-VALUE", "red": "HISTOGRAM-RED", "green": "HISTOGRAM-GREEN",
          "blue": "HISTOGRAM-BLUE", "alpha": "HISTOGRAM-ALPHA"}.get(channel.lower(), "HISTOGRAM-VALUE")
    # GIMP 2.10 gimp-curves-spline takes a flat vector of 0-255 int control points
    raw = []
    for pair in points.split():
        x, y = pair.split(",")
        raw.append(str(int(float(x))))
        raw.append(str(int(float(y))))
    bridge.eval(f"(gimp-curves-spline {d} {ch} {len(raw)} #({' '.join(raw)}))")
    _flush()
    return f"applied curves on {channel} for image {image_id}"


# ── FILTERS ──────────────────────────────────────────────────────────────────

@mcp.tool
def sharpen(image_id: int, amount: float = 0.5, radius: float = 3.0) -> str:
    """Unsharp-mask sharpen the active drawable. amount ~0.1-2.0, radius in px."""
    d = _drawable(image_id)
    bridge.eval(f"(plug-in-unsharp-mask RUN-NONINTERACTIVE {int(image_id)} {d} {float(radius)} {float(amount)} 0)")
    _flush()
    return f"sharpened image {image_id} (amount={amount}, radius={radius})"


@mcp.tool
def pixelize(image_id: int, block: int = 10) -> str:
    """Pixelate the active drawable with the given block size (px)."""
    d = _drawable(image_id)
    bridge.eval(f"(plug-in-pixelize RUN-NONINTERACTIVE {int(image_id)} {d} {int(block)})")
    _flush()
    return f"pixelized image {image_id} (block={block})"


@mcp.tool
def drop_shadow(image_id: int, offset_x: int = 8, offset_y: int = 8, blur: float = 15,
                color: str = "0,0,0", opacity: float = 80) -> str:
    """Add a drop shadow behind the active layer (script-fu-drop-shadow)."""
    d = _drawable(image_id)
    bridge.eval(
        f"(script-fu-drop-shadow {int(image_id)} {d} {int(offset_x)} {int(offset_y)} "
        f"{float(blur)} {_color(color)} {float(opacity)} TRUE)"
    )
    _flush()
    return f"added drop shadow to image {image_id}"


# ── SELECTION / FILL / SHAPES ────────────────────────────────────────────────

@mcp.tool
def select(image_id: int, shape: str = "rectangle", x: int = 0, y: int = 0,
           width: int = 100, height: int = 100) -> str:
    """Make a selection. shape: rectangle|ellipse|all|none. (x,y,width,height) for rect/ellipse."""
    iid = int(image_id)
    s = shape.lower()
    if s == "all":
        bridge.eval(f"(gimp-selection-all {iid})")
    elif s == "none":
        bridge.eval(f"(gimp-selection-none {iid})")
    elif s == "ellipse":
        bridge.eval(f"(gimp-image-select-ellipse {iid} CHANNEL-OP-REPLACE {int(x)} {int(y)} {int(width)} {int(height)})")
    else:
        bridge.eval(f"(gimp-image-select-rectangle {iid} CHANNEL-OP-REPLACE {int(x)} {int(y)} {int(width)} {int(height)})")
    _flush()
    return f"selection set ({shape}) on image {iid}"


@mcp.tool
def fill(image_id: int, color: str = "0,0,0") -> str:
    """Fill the current selection (or whole active drawable if none) with a color."""
    d = _drawable(image_id)
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    bridge.eval(f"(gimp-edit-fill {d} FILL-FOREGROUND)")
    _flush()
    return f"filled selection on image {image_id} with {color}"


@mcp.tool
def draw_rect(image_id: int, x: int, y: int, width: int, height: int,
             color: str = "0,0,0", fill_shape: bool = True) -> str:
    """Draw a filled rectangle on the active layer (selection-based fill, then deselect)."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(gimp-image-select-rectangle {iid} CHANNEL-OP-REPLACE {int(x)} {int(y)} {int(width)} {int(height)})")
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    bridge.eval(f"(gimp-edit-fill {d} FILL-FOREGROUND)")
    bridge.eval(f"(gimp-selection-none {iid})")
    _flush()
    return f"drew rectangle on image {iid} at ({x},{y}) {width}x{height}"


# ── FILE / SESSION ───────────────────────────────────────────────────────────

@mcp.tool
def save_xcf(image_id: int, path: str) -> str:
    """Save the full LAYERED image as a GIMP .xcf so the layer stack stays editable."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f'(gimp-xcf-save RUN-NONINTERACTIVE {iid} {d} "{_q(path)}" "{_q(os.path.basename(path))}")')
    return f"saved layered image {iid} -> {path}"


@mcp.tool
def export_layers(image_id: int, directory: str) -> str:
    """Export each layer as its own PNG (canvas-sized, position preserved) into `directory`."""
    iid = int(image_id)
    os.makedirs(directory, exist_ok=True)
    w = bridge.eval(f"(car (gimp-image-width {iid}))").strip()
    h = bridge.eval(f"(car (gimp-image-height {iid}))").strip()
    ids = bridge.eval(f"(vector->list (cadr (gimp-image-get-layers {iid})))").strip().strip("()").split()
    out = []
    for idx, lid in enumerate(ids):
        name = bridge.eval(f"(car (gimp-item-get-name {lid}))").strip().strip('"')
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name) or f"layer{idx}"
        path = os.path.join(directory, f"{idx:02d}_{safe}.png")
        tmp = bridge.eval(f"(car (gimp-image-new {w} {h} RGB))").strip()
        try:
            copy = bridge.eval(f"(car (gimp-layer-new-from-drawable {lid} {tmp}))").strip()
            bridge.eval(f"(gimp-image-insert-layer {tmp} {copy} 0 -1)")
            off = bridge.eval(f"(gimp-drawable-offsets {lid})").strip().strip("()").split()
            bridge.eval(f"(gimp-layer-set-offsets {copy} {off[0]} {off[1]})")
            bridge.eval(f"(gimp-image-flatten {tmp})")
            d = bridge.eval(f"(car (gimp-image-get-active-drawable {tmp}))").strip()
            bridge.eval(f'(file-png-save RUN-NONINTERACTIVE {tmp} {d} "{_q(path)}" "l" 0 9 1 1 1 1 1)')
            out.append(path)
        finally:
            bridge.eval(f"(gimp-image-delete {tmp})")
    return f"exported {len(out)} layer(s) to {directory}:\n" + "\n".join(out)


@mcp.tool
def close_image(image_id: int) -> str:
    """Delete an image from memory (free it). Does not touch any saved file."""
    bridge.eval(f"(gimp-image-delete {int(image_id)})")
    return f"closed image {image_id}"


# ═══ POWER TOOLS ═════════════════════════════════════════════════════════════

# ── auto-vision: render and return the image INLINE ──────────────────────────

@mcp.tool
def look(image_id: int, max_dim: int = 768, bg: str = "auto"):
    """Render the image and return it INLINE so you see it immediately (no Read step).

    Use this constantly: edit → look → judge → adjust. `bg` decides how transparency
    is shown — this matters because transparent art is INVISIBLE flattened on white:
      auto (default) → checkerboard if the image has alpha, else a plain flatten
      checker        → grey transparency checkerboard
      black / white  → composite on a solid backdrop (preview on a dark/light shirt)
      none           → keep the alpha (PNG with transparency)
    For exact coordinates/size use `describe`; for region brightness use `inspect`.
    """
    iid = int(image_id)
    path = f"/tmp/gimp-look-{iid}.png"
    _render(iid, max_dim, bg, path)
    return MCPImage(path=path)


@mcp.tool
def describe(image_id: int) -> str:
    """Structured metadata: dimensions, mode, precision, layer count, active-layer
    alpha, resolution (dpi), filename. Use for exact coordinates/sizes."""
    iid = int(image_id)
    w = bridge.eval(f"(car (gimp-image-width {iid}))").strip()
    h = bridge.eval(f"(car (gimp-image-height {iid}))").strip()
    base = bridge.eval(f"(car (gimp-image-base-type {iid}))").strip()
    mode = {"0": "RGB", "1": "GRAY", "2": "INDEXED"}.get(base, base)
    nlayers = bridge.eval(f"(car (gimp-image-get-layers {iid}))").strip()
    d = _drawable(iid)
    alpha = _truthy(f"(car (gimp-drawable-has-alpha {d}))")
    try:
        res = bridge.eval(f"(gimp-image-get-resolution {iid})").strip().strip("()").split()
        dpi = f"{float(res[0]):.0f}"
    except (GimpError, IndexError):
        dpi = "?"
    name = bridge.eval(f"(car (gimp-image-get-filename {iid}))").strip().strip('"') or "(unsaved)"
    return (f"image {iid}: {w}x{h}px  mode={mode}  layers={nlayers}  "
            f"active-alpha={'yes' if alpha else 'no'}  {dpi}dpi\n  file: {name}")


@mcp.tool
def inspect(image_id: int, x: int = 0, y: int = 0, width: int = 0, height: int = 0) -> str:
    """Measure a region's brightness/color (whole image if width/height omitted).

    Returns mean luminance, contrast (std-dev), and mean R/G/B (all 0-255), plus a
    placement hint (flat+dark → light text reads well; busy → avoid text there).
    Quantitative eyes for smart compositing.
    """
    iid = int(image_id)
    if width and height:
        bridge.eval(f"(gimp-image-select-rectangle {iid} CHANNEL-OP-REPLACE {int(x)} {int(y)} {int(width)} {int(height)})")
    d = _drawable(iid)

    def hist(channel):
        # gimp-drawable-histogram returns mean/std on a 0..255 scale here
        r = bridge.eval(f"(gimp-drawable-histogram {d} {channel} 0.0 1.0)").strip().strip("()").split()
        return float(r[0]), float(r[1])

    vmean, vstd = hist("HISTOGRAM-VALUE")
    rmean, _ = hist("HISTOGRAM-RED")
    gmean, _ = hist("HISTOGRAM-GREEN")
    bmean, _ = hist("HISTOGRAM-BLUE")
    if width and height:
        bridge.eval(f"(gimp-selection-none {iid})")
    norm_std = vstd / 255.0
    flat = ("flat (good for text)" if norm_std < 0.10
            else "moderate" if norm_std < 0.20 else "busy (avoid text)")
    textcol = "light/white text" if vmean < 128 else "dark/black text"
    region = f"region ({x},{y} {width}x{height})" if width and height else "whole image"
    return (f"{region}: luminance={vmean:.0f}/255  contrast(σ)={vstd:.0f}  "
            f"mean RGB=({rmean:.0f},{gmean:.0f},{bmean:.0f})\n"
            f"  → {flat}; if placing text here use {textcol}")


@mcp.tool
def gimp_batch(statements: list) -> str:
    """Run a list of Scheme statements in order, stopping at the first error.

    Returns each statement's result (or the error + which step failed). Fewer
    round-trips for multi-step composites, with per-step diagnostics.
    """
    out = []
    for i, st in enumerate(statements):
        try:
            r = bridge.eval(st)
            out.append(f"[{i}] ok: {r.strip()[:120]}")
        except GimpError as e:
            out.append(f"[{i}] ERROR in `{st[:80]}`: {e}")
            out.append(f"… stopped at step {i} of {len(statements)}")
            return "\n".join(out)
    bridge.eval("(gimp-displays-flush)")
    return "\n".join(out)


# ── experiment safely: immutable snapshots ───────────────────────────────────

@mcp.tool
def checkpoint(image_id: int) -> str:
    """Snapshot the image (an immutable hidden duplicate). Returns the snapshot id;
    pass it to `restore_checkpoint` to get a fresh working copy back."""
    snap = bridge.eval(f"(car (gimp-image-duplicate {int(image_id)}))").strip()
    return f"checkpoint snapshot id={snap} of image {image_id} (use restore_checkpoint({snap}))"


@mcp.tool
def restore_checkpoint(snapshot_id: int) -> str:
    """Duplicate a snapshot into a fresh working image. Returns the new image id."""
    work = bridge.eval(f"(car (gimp-image-duplicate {int(snapshot_id)}))").strip()
    return f"restored snapshot {snapshot_id} -> new working image id={work}"


# ── transforms & creative composites ─────────────────────────────────────────

@mcp.tool
def scale_to_fit(image_id: int, max_dim: int = 1600) -> str:
    """Resize so the longest side is max_dim, preserving aspect ratio."""
    iid = int(image_id)
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    s = min(1.0, max_dim / max(w, h))
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    bridge.eval(f"(gimp-image-scale {iid} {nw} {nh})")
    _flush()
    return f"scaled image {iid} to {nw}x{nh} (longest side {max_dim})"


@mcp.tool
def add_border(image_id: int, size: int = 20, color: str = "#ffffff") -> str:
    """Add a solid color border of `size` px around the image (grows the canvas)."""
    iid = int(image_id)
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    nw, nh = w + 2 * size, h + 2 * size
    bridge.eval(f"(gimp-image-resize {iid} {nw} {nh} {size} {size})")
    layer = bridge.eval(f'(car (gimp-layer-new {iid} {nw} {nh} RGB-IMAGE "border" 100 LAYER-MODE-NORMAL))').strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {layer} 0 -1)")
    bridge.eval(f"(gimp-image-lower-item-to-bottom {iid} {layer})")
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    bridge.eval(f"(gimp-image-set-active-layer {iid} {layer})")
    bridge.eval(f"(gimp-drawable-fill {layer} FILL-FOREGROUND)")
    bridge.eval(f"(gimp-image-flatten {iid})")
    _flush()
    return f"added {size}px {color} border to image {iid} (now {nw}x{nh})"


@mcp.tool
def gradient_fill(image_id: int, color1: str = "#000000", color2: str = "#ffffff",
                  direction: str = "vertical") -> str:
    """Fill the active drawable with a linear gradient from color1→color2.
    direction: vertical | horizontal | diagonal."""
    iid = int(image_id)
    d = _drawable(iid)
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    pts = {"horizontal": (0, h // 2, w, h // 2),
           "diagonal": (0, 0, w, h)}.get(direction.lower(), (w // 2, 0, w // 2, h))
    bridge.eval(f"(gimp-context-set-foreground {_color(color1)})")
    bridge.eval(f"(gimp-context-set-background {_color(color2)})")
    bridge.eval(
        f"(gimp-drawable-edit-gradient-fill {d} GRADIENT-LINEAR 0 FALSE 1 0 TRUE "
        f"{pts[0]} {pts[1]} {pts[2]} {pts[3]})"
    )
    _flush()
    return f"gradient {color1}->{color2} ({direction}) on image {iid}"


@mcp.tool
def vignette(image_id: int, strength: float = 60, feather: float = 0.0) -> str:
    """Darken the edges (vignette). strength 0-100 = corner darkness; feather px
    (0 = auto ~30% of the short side)."""
    iid = int(image_id)
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    feath = feather if feather > 0 else 0.30 * min(w, h)
    mx, my = int(0.12 * w), int(0.12 * h)
    layer = bridge.eval(f'(car (gimp-layer-new {iid} {w} {h} RGBA-IMAGE "vignette" 100 LAYER-MODE-NORMAL))').strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {layer} 0 -1)")
    bridge.eval(f"(gimp-image-set-active-layer {iid} {layer})")
    bridge.eval(f"(gimp-drawable-fill {layer} FILL-TRANSPARENT)")
    bridge.eval(f"(gimp-image-select-ellipse {iid} CHANNEL-OP-REPLACE {mx} {my} {w-2*mx} {h-2*my})")
    bridge.eval(f"(gimp-selection-invert {iid})")
    bridge.eval(f"(gimp-selection-feather {iid} {float(feath)})")
    bridge.eval("(gimp-context-set-foreground '(0 0 0))")
    bridge.eval(f"(gimp-image-set-active-layer {iid} {layer})")
    bridge.eval(f"(gimp-edit-fill {layer} FILL-FOREGROUND)")
    bridge.eval(f"(gimp-selection-none {iid})")
    bridge.eval(f"(gimp-layer-set-opacity {layer} {float(strength)})")
    _flush()
    return f"vignette (strength={strength}) added to image {iid} as a layer"


@mcp.tool
def outline_text(image_id: int, text: str, x: int = 20, y: int = 20, size: float = 72,
                 fill_color: str = "#ffffff", outline_color: str = "#000000",
                 outline_width: int = 3, font: str = "Sans Bold") -> str:
    """Add text with a colored outline (fill layer + grown-alpha outline layer beneath)."""
    iid = int(image_id)
    bridge.eval(f"(gimp-context-set-foreground {_color(fill_color)})")
    tid = bridge.eval(
        f'(car (gimp-text-fontname {iid} -1 {int(x)} {int(y)} "{_q(text)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
    ).strip()
    # outline layer beneath
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    ol = bridge.eval(f'(car (gimp-layer-new {iid} {w} {h} RGBA-IMAGE "outline" 100 LAYER-MODE-NORMAL))').strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {ol} 0 -1)")
    bridge.eval(f"(gimp-drawable-fill {ol} FILL-TRANSPARENT)")
    bridge.eval(f"(gimp-image-lower-item {iid} {ol})")  # put below the text layer
    bridge.eval(f"(gimp-image-select-item {iid} CHANNEL-OP-REPLACE {tid})")
    bridge.eval(f"(gimp-selection-grow {iid} {int(outline_width)})")
    bridge.eval(f"(gimp-context-set-foreground {_color(outline_color)})")
    bridge.eval(f"(gimp-image-set-active-layer {iid} {ol})")
    bridge.eval(f"(gimp-edit-fill {ol} FILL-FOREGROUND)")
    bridge.eval(f"(gimp-selection-none {iid})")
    _flush()
    return f"outlined text '{text}' (fill={fill_color}, outline={outline_color} {outline_width}px) on image {iid}"


@mcp.tool
def text_with_shadow(image_id: int, text: str, x: int = 20, y: int = 20, size: float = 72,
                     color: str = "#ffffff", font: str = "Sans Bold",
                     dx: int = 5, dy: int = 5, blur: float = 8) -> str:
    """Add a text layer with a soft drop shadow behind it."""
    iid = int(image_id)
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    tid = bridge.eval(
        f'(car (gimp-text-fontname {iid} -1 {int(x)} {int(y)} "{_q(text)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
    ).strip()
    bridge.eval(f"(gimp-image-set-active-layer {iid} {tid})")
    bridge.eval(f"(script-fu-drop-shadow {iid} {tid} {int(dx)} {int(dy)} {float(blur)} '(0 0 0) 80 TRUE)")
    _flush()
    return f"text '{text}' with drop shadow on image {iid}"


@mcp.tool
def overlay_blend(image_id: int, path: str, mode: str = "normal", opacity: float = 100,
                  x: int = 0, y: int = 0) -> str:
    """Load an image file as a layer with a blend mode + opacity (composite/texture)."""
    iid = int(image_id)
    lid = bridge.eval(f'(car (gimp-file-load-layer RUN-NONINTERACTIVE {iid} "{_q(path)}"))').strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {lid} 0 -1)")
    bridge.eval(f"(gimp-layer-set-offsets {lid} {int(x)} {int(y)})")
    bridge.eval(f"(gimp-layer-set-mode {lid} {_mode(mode)})")
    bridge.eval(f"(gimp-layer-set-opacity {lid} {float(opacity)})")
    _flush()
    return f"overlaid {path} as layer {lid} (mode={mode}, opacity={opacity}) on image {iid}"


# ── RICHER SELECTIONS ────────────────────────────────────────────────────────

@mcp.tool
def select_by_color(image_id: int, color: str, threshold: int = 15,
                    operation: str = "replace") -> str:
    """Select every pixel close to `color` (the magic-wand-by-color / keying primitive).

    threshold 0-255 = how far a pixel may differ and still be selected (higher = looser).
    operation: replace | add | subtract | intersect. Use this to key out a solid/near-solid
    background before deleting it, then `fill`/delete the selection.
    """
    iid = int(image_id)
    d = _drawable(iid)
    op = {"add": "CHANNEL-OP-ADD", "subtract": "CHANNEL-OP-SUBTRACT",
          "intersect": "CHANNEL-OP-INTERSECT"}.get(operation.lower(), "CHANNEL-OP-REPLACE")
    bridge.eval(f"(gimp-context-set-sample-threshold-int {int(threshold)})")
    bridge.eval(f"(gimp-image-select-color {iid} {op} {d} {_color(color)})")
    _flush()
    return f"selected color {color} (±{threshold}, {operation}) on image {iid}"


@mcp.tool
def feather_selection(image_id: int, radius: float = 10) -> str:
    """Feather (soften) the current selection edge by `radius` px."""
    iid = int(image_id)
    bridge.eval(f"(gimp-selection-feather {iid} {float(radius)})")
    _flush()
    return f"feathered selection by {radius}px on image {iid}"


@mcp.tool
def grow_shrink_selection(image_id: int, pixels: int) -> str:
    """Grow (pixels > 0) or shrink (pixels < 0) the current selection by |pixels| px."""
    iid = int(image_id)
    n = int(pixels)
    if n >= 0:
        bridge.eval(f"(gimp-selection-grow {iid} {n})")
        verb = "grew"
    else:
        bridge.eval(f"(gimp-selection-shrink {iid} {-n})")
        verb = "shrank"
    _flush()
    return f"{verb} selection by {abs(n)}px on image {iid}"


# ── PATHS / CURVED TEXT ──────────────────────────────────────────────────────

@mcp.tool
def arc_text(image_id: int, text: str, radius: float = 400, size: float = 100,
             font: str = "Sans Bold", color: str = "#ffffff",
             center_x: int = -1, center_y: int = -1, center_angle: float = 90,
             step_deg: float = 8, flip: bool = False) -> str:
    """Set text along a circular arc — the mission-patch / seal / badge primitive.

    Each glyph is rendered, rotated to sit radially, and placed on a circle of
    `radius` px around (center_x, center_y) — defaults to the image center. The band
    is centred on `center_angle` (math degrees: 90 = top arch ∩, 270 = bottom arch ∪)
    and consumes `step_deg` degrees per character. Set flip=True for a bottom arc so
    the letters read upright. All glyphs are composited into one returned layer so you
    can style it (outline_text-style) or distress it afterward.
    """
    import math
    iid = int(image_id)
    W = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    H = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    cx = W / 2 if center_x < 0 else center_x
    cy = H / 2 if center_y < 0 else center_y
    span = (len(text) - 1) * step_deg
    direction = -1 if flip else 1
    arc = bridge.eval(
        f'(car (gimp-layer-new {iid} {W} {H} RGBA-IMAGE "arc-text" 100 LAYER-MODE-NORMAL))'
    ).strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {arc} 0 -1)")
    bridge.eval(f"(gimp-drawable-fill {arc} FILL-TRANSPARENT)")
    bridge.eval("(gimp-context-set-transform-resize TRANSFORM-RESIZE-ADJUST)")
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        th = center_angle + direction * (span / 2 - i * step_deg)
        rad = math.radians(th)
        t = bridge.eval(
            f'(car (gimp-text-fontname {iid} -1 0 0 "{_q(ch)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
        ).strip()
        rot = math.radians(90 - th) + (math.pi if flip else 0)
        bridge.eval(f"(gimp-item-transform-rotate {t} {rot} TRUE 0 0)")
        gw = int(bridge.eval(f"(car (gimp-drawable-width {t}))").strip())
        gh = int(bridge.eval(f"(car (gimp-drawable-height {t}))").strip())
        px = int(cx + radius * math.cos(rad) - gw / 2)
        py = int(cy - radius * math.sin(rad) - gh / 2)
        bridge.eval(f"(gimp-layer-set-offsets {t} {px} {py})")
        # composite this glyph into the arc layer, then drop the temp text layer
        bridge.eval(f"(gimp-image-select-item {iid} CHANNEL-OP-REPLACE {t})")
        bridge.eval(f"(gimp-image-set-active-layer {iid} {arc})")
        bridge.eval(f"(gimp-edit-fill {arc} FILL-FOREGROUND)")
        bridge.eval(f"(gimp-image-remove-layer {iid} {t})")
    bridge.eval(f"(gimp-selection-none {iid})")
    _flush()
    return f"arc text '{text}' on layer {arc} (r={radius}, center_angle={center_angle}, image {iid})"


# ── MORE FX ──────────────────────────────────────────────────────────────────

@mcp.tool
def oilify(image_id: int, mask_size: int = 8, intensity: bool = False) -> str:
    """Oil-painting smear. mask_size 1-200 (bigger = broader strokes).
    intensity=True uses the intensity algorithm (crisper) vs RGB."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(plug-in-oilify RUN-NONINTERACTIVE {iid} {d} {int(mask_size)} {1 if intensity else 0})")
    _flush()
    return f"oilified image {iid} (mask_size={mask_size})"


@mcp.tool
def emboss(image_id: int, azimuth: float = 30, elevation: float = 45,
           depth: int = 20, bumpmap: bool = False) -> str:
    """Emboss the active drawable. azimuth = light angle°, elevation = light height°,
    depth = filter width. bumpmap=True keeps colors (bump) vs grayscale emboss."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(
        f"(plug-in-emboss RUN-NONINTERACTIVE {iid} {d} {float(azimuth)} {float(elevation)} "
        f"{int(depth)} {0 if bumpmap else 1})"
    )
    _flush()
    return f"embossed image {iid} (azimuth={azimuth}, elevation={elevation}, depth={depth})"


@mcp.tool
def lens_flare(image_id: int, x: int, y: int) -> str:
    """Add a lens-flare highlight centered at (x, y) px on the active drawable."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(plug-in-flarefx RUN-NONINTERACTIVE {iid} {d} {int(x)} {int(y)})")
    _flush()
    return f"lens flare at ({x},{y}) on image {iid}"


@mcp.tool
def motion_blur(image_id: int, length: float = 20, angle: float = 0,
                kind: str = "linear") -> str:
    """Directional motion blur. length = px, angle = 0-360°.
    kind: linear | radial | zoom (radial/zoom pivot on the image center)."""
    iid = int(image_id)
    d = _drawable(iid)
    t = {"radial": 1, "zoom": 2}.get(kind.lower(), 0)
    W = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    H = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    bridge.eval(
        f"(plug-in-mblur RUN-NONINTERACTIVE {iid} {d} {t} {float(length)} {float(angle)} "
        f"{W//2} {H//2})"
    )
    _flush()
    return f"motion blur ({kind}, length={length}, angle={angle}) on image {iid}"


# ── PLACEMENT / TRANSPARENCY (agent ergonomics) ──────────────────────────────

@mcp.tool
def place(image_id: int, anchor: str = "center", dx: int = 0, dy: int = 0,
          layer_id: int = -1, margin: int = 0) -> str:
    """Move a layer to a canvas anchor (gravity) — no manual width/height math.

    Collapses the get-size → compute-offset → set-offset round-trip into one call.
    anchor: center | top | bottom | left | right | top-left | top-right |
    bottom-left | bottom-right | top-center | bottom-center (etc). `dx`/`dy` nudge
    after anchoring; `margin` insets from the edges. layer_id defaults to the active
    layer. Ideal for titles, badges, watermarks, logo placement.
    """
    iid = int(image_id)
    lid = _drawable(iid) if int(layer_id) < 0 else int(layer_id)
    x, y = _place_layer(iid, lid, anchor, dx, dy, margin)
    _flush()
    return f"placed layer {lid} at '{anchor}' -> ({x},{y}) on image {iid}"


@mcp.tool
def color_to_alpha(image_id: int, color: str = "#ffffff") -> str:
    """Knock a color out to transparency on the active layer (native soft keying).

    Softer/cleaner than select-by-color+delete for solid or near-solid backgrounds —
    each pixel keeps a matching amount of alpha. The go-to for making print/sticker art
    transparent. Adds an alpha channel first if the layer lacks one.
    """
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(if (= (car (gimp-drawable-has-alpha {d})) FALSE) (gimp-image-set-active-layer {iid} {d}))")
    bridge.eval(f"(if (= (car (gimp-drawable-has-alpha {d})) FALSE) (gimp-layer-add-alpha {d}))")
    bridge.eval(f"(plug-in-colortoalpha RUN-NONINTERACTIVE {iid} {d} {_color(color)})")
    _flush()
    return f"keyed {color} -> alpha on image {iid}"


@mcp.tool
def trim_to_content(image_id: int) -> str:
    """Crop the canvas to the non-transparent bounding box of the active layer.

    Trims empty margins around transparent art before export (tighter print files,
    correct centering). No-op if the layer is fully opaque or fully empty.
    """
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(gimp-image-select-item {iid} CHANNEL-OP-REPLACE {d})")
    b = bridge.eval(f"(gimp-selection-bounds {iid})").strip().strip("()").split()
    bridge.eval(f"(gimp-selection-none {iid})")
    if not b or b[0].upper() in ("FALSE", "0", "#F"):
        return f"no content bounds on image {iid} (fully transparent or no alpha) — not trimmed"
    x1, y1, x2, y2 = int(b[1]), int(b[2]), int(b[3]), int(b[4])
    nw, nh = x2 - x1, y2 - y1
    bridge.eval(f"(gimp-image-crop {iid} {nw} {nh} {x1} {y1})")
    _flush()
    return f"trimmed image {iid} to content: {nw}x{nh} (was cropped from {x1},{y1})"


# ── RECIPES & JOURNAL: the power-user layer ──────────────────────────────────
# A recipe = a named, parameterized sequence of Scheme steps replayable on ANY
# image. Bundled recipes ship in <repo>/recipes/; user recipes live in
# ~/.config/gimp-mcp/recipes/ (override with $GIMP_MCP_RECIPES). Steps use:
#   $BINDINGS — runtime handles: $IMG $LAYER $W $H $CX $CY $RAND, plus anything a
#               step captures via its "bind" field (e.g. a new mask/layer id).
#   {params}  — user knobs with defaults; a param whose name contains "color" is
#               auto-converted from #hex / "r,g,b" to a Scheme color literal.

_BUNDLED_RECIPES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recipes")
_USER_RECIPES = os.path.expanduser(os.environ.get("GIMP_MCP_RECIPES", "~/.config/gimp-mcp/recipes"))


def _recipe_files() -> dict:
    """name -> path, user recipes overriding bundled ones of the same name."""
    found = {}
    for d in (_BUNDLED_RECIPES, _USER_RECIPES):
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            found[os.path.splitext(os.path.basename(p))[0]] = p
    return found


def _load_recipe(name: str) -> dict:
    files = _recipe_files()
    if name not in files:
        raise GimpError(f"no recipe '{name}'. Available: {', '.join(sorted(files)) or '(none)'}")
    with open(files[name]) as f:
        return json.load(f)


def _subst(scheme: str, env: dict, params: dict) -> str:
    for k in sorted(params, key=len, reverse=True):
        scheme = scheme.replace("{" + k + "}", str(params[k]))
    for k in sorted(env, key=len, reverse=True):
        scheme = scheme.replace("$" + k, str(env[k]))
    return scheme


@mcp.tool
def list_recipes() -> str:
    """List available recipes (bundled + your saved ones) with their tunable params."""
    files = _recipe_files()
    if not files:
        return "no recipes yet — apply a bundled one, or capture with save_recipe(from_journal=True)."
    out = []
    for name, path in sorted(files.items()):
        try:
            r = json.load(open(path))
            loc = "user" if path.startswith(_USER_RECIPES) else "bundled"
            ps = ", ".join(f"{k}={v}" for k, v in r.get("params", {}).items())
            out.append(f"{name} [{loc}] — {r.get('description', '')[:90]}" + (f"  (params: {ps})" if ps else ""))
        except Exception as e:
            out.append(f"{name} — (unreadable: {e})")
    return "\n".join(out)


@mcp.tool
def show_recipe(name: str) -> str:
    """Show a recipe's description, params, and its Scheme steps (for review/editing)."""
    r = _load_recipe(name)
    lines = [f"=== {name} ===", r.get("description", ""),
             f"params: {json.dumps(r.get('params', {}))}", "steps:"]
    for i, s in enumerate(r.get("steps", [])):
        pre = f"${s['bind']} = " if s.get("bind") else ""
        lines.append(f"  {i:2}: {pre}{s['scheme']}")
    return "\n".join(lines)


@mcp.tool
def apply_recipe(name: str, image_id: int, params: str = "{}", layer_id: int = -1) -> str:
    """Apply a saved recipe to an image — the power move. `params` is a JSON object of
    overrides (e.g. '{"grit": 60}'); omitted knobs use the recipe's defaults. Targets
    the active layer unless `layer_id` is given. Runtime handles ($IMG/$LAYER/$W/$H/…)
    are bound automatically. Recorded in the journal as a single high-level step.
    """
    iid = int(image_id)
    r = _load_recipe(name)
    knobs = dict(r.get("params", {}))
    try:
        knobs.update(json.loads(params) if isinstance(params, str) and params.strip() else (params or {}))
    except (ValueError, TypeError) as e:
        raise GimpError(f"params must be a JSON object like '{{\"grit\": 60}}' — got {params!r}: {e}")
    for k, v in list(knobs.items()):
        if "color" in k.lower() and isinstance(v, str) and not v.strip().startswith("'("):
            knobs[k] = _color(v)
    layer = _drawable(iid) if int(layer_id) < 0 else int(layer_id)
    W = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    H = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    env = {"IMG": iid, "LAYER": layer, "W": W, "H": H,
           "CX": W // 2, "CY": H // 2, "RAND": random.randint(1, 999999)}
    if _JOURNAL["on"]:
        _JOURNAL["ops"].append(f"; apply_recipe {name} {json.dumps(knobs)}")
    _SUSPEND["n"] += 1
    try:
        for step in r.get("steps", []):
            res = bridge.eval(_subst(step["scheme"], env, knobs))
            if step.get("bind"):
                tok = res.strip().strip("()").split()
                env[step["bind"]] = tok[0] if tok else res.strip()
    finally:
        _SUSPEND["n"] -= 1
    _flush()
    return f"applied '{name}' to image {iid} — {len(r.get('steps', []))} steps, params {json.dumps(knobs)}"


@mcp.tool
def save_recipe(name: str, description: str = "", from_journal: bool = True,
                image_id: int = -1, steps: str = "", params: str = "{}") -> str:
    """Save a reusable recipe to your user library (~/.config/gimp-mcp/recipes/).

    from_journal=True turns the ops you just ran (see `journal`) into a recipe: pass
    image_id so its handle becomes $IMG and its active layer becomes $LAYER. Other
    literal ids stay as-is — for multi-layer pipelines, `show_recipe` then edit the
    intermediate handles into $BINDINGs. Or author directly: steps=<JSON list of
    {"scheme": "...", "bind": "NAME"?}>, params=<JSON object of defaults>.
    """
    try:
        pdict = json.loads(params) if params and params.strip() else {}
    except ValueError as e:
        raise GimpError(f"params must be a JSON object: {e}")
    if steps:
        step_list = json.loads(steps)
    elif from_journal:
        raw = [s for s in _JOURNAL["ops"] if not s.strip().startswith(";")]
        if not raw:
            raise GimpError("journal is empty — run `journal start`, do some edits, then save_recipe.")
        step_list = [{"scheme": s} for s in raw]
        if int(image_id) >= 0:
            iid = int(image_id)
            lyr = str(_drawable(iid))
            for st in step_list:
                st["scheme"] = re.sub(rf"(?<![0-9]){iid}(?![0-9])", "$IMG", st["scheme"])
                st["scheme"] = re.sub(rf"(?<![0-9]){lyr}(?![0-9])", "$LAYER", st["scheme"])
    else:
        raise GimpError("nothing to save — set from_journal=True (with image_id) or pass steps=<JSON>.")
    os.makedirs(_USER_RECIPES, exist_ok=True)
    path = os.path.join(_USER_RECIPES, f"{name}.json")
    with open(path, "w") as f:
        json.dump({"name": name, "description": description, "params": pdict, "steps": step_list}, f, indent=2)
    return f"saved recipe '{name}' ({len(step_list)} steps) -> {path}"


@mcp.tool
def delete_recipe(name: str) -> str:
    """Delete a recipe from your user library. Bundled recipes can't be deleted."""
    path = os.path.join(_USER_RECIPES, f"{name}.json")
    if not os.path.exists(path):
        raise GimpError(f"no user recipe '{name}' at {path} (bundled recipes are read-only).")
    os.remove(path)
    return f"deleted user recipe '{name}'"


@mcp.tool
def journal(action: str = "show", label: str = "", path: str = "") -> str:
    """Record/replay the design ops you run — a macro recorder for the session.

    action:
      start  → begin recording (optional label); clears the previous log
      stop   → pause recording
      show   → list the recorded ops
      clear  → wipe the log
      script → write a standalone replay .py to `path` (default /tmp/gimp-journal.py)
    Pure queries and preview/export scratch are filtered out automatically, so the log
    reads like a recipe. Turn a recording into a reusable recipe with
    save_recipe(from_journal=True, image_id=<id>).
    """
    a = action.lower().strip()
    if a == "start":
        _JOURNAL.update(on=True, label=label, ops=[])
        return f"journal recording{f' [{label}]' if label else ''} — run your edits, then `journal show` / save_recipe."
    if a == "stop":
        _JOURNAL["on"] = False
        return f"journal paused — {len(_JOURNAL['ops'])} ops recorded."
    if a == "clear":
        _JOURNAL["ops"] = []
        return "journal cleared."
    if a == "show":
        ops = _JOURNAL["ops"]
        head = f"journal [{_JOURNAL['label']}]  recording={_JOURNAL['on']}  {len(ops)} ops"
        return head + (":\n" + "\n".join(f"{i:3}: {s}" for i, s in enumerate(ops)) if ops else " (empty)")
    if a == "script":
        p = path or "/tmp/gimp-journal.py"
        ops = [s for s in _JOURNAL["ops"] if not s.strip().startswith(";")]
        body = "\n".join(f"    ev({json.dumps(s)})" for s in ops) or "    pass"
        script = (
            "#!/usr/bin/env python3\n"
            '"""Replay of a gimp-mcp session. Start the Script-Fu server, load your\n'
            'source image, set IMG, then run. Generated by gimp-mcp `journal script`."""\n'
            "import os, sys\n"
            "sys.path.insert(0, os.path.expanduser('~/projects/gimp-mcp'))\n"
            "from gimp_bridge import GimpBridge\n"
            "b = GimpBridge(); ev = lambda s: b.eval(s).strip()\n"
            "IMG = 1  # <- set to your image id\n\n"
            "def run():\n" + body + "\n\n"
            "if __name__ == '__main__':\n    run()\n"
        )
        with open(p, "w") as f:
            f.write(script)
        return f"wrote replay script ({len(ops)} ops) -> {p}"
    raise GimpError(f"unknown action '{action}' — use start | stop | show | clear | script")


# ── KNOWLEDGE BASE: search the generated GIMP corpus in-session ───────────────

_KN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")


@mcp.tool
def gimp_docs(query: str, limit: int = 12) -> str:
    """Search the GIMP knowledge base (PDB blurbs + cookbook recipes) by keyword.

    Returns matching PDB procedures (name + blurb + arg names) and cookbook
    sections (file + heading). Use this to learn how to do something before
    reaching for gimp_eval. For an exact live signature use pdb_help instead.
    """
    q = query.lower().strip()
    out = []

    # 1. PDB procedures from pdb_full.json
    pj = os.path.join(_KN, "pdb_full.json")
    if os.path.exists(pj):
        import json
        data = json.load(open(pj))
        hits = []
        for name, p in data.get("procedures", {}).items():
            blurb = (p.get("blurb") or "")
            if q in name.lower() or q in blurb.lower():
                argnames = " ".join(a["name"] for a in p.get("args", []))
                hits.append((name, blurb.split("\n")[0].strip(), argnames))
        hits.sort(key=lambda h: (q not in h[0].lower(), len(h[0])))
        if hits:
            out.append(f"## PDB procedures ({len(hits)} match, showing {min(limit,len(hits))})")
            for name, blurb, argnames in hits[:limit]:
                out.append(f"- `{name}` ({argnames}) — {blurb}")

    # 2. cookbook headings
    cb = os.path.join(_KN, "cookbook")
    sec_hits = []
    if os.path.isdir(cb):
        for fn in sorted(os.listdir(cb)):
            if not fn.endswith(".md"):
                continue
            try:
                for line in open(os.path.join(cb, fn)):
                    s = line.strip()
                    if s.startswith("#") and q in s.lower():
                        sec_hits.append(f"- {fn} → {s.lstrip('# ').strip()}")
            except OSError:
                continue
    if sec_hits:
        out.append(f"\n## Cookbook sections ({len(sec_hits)})")
        out.extend(sec_hits[:limit])

    if not out:
        return (f"no matches for '{query}'. Try pdb_query('{query}') for a live PDB "
                f"name search, or browse knowledge/cookbook/.")
    out.append(f"\n(full reference: knowledge/pdb_index.md · cookbook/ · or pdb_help(name))")
    return "\n".join(out)


if __name__ == "__main__":
    mcp.run()
