# Automation & Batch — driving GIMP at scale

How to run the same edit over many files, script multi-step pipelines, and use the
bridge directly. This domain is about *orchestration*, not a PDB category.

## The bridge (what you're actually talking to)

`./gimp_bridge.py` is a zero-dep socket client for GIMP's
Script-Fu TCP server. Three ways to use it:

```bash
# one-off from the shell
python3 ./gimp_bridge.py '(car (gimp-version))'
```
```python
# from Python
from gimp_bridge import GimpBridge
b = GimpBridge()                       # 127.0.0.1:10008
print(b.eval("(+ 2 2)"))               # raises GimpError on a PDB error
```
```
# from an MCP session: the gimp_eval tool, or any of the 39 wrapper tools
gimp_eval("(gimp-image-flatten 1)")
```

Start the server first (idempotent): `./start-gimp-server.sh`.
It stays up across calls; the interpreter keeps global state.

## Batch a folder (the canonical pattern)

Do the loop in Python, the image work in Scheme. Each file is load → edit → export
→ **delete the image** (or memory grows unbounded across a big run).

```python
import glob, os
from gimp_bridge import GimpBridge
b = GimpBridge()

def edit_one(path, outdir):
    img = int(b.eval(f'(car (gimp-file-load RUN-NONINTERACTIVE "{path}" "{os.path.basename(path)}"))'))
    try:
        b.eval(f"(gimp-image-scale {img} 1200 (quotient (* 1200 (car (gimp-image-height {img}))) (car (gimp-image-width {img}))))")
        d = b.eval(f"(car (gimp-image-get-active-drawable {img}))").strip()
        b.eval(f"(plug-in-unsharp-mask RUN-NONINTERACTIVE {img} {d} 3.0 0.5 0)")
        b.eval(f"(gimp-image-flatten {img})")
        d = b.eval(f"(car (gimp-image-get-active-drawable {img}))").strip()
        out = os.path.join(outdir, os.path.basename(path).rsplit(".",1)[0] + ".png")
        b.eval(f'(file-png-save RUN-NONINTERACTIVE {img} {d} "{out}" "x" 0 9 1 1 1 1 1)')
        return out
    finally:
        b.eval(f"(gimp-image-delete {img})")   # ALWAYS free it

for f in glob.glob("/path/in/*.jpg"):
    print(edit_one(f, "/path/out"))
```

Equivalent fully-headless one-shot (no persistent server) — good for cron:

```bash
gimp -i -b '(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "in.jpg" "in.jpg")))
                   (d   (car (gimp-image-flatten img))))
              (gimp-image-scale img 1200 800)
              (file-png-save RUN-NONINTERACTIVE img d "out.png" "x" 0 9 1 1 1 1 1)
              (gimp-image-delete img))' -b '(gimp-quit 0)'
```

## Multi-step pipeline hygiene

- **Free images** with `(gimp-image-delete id)` when done — they don't auto-close.
- **Scope context** with `(gimp-context-push)` … `(gimp-context-pop)` around any
  recipe that changes foreground color / brush / opacity, so you don't poison the
  next operation (the process is long-lived; state sticks). See 10-context-resources.
- **Reproducibility:** a finished edit *is* a Scheme script. Capture the exact
  `gimp_eval` calls you made and you can replay them on any image — that's your
  "saved action".
- **Selections persist** on an image until cleared. `(gimp-selection-none img)`
  before an export if you didn't mean to constrain it.

## Register reusable Scheme functions

The server keeps definitions across calls, so you can install a helper once and call
it many times in a session:

```scheme
(define (thumb img max)
  (let* ((w (car (gimp-image-width img))) (h (car (gimp-image-height img)))
         (s (min 1.0 (/ max (max w h)))))
    (gimp-image-scale img (round (* w s)) (round (* h s)))))
```
Then `(thumb 1 512)`. (For a *permanent* script, drop a `.scm` in
`~/.config/GIMP/2.10/scripts/` and `(gimp-scripts-refresh)` — but in-session
`define` is enough for agent work.)

## Performance notes

- One `gimp_eval` = one TCP round-trip (~ms). For tight loops, build a bigger Scheme
  expression and send it once rather than many tiny calls.
- Response payloads are capped at 65535 bytes by the protocol — don't return huge
  strings (e.g. whole pixel regions); write to a file and read the file instead.
- The server is single-threaded: concurrent clients serialize. Don't expect parallelism
  from multiple connections.

## See also

- `00-overview.md` — the execution model and the preview work-loop.
- `../../server.py` — 39 wrapper tools; `render_preview` for the see→edit loop.
- `../../README.md` (knowledge) — how this corpus is generated and kept live.
