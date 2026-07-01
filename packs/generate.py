"""pack: generate — draw & CREATE imagery from scratch (not just edit).

Vector/procedural primitives an agent composes into original art, checking each move
with `look`: ellipses, arbitrary polygons, stars, lines, radial sunbursts, and
procedural texture (plasma nebulae, cloud/solid noise). The building blocks for the
draw → look → refine loop.
"""
import math
from _core import mcp, bridge, _color, _drawable, _flush


def _poly_select(iid, art, pts, color, fill_shape, line_width):
    """Select a polygon from a flat [x0,y0,x1,y1,...] list and fill or stroke it."""
    flat = " ".join(str(round(v, 2)) for v in pts)
    bridge.eval(f"(gimp-image-select-polygon {iid} CHANNEL-OP-REPLACE {len(pts)} #({flat}))")
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    if fill_shape:
        bridge.eval(f"(gimp-edit-fill {art} FILL-FOREGROUND)")
    else:
        bridge.eval(f"(gimp-context-set-line-width {int(line_width)})")
        bridge.eval(f"(gimp-drawable-edit-stroke-selection {art})")
    bridge.eval(f"(gimp-selection-none {iid})")


@mcp.tool
def draw_ellipse(image_id: int, x: int, y: int, width: int, height: int,
                 color: str = "#000000", fill_shape: bool = True, line_width: int = 3) -> str:
    """Draw an ellipse in the bounding box (x,y,width,height). fill_shape=True fills it;
    False strokes an outline `line_width` px thick."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(gimp-image-select-ellipse {iid} CHANNEL-OP-REPLACE {int(x)} {int(y)} {int(width)} {int(height)})")
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
    return f"drew {how} ellipse on image {iid} at ({x},{y}) {width}x{height}"


@mcp.tool
def draw_polygon(image_id: int, points: str, color: str = "#000000",
                 fill_shape: bool = True, line_width: int = 3) -> str:
    """Draw an arbitrary polygon. `points` is 'x,y x,y x,y ...' (>=3 vertices); the shape
    auto-closes. fill_shape=True fills, False strokes an outline. The general 2D shape tool
    — triangles, arrows, mountains, banners, crystals, anything."""
    iid = int(image_id)
    d = _drawable(iid)
    pts = []
    for pair in points.split():
        xs, ys = pair.split(",")
        pts += [float(xs), float(ys)]
    if len(pts) < 6:
        return "need at least 3 points (e.g. '100,100 200,100 150,200')"
    _poly_select(iid, d, pts, color, fill_shape, line_width)
    _flush()
    return f"drew {'filled' if fill_shape else 'outlined'} {len(pts)//2}-gon on image {iid}"


@mcp.tool
def draw_star(image_id: int, cx: int, cy: int, points: int = 5, outer: int = 100,
              inner: int = 45, color: str = "#000000", rotation: float = 0,
              fill_shape: bool = True, line_width: int = 3) -> str:
    """Draw an n-pointed star centered at (cx,cy). `outer`/`inner` are the point/valley
    radii; `rotation` in degrees. Great for badges, ratings, sparkles, insignia."""
    iid = int(image_id)
    d = _drawable(iid)
    pts = []
    for i in range(int(points) * 2):
        r = outer if i % 2 == 0 else inner
        a = math.radians(rotation - 90 + i * 180.0 / int(points))
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    _poly_select(iid, d, pts, color, fill_shape, line_width)
    _flush()
    return f"drew {points}-point star at ({cx},{cy}) r={outer}/{inner} on image {iid}"


@mcp.tool
def draw_line(image_id: int, x1: int, y1: int, x2: int, y2: int,
              color: str = "#000000", width: int = 3) -> str:
    """Stroke a straight line from (x1,y1) to (x2,y2), `width` px, on the active layer."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    bridge.eval(f"(gimp-context-set-line-width {int(width)})")
    bridge.eval(f"(gimp-pencil {d} 4 (list->vector (list {int(x1)} {int(y1)} {int(x2)} {int(y2)})))")
    _flush()
    return f"drew line ({x1},{y1})->({x2},{y2}) w={width} on image {iid}"


@mcp.tool
def sunburst(image_id: int, cx: int, cy: int, rays: int = 12, radius: int = 600,
             color: str = "#ffcc33", rotation: float = 0) -> str:
    """Draw a radial sunburst — `rays` filled wedges radiating from (cx,cy) out to
    `radius`, with equal gaps. Retro poster / emblem backdrop staple."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    step = 360.0 / int(rays)
    half = step / 2.0
    for i in range(int(rays)):
        a = math.radians(rotation + i * step)
        a1, a2 = a - math.radians(half / 2), a + math.radians(half / 2)
        pts = [cx, cy,
               cx + radius * math.cos(a1), cy + radius * math.sin(a1),
               cx + radius * math.cos(a2), cy + radius * math.sin(a2)]
        flat = " ".join(str(round(v, 2)) for v in pts)
        bridge.eval(f"(gimp-image-select-polygon {iid} CHANNEL-OP-REPLACE 6 #({flat}))")
        bridge.eval(f"(gimp-edit-fill {d} FILL-FOREGROUND)")
    bridge.eval(f"(gimp-selection-none {iid})")
    _flush()
    return f"drew {rays}-ray sunburst at ({cx},{cy}) r={radius} on image {iid}"


@mcp.tool
def render_plasma(image_id: int, turbulence: float = 2.5, seed: int = 42) -> str:
    """Fill the active drawable with procedural plasma (marbled nebula/cloud colour field).
    turbulence ~0.1-7 (higher = more chaotic). A from-scratch texture/background source."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(f"(plug-in-plasma RUN-NONINTERACTIVE {iid} {d} {int(seed)} {float(turbulence)})")
    _flush()
    return f"rendered plasma (turbulence={turbulence}, seed={seed}) on image {iid}"


@mcp.tool
def render_noise(image_id: int, detail: int = 3, size: float = 4.0,
                 turbulent: bool = False, seed: int = 42, tileable: bool = False) -> str:
    """Fill the active drawable with solid/cloud noise (grayscale). detail 1-15, size 0.1-16
    (bigger = larger blobs), turbulent=True for wispy marble. Use as clouds, smoke, a bump
    source, or colorize it afterward."""
    iid = int(image_id)
    d = _drawable(iid)
    bridge.eval(
        f"(plug-in-solid-noise RUN-NONINTERACTIVE {iid} {d} {1 if tileable else 0} "
        f"{1 if turbulent else 0} {int(seed)} {int(detail)} {float(size)} {float(size)})"
    )
    _flush()
    return f"rendered solid noise (detail={detail}, size={size}) on image {iid}"
