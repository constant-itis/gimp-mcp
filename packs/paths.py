"""pack: paths — real vector bezier curves. Draw smooth flowing lines/shapes through
anchor points (auto-computed control points), stroke or fill them. The illustration
primitive gimp-mcp was missing — waves, ribbons, organic outlines, swashes."""
from _core import mcp, bridge, _color, _drawable, _flush


def _catmull_bezier(anchors, closed):
    """Anchors [(x,y),...] → bezier control array in the proc's CACC… order
    (in-ctrl, anchor, out-ctrl per point) using a Catmull-Rom tangent."""
    n = len(anchors)
    ctrl = []
    for i in range(n):
        p = anchors[i]
        if closed:
            prv, nxt = anchors[(i - 1) % n], anchors[(i + 1) % n]
        else:
            prv = anchors[i - 1] if i > 0 else anchors[i]
            nxt = anchors[i + 1] if i < n - 1 else anchors[i]
        tx, ty = (nxt[0] - prv[0]) / 6.0, (nxt[1] - prv[1]) / 6.0
        ctrl += [p[0] - tx, p[1] - ty, p[0], p[1], p[0] + tx, p[1] + ty]  # Cin, A, Cout
    return ctrl


def _parse(points):
    pts = []
    for pair in points.split():
        xs, ys = pair.split(",")
        pts.append((float(xs), float(ys)))
    return pts


@mcp.tool
def draw_curve(image_id: int, points: str, color: str = "#000000", width: int = 4,
               closed: bool = False, fill_shape: bool = False) -> str:
    """Draw a SMOOTH bezier curve flowing through the anchor points 'x,y x,y x,y ...'
    (>=2). closed=True joins the ends; fill_shape=True fills the enclosed area instead of
    stroking `width` px. For waves, ribbons, swashes, organic blobs and outlines."""
    iid = int(image_id)
    d = _drawable(iid)
    anchors = _parse(points)
    if len(anchors) < 2:
        return "need at least 2 anchor points (e.g. '100,300 300,150 500,300')"
    ctrl = _catmull_bezier(anchors, closed)
    flat = " ".join(str(round(v, 2)) for v in ctrl)
    v = int(bridge.eval(f'(car (gimp-vectors-new {iid} "curve"))').strip())
    bridge.eval(f"(gimp-image-insert-vectors {iid} {v} 0 -1)")
    bridge.eval(f"(gimp-vectors-stroke-new-from-points {v} 0 {len(ctrl)} #({flat}) {'TRUE' if closed else 'FALSE'})")
    bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
    if fill_shape:
        bridge.eval(f"(gimp-image-select-item {iid} CHANNEL-OP-REPLACE {v})")
        bridge.eval(f"(gimp-edit-fill {d} FILL-FOREGROUND)")
        bridge.eval(f"(gimp-selection-none {iid})")
        how = "filled"
    else:
        bridge.eval(f"(gimp-context-set-line-width {int(width)})")
        bridge.eval(f"(gimp-context-set-line-cap-style CAP-ROUND)")
        bridge.eval(f"(gimp-context-set-line-join-style JOIN-ROUND)")
        bridge.eval(f"(gimp-drawable-edit-stroke-item {d} {v})")
        how = f"stroked ({width}px)"
    bridge.eval(f"(gimp-image-remove-vectors {iid} {v})")
    _flush()
    return f"drew {how} curve through {len(anchors)} points on image {iid}"
