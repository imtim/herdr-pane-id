#!/usr/bin/env bash
# pane-id plugin: run on every pane.created event.
#
# For each new pane it:
#   1. renames the pane so the herdr UI title shows the pane ID
#   2. waits for the pane shell to reach its interactive prompt, then
#      prepends "[<pane-id>] " to the prompt (session-local, no rc files touched)
#   3. prints a one-line banner into the pane
#
# Runtime env provided by herdr: HERDR_BIN_PATH, HERDR_PLUGIN_EVENT_JSON,
# HERDR_PLUGIN_STATE_DIR, HERDR_PANE_ID (when available).
set -u

HERDR="${HERDR_BIN_PATH:-herdr}"
STATE_DIR="${HERDR_PLUGIN_STATE_DIR:-${TMPDIR:-/tmp}}"
LOG="$STATE_DIR/pane-id.log"
mkdir -p "$STATE_DIR" 2>/dev/null || true

log() { printf '%s\n' "$*" >>"$LOG" 2>/dev/null || true; }
json_get() {
  python3 - "$1" <<'PYEOF'
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
PYEOF
}

# --- 1. Resolve the new pane ID -------------------------------
PANE_ID="${HERDR_PANE_ID:-}"
if [ -z "$PANE_ID" ] && [ -n "${HERDR_PLUGIN_EVENT_JSON:-}" ]; then
  PANE_ID="$(printf '%s' "$HERDR_PLUGIN_EVENT_JSON" | json_get)" 2>/dev/null || PANE_ID=""
fi
log "$(date '+%F %T') event=${HERDR_PLUGIN_EVENT:-} pane=$PANE_ID"
[ -z "$PANE_ID" ] && { log "  -> no pane id, skipping"; exit 0; }

# --- 2. Label the pane in the herdr UI ------------------------
"$HERDR" pane rename "$PANE_ID" "▍ $PANE_ID" >>"$LOG" 2>&1 || log "  -> rename failed"

# --- 3. Wait until the pane shell is at an interactive prompt -
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
  # at an interactive prompt the foreground process is the shell itself
  case "$FG" in zsh|bash|-zsh|-bash|sh|dash|fish) break ;; esac
  sleep 1
done
log "  -> foreground=$FG"

case "$FG" in
  zsh|-zsh)
    # zsh: PROMPT and PS1 are the same variable; prepend the ID prefix
    "$HERDR" pane run "$PANE_ID" "PS1='[$PANE_ID] '" >>"$LOG" 2>&1 || true
    ;;
  bash|-bash)
    "$HERDR" pane run "$PANE_ID" "PS1='[$PANE_ID] '" >>"$LOG" 2>&1 || true
    ;;
  sh|dash|fish)
    ;;
esac

# --- 4. One-line banner inside the pane -----------------------
case "$FG" in
  zsh|bash|-zsh|-bash|sh|dash|fish)
    "$HERDR" pane run "$PANE_ID" "printf '\033[2m▍ pane %s\033[0m\n' '$PANE_ID'" >>"$LOG" 2>&1 || true
    ;;
esac
log "  -> done"
exit 0
