#!/usr/bin/env python3
"""
teach/trial_35b.py — the real "is it agent-ready for a LOCAL model" test.

Closes the teach/ loop: few-shot a small local model (Qwen 35B on evo-x2) with the
corpus, hand it a fresh design brief, let IT plan the gimp-mcp tool calls, then
EXECUTE its plan against live GIMP, render, and measure. This turns teach/ from
"a corpus" into "measured uplift": does few-shotting the demos let a weak model
produce gimp-mcp programs that actually run?

Run (Script-Fu server + the 35B both up):  python3 teach/trial_35b.py
Endpoint override: GIMP_MCP_LLM_URL (default http://192.168.1.152:8100/v1/chat/completions)
"""
import os
import re
import sys
import json
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import factory  # noqa: E402  (imports packs + builds the tool registry + run_spec)

LLM_URL = os.environ.get("GIMP_MCP_LLM_URL", "http://192.168.1.152:8100/v1/chat/completions")

TOOL_REF = """\
Tools you may use (exact arg names). image_id is always "$IMG" (captured from new_image).
  new_image(width,height,fill_white,transparent)  -> capture "IMG"; transparent=true for alpha canvas
  fill(image_id,color)  gradient_fill(image_id,color1,color2,direction[vertical|horizontal|diagonal])
  select(image_id,shape[rectangle|ellipse|all|none],x,y,width,height)  erase(image_id)  trim_to_content(image_id)
  draw_ellipse(image_id,x,y,width,height,color,fill_shape,line_width)  draw_rect(image_id,x,y,width,height,color,fill_shape,line_width)
  draw_polygon(image_id,points"x,y x,y x,y",color,fill_shape,line_width)  draw_star(image_id,cx,cy,points,outer,inner,color,rotation,fill_shape)
  draw_line(image_id,x1,y1,x2,y2,color,width)  sunburst(image_id,cx,cy,rays,radius,color,rotation)  draw_curve(image_id,points"x,y ...",color,width,closed,fill_shape)
  add_text(image_id,text,x,y,size,color,font,anchor)  outline_text(image_id,text,x,y,size,fill_color,outline_color,outline_width,font,anchor)
  arc_text(image_id,text,radius,size,font,color,center_angle,step_deg,flip)  -- center_angle 90=top arch, 270=bottom(flip=true)
  color_to_alpha(image_id,color)  apply_recipe(name,image_id,params)  -- recipes: distressed-text{grit}, vintage{}, sticker-outline{}
  export_image(image_id,path)
anchors: center|top-center|bottom-center|top-left|top-right|bottom-left|bottom-right. colors "#rrggbb". fonts: "Sans Bold".
"""

SYSTEM = (
    "You are a graphic designer that drives the gimp-mcp tool. Given a brief, output a JSON "
    "ARRAY of steps that builds it. Each step is {\"tool\":<name>,\"args\":{...}} and the FIRST "
    "step MUST be new_image with \"capture\":\"IMG\"; every later step passes \"image_id\":\"$IMG\". "
    "Output ONLY the JSON array — no prose, no markdown fences.\n\n" + TOOL_REF
)

# few-shot exemplars drawn from the verified seed curriculum
FEWSHOT = [
    ("Centered gold title 'APOLLO' with a heavy dark outline on a dark canvas.",
     [{"tool": "new_image", "args": {"width": 1200, "height": 400}, "capture": "IMG"},
      {"tool": "fill", "args": {"image_id": "$IMG", "color": "#14141f"}},
      {"tool": "outline_text", "args": {"image_id": "$IMG", "text": "APOLLO", "size": 180,
       "fill_color": "#ffce5a", "outline_color": "#160a04", "outline_width": 8, "anchor": "center"}}]),
    ("Round badge: blue planet centre, 'THE EAGLE HAS LANDED' arched top, 'APOLLO XI' bottom.",
     [{"tool": "new_image", "args": {"width": 1000, "height": 1000}, "capture": "IMG"},
      {"tool": "fill", "args": {"image_id": "$IMG", "color": "#0b0b14"}},
      {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 320, "y": 320, "width": 360, "height": 360, "color": "#3a5f9f"}},
      {"tool": "arc_text", "args": {"image_id": "$IMG", "text": "THE EAGLE HAS LANDED", "radius": 430, "size": 66, "center_angle": 90, "step_deg": 7.4, "color": "#ffce5a"}},
      {"tool": "arc_text", "args": {"image_id": "$IMG", "text": "APOLLO XI", "radius": 430, "size": 64, "center_angle": 270, "step_deg": 9, "flip": True, "color": "#ffce5a"}}]),
    ("A red disc as a trimmed transparent sticker.",
     [{"tool": "new_image", "args": {"width": 600, "height": 600, "transparent": True}, "capture": "IMG"},
      {"tool": "draw_ellipse", "args": {"image_id": "$IMG", "x": 150, "y": 150, "width": 300, "height": 300, "color": "#c0392b"}},
      {"tool": "apply_recipe", "args": {"name": "sticker-outline", "image_id": "$IMG"}},
      {"tool": "trim_to_content", "args": {"image_id": "$IMG"}}]),
]

TEST_BRIEFS = [
    ("nova-labs", "A circular emblem for 'NOVA LABS' with the name arched across the top on a dark navy field ringed in gold, with a bright star in the centre."),
    ("blast", "The word 'BLAST' as a big distressed orange headline centered on a black canvas."),
    ("star-sticker", "A single yellow five-pointed star as a transparent sticker with a die-cut white outline."),
    ("sunny-hills", "A simple sunny landscape on a 900x600 canvas: light-blue sky, green ground across the bottom third, and a yellow sun with rays in the top-left corner."),
    ("vintage-fade", "A purple-to-orange diagonal gradient given a faded vintage-photo treatment."),
    ("bullseye", "A target/bullseye: concentric circles alternating red and white, centered."),
]


def _post(messages, max_tokens=1200):
    body = json.dumps({"model": "local", "messages": messages, "max_tokens": max_tokens,
                       "temperature": 0.3, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(LLM_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def _extract_json(text):
    text = text.strip()
    if "```" in text:                       # strip markdown fences if the model adds them
        text = re.sub(r"```(?:json)?", "", text).strip()
    a, b = text.find("["), text.rfind("]")
    if a >= 0 and b > a:
        text = text[a:b + 1]
    return json.loads(text)


def ask_35b(brief, retries=1):
    msgs = [{"role": "system", "content": SYSTEM}]
    for ex_brief, ex_steps in FEWSHOT:
        msgs.append({"role": "user", "content": ex_brief})
        msgs.append({"role": "assistant", "content": json.dumps(ex_steps)})
    msgs.append({"role": "user", "content": brief})
    last = ""
    for attempt in range(retries + 1):
        raw = _post(msgs, max_tokens=1200 + attempt * 600)
        last = raw
        try:
            return _extract_json(raw), None
        except (ValueError, json.JSONDecodeError) as e:
            err = f"JSON parse failed: {e}"
    return None, f"{err}; raw head: {last[:160]!r}"


def main():
    print(f"trial: {len(TEST_BRIEFS)} briefs → 35B @ {LLM_URL}\n")
    results = []
    for tid, brief in TEST_BRIEFS:
        steps, perr = ask_35b(brief)
        if steps is None:
            print(f"  PLAN-FAIL {tid}: {perr}")
            results.append({"id": tid, "task": brief, "planned": False, "verified": False,
                            "error": perr, "preview": None, "trace": []})
            continue
        spec = {"id": f"35b-{tid}", "task": brief, "steps": steps}
        demo = factory.run_spec(spec)
        demo["planned"] = True
        demo["n_steps"] = len(steps)
        results.append(demo)
        mark = "ok  " if demo["verified"] else "RUN-FAIL"
        print(f"  {mark} {tid}  ({len(steps)} steps)" + ("" if demo["verified"] else f"  ← {demo['error']}"))

    planned = sum(r["planned"] for r in results)
    verified = sum(r["verified"] for r in results)
    with open(os.path.join(HERE, "trial_35b_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    sheet = _sheet([r for r in results if r.get("preview")])
    print(f"\n35B trial: planned valid JSON {planned}/{len(results)} · "
          f"executed clean {verified}/{len(results)}")
    print("→ teach/trial_35b_results.json" + (f", {os.path.relpath(sheet, factory.ROOT)}" if sheet else ""))


def _sheet(shots, cols=3, thumb=340):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    if not shots:
        return None
    pad, lh = 14, 22
    rows = (len(shots) + cols - 1) // cols
    cw, ch = thumb + pad, thumb + pad + lh
    im = Image.new("RGB", (cols * cw + pad, rows * ch + pad), (24, 24, 28))
    dr = ImageDraw.Draw(im)
    for i, r in enumerate(shots):
        rr, cc = divmod(i, cols)
        x0, y0 = pad + cc * cw, pad + rr * ch
        t = Image.open(r["preview"]).convert("RGB"); t.thumbnail((thumb, thumb))
        im.paste(t, (x0 + (thumb - t.width) // 2, y0 + (thumb - t.height) // 2))
        dr.text((x0, y0 + thumb + 4), r["id"], fill=(210, 210, 210))
    path = os.path.join(HERE, "trial_35b_sheet.png")
    im.save(path)
    return path


if __name__ == "__main__":
    main()
