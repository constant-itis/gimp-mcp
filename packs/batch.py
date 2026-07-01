"""pack: batch — process whole FOLDERS of images. GIMP's automation superpower:
resize/convert/watermark a directory, or apply any saved recipe to every file. This is
what turns the tool from 'edit one image' into 'run a production pipeline'."""
import os
import glob
from _core import mcp, bridge, GimpError, _q, _color, _drawable, _place_layer, _suspend


def _images(folder, pattern):
    folder = os.path.expanduser(folder)
    files = []
    for p in pattern.split(","):
        files += glob.glob(os.path.join(folder, p.strip()))
    return sorted(f for f in set(files) if os.path.isfile(f))


def _load(path):
    return int(bridge.eval(
        f'(car (gimp-file-load RUN-NONINTERACTIVE "{_q(path)}" "{_q(os.path.basename(path))}"))'
    ).strip())


def _save(img, path):
    """Alpha-preserving save (merge, not flatten) unless the format has no alpha."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".bmp", ".pnm", ".ppm"):
        bridge.eval(f"(gimp-image-flatten {img})")
    else:
        bridge.eval(f"(gimp-image-merge-visible-layers {img} CLIP-TO-IMAGE)")
    d = bridge.eval(f"(car (gimp-image-get-active-drawable {img}))").strip()
    bridge.eval(f'(gimp-file-save RUN-NONINTERACTIVE {img} {d} "{_q(path)}" "{_q(os.path.basename(path))}")')


def _run(folder, pattern, out_folder, suffix, op):
    """Common loop: load → op(img) → save to out_folder → free. Returns a summary."""
    files = _images(folder, pattern)
    if not files:
        return f"no images in {folder} matching '{pattern}'"
    out = os.path.expanduser(out_folder) if out_folder else os.path.join(os.path.expanduser(folder), suffix)
    os.makedirs(out, exist_ok=True)
    done, errs = [], []
    with _suspend():
        for f in files:
            try:
                img = _load(f)
                try:
                    op(img)
                    _save(img, os.path.join(out, os.path.basename(f)))
                    done.append(os.path.basename(f))
                finally:
                    bridge.eval(f"(gimp-image-delete {img})")
            except GimpError as e:
                errs.append(f"{os.path.basename(f)}: {e}")
    msg = f"processed {len(done)}/{len(files)} → {out}"
    if errs:
        msg += "\nerrors:\n  " + "\n  ".join(errs[:8])
    return msg


@mcp.tool
def batch_resize(folder: str, max_dim: int = 1600, out_folder: str = "",
                 pattern: str = "*.png,*.jpg,*.jpeg") -> str:
    """Scale every image in `folder` so its longest side is `max_dim` (aspect preserved).
    Writes to out_folder (default <folder>/resized)."""
    def op(img):
        w = int(bridge.eval(f"(car (gimp-image-width {img}))").strip())
        h = int(bridge.eval(f"(car (gimp-image-height {img}))").strip())
        s = min(1.0, max_dim / max(w, h))
        bridge.eval("(gimp-context-set-interpolation INTERPOLATION-LOHALO)")
        bridge.eval(f"(gimp-image-scale {img} {max(1, round(w*s))} {max(1, round(h*s))})")
    return _run(folder, pattern, out_folder, "resized", op)


@mcp.tool
def batch_convert(folder: str, to: str = "png", out_folder: str = "",
                  pattern: str = "*.*") -> str:
    """Convert every image in `folder` to a new format (png/jpg/webp/tiff/…). Writes to
    out_folder (default <folder>/<to>). Alpha preserved for formats that support it."""
    to = to.lstrip(".").lower()
    files = _images(folder, pattern)
    if not files:
        return f"no images in {folder} matching '{pattern}'"
    out = os.path.expanduser(out_folder) if out_folder else os.path.join(os.path.expanduser(folder), to)
    os.makedirs(out, exist_ok=True)
    done, errs = [], []
    with _suspend():
        for f in files:
            try:
                img = _load(f)
                try:
                    stem = os.path.splitext(os.path.basename(f))[0]
                    _save(img, os.path.join(out, f"{stem}.{to}"))
                    done.append(stem)
                finally:
                    bridge.eval(f"(gimp-image-delete {img})")
            except GimpError as e:
                errs.append(f"{os.path.basename(f)}: {e}")
    return f"converted {len(done)}/{len(files)} → {out}" + (("\nerrors:\n  " + "\n  ".join(errs[:8])) if errs else "")


@mcp.tool
def batch_watermark(folder: str, text: str, size: float = 40, color: str = "#ffffff",
                    opacity: float = 45, anchor: str = "bottom-right", margin: int = 30,
                    font: str = "Sans Bold", out_folder: str = "",
                    pattern: str = "*.png,*.jpg,*.jpeg") -> str:
    """Stamp a semi-transparent text watermark on every image in `folder`. anchor +
    margin place it (bottom-right default). Writes to out_folder (default <folder>/watermarked)."""
    def op(img):
        bridge.eval(f"(gimp-context-set-foreground {_color(color)})")
        t = int(bridge.eval(
            f'(car (gimp-text-fontname {img} -1 0 0 "{_q(text)}" 0 TRUE {float(size)} UNIT-PIXEL "{_q(font)}"))'
        ).strip())
        _place_layer(img, t, anchor, margin=int(margin))
        bridge.eval(f"(gimp-layer-set-opacity {t} {float(opacity)})")
    return _run(folder, pattern, out_folder, "watermarked", op)


@mcp.tool
def batch_recipe(name: str, folder: str, params: str = "{}", out_folder: str = "",
                 pattern: str = "*.png,*.jpg,*.jpeg") -> str:
    """Apply a saved recipe (see the recipes pack) to EVERY image in `folder` — bulk
    distress/vintage/sticker/etc. Writes to out_folder (default <folder>/<recipe>)."""
    import json
    import random
    from packs.recipes import _load_recipe, _subst
    recipe = _load_recipe(name)
    knobs = dict(recipe.get("params", {}))
    try:
        knobs.update(json.loads(params) if params and params.strip() else {})
    except ValueError as e:
        raise GimpError(f"params must be JSON: {e}")
    for k, v in list(knobs.items()):
        if "color" in k.lower() and isinstance(v, str) and not v.strip().startswith("'("):
            knobs[k] = _color(v)

    def op(img):
        layer = _drawable(img)
        W = int(bridge.eval(f"(car (gimp-image-width {img}))").strip())
        H = int(bridge.eval(f"(car (gimp-image-height {img}))").strip())
        env = {"IMG": img, "LAYER": layer, "W": W, "H": H,
               "CX": W // 2, "CY": H // 2, "RAND": random.randint(1, 999999)}
        for step in recipe.get("steps", []):
            res = bridge.eval(_subst(step["scheme"], env, knobs))
            if step.get("bind"):
                tok = res.strip().strip("()").split()
                env[step["bind"]] = tok[0] if tok else res.strip()
    return _run(folder, pattern, out_folder, name, op)


@mcp.tool
def contact_sheet(folder: str, out_path: str = "", cols: int = 4, thumb: int = 320,
                  pattern: str = "*.png,*.jpg,*.jpeg") -> str:
    """Build a grid contact sheet of every image in `folder` (labels underneath).
    Writes out_path (default <folder>/contact-sheet.png)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return "contact_sheet needs Pillow (pip install pillow)"
    files = _images(folder, pattern)
    if not files:
        return f"no images in {folder} matching '{pattern}'"
    out = os.path.expanduser(out_path) if out_path else os.path.join(os.path.expanduser(folder), "contact-sheet.png")
    pad, label_h = 14, 22
    rows = (len(files) + cols - 1) // cols
    cw, ch = thumb + pad, thumb + pad + label_h
    sheet = Image.new("RGB", (cols * cw + pad, rows * ch + pad), (26, 26, 30))
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        r, c = divmod(i, cols)
        x0, y0 = pad + c * cw, pad + r * ch
        try:
            im = Image.open(f).convert("RGB"); im.thumbnail((thumb, thumb))
            sheet.paste(im, (x0 + (thumb - im.width) // 2, y0 + (thumb - im.height) // 2))
        except Exception:
            draw.rectangle([x0, y0, x0 + thumb, y0 + thumb], outline=(90, 60, 60))
        draw.text((x0, y0 + thumb + 4), os.path.basename(f)[:28], fill=(210, 210, 210))
    sheet.save(out)
    return f"contact sheet of {len(files)} images → {out}"
