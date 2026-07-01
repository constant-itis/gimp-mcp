# GIMP-MCP Knowledge Base

An **AI-native, self-regenerating reference** for driving GIMP 2.10 from an LLM agent.
Not human docs — it's optimized for a model issuing Script-Fu commands through the
`gimp-mcp` bridge.

## Why it exists

GIMP's real interface for an agent is its **PDB** (1264 procedures). The web manual is
written for humans clicking menus and drifts from the installed version. So this corpus
is generated *from the actually-installed GIMP via introspection* — it is always exactly
in sync with what you can call.

## Layout

```
knowledge/
  README.md          ← you are here
  pdb_full.json      ← ground truth: every procedure, blurb, typed args (machine-read)
  pdb_index.md       ← all 1264 procedures, categorized, one line each (browse/grep)
  recipes.md         ← "I want to do X" → which tool / cookbook
  cookbook/          ← dense per-domain guides with working Scheme (the daily driver)
    00-overview.md   ← READ FIRST: execution model, the 5 traps, the preview loop
    01..11           ← images-io, layers, text, color, selections, transforms,
                       paint, filters, vectors, context, automation
  _slices/           ← per-domain JSON the cookbook authors were built from (intermediate)
```

## How an agent should use it

1. New to GIMP-MCP this session? Read `cookbook/00-overview.md`.
2. Know the domain? Open that cookbook (e.g. text → `cookbook/03-text-fonts.md`).
3. Need a specific procedure's signature? Use the **live** MCP tools `pdb_query` /
   `pdb_help` — never stale. Or grep `pdb_index.md` / `pdb_full.json`.
4. Searching by intent? `recipes.md`, or the `gimp_docs` MCP tool (searches this corpus).

## Living / regeneration

Everything except the hand-written cookbook prose is generated. After a GIMP upgrade
(or to rebuild from scratch):

```bash
./build-knowledge.sh        # re-dumps PDB + index from live GIMP
```

That refreshes `pdb_full.json`, `pdb_index.md`, and `_slices/`. The cookbooks are
authored content; regenerate them by re-running the fan-out (see the project README)
only when the GIMP major version changes enough to matter.

Provenance: `pdb_full.json` carries the `gimp_version` it was dumped from. If that
differs from `gimp --version`, the corpus is stale — rebuild.
