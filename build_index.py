#!/usr/bin/env python3
"""
From knowledge/pdb_full.json produce:
  - knowledge/pdb_index.md         categorized one-line index of all procedures
  - knowledge/_slices/<domain>.json per-domain procedure slices (fed to cookbook authors)

Domain assignment is first-match-wins over an ordered rule list, so more specific
rules precede generic prefixes.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
KN = os.path.join(HERE, "knowledge")

# (domain, predicate) — ordered, first match wins.
def rule(*subs):
    return lambda n: any(s in n for s in subs)

def pref(*prefixes):
    return lambda n: any(n.startswith(p) for p in prefixes)

DOMAINS = [
    ("text-fonts",        pref("gimp-text-", "gimp-fonts-", "gimp-font-")),
    ("layers-masks",      lambda n: pref("gimp-layer-")(n) or "layer" in n and pref("gimp-image-")(n) or pref("gimp-image-insert", "gimp-image-remove-layer", "gimp-image-flatten", "gimp-image-merge", "gimp-image-get-layer", "gimp-image-set-active-layer")(n)),
    ("selections",        pref("gimp-selection-", "gimp-image-select-", "gimp-channel-")),
    ("transforms-canvas", pref("gimp-item-transform-", "gimp-image-scale", "gimp-image-resize", "gimp-image-crop", "gimp-image-rotate", "gimp-image-flip", "gimp-layer-scale", "gimp-layer-resize", "gimp-drawable-transform-")),
    ("color-tone",        rule("curves", "levels", "brightness", "contrast", "hue-saturation", "color-balance", "colorize", "desaturate", "threshold", "posterize", "invert", "exposure", "shadows-highlights", "histogram")),
    ("paint-draw",        pref("gimp-pencil", "gimp-paintbrush", "gimp-airbrush", "gimp-ink", "gimp-clone", "gimp-smudge", "gimp-eraser", "gimp-bucket-fill", "gimp-blend", "gimp-image-select-color", "gimp-edit-", "gimp-drawable-edit-", "gimp-gradient-")),
    ("vectors-paths",     pref("gimp-vectors-", "gimp-path-")),
    ("filters-fx",        pref("plug-in-", "script-fu-")),
    ("context-resources", pref("gimp-context-", "gimp-brush", "gimp-palette", "gimp-gradient", "gimp-pattern", "gimp-dynamics", "gimp-unit")),
    ("images-io",         pref("gimp-image-", "gimp-file-", "file-", "gimp-display-", "gimp-drawable-", "gimp-item-")),
]

# Friendly category headers for the index (by prefix), independent of cookbook domains.
def main():
    data = json.load(open(os.path.join(KN, "pdb_full.json")))
    procs = data["procedures"]
    names = sorted(procs)

    # assign domains
    slices = {d: {} for d, _ in DOMAINS}
    misc = {}
    for n in names:
        for d, pred in DOMAINS:
            try:
                if pred(n):
                    slices[d][n] = procs[n]
                    break
            except Exception:
                continue
        else:
            misc[n] = procs[n]
    if misc:
        slices.setdefault("misc", {}).update(misc)

    os.makedirs(os.path.join(KN, "_slices"), exist_ok=True)
    for d, sl in slices.items():
        with open(os.path.join(KN, "_slices", f"{d}.json"), "w") as fh:
            json.dump({"domain": d, "count": len(sl), "procedures": sl}, fh, indent=1, ensure_ascii=False)

    # index.md
    lines = [f"# GIMP {data['gimp_version']} PDB Index — {data['count']} procedures",
             "",
             "Auto-generated from the installed GIMP via `build_pdb_dump.py` + `build_index.py`.",
             "Full machine reference: `pdb_full.json`. Per-domain cookbooks: `cookbook/`.",
             "For live signatures in a session use the `pdb_help` / `pdb_query` MCP tools.",
             ""]
    for d, sl in slices.items():
        if not sl:
            continue
        lines.append(f"## {d}  ({len(sl)})")
        for n in sorted(sl):
            blurb = (sl[n]["blurb"] or "").split("\n")[0].strip()
            nargs = len(sl[n]["args"])
            lines.append(f"- `{n}` ({nargs} args) — {blurb}")
        lines.append("")
    with open(os.path.join(KN, "pdb_index.md"), "w") as fh:
        fh.write("\n".join(lines))

    print("slice counts:")
    for d, sl in slices.items():
        print(f"  {len(sl):4d}  {d}")
    print(f"index -> {os.path.join(KN, 'pdb_index.md')}")


if __name__ == "__main__":
    main()
