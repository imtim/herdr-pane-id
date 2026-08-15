#!/usr/bin/env python3
"""pane-id plugin startup hook: prefix every workspace label with its id.

Makes the workspace display name "wP Projects" (id + name) so the workspace id
is always visible in the herdr UI. Idempotent: labels already starting with
"<id> " are left alone, so manual renames that keep the prefix survive, and a
manual rename like "Projects2" becomes "wP Projects2" on the next start.

Tabs are left at their default 1/2/3 numbering (the plugin never renames tabs).
"""
import datetime
import json
import os
import subprocess
import sys

HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")
STATE_DIR = os.environ.get("HERDR_PLUGIN_STATE_DIR", "/tmp")
LOG = os.path.join(STATE_DIR, "pane-id.log")


def run(*args):
    r = subprocess.run([HERDR, *args], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get("result")
    except Exception:
        return None


def logmsg(msg):
    try:
        with open(LOG, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def main():
    logmsg(f"{datetime.datetime.now():%F %T} startup: prefix workspace labels with id")
    res = run("workspace", "list")
    if not res:
        logmsg("startup: workspace list failed")
        return 0
    for w in res.get("workspaces", []):
        ws_id = w["workspace_id"]
        label = w.get("label", "")
        if label.startswith(ws_id + " "):
            continue  # already prefixed
        new_label = f"{ws_id} {label}" if label else ws_id
        if run("workspace", "rename", ws_id, new_label) is not None:
            logmsg(f"startup: {ws_id} '{label}' -> '{new_label}'")
        else:
            logmsg(f"startup: rename failed for {ws_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
