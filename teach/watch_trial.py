#!/usr/bin/env python3
"""
teach/watch_trial.py — the 35B trial, but RICHER few-shot + WATCHABLE.

Two changes vs trial_35b.py:
  1. Few-shot is expanded from 3 hand-picked examples to a spread of the VERIFIED
     corpus (feed the demos back), to test whether more examples lift quality.
  2. Runs against a GUI GIMP and pops each image into a window (gimp-display-new),
     keeping it open, so a human watches the 35B's designs build live.

Point it at a watchable GIMP:  ./start-gimp-server.sh --gui  (starts the server in
your open GIMP). Then:  GIMP_PORT=<that port> python3 teach/watch_trial.py
"""
import os
import sys
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import factory                      # imports _core (reads GIMP_PORT) + builds TOOLS
from _core import bridge
import trial_35b as T               # reuse _post / _extract_json / TOOL_REF / TEST_BRIEFS / _sheet

# ── richer few-shot: a diverse spread of the verified corpus (was 3) ──────────
FEWSHOT_IDS = ["gold-title", "mission-patch", "cutout-logo", "vintage-gradient",
               "die-cut-sticker", "neon-title", "explorers-guild-seal",
               "duotone-ellipse-pop", "radial-flare-burst"]


def _build_fewshot():
    by_id = {s["id"]: s for s in factory.load_specs()}
    shots = []
    for i in FEWSHOT_IDS:
        s = by_id.get(i)
        if s:
            shots.append((s["task"], s["steps"]))
    return shots


SYSTEM = T.SYSTEM
FEWSHOT = _build_fewshot()


def ask(brief, retries=1):
    msgs = [{"role": "system", "content": SYSTEM}]
    for ex_brief, ex_steps in FEWSHOT:
        msgs.append({"role": "user", "content": ex_brief})
        msgs.append({"role": "assistant", "content": json.dumps(ex_steps)})
    msgs.append({"role": "user", "content": brief})
    last = ""
    for attempt in range(retries + 1):
        raw = T._post(msgs, max_tokens=1400 + attempt * 600)
        last = raw
        try:
            return T._extract_json(raw), None
        except Exception as e:
            err = f"JSON parse failed: {e}"
    return None, f"{err}; raw head: {last[:160]!r}"


def run_watch(spec, pause=0.5):
    """Execute a spec, popping the image into the GUI so it builds live. Keeps it open."""
    env, trace, err, shown = {}, [], None, False
    for step in spec["steps"]:
        tool = step["tool"]
        args = {k: factory._resolve(v, env) for k, v in step.get("args", {}).items()}
        if tool not in factory.TOOLS:
            err = f"unknown tool '{tool}'"
            break
        try:
            result = str(factory.TOOLS[tool](**args))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            trace.append({"tool": tool, "args": args, "error": err})
            break
        trace.append({"tool": tool, "args": args, "result": result[:200]})
        if step.get("capture"):
            m = factory._ID_RE.search(result)
            if m:
                env[step["capture"]] = int(m.group(1))
        if not shown and "IMG" in env:           # window opens as soon as the image exists
            shown = True
            try:
                bridge.eval(f"(gimp-display-new {env['IMG']})")
            except Exception:
                pass
        bridge.eval("(gimp-displays-flush)")
        time.sleep(pause)
    img = env.get("IMG")
    preview = None
    if img is not None and err is None:
        os.makedirs(factory.OUT, exist_ok=True)
        preview = os.path.join(factory.OUT, f"{spec['id']}.png")
        try:
            factory._render(img, 512, "auto", preview)
        except Exception:
            preview = None
        bridge.eval("(gimp-displays-flush)")
    # NOTE: intentionally do NOT delete img — leave it open in the GUI to watch
    return {"id": spec["id"], "task": spec["task"], "trace": trace,
            "verified": err is None, "error": err, "preview": preview}


def main():
    print(f"WATCH trial: {len(T.TEST_BRIEFS)} briefs · few-shot={len(FEWSHOT)} corpus examples\n"
          f"(watch your GIMP window — each design opens + builds live)\n")
    results = []
    for tid, brief in T.TEST_BRIEFS:
        steps, perr = ask(brief)
        if steps is None:
            print(f"  PLAN-FAIL {tid}: {perr}")
            results.append({"id": tid, "task": brief, "verified": False, "error": perr, "preview": None})
            continue
        demo = run_watch({"id": f"w-{tid}", "task": brief, "steps": steps})
        results.append(demo)
        mark = "ok  " if demo["verified"] else "RUN-FAIL"
        print(f"  {mark} {tid}  ({len(steps)} steps)" + ("" if demo["verified"] else f"  ← {demo['error']}"))
        time.sleep(0.8)
    verified = sum(r["verified"] for r in results)
    sheet = T._sheet([r for r in results if r.get("preview")])
    if sheet:
        os.replace(sheet, os.path.join(HERE, "watch_trial_sheet.png"))
        sheet = os.path.join(HERE, "watch_trial_sheet.png")
    print(f"\nWATCH trial: executed clean {verified}/{len(results)} · few-shot={len(FEWSHOT)}")
    print("images left OPEN in your GIMP to inspect." + (f"\n→ {os.path.relpath(sheet, factory.ROOT)}" if sheet else ""))


if __name__ == "__main__":
    main()
