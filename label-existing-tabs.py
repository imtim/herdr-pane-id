#!/usr/bin/env python3
"""pane-id plugin startup hook: label existing tabs.

Runs once when the herdr session is restored. Any tab whose label is still the
default number ("1", "2", ...) is renamed:

  - the workspace's first tab (number == 1) -> workspace id (e.g. "wP")
  - other tabs                             -> project name (cwd basename of the
                                              first pane in the tab)

Manual labels (non-numeric) are never touched.
"""
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


def project_name(tab_id, workspace_id):
    res = run("pane", "list", "--workspace", workspace_id)
    if not res:
        return None
    for p in res.get("panes", []):
        if p.get("tab_id") == tab_id and p.get("cwd"):
            base = os.path.basename(p["cwd"].rstrip("/"))
            return base or None
    return None


def main():
    logmsg(f"{__import__('datetime').datetime.now():%F %T} startup: labeling existing tabs")
    res = run("workspace", "list")
    if not res:
        logmsg("startup: workspace list failed")
        return 0
    for w in res.get("workspaces", []):
        ws_id = w["workspace_id"]
        tres = run("tab", "list", "--workspace", ws_id)
        if not tres:
            continue
        for t in tres.get("tabs", []):
            label = t.get("label", "")
            if not label.isdigit():
                continue  # manual or already named — leave alone
            if t.get("number") == 1:
                new_label = ws_id
            else:
                new_label = project_name(t["tab_id"], ws_id)
            if not new_label:
                continue
            if run("tab", "rename", t["tab_id"], new_label) is not None:
                logmsg(f"startup: {t['tab_id']} '{label}' -> '{new_label}'")
            else:
                logmsg(f"startup: rename failed for {t['tab_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
