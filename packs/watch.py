"""pack: watch — human-in-the-loop tools: show the image in the GIMP window, and
suggest context-aware next moves. See ../AGENTS.md for the interfacing conventions."""
from _core import mcp, bridge, GimpError, _drawable, _truthy, _suspend

_SHOWN = set()


@mcp.tool
def show(image_id: int) -> str:
    """Open this image in the GIMP WINDOW so a human can WATCH edits happen live.

    Only meaningful when the server was started with `--gui`
    (`./start-gimp-server.sh --gui`). First call opens a window; later calls just
    refresh it. In headless mode there is no display — this reports that and is
    otherwise harmless. Your own visual checks should still use `look` (works in
    both modes); `show` is for the human watching the GUI.
    """
    iid = int(image_id)
    try:
        with _suspend():
            if iid not in _SHOWN:
                bridge.eval(f"(gimp-display-new {iid})")
                _SHOWN.add(iid)
            bridge.eval("(gimp-displays-flush)")
        return f"image {iid} is live in the GIMP window — watch it update as tools run."
    except GimpError:
        return ("no display — you're running headless. Restart the server with "
                "`./start-gimp-server.sh --gui` to watch in a window. (`look` still works headless.)")


@mcp.tool
def suggest(image_id: int = -1) -> str:
    """Read the current image state and propose relevant next moves — the menu to
    show the user at each stage (see AGENTS.md). Advisory only; picks nothing.

    Pass an image id, or omit to use the first open image (e.g. the one the designer
    already has open in GIMP). Great for local models that don't know what's possible.
    """
    ids = bridge.eval("(vector->list (cadr (gimp-image-list)))").strip().strip("()").split()
    if not ids:
        return ("no images open.\n"
                "  · already working in GIMP? start the server in it (./start-gimp-server.sh --gui) "
                "and your open image shows up here\n"
                "  · or load_image(path) / new_image(w, h)")
    iid = int(image_id) if int(image_id) >= 0 else int(ids[0])
    with _suspend():
        w = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
        h = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
        nlayers = int(bridge.eval(f"(car (gimp-image-get-layers {iid}))").strip())
        d = _drawable(iid)
        alpha = _truthy(f"(car (gimp-drawable-has-alpha {d}))")
        fname = bridge.eval(f"(car (gimp-image-get-filename {iid}))").strip().strip('"')
        try:
            dpi = round(float(bridge.eval(f"(car (gimp-image-get-resolution {iid}))").strip()))
        except (GimpError, ValueError):
            dpi = 0
        tight = False
        if alpha:
            bridge.eval(f"(gimp-image-select-item {iid} CHANNEL-OP-REPLACE {d})")
            b = bridge.eval(f"(gimp-selection-bounds {iid})").strip().strip("()").split()
            bridge.eval(f"(gimp-selection-none {iid})")
            if b and b[0].upper() not in ("FALSE", "0", "#F"):
                tight = (int(b[3]) - int(b[1]) < w) or (int(b[4]) - int(b[2]) < h)

    tips = []
    if len(ids) > 1:
        tips.append(f"{len(ids)} images open — this is #{iid}; pass image_id to target another")
    tips.append("see it: `look` (checker/black/white bg) — or `show` to watch live in the GIMP window")
    if alpha and tight:
        tips.append("transparent margins around the art → `trim_to_content` before export")
    if alpha:
        tips.append("die-cut edge → apply_recipe('sticker-outline'); keep a hard bg out with `color_to_alpha`")
    if not alpha:
        tips.append("solid background → `color_to_alpha` to knock it out to transparency")
        tips.append("age it → apply_recipe('vintage'); grit text/art → apply_recipe('distressed-text')")
    tips.append("add a title → add_text(anchor='top-center') / place; badge arc → arc_text")
    if nlayers > 1:
        tips.append(f"{nlayers} layers → `merge_visible`, or `export_layers` to split them out")
    if not fname:
        tips.append("unsaved → `save_xcf` (keep layers) and/or `export_image` (flatten to PNG)")
    if dpi and dpi < 150 and max(w, h) < 2000:
        tips.append(f"low res for print ({w}x{h}@{dpi}dpi) → upscale (LoHalo) before a print export")
    tips.append("before any destructive/automated step: `checkpoint` first (it's the undo) — see AGENTS.md")
    head = f"image {iid}: {w}x{h}  layers={nlayers}  alpha={'yes' if alpha else 'no'}  {dpi or '?'}dpi  {'unsaved' if not fname else fname}"
    return head + "\noptions:\n" + "\n".join(f"  · {t}" for t in tips)
