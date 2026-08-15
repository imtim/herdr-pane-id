#!/usr/bin/env bash
# pane-id plugin: label panes with their pane ID (+ agent name when detected).
#
# Handles two events:
#   pane.created        -> label "▍ <pane_id>"
#   pane.agent_detected -> label "<agent> ▍ <pane_id>"; back to "▍ <pane_id>"
#                          when the agent is released or gone
#
# Nothing is typed into the pane — the label is herdr-side only (pane rename).
set -u

HERDR="${HERDR_BIN_PATH:-herdr}"
STATE_DIR="${HERDR_PLUGIN_STATE_DIR:-${TMPDIR:-/tmp}}"
LOG="$STATE_DIR/pane-id.log"
mkdir -p "$STATE_DIR" 2>/dev/null || true

log() { printf '%s\n' "$*" >>"$LOG" 2>/dev/null || true; }

# json_get <path>... reads JSON from stdin and prints the first found value
json_get() {
  python3 - "$@" <<'PYEOF'
import json, sys
d = json.load(sys.stdin)
for path in sys.argv[1:]:
    node = d
    for key in path.split("."):
        if not isinstance(node, dict):
            node = None
            break
        node = node.get(key)
    if node is not None:
        print(node)
        sys.exit(0)
sys.exit(1)
PYEOF
}

EVENT="${HERDR_PLUGIN_EVENT:-}"
EVENT_JSON="${HERDR_PLUGIN_EVENT_JSON:-}"

# --- Resolve the pane id --------------------------------------
PANE_ID="${HERDR_PANE_ID:-}"
if [ -z "$PANE_ID" ] && [ -n "$EVENT_JSON" ]; then
  PANE_ID="$(printf '%s' "$EVENT_JSON" | json_get data.pane_id data.pane.pane_id pane_id)" 2>/dev/null || PANE_ID=""
fi
[ -z "$PANE_ID" ] && { log "$(date '+%F %T') event=$EVENT no pane id"; exit 0; }
log "$(date '+%F %T') event=$EVENT pane=$PANE_ID"

case "$EVENT" in
  pane.created)
    LABEL="▍ $PANE_ID"
    ;;
  pane.agent_detected)
    AGENT="$(printf '%s' "$EVENT_JSON" | json_get data.agent agent 2>/dev/null || true)"
    RELEASED="$(printf '%s' "$EVENT_JSON" | json_get data.released released 2>/dev/null || true)"
    if [ -n "$AGENT" ] && [ "$AGENT" != "None" ] && [ "$RELEASED" != "True" ]; then
      LABEL="$AGENT ▍ $PANE_ID"
      log "  -> agent=$AGENT"
    else
      LABEL="▍ $PANE_ID"
      log "  -> agent released/gone, back to plain label"
    fi
    ;;
  *)
    exit 0
    ;;
esac

"$HERDR" pane rename "$PANE_ID" "$LABEL" >>"$LOG" 2>&1 || log "  -> rename failed"
exit 0
