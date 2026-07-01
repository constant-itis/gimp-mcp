#!/usr/bin/env python3
"""
Introspect the entire GIMP PDB into knowledge/pdb_full.json — the ground-truth
machine reference, regenerated from the actually-installed GIMP. Run anytime the
GIMP version changes to keep the knowledge base in sync.

Output schema (pdb_full.json):
{
  "gimp_version": "2.10.30",
  "count": 1264,
  "procedures": {
    "gimp-image-new": {
      "blurb": "...", "help": "...",
      "args": [{"type": "INT32", "name": "width", "desc": "..."}, ...]
    }, ...
  }
}
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gimp_bridge import GimpBridge, GimpError

TYPE_NAMES = {
    "0": "INT32", "1": "INT16", "2": "INT8", "3": "FLOAT", "4": "STRING",
    "5": "INT32ARRAY", "6": "INT16ARRAY", "7": "INT8ARRAY", "8": "FLOATARRAY",
    "9": "STRINGARRAY", "10": "COLOR", "11": "ITEM", "12": "DISPLAY",
    "13": "IMAGE", "14": "LAYER", "15": "CHANNEL", "16": "DRAWABLE",
    "17": "SELECTION", "18": "COLORARRAY", "19": "VECTORS", "20": "PARASITE",
}
GS = "\x1d"  # group separator between blurb/help/nargs
US = "\t"    # unit separator between args

PDOC = r'''(define (pdoc name)
  (let* ((info (gimp-procedural-db-proc-info name))
         (blurb (car info)) (help (cadr info)) (nargs (list-ref info 6)))
    (let loop ((i 0) (acc ""))
      (if (< i nargs)
          (let ((a (gimp-procedural-db-proc-arg name i)))
            (loop (+ i 1) (string-append acc "\t" (number->string (car a)) "|" (cadr a) "|" (caddr a))))
          (string-append blurb "\x1d" help "\x1d" (number->string nargs) acc)))))'''


def main():
    b = GimpBridge(timeout=120)
    version = b.eval("(car (gimp-version))").strip().strip('"')
    b.eval(PDOC)
    raw = b.eval('(cadr (gimp-procedural-db-query ".*" ".*" ".*" ".*" ".*" ".*" ".*"))')
    names = sorted(n.strip('"') for n in raw.strip().strip("()").split() if n.strip())
    procs = {}
    errs = []
    for i, name in enumerate(names):
        try:
            out = b.eval(f'(pdoc "{name}")')
        except GimpError as e:
            errs.append((name, str(e)))
            continue
        # response is a single scheme string, serialized with escapes by the
        # server (real TAB -> \t, real 0x1D -> \x1D). Strip quotes, then decode.
        s = out.strip()
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        s = re.sub(r"\\x([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), s)
        s = (s.replace("\\t", "\t").replace("\\n", "\n")
              .replace('\\"', '"').replace("\\\\", "\\"))
        parts = s.split(GS)
        blurb = parts[0] if len(parts) > 0 else ""
        helptxt = parts[1] if len(parts) > 1 else ""
        rest = parts[2] if len(parts) > 2 else "0"
        bits = rest.split(US)
        args = []
        for spec in bits[1:]:
            f = spec.split("|")
            if len(f) >= 2:
                args.append({
                    "type": TYPE_NAMES.get(f[0], f[0]),
                    "name": f[1],
                    "desc": f[2] if len(f) > 2 else "",
                })
        procs[name] = {"blurb": blurb.strip(), "help": helptxt.strip(), "args": args}
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1}/{len(names)}", file=sys.stderr)
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "pdb_full.json")
    with open(path, "w") as fh:
        json.dump({"gimp_version": version, "count": len(procs), "procedures": procs},
                  fh, indent=1, ensure_ascii=False)
    print(f"wrote {len(procs)} procedures -> {path}  (gimp {version})")
    if errs:
        print(f"{len(errs)} procedures failed introspection:", [e[0] for e in errs[:10]])


if __name__ == "__main__":
    main()
