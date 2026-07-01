"""pack: recipes — named, parameterized, reusable Scheme pipelines applied to any image.

A recipe = a JSON file of steps replayable on ANY image. Bundled recipes ship in
<repo>/recipes/; user recipes live in ~/.config/gimp-mcp/recipes/ (override with
$GIMP_MCP_RECIPES). Steps use:
  $BINDINGS — runtime handles: $IMG $LAYER $W $H $CX $CY $RAND, plus anything a
              step captures via its "bind" field (e.g. a new mask/layer id).
  {params}  — user knobs with defaults; a param whose name contains "color" is
              auto-converted from #hex / "r,g,b" to a Scheme color literal.
"""
import os
import glob
import json
import random
from _core import mcp, bridge, GimpError, _color, _drawable, _flush, _JOURNAL, _SUSPEND, HERE

_BUNDLED_RECIPES = os.path.join(HERE, "recipes")
_USER_RECIPES = os.path.expanduser(os.environ.get("GIMP_MCP_RECIPES", "~/.config/gimp-mcp/recipes"))


def _recipe_files() -> dict:
    """name -> path, user recipes overriding bundled ones of the same name."""
    found = {}
    for d in (_BUNDLED_RECIPES, _USER_RECIPES):
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            found[os.path.splitext(os.path.basename(p))[0]] = p
    return found


def _load_recipe(name: str) -> dict:
    files = _recipe_files()
    if name not in files:
        raise GimpError(f"no recipe '{name}'. Available: {', '.join(sorted(files)) or '(none)'}")
    with open(files[name]) as f:
        return json.load(f)


def _subst(scheme: str, env: dict, params: dict) -> str:
    for k in sorted(params, key=len, reverse=True):
        scheme = scheme.replace("{" + k + "}", str(params[k]))
    for k in sorted(env, key=len, reverse=True):
        scheme = scheme.replace("$" + k, str(env[k]))
    return scheme


@mcp.tool
def list_recipes() -> str:
    """List available recipes (bundled + your saved ones) with their tunable params."""
    files = _recipe_files()
    if not files:
        return "no recipes yet — apply a bundled one, or capture with save_recipe(from_journal=True)."
    out = []
    for name, path in sorted(files.items()):
        try:
            r = json.load(open(path))
            loc = "user" if path.startswith(_USER_RECIPES) else "bundled"
            ps = ", ".join(f"{k}={v}" for k, v in r.get("params", {}).items())
            out.append(f"{name} [{loc}] — {r.get('description', '')[:90]}" + (f"  (params: {ps})" if ps else ""))
        except Exception as e:
            out.append(f"{name} — (unreadable: {e})")
    return "\n".join(out)


@mcp.tool
def show_recipe(name: str) -> str:
    """Show a recipe's description, params, and its Scheme steps (for review/editing)."""
    r = _load_recipe(name)
    lines = [f"=== {name} ===", r.get("description", ""),
             f"params: {json.dumps(r.get('params', {}))}", "steps:"]
    for i, s in enumerate(r.get("steps", [])):
        pre = f"${s['bind']} = " if s.get("bind") else ""
        lines.append(f"  {i:2}: {pre}{s['scheme']}")
    return "\n".join(lines)


@mcp.tool
def apply_recipe(name: str, image_id: int, params: str = "{}", layer_id: int = -1) -> str:
    """Apply a saved recipe to an image — the power move. `params` is a JSON object of
    overrides (e.g. '{"grit": 60}'); omitted knobs use the recipe's defaults. Targets
    the active layer unless `layer_id` is given. Runtime handles ($IMG/$LAYER/$W/$H/…)
    are bound automatically. Recorded in the journal as a single high-level step.
    """
    iid = int(image_id)
    r = _load_recipe(name)
    knobs = dict(r.get("params", {}))
    try:
        knobs.update(json.loads(params) if isinstance(params, str) and params.strip() else (params or {}))
    except (ValueError, TypeError) as e:
        raise GimpError(f"params must be a JSON object like '{{\"grit\": 60}}' — got {params!r}: {e}")
    for k, v in list(knobs.items()):
        if "color" in k.lower() and isinstance(v, str) and not v.strip().startswith("'("):
            knobs[k] = _color(v)
    layer = _drawable(iid) if int(layer_id) < 0 else int(layer_id)
    W = int(bridge.eval(f"(car (gimp-image-width {iid}))").strip())
    H = int(bridge.eval(f"(car (gimp-image-height {iid}))").strip())
    env = {"IMG": iid, "LAYER": layer, "W": W, "H": H,
           "CX": W // 2, "CY": H // 2, "RAND": random.randint(1, 999999)}
    if _JOURNAL["on"]:
        _JOURNAL["ops"].append(f"; apply_recipe {name} {json.dumps(knobs)}")
    _SUSPEND["n"] += 1
    try:
        for step in r.get("steps", []):
            res = bridge.eval(_subst(step["scheme"], env, knobs))
            if step.get("bind"):
                tok = res.strip().strip("()").split()
                env[step["bind"]] = tok[0] if tok else res.strip()
    finally:
        _SUSPEND["n"] -= 1
    _flush()
    return f"applied '{name}' to image {iid} — {len(r.get('steps', []))} steps, params {json.dumps(knobs)}"


@mcp.tool
def save_recipe(name: str, description: str = "", from_journal: bool = True,
                image_id: int = -1, steps: str = "", params: str = "{}") -> str:
    """Save a reusable recipe to your user library (~/.config/gimp-mcp/recipes/).

    from_journal=True turns the ops you just ran (see `journal`) into a recipe: pass
    image_id so its handle becomes $IMG and its active layer becomes $LAYER. Other
    literal ids stay as-is — for multi-layer pipelines, `show_recipe` then edit the
    intermediate handles into $BINDINGs. Or author directly: steps=<JSON list of
    {"scheme": "...", "bind": "NAME"?}>, params=<JSON object of defaults>.
    """
    import re
    try:
        pdict = json.loads(params) if params and params.strip() else {}
    except ValueError as e:
        raise GimpError(f"params must be a JSON object: {e}")
    if steps:
        step_list = json.loads(steps)
    elif from_journal:
        raw = [s for s in _JOURNAL["ops"] if not s.strip().startswith(";")]
        if not raw:
            raise GimpError("journal is empty — run `journal start`, do some edits, then save_recipe.")
        step_list = [{"scheme": s} for s in raw]
        if int(image_id) >= 0:
            iid = int(image_id)
            lyr = str(_drawable(iid))
            for st in step_list:
                st["scheme"] = re.sub(rf"(?<![0-9]){iid}(?![0-9])", "$IMG", st["scheme"])
                st["scheme"] = re.sub(rf"(?<![0-9]){lyr}(?![0-9])", "$LAYER", st["scheme"])
    else:
        raise GimpError("nothing to save — set from_journal=True (with image_id) or pass steps=<JSON>.")
    os.makedirs(_USER_RECIPES, exist_ok=True)
    path = os.path.join(_USER_RECIPES, f"{name}.json")
    with open(path, "w") as f:
        json.dump({"name": name, "description": description, "params": pdict, "steps": step_list}, f, indent=2)
    return f"saved recipe '{name}' ({len(step_list)} steps) -> {path}"


@mcp.tool
def delete_recipe(name: str) -> str:
    """Delete a recipe from your user library. Bundled recipes can't be deleted."""
    path = os.path.join(_USER_RECIPES, f"{name}.json")
    if not os.path.exists(path):
        raise GimpError(f"no user recipe '{name}' at {path} (bundled recipes are read-only).")
    os.remove(path)
    return f"deleted user recipe '{name}'"
