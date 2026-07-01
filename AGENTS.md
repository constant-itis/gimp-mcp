# Driving gimp-mcp — house rules for the agent

These are conventions for **any LLM** (Claude, Hermes, a local model, whatever) that
drives this tool with a human in the loop. They're not baked into the server — the
server exposes *abilities*; this file defines how to *use* them like a good assistant to
a designer. Follow them unless the user says otherwise.

## 1. The designer already has the file open

The default situation is **not** "generate an image from scratch." It's: the human has
GIMP open with their artwork and says *"hey, do X to this."* So:

- **Find their open image** with `list_images` (or `suggest`) — don't spawn a fresh one
  unless they ask for a new document.
- Start the server *inside their GIMP* so it's the same window they're looking at:
  `./start-gimp-server.sh --gui` attaches to the already-open GIMP (it's single-instance),
  or they can use **Filters ▸ Script-Fu ▸ Start Server** on port 10008.
- `show <image_id>` to make sure the right image is up, then work on **that** image.

## 2. Abilities, not pipelines

The tools are primitives; **recipes are optional, editable suggestions**, not a fixed
workflow. Compose the smallest set of abilities that does what was asked. Don't impose a
canned pipeline, and don't assume a "house style" — the human is the art director.

## 3. Surface options at each stage — don't railroad

At every meaningful stage, **show then ask**: `look` (or `show`) the current state, then
present **2–4 concrete options** and let the user pick before you continue. Use `suggest`
to generate a context-aware menu. Meaningful stages:

- after loading / keying a background
- **before anything destructive or irreversible** (flatten, big crop, overwrite)
- before export (format, size, dpi, transparent vs flattened)
- whenever there's a real design choice — font, placement, color, crop, effect strength

If the request is ambiguous or a choice has trade-offs, **ask** — don't guess a default.

## 4. Back up before you automate

GIMP 2.10 has **no undo over the API** — so a snapshot *is* the undo. Before any
destructive or automated multi-step action (flatten, `apply_recipe`, `color_to_alpha`,
large transforms, `trim_to_content`):

1. `checkpoint <image_id>` first, and tell the user how to `restore_checkpoint`.
2. For **irreversible or outward** actions — overwriting an existing file, exporting over
   a path that exists — confirm before doing it.

## 5. Watch mode

If the user wants to watch it happen: they open GIMP, start the server with `--gui`
(or the menu), and you `show` the image. Every mutating tool flushes the display, so
edits appear live in their window. In headless mode (`look` still works) there's no window
to watch — offer `--gui` if they ask to see it.

## 6. See your own work

Separate from the human watching: **you** should `look` after edits (checker background
by default, so transparency is visible), and use `inspect`/`describe` for exact numbers.
Edit → look → judge → adjust. Don't work blind.

---

**TL;DR:** attach to the file they already have open · compose abilities, don't railroad ·
show + offer options at each stage · snapshot before you automate · let them watch.
