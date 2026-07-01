#!/usr/bin/env python3
"""Regenerate the gimp-mcp crest (assets/crest.png) — the repo's logo, made by the
tool it advertises. Shapes via the Script-Fu bridge, the two bands via the arc_text
tool, a die-cut drop shadow, exported transparent.

Run (with the Script-Fu server up):  python3 assets/make_crest.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from _core import bridge                     # wrapped bridge (journaling + error hints)
from packs.text import arc_text              # the badge primitive

S = 1200
OUT = os.path.join(ROOT, "assets", "crest.png")


def disc(img, art, x, y, d, col):
    bridge.eval(f"(gimp-image-select-ellipse {img} CHANNEL-OP-REPLACE {x} {y} {d} {d})")
    bridge.eval(f"(gimp-context-set-foreground '{col})")
    bridge.eval(f"(gimp-edit-fill {art} FILL-FOREGROUND)")


def main():
    img = int(bridge.eval(f"(car (gimp-image-new {S} {S} RGB))").strip())
    art = int(bridge.eval(f'(car (gimp-layer-new {img} {S} {S} RGBA-IMAGE "badge" 100 LAYER-MODE-NORMAL))').strip())
    bridge.eval(f"(gimp-image-insert-layer {img} {art} 0 -1)")
    bridge.eval(f"(gimp-drawable-fill {art} FILL-TRANSPARENT)")
    bridge.eval(f"(gimp-image-set-active-layer {img} {art})")

    disc(img, art, 40, 40, 1120, "(217 164 65)")     # outer gold rim
    disc(img, art, 78, 78, 1044, "(14 20 32)")        # navy field
    disc(img, art, 150, 150, 900, "(217 164 65)")     # inner gold ring
    disc(img, art, 168, 168, 864, "(14 20 32)")
    disc(img, art, 440, 430, 320, "(42 161 152)")     # planet
    disc(img, art, 470, 430, 290, "(60 190 178)")     # planet terminator
    disc(img, art, 690, 360, 70, "(210 205 190)")     # moon
    for x, y, d in [(360, 300, 10), (850, 520, 8), (320, 640, 7), (820, 720, 9)]:
        disc(img, art, x, y, d, "(240 240 230)")       # stars
    bridge.eval(f"(gimp-selection-none {img})")

    arc_text(img, "DRIVEN BY CLAUDE", radius=490, size=64, color="#f2e2c4",
             center_angle=90, step_deg=8.2)
    arc_text(img, "GIMP × MCP", radius=490, size=70, color="#d9a441",
             center_angle=270, step_deg=11, flip=True)

    L = int(bridge.eval(f"(car (gimp-image-merge-visible-layers {img} CLIP-TO-IMAGE))").strip())
    bridge.eval(f"(gimp-image-set-active-layer {img} {L})")
    bridge.eval(f"(script-fu-drop-shadow {img} {L} 0 14 34 '(0 0 0) 55 FALSE)")
    flat = int(bridge.eval(f"(car (gimp-image-merge-visible-layers {img} CLIP-TO-IMAGE))").strip())
    bridge.eval(f"(gimp-layer-resize-to-image-size {flat})")
    bridge.eval(f'(file-png-save RUN-NONINTERACTIVE {img} {flat} "{OUT}" "c" 0 9 1 1 1 1 1)')
    bridge.eval(f"(gimp-image-delete {img})")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
