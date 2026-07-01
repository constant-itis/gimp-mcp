# teach/ — the demonstration factory

The **Opus→Fable move, applied to a tool.** A capable model (the one that built this)
manufactures a *verified* corpus of worked examples that teaches a smaller / local model
(Hermes, a Qwen, a fine-tune) to drive gimp-mcp well — the same shape as using a strong
model to generate the training signal for a smaller one.

Nothing here is baked into the server. It's a standalone factory that produces data.

## What it does

`factory.py` takes **task specs** (natural-language brief + an ordered list of tool
calls), executes each against a **live GIMP**, records the exact tool-call trace,
renders the result, and keeps only the ones that actually run. Output:

- **`demos.jsonl`** — one verified trace per task: `{id, task, trace:[{tool,args,result}], verified, preview}`. Fine-tune / eval ready.
- **`fewshot.md`** — the same traces as readable worked examples. Paste a handful into a
  local model's prompt as "here's *how* to compose a sequence for a brief like this."
- **`contact-sheet.png`** — a grid of every rendered result (proof it runs).
- **`out/*.png`** — each task's rendered output.

Because a spec is just JSON, the curriculum is authored by *models*, not code — the
bundled set was written by a seed pass plus four subagents (typography, transparency,
treatments, emblems). The factory is the verifier: a spec that references a wrong tool
or arg simply fails and is dropped, so the emitted corpus is **only** things that work.

## Run it

```bash
./start-gimp-server.sh          # live GIMP (headless is fine)
python3 teach/factory.py        # executes seed + teach/specs/*.json, emits the corpus
```

## Spec format

```json
{
  "id": "gold-title",
  "task": "Centered gold title 'APOLLO' with a heavy dark outline on a dark canvas.",
  "steps": [
    {"tool": "new_image",   "args": {"width": 1200, "height": 400}, "capture": "IMG"},
    {"tool": "fill",        "args": {"image_id": "$IMG", "color": "#14141f"}},
    {"tool": "outline_text","args": {"image_id": "$IMG", "text": "APOLLO", "size": 180,
                                     "fill_color": "#ffce5a", "outline_color": "#160a04",
                                     "outline_width": 8, "anchor": "center"}}
  ]
}
```

- A step's `capture: "NAME"` grabs the first `id=`/`layer=` integer from its result;
  later steps reference it as `"$NAME"` (e.g. `"image_id": "$IMG"`).
- Drop new spec files in `teach/specs/*.json` (a single spec or an array). They're
  de-duped by `id` and merged with the seed curriculum.

## Using the corpus to uplift a local model

1. **Few-shot (no training):** prepend a handful of `fewshot.md` examples to the local
   model's system/user prompt. Small models that flail at "compose a GIMP sequence"
   become reliable when shown 3–5 verified traces for similar briefs.
2. **Fine-tune / distill:** `demos.jsonl` is ready to shape into instruction→tool-call
   pairs. Grow it by adding specs and re-running — every new verified trace is free
   supervised data, generated and checked by the stronger model.

This is the flywheel: the capable model does the work *and* checks it, and the smaller
model learns from the verified result — no human labeling in the loop.
