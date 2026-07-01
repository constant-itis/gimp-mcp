"""pack: select — selections, fill/rect, color-key + feather/grow, transparency ops."""
from _core import mcp, bridge, _color, _drawable, _flush


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
             color: str = "0,0,0", fill_shape: bool = True, line_width: int = 3) -> str:
    """Draw a rectangle on the active layer. fill_shape=True fills it; False strokes an
    outline `line_width` px thick. Selection-based, then deselected."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(gimp-image-select-rectangle {iid} CHANNEL-OP-REPLACE {int(x)} {int(y)} {int(width)} {int(height)})")
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    if fill_shape:
        bridge.eval(f"(gimp-edit-fill {d} FILL-FOREGROUND)")
        how = "filled"
    else:
        bridge.eval(f"(gimp-context-set-line-width {int(line_width)})")
        bridge.eval(f"(gimp-drawable-edit-stroke-selection {d})")
        how = f"outlined ({line_width}px)"
    bridge.eval(f"(gimp-selection-none {iid})")
    _flush()
    return f"drew {how} rectangle on image {iid} at ({x},{y}) {width}x{height}"


@mcp.tool
def erase(image_id: int) -> str:
    """Clear the current selection to transparency (whole active layer if no selection).

    Adds an alpha channel first if the layer lacks one — the cut-a-hole / knockout
    primitive for punching transparent gaps into art (orbit rings, windows, negative space).
    """
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(if (= (car (gimp-drawable-has-alpha {d})) FALSE) (gimp-layer-add-alpha {d}))")
    bridge.eval(f"(gimp-edit-clear {d})")
    _flush()
    return f"cleared selection to transparency on image {iid}"


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
