#!/usr/bin/env bash
# Start GIMP 2.10 headless with the Script-Fu TCP server bound to localhost:10008.
# Idempotent: exits early if the port is already serving.
set -euo pipefail

HOST="${GIMP_HOST:-127.0.0.1}"
PORT="${GIMP_PORT:-10008}"
LOG="${GIMP_LOG:-/tmp/gimp-scriptfu.log}"

if (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
  echo "Script-Fu server already up on ${HOST}:${PORT}"
  exit 0
fi

echo "Launching GIMP Script-Fu server on ${HOST}:${PORT} (log: ${LOG})…"
# -i no GUI, -d no data preload (faster). NOTE: do NOT pass -f (--no-fonts) —
# text layers (gimp-text-fontname) need fonts loaded or they silently no-op.
setsid nohup gimp -i \
  --batch-interpreter=plug-in-script-fu-eval \
  -b "(plug-in-script-fu-server RUN-NONINTERACTIVE \"${HOST}\" ${PORT} \"${LOG}\")" \
  </dev/null >/tmp/gimp-server-stdout.log 2>&1 &
disown || true

for i in $(seq 1 30); do
  if (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
    echo "ready after ${i}s"
    exit 0
  fi
  sleep 1
done
echo "ERROR: server did not come up within 30s — see ${LOG} and /tmp/gimp-server-stdout.log" >&2
exit 1
