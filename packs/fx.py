"""pack: fx — blur/sharpen/pixelize, drop-shadow, vignette, oilify, emboss, lens-flare,
motion-blur, gradient fill, border, overlay-blend."""
from _core import mcp, bridge, _q, _color, _mode, _drawable, _flush


@mcp.tool
def gaussian_blur(image_id: int, radius: float = 5.0) -> str:
    """Apply a Gaussian blur of the given radius (px) to the active drawable."""
    d = _drawable(image_id)
    bridge.eval(f"(plug-in-gauss RUN-NONINTERACTIVE {int(image_id)} {d} {float(radius)} {float(radius)} 0)")
    _flush()
    return f"blurred image {image_id} radius={radius}"


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
