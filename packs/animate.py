"""pack: animate — turn layers or a folder of frames into an animated GIF. GIMP's
layers-as-frames model, exposed: motion graphics, spinners, blinking badges, sequences."""
import os
import glob
from _core import mcp, bridge, GimpError, _q, _suspend


def _export_gif(img, path, delay, loop):
    """Convert a copy to indexed and gif-save its layers as frames."""
    dup = bridge.eval(f"(car (gimp-image-duplicate {img}))").strip()
    try:
        bridge.eval(f"(gimp-image-convert-indexed {dup} CONVERT-DITHER-NONE CONVERT-PALETTE-GENERATE 255 FALSE FALSE \"\")")
        d = bridge.eval(f"(car (gimp-image-get-active-drawable {dup}))").strip()
        bridge.eval(
            f'(file-gif-save RUN-NONINTERACTIVE {dup} {d} "{_q(path)}" "{_q(os.path.basename(path))}" '
            f"0 {'TRUE' if loop else 'FALSE'} {int(delay)} 2)"
        )
    finally:
        bridge.eval(f"(gimp-image-delete {dup})")


@mcp.tool
def frames_to_gif(image_id: int, path: str, delay: int = 120, loop: bool = True) -> str:
    """Export the image's LAYERS as an animated GIF (each layer = one frame, bottom→top).
    `delay` = ms per frame. Build the frames as layers, then call this."""
    iid = int(image_id)
    n = int(bridge.eval(f"(car (gimp-image-get-layers {iid}))").strip())
    if n < 2:
        return f"image {iid} has {n} layer(s) — add layers (one per frame) before exporting a GIF"
    with _suspend():
        _export_gif(iid, os.path.expanduser(path), delay, loop)
    return f"exported {n}-frame GIF ({delay}ms/frame, loop={loop}) → {path}"


@mcp.tool
def gif_from_folder(folder: str, path: str, delay: int = 120, loop: bool = True,
                    pattern: str = "*.png") -> str:
    """Build an animated GIF from a folder of frame images (sorted by name). Each file
    becomes a frame. `delay` = ms per frame."""
    folder = os.path.expanduser(folder)
    files = sorted(f for p in pattern.split(",") for f in glob.glob(os.path.join(folder, p.strip())))
    if len(files) < 2:
        return f"need >=2 frames in {folder} matching '{pattern}' (found {len(files)})"
    with _suspend():
        base = int(bridge.eval(f'(car (gimp-file-load RUN-NONINTERACTIVE "{_q(files[0])}" "f"))').strip())
        for f in files[1:]:
            lay = int(bridge.eval(f'(car (gimp-file-load-layer RUN-NONINTERACTIVE {base} "{_q(f)}"))').strip())
            bridge.eval(f"(gimp-image-insert-layer {base} {lay} 0 -1)")
        # layers load top-first; reverse so frame order matches filename order
        bridge.eval(
            f"(let loop ((ls (vector->list (cadr (gimp-image-get-layers {base}))))) "
            f"(if (pair? ls) (begin (gimp-image-lower-item-to-bottom {base} (car ls)) (loop (cdr ls)))))"
        )
        try:
            _export_gif(base, os.path.expanduser(path), delay, loop)
        finally:
            bridge.eval(f"(gimp-image-delete {base})")
    return f"built {len(files)}-frame GIF ({delay}ms/frame) → {path}"


@mcp.tool
def spin_gif(image_id: int, path: str, frames: int = 12, delay: int = 80,
             layer_id: int = -1) -> str:
    """Render a spinning-rotation GIF of a layer: `frames` copies each rotated a step
    further around a full turn. Great for loaders/badges/logos. The source image should be
    square with the subject centered."""
    iid = int(image_id)
    import math
    src = int(layer_id) if int(layer_id) >= 0 else int(bridge.eval(f"(car (gimp-image-get-active-drawable {iid}))").strip())
    W = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    H = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    with _suspend():
        anim = int(bridge.eval(f"(car (gimp-image-new {W} {H} RGB))").strip())
        for i in range(int(frames)):
            lay = int(bridge.eval(f"(car (gimp-layer-new-from-drawable {src} {anim}))").strip())
            bridge.eval(f"(gimp-image-insert-layer {anim} {lay} 0 -1)")
            bridge.eval(f'(gimp-item-set-name {lay} "f{i}")')
            if i:
                bridge.eval("(gimp-context-set-interpolation INTERPOLATION-CUBIC)")
                bridge.eval("(gimp-context-set-transform-resize TRANSFORM-RESIZE-CLIP)")
                bridge.eval(f"(gimp-item-transform-rotate {lay} {i * 2 * math.pi / int(frames)} TRUE 0 0)")
        try:
            _export_gif(anim, os.path.expanduser(path), delay, True)
        finally:
            bridge.eval(f"(gimp-image-delete {anim})")
    return f"rendered {frames}-frame spin GIF ({delay}ms/frame) → {path}"
