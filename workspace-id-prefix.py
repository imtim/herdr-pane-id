#!/usr/bin/env python3
"""pane-id plugin startup hook: append the workspace id to its label.

Makes the workspace display name "Projects: wP" (name + id) so the workspace id
is always visible in the herdr UI. Idempotent: labels already ending with
": <id>" are left alone. Labels in the old "<id> Name" format are migrated.

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
    logmsg(f"{datetime.datetime.now():%F %T} startup: append workspace id to label")
    res = run("workspace", "list")
    if not res:
        logmsg("startup: workspace list failed")
        return 0
    for w in res.get("workspaces", []):
        ws_id = w["workspace_id"]
        label = w.get("label", "")
        suffix = ": " + ws_id
        if label.endswith(suffix):
            continue  # already in "Name: id" format
        if label.startswith(ws_id + " "):
            label = label[len(ws_id) + 1:]  # migrate old "id Name" format
        new_label = f"{label}{suffix}" if label else ws_id
        if run("workspace", "rename", ws_id, new_label) is not None:
            logmsg(f"startup: {ws_id} '{label}' -> '{new_label}'")
        else:
            logmsg(f"startup: rename failed for {ws_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
