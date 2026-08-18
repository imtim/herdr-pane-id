#!/usr/bin/env python3
"""Relabel tabs compactly.

A single-pane tab with herdr's default numbering is renamed to
"<number>_<tab-id>:<pane-id>" (e.g. "1_t1:p1"); a tab with two or more panes
shows its pane count instead: "1_t1(2)". Manual (non-numeric) tab labels keep
the user's name with the short tab id appended ("MyTab" -> "MyTab:t2"), so the
tab id stays visible no matter what.

The base number always comes from the tab's own label: herdr's default tab
numbering (a plain integer) or the integer prefix of a label this plugin set
("1_t1:p1" -> base "1"). This keeps the label consistent with what the tab bar
displays, even when herdr's internal tab ordinals drift as tabs close.

Idempotent, so it is safe to call from every pane/tab event and at startup.
Labels from older plugin versions ("3: t5: pP" and "3: pP") are upgraded
automatically.
"""
import datetime
import json
import os
import re
import subprocess
import sys

HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")
STATE_DIR = os.environ.get("HERDR_PLUGIN_STATE_DIR", "/tmp")
LOG = os.path.join(STATE_DIR, "pane-id.log")

DEFAULT_LABEL = re.compile(r"^[0-9]+$")                                   # herdr default tab numbering
OWN_LABEL = re.compile(r"^([0-9]+)_t[0-9A-Za-z]+(:p[0-9A-Za-z]+|\(\d+\))$")  # current format
LEGACY_TAB_LABEL = re.compile(r"^([0-9]+): t[0-9A-Za-z]+: p[0-9A-Za-z]+$")   # 0.3.1, upgraded
LEGACY_PANE_LABEL = re.compile(r"^([0-9]+): p[0-9A-Za-z]+$")                 # 0.3.0, upgraded


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
            f.write(f"{datetime.datetime.now():%F %T} tab-label: {msg}\n")
    except Exception:
        pass


def short(pid):
    return pid.split(":")[-1]


def reconcile():
    res = run("tab", "list")
    if not res:
        logmsg("tab list failed")
        return
    # Group tabs by workspace so each workspace's panes are fetched once.
    by_ws = {}
    for t in res.get("tabs", []):
        by_ws.setdefault(t.get("workspace_id"), []).append(t)

    for ws_id, tabs in by_ws.items():
        plist = run("pane", "list", "--workspace", ws_id)
        panes = plist.get("panes", []) if plist else []
        panes_by_tab = {}
        for p in panes:
            panes_by_tab.setdefault(p.get("tab_id"), []).append(p)
        for t in tabs:
            label = t.get("label", "")
            if DEFAULT_LABEL.match(label):
                base = label
            else:
                m = OWN_LABEL.match(label) or LEGACY_TAB_LABEL.match(label) or LEGACY_PANE_LABEL.match(label)
                if not m:
                    # manual label: keep the user's name, append the short tab
                    # id so the tab id always stays visible ("MyTab" -> "MyTab:t2")
                    short_tid = short(t["tab_id"])
                    if label.endswith(":" + short_tid):
                        continue
                    new_label = f"{label}:{short_tid}"
                    if new_label != label and run("tab", "rename", t["tab_id"], new_label) is not None:
                        logmsg(f"{t['tab_id']} '{label}' -> '{new_label}' (manual + id)")
                    continue
                base = m.group(1)
            tab_panes = panes_by_tab.get(t.get("tab_id"), [])
            count = len(tab_panes)
            if count == 1:
                new_label = f"{base}_{short(t['tab_id'])}:{short(tab_panes[0]['pane_id'])}"
            elif count >= 2:
                new_label = f"{base}_{short(t['tab_id'])}({count})"
            else:
                new_label = base  # no panes left (should not happen)
            if new_label != label:
                if run("tab", "rename", t["tab_id"], new_label) is not None:
                    logmsg(f"{t['tab_id']} '{label}' -> '{new_label}' ({count} panes)")
                else:
                    logmsg(f"rename failed for {t['tab_id']} '{label}' -> '{new_label}'")


def main():
    try:
        reconcile()
    except Exception as e:
        logmsg(f"error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
