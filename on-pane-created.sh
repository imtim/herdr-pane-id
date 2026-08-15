#!/usr/bin/env bash
# pane-id plugin: run on every pane.created event.
#
# Default behavior (zero noise — nothing is ever typed into the pane):
#   1. renames the pane so the herdr UI shows the pane ID as its label
#
# Optional behavior: prepend "[<pane-id>] " to the pane's shell prompt.
# This runs `PS1=...` via `pane run`, which leaves ONE typed command line
# in the pane (it cannot be erased reliably — terminal escape sequences
# collide with zsh/bash line editors). Enable it only if you accept that:
#
#   printf '1' > "$(herdr plugin config-dir pane-id)/prompt-prefix"
#
# For a zero-noise in-pane prompt instead, herdr injects HERDR_PANE_ID into
# every pane's environment — see README for the one-line rc snippet.
set -u

HERDR="${HERDR_BIN_PATH:-herdr}"
STATE_DIR="${HERDR_PLUGIN_STATE_DIR:-${TMPDIR:-/tmp}}"
CONFIG_DIR="${HERDR_PLUGIN_CONFIG_DIR:-}"
LOG="$STATE_DIR/pane-id.log"
mkdir -p "$STATE_DIR" 2>/dev/null || true

log() { printf '%s\n' "$*" >>"$LOG" 2>/dev/null || true; }

# --- 1. Resolve the new pane ID -------------------------------
PANE_ID="${HERDR_PANE_ID:-}"
if [ -z "$PANE_ID" ] && [ -n "${HERDR_PLUGIN_EVENT_JSON:-}" ]; then
  PANE_ID="$(printf '%s' "$HERDR_PLUGIN_EVENT_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
for path in (".data.pane.pane_id", ".pane.pane_id", ".pane_id"):
    node = d
    for key in path.lstrip(".").split("."):
        if not isinstance(node, dict):
            node = None
            break
        node = node.get(key)
    if isinstance(node, str) and node:
        print(node)
        sys.exit(0)
sys.exit(1)
')" 2>/dev/null || PANE_ID=""
fi
log "$(date '+%F %T') event=${HERDR_PLUGIN_EVENT:-} pane=$PANE_ID"
[ -z "$PANE_ID" ] && { log "  -> no pane id, skipping"; exit 0; }

# --- 2. Label the pane in the herdr UI (no output into the pane)
"$HERDR" pane rename "$PANE_ID" "▍ $PANE_ID" >>"$LOG" 2>&1 || log "  -> rename failed"

# --- 3. Optional prompt prefix (opt-in via config file) --------
if [ -n "$CONFIG_DIR" ] && [ -f "$CONFIG_DIR/prompt-prefix" ] \
   && [ "$(cat "$CONFIG_DIR/prompt-prefix" 2>/dev/null)" != "0" ]; then
  FG=""
  for _ in {1..15}; do
    FG="$("$HERDR" pane process-info --pane "$PANE_ID" 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    d = d.get("result", d).get("process_info", d)
    fg = d.get("foreground_processes") or []
    print(fg[0].get("argv0", "") if fg else "")
except Exception:
    print("")
')"
    case "$FG" in zsh|bash|-zsh|-bash) break ;; esac
    sleep 1
  done
  case "$FG" in
    zsh|-zsh|bash|-bash)
      log "  -> prompt prefix enabled, foreground=$FG"
      "$HERDR" pane run "$PANE_ID" "PS1='[$PANE_ID] '\$PS1" >>"$LOG" 2>&1 || true
      ;;
    *)
      log "  -> prompt prefix skipped, foreground=$FG"
      ;;
  esac
fi
exit 0
