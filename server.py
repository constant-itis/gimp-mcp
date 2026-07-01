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


def _flush():
    bridge.eval("(gimp-displays-flush)")


# ── VISION: the keystone preview loop ────────────────────────────────────────

@mcp.tool
def render_preview(image_id: int, max_dim: int = 640) -> str:
    """Export a flattened, downscaled PNG of the image so Claude can SEE it.

    Returns the file path (read it with the Read tool to view), the preview
    dimensions, and the scale factor preview->original. Use this to look before
    and after edits, and to map preview coordinates back to image coordinates
    (image_coord = preview_coord / scale). This is how visual judgement works.
    """
    iid = int(image_id)
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    scale = min(1.0, max_dim / max(w, h))
    pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
    path = f"/tmp/gimp-preview-{iid}.png"
    dup = bridge.eval(f"(car (gimp-image-duplicate {iid}))").strip()
    try:
        bridge.eval(f"(gimp-image-flatten {dup})")
        if scale < 1.0:
            bridge.eval(f"(gimp-image-scale {dup} {pw} {ph})")
        d = bridge.eval(f"(car (gimp-image-get-active-drawable {dup}))").strip()
        bridge.eval(f'(file-png-save RUN-NONINTERACTIVE {dup} {d} "{_q(path)}" "prev" 0 9 1 1 1 1 1)')
    finally:
        bridge.eval(f"(gimp-image-delete {dup})")
    return (f"{path}\norig={w}x{h}  preview={pw}x{ph}  scale={scale:.4f}\n"
            f"(image_coord = preview_coord / {scale:.4f}) — Read the path to view it.")


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
             color: str = "0,0,0", font: str = "Sans Bold") -> str:
    """Add a text layer at (x,y). color is '#rrggbb' or 'r,g,b'. Returns the text layer id.

    Render a preview afterward to check placement/legibility, then nudge with set_layer.
    """
    iid = int(image_id)
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    lid = bridge.eval(
        f'(car (gimp-text-fontname {iid} -1 {int(x)} {int(y)} "{_q(text)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
    ).strip()
    _flush()
    return f"added text layer id={lid}: '{text}' at ({x},{y})"


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
def look(image_id: int, max_dim: int = 768):
    """Render the image and return it INLINE so you see it immediately (no Read step).

    Flattens a copy, downscales to max_dim, returns the PNG as image content.
    Use this constantly: edit → look → judge → adjust. For numeric coordinates/size
    use `describe`; for region brightness use `inspect`.
    """
    iid = int(image_id)
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    scale = min(1.0, max_dim / max(w, h))
    pw, ph = max(1, round(w * scale)), max(1, round(h * scale))
    path = f"/tmp/gimp-look-{iid}.png"
    dup = bridge.eval(f"(car (gimp-image-duplicate {iid}))").strip()
    try:
        bridge.eval(f"(gimp-image-flatten {dup})")
        if scale < 1.0:
            bridge.eval(f"(gimp-image-scale {dup} {pw} {ph})")
        d = bridge.eval(f"(car (gimp-image-get-active-drawable {dup}))").strip()
        bridge.eval(f'(file-png-save RUN-NONINTERACTIVE {dup} {d} "{_q(path)}" "l" 0 9 1 1 1 1 1)')
    finally:
        bridge.eval(f"(gimp-image-delete {dup})")
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
    alpha = bridge.eval(f"(car (gimp-drawable-has-alpha {d}))").strip()
    try:
        res = bridge.eval(f"(gimp-image-get-resolution {iid})").strip().strip("()").split()
        dpi = f"{float(res[0]):.0f}"
    except (GimpError, IndexError):
        dpi = "?"
    name = bridge.eval(f"(car (gimp-image-get-filename {iid}))").strip().strip('"') or "(unsaved)"
    return (f"image {iid}: {w}x{h}px  mode={mode}  layers={nlayers}  "
            f"active-alpha={'yes' if alpha=='TRUE' else 'no'}  {dpi}dpi\n  file: {name}")


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
