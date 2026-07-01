#!/usr/bin/env python3
"""Offline smoke tests for gimp-mcp — no GIMP server required.

Covers what can be checked without a live GIMP: modules import, tools register,
pack selection composes, bundled recipes are valid, and the pure helpers
(_color, _subst, _hint) behave. Run: python3 test_smoke.py   (or pytest)
"""
import os
import sys
import glob
import json
import asyncio
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

BUNDLED_PACKS = ["layers", "text", "transform", "color", "fx", "select",
                 "generate", "paths", "batch", "animate", "recipes", "journal", "watch"]


def _tool_count(mcp):
    return len(asyncio.run(mcp._list_tools()))


def test_core_imports_and_tool_count():
    import _core
    n = _tool_count(_core.mcp)
    assert n >= 15, f"core should expose ~16 tools, got {n}"


def test_all_packs_import_and_register():
    import _core
    for name in BUNDLED_PACKS:
        importlib.import_module(f"packs.{name}")
    n = _tool_count(_core.mcp)
    assert n >= 70, f"core + all packs should be ~72 tools, got {n}"


def test_pack_selection_logic():
    import server
    os.environ["GIMP_MCP_PACKS"] = "core"
    assert server._enabled_packs() == []
    os.environ["GIMP_MCP_PACKS"] = "text,fx"
    assert server._enabled_packs() == ["text", "fx"]
    os.environ["GIMP_MCP_PACKS"] = "all"
    assert server._enabled_packs() == BUNDLED_PACKS
    del os.environ["GIMP_MCP_PACKS"]
    assert server._enabled_packs() == BUNDLED_PACKS   # unset = all


def test_color_parsing():
    from _core import _color
    assert _color("#ff8040") == "'(255 128 64)"
    assert _color("255,128,64") == "'(255 128 64)"
    assert _color("10 20 30") == "'(10 20 30)"


def test_recipe_substitution():
    from packs.recipes import _subst
    out = _subst("(gimp-threshold $MASK {grit} 255)", {"MASK": 9}, {"grit": 60})
    assert out == "(gimp-threshold 9 60 255)"
    # longer names substituted before shorter to avoid prefix clashes
    out2 = _subst("$LAYER $L", {"LAYER": 5, "L": 7}, {})
    assert out2 == "5 7"


def test_bundled_recipes_are_valid():
    files = glob.glob(os.path.join(HERE, "recipes", "*.json"))
    assert files, "expected bundled recipes"
    for f in files:
        r = json.load(open(f))
        assert "name" in r and "steps" in r, f"{f} missing name/steps"
        assert isinstance(r["steps"], list) and r["steps"], f"{f} has no steps"
        for step in r["steps"]:
            assert "scheme" in step, f"{f} step missing 'scheme'"


def test_error_hints():
    from _core import _hint
    assert "list_fonts" in _hint("Procedure returned no return values")
    assert "list_images" in _hint("Invalid image 42")
    assert _hint("something totally unrecognized") == ""


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERR  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
