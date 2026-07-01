#!/usr/bin/env python3
"""
gimp-mcp — entry point. Loads the lean core (_core.py) + whichever packs you enable,
then serves over stdio for `claude mcp add`.

Modular by design (like mycelium + mycelium-tools): the core alone reaches the whole
GIMP PDB and drives the vision loop; packs add ergonomic tools you opt into by usage,
so the tool surface stays light — which matters for context-limited / local models.

Choose packs with the GIMP_MCP_PACKS env var:
    (unset) or "all"     → core + every bundled pack (default)
    "core"               → core only (~16 tools)
    "text,fx,recipes"    → core + just those packs
Bundled packs live in packs/. Drop your own *.py packs in ~/.config/gimp-mcp/packs/
(override with $GIMP_MCP_PACKS_DIR) — each is a module that imports from _core and
registers @mcp.tool tools. See PACKS.md.

Run:   python3 server.py
Needs: the Script-Fu server running — ./start-gimp-server.sh  (add --gui to watch)
"""

import os
import sys
import glob
import importlib
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _core
from _core import mcp

BUNDLED_PACKS = ["layers", "text", "transform", "color", "fx", "select",
                 "recipes", "journal", "watch"]


def _enabled_packs():
    env = os.environ.get("GIMP_MCP_PACKS", "").strip()
    if not env or env.lower() == "all":
        return list(BUNDLED_PACKS)
    # comma list; "core" is implicit (always loaded) so ignore it as a pack name
    return [p.strip() for p in env.split(",") if p.strip() and p.strip().lower() != "core"]


def _load_external(directory):
    loaded = []
    for path in sorted(glob.glob(os.path.join(directory, "*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"gimp_pack_{name}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            loaded.append(name)
        except Exception as e:
            print(f"[gimp-mcp] external pack '{name}' failed: {e}", file=sys.stderr)
    return loaded


def _load_packs():
    loaded = []
    for name in _enabled_packs():
        if name not in BUNDLED_PACKS:
            print(f"[gimp-mcp] unknown pack '{name}' (have: {', '.join(BUNDLED_PACKS)})", file=sys.stderr)
            continue
        try:
            importlib.import_module(f"packs.{name}")
            loaded.append(name)
        except Exception as e:
            print(f"[gimp-mcp] pack '{name}' failed to load: {e}", file=sys.stderr)
    ext_dir = os.path.expanduser(os.environ.get("GIMP_MCP_PACKS_DIR", "~/.config/gimp-mcp/packs"))
    if os.path.isdir(ext_dir):
        loaded += _load_external(ext_dir)
    return loaded


loaded = _load_packs()
print(f"[gimp-mcp] core + packs: {', '.join(loaded) or '(core only)'}", file=sys.stderr)


if __name__ == "__main__":
    mcp.run()
