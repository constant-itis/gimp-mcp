"""pack: layers — create / list / tune / merge / export layers, save .xcf, close."""
import os
from _core import mcp, bridge, GimpError, _q, _mode, _drawable, _flush


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
