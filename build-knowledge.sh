#!/usr/bin/env bash
# Regenerate the machine-readable parts of the knowledge base from the LIVE GIMP:
#   knowledge/pdb_full.json, knowledge/pdb_index.md, knowledge/_slices/*.json
# Run after a GIMP upgrade or any time you want a fresh dump. Idempotent.
# (The cookbook/*.md prose is authored, not regenerated here — see project README.)
set -euo pipefail
cd "$(dirname "$0")"

# ensure the Script-Fu server is up
./start-gimp-server.sh

echo "[1/2] dumping full PDB from live GIMP…"
python3 build_pdb_dump.py

echo "[2/2] building index + domain slices…"
python3 build_index.py

echo
echo "knowledge base regenerated:"
ls -1 knowledge/*.json knowledge/*.md 2>/dev/null
echo "cookbooks (authored, untouched):"
ls -1 knowledge/cookbook/ 2>/dev/null | sed 's/^/  /'
