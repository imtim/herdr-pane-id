#!/usr/bin/env bash
# pane-id plugin: label panes with their pane ID (+ agent name when detected),
# and keep single-pane tab labels in sync via tab-label.py.
#
# Handles two events:
#   pane.created        -> label "<pane-short-id>"           e.g. "pF"
#   pane.agent_detected -> label "<agent> | <pane-short-id>" e.g. "pi | pF";
#                          back to plain when the agent is released or gone
#
# On every event, tab-label.py reconciles tab labels: a tab with exactly one
# pane reads "<number>_<tab-id>:<pane-id>" (e.g. "1_t1:p1"); with two or more
# panes it shows the pane count instead ("1_t1(2)"). It is also run as a
# startup hook.
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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Plugin config (see plugin_config.py): id separator (":wP" / "_wP" / ...)
# and whether manual renames keep the id visible.
SEP="$(python3 "$SCRIPT_DIR/plugin_config.py" get format.separator 2>/dev/null || printf ':')"
AV="$(python3 "$SCRIPT_DIR/plugin_config.py" get behavior.always_visible 2>/dev/null || printf 'true')"

# --- Startup reconcile: append the short pane id to manual pane labels -----
# Manual (user-set) pane labels keep their name and get ":<pane-id>" appended
# so the pane id is always visible ("MyPane" -> "MyPane:pF"). Plugin-managed
# labels ("pF" / "<agent> | pF") are left for the event path. Runs once at
# startup because herdr emits no event when a pane is renamed manually.
if [ "${1:-}" = "--reconcile" ]; then
  python3 - "$SCRIPT_DIR" "$LOG" "$SEP" "$AV" <<'PY'
import json, os, re, subprocess, sys
sys.path.insert(0, sys.argv[1])
HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")
LOG = sys.argv[2]
SEP = sys.argv[3]
AV = sys.argv[4].strip().lower() in ("1", "true", "yes")
AUTO = re.compile(r"^(?:p[0-9A-Z]+|[^|]*\| *p[0-9A-Z]+)$")

def run(*args):
    r = subprocess.run([HERDR, *args], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get("result")
    except Exception:
        return None

res = run("pane", "list")
if res is None:
    sys.exit(0)
for p in res.get("panes", []):
    pane_id = p.get("pane_id") or ""
    label = p.get("label") or ""
    if not pane_id or not label:
        continue
    short_id = pane_id.split(":")[-1]
    if AUTO.match(label.strip()):
        continue  # plugin-managed label (plain id or '<agent> | id')
    if label.endswith(SEP + short_id) or label.endswith(":" + short_id):
        continue  # manual label already carries its id (any separator)
    if not AV:
        continue  # configured: manual renames hide the id
    new_label = f"{label}{SEP}{short_id}"
    if run("pane", "rename", pane_id, new_label) is not None:
        with open(LOG, "a") as f:
            f.write(f"pane: {pane_id} '{label}' -> '{new_label}' (manual + id)\n")
PY
  exit 0
fi

# --- Tab labels: "<number>_<tab-id>:<pane-id>" or "<number>_<tab-id>(<n>)" -
# Runs for every event (pane.created/closed/moved, tab.created,
# pane.agent_detected); tab-label.py is idempotent and only touches tabs
# whose label is herdr's default numbering or a label this plugin set.
if [ -f "$SCRIPT_DIR/tab-label.py" ]; then
  python3 "$SCRIPT_DIR/tab-label.py" >>"$LOG" 2>&1 || log "$(date '+%F %T') tab reconcile failed"
fi

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
    ;;
  pane.agent_detected)
    CUR="$( "$HERDR" pane get "$PANE_ID" 2>/dev/null | json_get result.pane.label result.label label 2>/dev/null || true )"
    if printf '%s' "$CUR" | python3 -c 'import re,sys; sys.exit(0 if re.match(r"^(p[0-9A-Z]+|[^|]*\| *p[0-9A-Z]+)$", sys.stdin.read().strip()) else 1)'; then
      # plugin-managed label (plain id or '<agent> | id'): apply the agent label
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
    else
      # manual label: keep the user's name; ensure the pane id stays visible
      if [ "$AV" = "false" ]; then
        exit 0  # configured: manual renames hide the id
      fi
      if [ -n "$CUR" ] && ! printf '%s' "$CUR" | grep -qE "(:|_|${SEP})${SHORT_ID}$"; then
        LABEL="$CUR${SEP}$SHORT_ID"
        log "  -> manual label '$CUR', appended pane id"
      else
        exit 0
      fi
    fi
    ;;
  *)
    exit 0
    ;;
esac

"$HERDR" pane rename "$PANE_ID" "$LABEL" >>"$LOG" 2>&1 || log "  -> rename failed"
exit 0
