#!/usr/bin/env python3
"""
teach/factory.py — the demonstration factory.

The Opus→Fable move: a capable model (me) manufactures a *verified* corpus of worked
examples that teaches a smaller / local model (Hermes, Qwen, a fine-tune) to drive
gimp-mcp well. Each task spec is executed against a LIVE GIMP, the exact tool-call
trace is recorded, the result is rendered + sanity-checked, and the whole thing is
distilled into:
  teach/demos.jsonl       — one verified trace per task (fine-tune / eval ready)
  teach/fewshot.md        — readable worked examples (prompt a small model with these)
  teach/contact-sheet.png — a grid of every rendered result (proof it runs)

A task spec is data (JSON-able), so subagents can author them without touching code:
  {
    "id": "gold-title",
    "task": "one-sentence natural-language brief",
    "steps": [
      {"tool": "new_image", "args": {"width": 1200, "height": 400}, "capture": "IMG"},
      {"tool": "fill",       "args": {"image_id": "$IMG", "color": "#14141f"}},
      {"tool": "outline_text","args": {"image_id": "$IMG", "text": "APOLLO", ...}}
    ]
  }
$NAME placeholders resolve from a step's `capture` (the first id=/layer= int in its
result). Run:  python3 teach/factory.py   (needs the Script-Fu server up)
"""
import os
import re
import sys
import json
import asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import _core
# load every bundled pack so the factory's registry matches the live tool surface
for _p in ("layers", "text", "transform", "color", "fx", "select",
           "generate", "paths", "batch", "animate", "recipes", "journal", "watch"):
    __import__(f"packs.{_p}")
from _core import mcp, bridge, _render  # noqa: E402

TOOLS = {t.name: t.fn for t in asyncio.run(mcp._list_tools()) if hasattr(t, "fn")}
OUT = os.path.join(HERE, "out")
SPECS_DIR = os.path.join(HERE, "specs")     # subagent-authored specs land here
_ID_RE = re.compile(r"(?:id|layer)=(\d+)")


def _resolve(val, env):
    """Substitute $NAME placeholders using captured ids."""
    if isinstance(val, str):
        if val.startswith("$") and val[1:] in env:
            return env[val[1:]]
        if "$" in val:
            return re.sub(r"\$([A-Z_]+)", lambda m: str(env.get(m.group(1), m.group(0))), val)
    return val


def run_spec(spec: dict) -> dict:
    """Execute one task spec against live GIMP; record the trace + render a preview."""
    env, trace, err = {}, [], None
    for step in spec.get("steps", []):
        tool = step["tool"]
        args = {k: _resolve(v, env) for k, v in step.get("args", {}).items()}
        if tool not in TOOLS:
            err = f"unknown tool '{tool}'"
            break
        try:
            result = TOOLS[tool](**args)
        except Exception as e:                      # a spec that fails is a data point, not a crash
            err = f"{type(e).__name__}: {e}"
            trace.append({"tool": tool, "args": args, "error": err})
            break
        result = str(result)
        trace.append({"tool": tool, "args": args, "result": result[:300]})
        if step.get("capture"):
            m = _ID_RE.search(result)
            if m:
                env[step["capture"]] = int(m.group(1))
    # render the final image (prefer an explicitly captured IMG, else the newest open image)
    img = env.get("IMG")
    if img is None:
        ids = bridge.eval("(vector->list (cadr (gimp-image-list)))").strip().strip("()").split()
        img = int(ids[0]) if ids else None
    preview = None
    if img is not None and err is None:
        os.makedirs(OUT, exist_ok=True)
        preview = os.path.join(OUT, f"{spec['id']}.png")
        try:
            _render(img, 512, "auto", preview)
        except Exception as e:
            err = err or f"render failed: {e}"
            preview = None
    # free the image so the factory doesn't pile up open images
    if img is not None:
        try:
            bridge.eval(f"(gimp-image-delete {img})")
        except Exception:
            pass
    return {"id": spec["id"], "task": spec["task"], "trace": trace,
            "verified": err is None, "error": err, "preview": preview}


# ── SEED CURRICULUM (hand-authored by Opus; known-good) ──────────────────────
SEED = [
    {"id": "gold-title", "task": "On a fresh 1200x400 dark canvas, set a centered gold "
     "title 'APOLLO' with a heavy dark outline.", "steps": [
        {"tool": "new_image", "args": {"width": 1200, "height": 400}, "capture": "IMG"},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#14141f"}},
        {"tool": "outline_text", "args": {"image_id": "$IMG", "text": "APOLLO", "x": 250, "y": 110,
                                          "size": 180, "fill_color": "#ffce5a",
                                          "outline_color": "#160a04", "outline_width": 8}},
     ]},
    {"id": "distressed-headline", "task": "Weathered/distressed amber headline 'RENEGADE' "
     "centered on a dark canvas.", "steps": [
        {"tool": "new_image", "args": {"width": 1200, "height": 400}, "capture": "IMG"},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#101018"}},
        {"tool": "add_text", "args": {"image_id": "$IMG", "text": "RENEGADE", "size": 150,
                                      "color": "#ffb020", "anchor": "center"}},
        {"tool": "apply_recipe", "args": {"name": "distressed-text", "image_id": "$IMG",
                                          "params": "{\"grit\": 78}"}},
     ]},
    {"id": "mission-patch", "task": "A round Apollo-style mission patch: a blue planet in the "
     "centre with 'THE EAGLE HAS LANDED' arched over the top and 'APOLLO XI' along the bottom.",
     "steps": [
        {"tool": "new_image", "args": {"width": 1000, "height": 1000}, "capture": "IMG"},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#0b0b14"}},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "ellipse", "x": 320, "y": 320,
                                    "width": 360, "height": 360}},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#3a5f9f"}},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "none"}},
        {"tool": "arc_text", "args": {"image_id": "$IMG", "text": "THE EAGLE HAS LANDED",
                                      "radius": 430, "size": 66, "center_angle": 90,
                                      "step_deg": 7.4, "color": "#ffce5a"}},
        {"tool": "arc_text", "args": {"image_id": "$IMG", "text": "APOLLO XI", "radius": 430,
                                      "size": 64, "center_angle": 270, "step_deg": 9,
                                      "flip": True, "color": "#ffce5a"}},
     ]},
    {"id": "cutout-logo", "task": "Turn a solid-white-background graphic into a trimmed "
     "transparent PNG (cut it out).", "steps": [
        {"tool": "new_image", "args": {"width": 600, "height": 600}, "capture": "IMG"},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "ellipse", "x": 160, "y": 150,
                                    "width": 300, "height": 300}},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#c0392b"}},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "none"}},
        {"tool": "color_to_alpha", "args": {"image_id": "$IMG", "color": "#ffffff"}},
        {"tool": "trim_to_content", "args": {"image_id": "$IMG"}},
        {"tool": "export_image", "args": {"image_id": "$IMG", "path": "/tmp/teach_cutout.png"}},
     ]},
    {"id": "vintage-gradient", "task": "Give a colourful gradient an aged, faded vintage-photo "
     "treatment.", "steps": [
        {"tool": "new_image", "args": {"width": 800, "height": 600}, "capture": "IMG"},
        {"tool": "gradient_fill", "args": {"image_id": "$IMG", "color1": "#8fb0d0",
                                           "color2": "#d08040", "direction": "diagonal"}},
        {"tool": "apply_recipe", "args": {"name": "vintage", "image_id": "$IMG"}},
     ]},
    {"id": "die-cut-sticker", "task": "Make a die-cut sticker: a coloured blob on transparency "
     "with a thick white edge and soft shadow.", "steps": [
        {"tool": "new_image", "args": {"width": 600, "height": 600}, "capture": "IMG"},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "ellipse", "x": 140, "y": 160,
                                    "width": 320, "height": 260}},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#2d7dd2"}},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "none"}},
        {"tool": "color_to_alpha", "args": {"image_id": "$IMG", "color": "#ffffff"}},
        {"tool": "apply_recipe", "args": {"name": "sticker-outline", "image_id": "$IMG"}},
     ]},
    {"id": "watermark", "task": "Add a subtle bottom-right copyright watermark over a gradient.",
     "steps": [
        {"tool": "new_image", "args": {"width": 1000, "height": 600}, "capture": "IMG"},
        {"tool": "gradient_fill", "args": {"image_id": "$IMG", "color1": "#20303a",
                                           "color2": "#4a6a7a", "direction": "vertical"}},
        {"tool": "add_text", "args": {"image_id": "$IMG", "text": "© STUDIO", "size": 44,
                                      "color": "#ffffff", "anchor": "bottom-right"}, "capture": "WM"},
        {"tool": "set_layer", "args": {"image_id": "$IMG", "layer_id": "$WM", "opacity": 32}},
     ]},
    {"id": "neon-title", "task": "A glowing neon title 'NEON' centered on near-black.", "steps": [
        {"tool": "new_image", "args": {"width": 1000, "height": 420}, "capture": "IMG"},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#0a0a12"}},
        {"tool": "text_with_shadow", "args": {"image_id": "$IMG", "text": "NEON", "size": 190,
                                              "color": "#38f0e0", "anchor": "center", "blur": 22}},
     ]},
]


def load_specs():
    """Seed curriculum + any subagent-authored specs in teach/specs/*.json."""
    specs = list(SEED)
    if os.path.isdir(SPECS_DIR):
        for p in sorted(__import__("glob").glob(os.path.join(SPECS_DIR, "*.json"))):
            try:
                data = json.load(open(p))
                specs.extend(data if isinstance(data, list) else [data])
            except Exception as e:
                print(f"  ! skipped {p}: {e}", file=sys.stderr)
    # de-dup by id
    seen, uniq = set(), []
    for s in specs:
        if s.get("id") and s["id"] not in seen and s.get("steps"):
            seen.add(s["id"]); uniq.append(s)
    return uniq


def emit(demos):
    # demos.jsonl
    with open(os.path.join(HERE, "demos.jsonl"), "w") as f:
        for d in demos:
            f.write(json.dumps(d) + "\n")
    # fewshot.md
    lines = ["# gimp-mcp — worked examples (Opus-authored, verified against live GIMP)\n",
             "Prompt a local model with these: given the tool set, this is *how* to compose a",
             "sequence to satisfy a design brief. Only verified traces are included.\n"]
    for d in demos:
        if not d["verified"]:
            continue
        lines.append(f"## {d['task']}")
        lines.append("```")
        for c in d["trace"]:
            args = ", ".join(f"{k}={v!r}" for k, v in c["args"].items())
            lines.append(f"{c['tool']}({args})")
        lines.append("```")
    with open(os.path.join(HERE, "fewshot.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def contact_sheet(demos, cols=4, thumb=360, pad=16, label_h=26):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    shots = [d for d in demos if d.get("preview") and os.path.exists(d["preview"])]
    if not shots:
        return None
    rows = (len(shots) + cols - 1) // cols
    cell_w, cell_h = thumb + pad, thumb + pad + label_h
    sheet = Image.new("RGB", (cols * cell_w + pad, rows * cell_h + pad), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for i, d in enumerate(shots):
        r, c = divmod(i, cols)
        x0, y0 = pad + c * cell_w, pad + r * cell_h
        im = Image.open(d["preview"]).convert("RGB")
        im.thumbnail((thumb, thumb))
        sheet.paste(im, (x0 + (thumb - im.width) // 2, y0 + (thumb - im.height) // 2))
        draw.text((x0, y0 + thumb + 6), d["id"], fill=(210, 210, 210))
    path = os.path.join(HERE, "contact-sheet.png")
    sheet.save(path)
    return path


def main():
    specs = load_specs()
    print(f"factory: {len(specs)} task specs")
    demos = []
    for s in specs:
        d = run_spec(s)
        demos.append(d)
        mark = "ok  " if d["verified"] else "FAIL"
        print(f"  {mark} {d['id']}" + ("" if d["verified"] else f"  ← {d['error']}"))
    emit(demos)
    sheet = contact_sheet(demos)
    ok = sum(d["verified"] for d in demos)
    print(f"\n{ok}/{len(demos)} verified → teach/demos.jsonl, teach/fewshot.md"
          + (f", {os.path.relpath(sheet, ROOT)}" if sheet else ""))


if __name__ == "__main__":
    main()
