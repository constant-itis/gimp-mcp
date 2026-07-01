#!/usr/bin/env python3
"""
teach/opus_trial.py — the ceiling: the SAME briefs as the 35B trial, but the plans are
authored by the frontier model (Opus). Runs through the identical factory + GUI watch
and renders teach/opus_sheet.png so you can put it next to the 35B's sheet.

Run:  GIMP_PORT=<gui port> python3 teach/opus_trial.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import factory
from watch_trial import run_watch, T   # GUI-display execution + _sheet

# Opus-authored plans for the exact 6 briefs the 35B got.
OPUS_SPECS = [
    {"id": "o-nova-labs", "task": "NOVA LABS circular emblem (navy + gold, star centre)", "steps": [
        {"tool": "new_image", "args": {"width": 1000, "height": 1000, "transparent": True}, "capture": "IMG"},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 55, "y": 55, "width": 890, "height": 890, "color": "#d4af37"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 90, "y": 90, "width": 820, "height": 820, "color": "#0d1b3a"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 150, "y": 150, "width": 700, "height": 700, "color": "#c9a233"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 166, "y": 166, "width": 668, "height": 668, "color": "#0d1b3a"}},
        {"tool": "draw_star", "args": {"image_id": "$IMG", "cx": 500, "cy": 515, "points": 5, "outer": 120, "inner": 50, "color": "#f4ead0"}},
        {"tool": "arc_text", "args": {"image_id": "$IMG", "text": "NOVA LABS", "radius": 372, "size": 84, "center_angle": 90, "step_deg": 13.5, "color": "#e8c66a"}},
        {"tool": "arc_text", "args": {"image_id": "$IMG", "text": "STELLAR SYSTEMS", "radius": 372, "size": 50, "center_angle": 270, "step_deg": 8.6, "flip": True, "color": "#e8c66a"}},
    ]},
    {"id": "o-blast", "task": "BLAST distressed orange headline on black", "steps": [
        {"tool": "new_image", "args": {"width": 1200, "height": 400}, "capture": "IMG"},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#0a0a0a"}},
        {"tool": "add_text", "args": {"image_id": "$IMG", "text": "BLAST", "size": 210, "color": "#ff6a1a", "anchor": "center"}},
        {"tool": "apply_recipe", "args": {"name": "distressed-text", "image_id": "$IMG", "params": "{\"grit\": 72}"}},
    ]},
    {"id": "o-star-sticker", "task": "Yellow star die-cut transparent sticker", "steps": [
        {"tool": "new_image", "args": {"width": 600, "height": 600, "transparent": True}, "capture": "IMG"},
        {"tool": "draw_star", "args": {"image_id": "$IMG", "cx": 300, "cy": 305, "points": 5, "outer": 215, "inner": 88, "color": "#ffd21e"}},
        {"tool": "apply_recipe", "args": {"name": "sticker-outline", "image_id": "$IMG", "params": "{\"outline\": 20, \"outline_color\": \"#ffffff\", \"shadow\": 18}"}},
        {"tool": "trim_to_content", "args": {"image_id": "$IMG"}},
    ]},
    {"id": "o-sunny-hills", "task": "Sunny landscape: sky, green ground, sun with rays top-left", "steps": [
        {"tool": "new_image", "args": {"width": 900, "height": 600}, "capture": "IMG"},
        {"tool": "gradient_fill", "args": {"image_id": "$IMG", "color1": "#5bb8e6", "color2": "#cdeefb", "direction": "vertical"}},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "rectangle", "x": 0, "y": 430, "width": 900, "height": 170}},
        {"tool": "fill", "args": {"image_id": "$IMG", "color": "#4a9d3f"}},
        {"tool": "select", "args": {"image_id": "$IMG", "shape": "none"}},
        {"tool": "sunburst", "args": {"image_id": "$IMG", "cx": 150, "cy": 140, "rays": 16, "radius": 340, "color": "#ffe08a"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 78, "y": 68, "width": 150, "height": 150, "color": "#ffd21e"}},
    ]},
    {"id": "o-vintage-fade", "task": "Purple→orange gradient, vintage-faded", "steps": [
        {"tool": "new_image", "args": {"width": 800, "height": 600}, "capture": "IMG"},
        {"tool": "gradient_fill", "args": {"image_id": "$IMG", "color1": "#6a3d9a", "color2": "#ff9e42", "direction": "diagonal"}},
        {"tool": "apply_recipe", "args": {"name": "vintage", "image_id": "$IMG", "params": "{\"desat\": 28, \"grain\": 18, \"vignette\": 48}"}},
    ]},
    {"id": "o-bullseye", "task": "Concentric red/white bullseye", "steps": [
        {"tool": "new_image", "args": {"width": 700, "height": 700}, "capture": "IMG"},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 90, "y": 90, "width": 520, "height": 520, "color": "#d7263d"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 158, "y": 158, "width": 384, "height": 384, "color": "#ffffff"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 222, "y": 222, "width": 256, "height": 256, "color": "#d7263d"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 285, "y": 285, "width": 130, "height": 130, "color": "#ffffff"}},
        {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 322, "y": 322, "width": 56, "height": 56, "color": "#d7263d"}},
    ]},
]


def main():
    print(f"OPUS trial: {len(OPUS_SPECS)} briefs (frontier-authored plans)\n")
    results = []
    for spec in OPUS_SPECS:
        demo = run_watch(spec)
        results.append(demo)
        print(f"  {'ok  ' if demo['verified'] else 'FAIL'} {spec['id']}" + ("" if demo["verified"] else f"  ← {demo['error']}"))
    sheet = T._sheet([r for r in results if r.get("preview")])
    if sheet:
        os.replace(sheet, os.path.join(HERE, "opus_sheet.png"))
        sheet = os.path.join(HERE, "opus_sheet.png")
    print(f"\nOPUS trial: {sum(r['verified'] for r in results)}/{len(results)} clean"
          + (f" → {os.path.relpath(sheet, factory.ROOT)}" if sheet else ""))


if __name__ == "__main__":
    main()
