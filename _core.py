#!/usr/bin/env python3
"""
gimp-mcp core — the substrate every pack builds on.

This is the "mycelium" layer: the raw escape hatch (`gimp_eval`) + PDB
introspection so the *entire* GIMP procedure database is reachable, the vision
loop (`look`/`describe`/`inspect`), basic image IO, and safety (`checkpoint`).
With just these you can already do anything; packs (packs/*.py) add ergonomic
tools on top and are loaded on demand by server.py.

Shared infra exported for packs to import:
    mcp, bridge, GimpError, MCPImage,
    _q, _color, _mode, _drawable, _truthy, _flush, _place_layer, _render,
    _JOURNAL, _SUSPEND, _suspend, KNOWLEDGE_DIR
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
from fastmcp import FastMCP
from fastmcp.utilities.types import Image as MCPImage
from gimp_bridge import GimpBridge, GimpError

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(HERE, "knowledge")
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
# reads like the recipe you'd hand-write, not socket noise. (The `journal` tool
# lives in packs/journal.py; the state + hook live here because _smart_eval needs them.)
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


# ── shared helpers (packs import these) ──────────────────────────────────────

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


# ═══ CORE TOOLS ══════════════════════════════════════════════════════════════
# raw eval + introspection: the whole PDB reachable from three tools.

@mcp.tool
def gimp_eval(scheme: str) -> str:
    """Evaluate a raw Script-Fu (Scheme) expression against GIMP's full PDB.

    This is the escape hatch — any GIMP operation can be done here. Returns the
    printed result, or raises with GIMP's error text. Image/drawable handles are
    integers. Example: '(gimp-image-width 1)' or '(gimp-image-scale 1 800 600)'.
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


# ── image IO ─────────────────────────────────────────────────────────────────

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


@mcp.tool
def export_image(image_id: int, path: str, flatten: bool = False) -> str:
    """Export a copy of the image to `path` (format from the extension).

    Transparency is PRESERVED by default (the layers are merged, not flattened) so
    PNG/WebP/etc. keep their alpha — important for cut-out / sticker / print art.
    Set flatten=True to composite onto the background first. Formats without an alpha
    channel (JPEG/BMP) are always flattened. The original image is left untouched.
    """
    ext = os.path.splitext(path)[1].lower()
    no_alpha_fmt = ext in (".jpg", ".jpeg", ".bmp", ".pnm", ".ppm", ".pgm")
    with _suspend():
        dup = bridge.eval(f"(car (gimp-image-duplicate {int(image_id)}))").strip()
        try:
            if flatten or no_alpha_fmt:
                bridge.eval(f"(gimp-image-flatten {dup})")
            else:
                bridge.eval(f"(gimp-image-merge-visible-layers {dup} CLIP-TO-IMAGE)")
            d = bridge.eval(f"(car (gimp-image-get-active-drawable {dup}))").strip()
            bridge.eval(
                f'(gimp-file-save RUN-NONINTERACTIVE {dup} {d} "{_q(path)}" "{_q(os.path.basename(path))}")'
            )
        finally:
            bridge.eval(f"(gimp-image-delete {dup})")
    kept = "flattened" if (flatten or no_alpha_fmt) else "alpha preserved"
    return f"exported image {image_id} -> {path} ({kept})"


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


# ── batch + safety ───────────────────────────────────────────────────────────

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


@mcp.tool
def checkpoint(image_id: int) -> str:
    """Snapshot the image (an immutable hidden duplicate). Returns the snapshot id;
    pass it to `restore_checkpoint` to get a fresh working copy back. GIMP 2.10 has
    no API undo — this snapshot IS the undo. Take one before destructive/automated steps."""
    with _suspend():
        snap = bridge.eval(f"(car (gimp-image-duplicate {int(image_id)}))").strip()
    return f"checkpoint snapshot id={snap} of image {image_id} (use restore_checkpoint({snap}))"


@mcp.tool
def restore_checkpoint(snapshot_id: int) -> str:
    """Duplicate a snapshot into a fresh working image. Returns the new image id."""
    with _suspend():
        work = bridge.eval(f"(car (gimp-image-duplicate {int(snapshot_id)}))").strip()
    return f"restored snapshot {snapshot_id} -> new working image id={work}"


# ── knowledge base: search the generated GIMP corpus in-session ──────────────

@mcp.tool
def gimp_docs(query: str, limit: int = 12) -> str:
    """Search the GIMP knowledge base (PDB blurbs + cookbook recipes) by keyword.

    Returns matching PDB procedures (name + blurb + arg names) and cookbook
    sections (file + heading). Use this to learn how to do something before
    reaching for gimp_eval. For an exact live signature use pdb_help instead.
    """
    import json
    q = query.lower().strip()
    out = []
    pj = os.path.join(KNOWLEDGE_DIR, "pdb_full.json")
    if os.path.exists(pj):
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
    cb = os.path.join(KNOWLEDGE_DIR, "cookbook")
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
    out.append("\n(full reference: knowledge/pdb_index.md · cookbook/ · or pdb_help(name))")
    return "\n".join(out)
