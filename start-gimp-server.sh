#!/usr/bin/env bash
# Start GIMP 2.10 with the Script-Fu TCP server bound to localhost:10008.
# Idempotent: exits early if the port is already serving.
#
#   ./start-gimp-server.sh          headless (fast, no window) — default
#   ./start-gimp-server.sh --gui    open the GIMP WINDOW too, so you can WATCH
#                                    the agent work live (edits appear in real time)
#
# In --gui mode, use the `show <image_id>` MCP tool (or call gimp-display-new) to
# pop an image into a window; every mutating tool already flushes the display.
set -euo pipefail

HOST="${GIMP_HOST:-127.0.0.1}"
PORT="${GIMP_PORT:-10008}"
LOG="${GIMP_LOG:-/tmp/gimp-scriptfu.log}"

MODE="headless"
case "${1:-}" in
  --gui|-g) MODE="gui" ;;
  "" ) ;;
  * ) echo "usage: $0 [--gui]" >&2; exit 2 ;;
esac

if (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
  echo "Script-Fu server already up on ${HOST}:${PORT} (mode unchanged — stop the old one to switch)"
  exit 0
fi

SRV="(plug-in-script-fu-server RUN-NONINTERACTIVE \"${HOST}\" ${PORT} \"${LOG}\")"
# NOTE: never pass -f (--no-fonts) — text layers (gimp-text-fontname) need fonts
# loaded or they silently render nothing.
if [ "$MODE" = "gui" ]; then
  echo "Launching GIMP (GUI, watchable) + Script-Fu server on ${HOST}:${PORT}…"
  if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "WARNING: no DISPLAY/WAYLAND_DISPLAY set — GUI may not appear. Run from a graphical session." >&2
  fi
  # no -i: the window opens; the server runs alongside it (same as Filters ▸ Script-Fu ▸ Start Server)
  setsid nohup gimp \
    --batch-interpreter=plug-in-script-fu-eval \
    -b "$SRV" \
    </dev/null >/tmp/gimp-server-stdout.log 2>&1 &
else
  echo "Launching GIMP (headless) Script-Fu server on ${HOST}:${PORT} (log: ${LOG})…"
  setsid nohup gimp -i \
    --batch-interpreter=plug-in-script-fu-eval \
    -b "$SRV" \
    </dev/null >/tmp/gimp-server-stdout.log 2>&1 &
fi
disown || true

for i in $(seq 1 45); do
  if (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
    echo "ready after ${i}s (${MODE})"
    [ "$MODE" = "gui" ] && echo "→ window should be open; use the show tool to view images live."
    exit 0
  fi
  sleep 1
done
echo "ERROR: server did not come up within 45s — see ${LOG} and /tmp/gimp-server-stdout.log" >&2
exit 1
