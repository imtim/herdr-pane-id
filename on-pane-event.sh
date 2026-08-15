#!/usr/bin/env bash
# pane-id plugin: label panes with their pane ID (+ agent name when detected).
#
# Handles two events:
#   pane.created        -> label "<pane-short-id>"           e.g. "pF"
#   pane.agent_detected -> label "<agent> | <pane-short-id>" e.g. "pi | pF";
#                          back to plain when the agent is released or gone
#
# Nothing is typed into the pane — the label is herdr-side only (pane rename).
set -u

HERDR="${HERDR_BIN_PATH:-herdr}"
STATE_DIR="${HERDR_PLUGIN_STATE_DIR:-${TMPDIR:-/tmp}}"
LOG="$STATE_DIR/pane-id.log"
mkdir -p "$STATE_DIR" 2>/dev/null || true

log() { printf '%s\n' "$*" >>"$LOG" 2>/dev/null || true; }

# json_get <path>... reads JSON from stdin and prints the first found value
# (python3 -c so stdin stays available for the piped JSON data)
json_get() {
  python3 -c '
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
' "$@"
}

EVENT="${HERDR_PLUGIN_EVENT:-}"
EVENT_JSON="${HERDR_PLUGIN_EVENT_JSON:-}"

# --- Resolve the pane id --------------------------------------
PANE_ID="${HERDR_PANE_ID:-}"
if [ -z "$PANE_ID" ] && [ -n "$EVENT_JSON" ]; then
  PANE_ID="$(printf '%s' "$EVENT_JSON" | json_get data.pane_id data.pane.pane_id pane_id)" 2>/dev/null || PANE_ID=""
fi
[ -z "$PANE_ID" ] && { log "$(date '+%F %T') event=$EVENT no pane id"; exit 0; }
log "$(date '+%F %T') event=$EVENT pane=$PANE_ID json=$EVENT_JSON"

# short pane id: wP:pF -> pF
SHORT_ID="${PANE_ID##*:}"

case "$EVENT" in
  pane.created)
    LABEL="$SHORT_ID"
    # Name the tab after the project (cwd basename) when it still has the
    # default numeric label ("1", "2", ...). Manual labels are never touched.
    TAB_ID="${HERDR_TAB_ID:-}"
    [ -z "$TAB_ID" ] && TAB_ID="$(printf '%s' "$EVENT_JSON" | json_get data.pane.tab_id tab_id 2>/dev/null || true)"
    CWD="$(printf '%s' "$EVENT_JSON" | json_get data.pane.cwd cwd 2>/dev/null || true)"
    if [ -n "$TAB_ID" ] && [ -n "$CWD" ]; then
      TAB_LABEL="$( "$HERDR" tab get "$TAB_ID" 2>/dev/null | json_get result.tab.label label 2>/dev/null || true)"
      case "$TAB_LABEL" in
        ''|*[!0-9]*) : ;; # not the default numeric label — leave it alone
        *)
          BASE="${CWD##*/}"
          if [ -n "$BASE" ] && "$HERDR" tab rename "$TAB_ID" "$BASE" >>"$LOG" 2>&1; then
            log "  -> tab $TAB_ID renamed to $BASE"
          else
            log "  -> tab rename failed (tab=$TAB_ID cwd=$CWD)"
          fi
          ;;
      esac
    fi
    ;;
  pane.agent_detected)
    AGENT="$(printf '%s' "$EVENT_JSON" | json_get data.agent agent 2>/dev/null || true)"
    RELEASED="$(printf '%s' "$EVENT_JSON" | json_get data.released released 2>/dev/null || true)"
    if [ -n "$AGENT" ] && [ "$AGENT" != "None" ] && [ "$RELEASED" != "True" ]; then
      # prefer the user-assigned agent name (e.g. `agent start testpi`), which is
      # what you address with `herdr agent prompt <name>`; fall back to the
      # detected kind label
      NAME="$( "$HERDR" agent list 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    for a in d.get("result", {}).get("agents", []):
        if a.get("pane_id") == sys.argv[1]:
            print(a.get("name") or a.get("agent") or "")
            sys.exit(0)
except Exception:
    pass
' "$PANE_ID" )"
      [ -z "$NAME" ] && NAME="$AGENT"
      LABEL="$NAME | $SHORT_ID"
      log "  -> agent=$AGENT name=$NAME"
    else
      LABEL="$SHORT_ID"
      log "  -> agent released/gone, back to plain label"
    fi
    ;;
  *)
    exit 0
    ;;
esac

"$HERDR" pane rename "$PANE_ID" "$LABEL" >>"$LOG" 2>&1 || log "  -> rename failed"
exit 0
