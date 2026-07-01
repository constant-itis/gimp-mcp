# Contributing to gimp-mcp

Thanks for hacking on this. The design is deliberately modular so most contributions
are *additive* — a new pack, a new recipe, or a tool inside an existing pack — with no
core changes and no forking.

## Dev setup

```bash
git clone https://github.com/constant-itis/gimp-mcp.git
cd gimp-mcp
pip install -r requirements.txt
./start-gimp-server.sh          # a live GIMP for hand-testing (headless is fine)
```

## Before you open a PR

```bash
python3 -m py_compile server.py _core.py gimp_bridge.py packs/*.py   # nothing broken
python3 test_smoke.py                                                # offline checks (no GIMP needed)
```

CI runs exactly these on Python 3.10 + 3.12. `test_smoke.py` covers registration, pack
selection, colour parsing, recipe substitution, bundled-recipe validity and error hints —
add a check there if your change introduces new pure logic. Anything that touches the live
GIMP interaction should also be **hand-dogfooded** against a running server (see below).

## Add a tool to an existing pack

Open the relevant `packs/<name>.py`, import what you need from `_core`, and add an
`@mcp.tool`-decorated function. Conventions the codebase follows:

- The **docstring's first line is the tool's description** the model sees — make it a
  crisp, action-first sentence. Keep it short; put arg detail in the body.
- Cast args at the boundary (`int(image_id)`, `float(size)`); colours go through `_color`,
  the active drawable through `_drawable`, and call `_flush()` after a visible change.
- Return a short human-readable status string (ids/bboxes the caller might need next).
- GIMP booleans come back over the bridge as `'1'`/`'0'`, **not** `'TRUE'` — use `_truthy`.

## Add a new pack

A pack is a module that imports from `_core` and registers tools — importing it enables it.
See **[PACKS.md](PACKS.md)** for the full contract and a copy-paste template.

- **Bundled:** drop `packs/<name>.py`, then add `"<name>"` to `BUNDLED_PACKS` in both
  `server.py` and `test_smoke.py`.
- **External (no fork):** drop it in `~/.config/gimp-mcp/packs/` and it auto-loads.

Keep packs focused — one capability domain each — so `GIMP_MCP_PACKS` stays meaningful and
the core context footprint stays small.

## Add a recipe

Recipes are data, not code — a JSON pipeline of existing tool/Scheme steps. Drop a file in
`recipes/` (bundled) or `~/.config/gimp-mcp/recipes/` (yours). Format, `$BINDINGS` and
`{params}` are documented in the recipes section of the README and in existing files like
`recipes/distressed-text.json`. Validate it:

```python
# with the server up:
apply_recipe("your-recipe", <image_id>, '{"param": value}')
```

`test_smoke.py` checks every bundled recipe is valid JSON with `name`/`steps`.

## Dogfood against live GIMP

The honest test is visual. With the server up, drive your change and **look** at it:
edit → `look` → judge → adjust. For a repeatable check, add a spec to
`teach/specs/*.json` and run `python3 teach/factory.py` — it executes your spec against
GIMP, renders it, and drops anything that doesn't run.

## PR flow

1. Branch, make the change, keep it focused.
2. `py_compile` + `test_smoke.py` green; dogfood the live behaviour.
3. Open a PR describing what it adds and how you verified it (a rendered screenshot helps).

Small, well-scoped PRs (one pack / one recipe / one fix) get merged fastest. Bug reports
and "this tool fought me as an agent" friction reports are just as welcome as code.
