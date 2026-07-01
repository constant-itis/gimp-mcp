"""pack: text — text layers, fonts, outlined/shadowed text, arc/badge text, placement."""
import math
import re
from _core import mcp, bridge, _q, _color, _drawable, _flush, _place_layer


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
    names = re.findall(r'"([^"]*)"', raw)
    if keyword:
        names = [n for n in names if keyword.lower() in n.lower()]
    names = sorted(set(names))
    more = "" if len(names) <= limit else f"\n… (+{len(names)-limit} more)"
    return f"{len(names)} font(s):\n" + "\n".join(names[:limit]) + more


@mcp.tool
def outline_text(image_id: int, text: str, x: int = 20, y: int = 20, size: float = 72,
                 fill_color: str = "#ffffff", outline_color: str = "#000000",
                 outline_width: int = 3, font: str = "Sans Bold", anchor: str = "") -> str:
    """Add text with a colored outline (fill layer + grown-alpha outline layer beneath).
    Pass `anchor` (center | top-center | … same as `place`) to auto-position, ignoring x/y."""
    iid = int(image_id)
    bridge.eval(f"(gimp-context-set-foreground {_color(fill_color)})")
    tid = bridge.eval(
        f'(car (gimp-text-fontname {iid} -1 {int(x)} {int(y)} "{_q(text)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
    ).strip()
    if anchor:
        _place_layer(iid, tid, anchor)
    w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    ol = bridge.eval(f'(car (gimp-layer-new {iid} {w} {h} RGBA-IMAGE "outline" 100 LAYER-MODE-NORMAL))').strip()
    bridge.eval(f"(gimp-image-insert-layer {iid} {ol} 0 -1)")
    bridge.eval(f"(gimp-drawable-fill {ol} FILL-TRANSPARENT)")
    bridge.eval(f"(gimp-image-lower-item {iid} {ol})")
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
                     dx: int = 5, dy: int = 5, blur: float = 8, anchor: str = "") -> str:
    """Add a text layer with a soft drop shadow behind it.
    Pass `anchor` (center | top-center | … same as `place`) to auto-position, ignoring x/y."""
    iid = int(image_id)
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    tid = bridge.eval(
        f'(car (gimp-text-fontname {iid} -1 {int(x)} {int(y)} "{_q(text)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
    ).strip()
    if anchor:
        _place_layer(iid, tid, anchor)
    bridge.eval(f"(gimp-image-set-active-layer {iid} {tid})")
    bridge.eval(f"(script-fu-drop-shadow {iid} {tid} {int(dx)} {int(dy)} {float(blur)} '(0 0 0) 80 TRUE)")
    _flush()
    return f"text '{text}' with drop shadow on image {iid}"


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
        bridge.eval(f"(gimp-image-select-item {iid} CHANNEL-OP-REPLACE {t})")
        bridge.eval(f"(gimp-image-set-active-layer {iid} {arc})")
        bridge.eval(f"(gimp-edit-fill {arc} FILL-FOREGROUND)")
        bridge.eval(f"(gimp-image-remove-layer {iid} {t})")
    bridge.eval(f"(gimp-selection-none {iid})")
    _flush()
    return f"arc text '{text}' on layer {arc} (r={radius}, center_angle={center_angle}, image {iid})"


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
