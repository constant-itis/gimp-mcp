"""pack: transform — scale, crop, autocrop, rotate, flip, canvas resize, fit."""
from _core import mcp, bridge, _drawable, _flush


@mcp.tool
def scale_image(image_id: int, width: int, height: int) -> str:
    """Resize an image to width x height pixels (in place)."""
    bridge.eval(f"(gimp-image-scale {int(image_id)} {int(width)} {int(height)})")
    _flush()
    return f"scaled image {image_id} to {width}x{height}"


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
