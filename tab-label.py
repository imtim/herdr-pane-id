#!/usr/bin/env python3
"""Relabel tabs so a single-pane tab shows "<number>: <tab id>: <pane id>".

Example: a tab with herdr's default label "3", tab id "wP:t5" and one pane
"wP:pP" is renamed to "3: t5: pP". When the tab gains a second pane the
label reverts to the plain number ("3"). Manual (non-numeric) tab labels
are never touched.

The base number always comes from the tab's own label: herdr's default tab
numbering (a plain integer) or the integer prefix of a label this plugin set
("3: t5: pP" -> base "3"). This keeps the label consistent with what the tab
bar displays, even when herdr's internal tab ordinals drift as tabs close.

Idempotent, so it is safe to call from every pane/tab event and at startup.
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

DEFAULT_LABEL = re.compile(r"^[0-9]+$")                       # herdr default tab numbering
OWN_LABEL = re.compile(r"^([0-9]+): t[0-9A-Za-z]+: p[0-9A-Za-z]+$")  # current format
OLD_LABEL = re.compile(r"^([0-9]+): p[0-9A-Za-z]+$")         # pre-0.3.1 format, upgraded


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


def short(pane_id):
    return pane_id.split(":")[-1]


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
                m = OWN_LABEL.match(label)
                if not m:
                    m = OLD_LABEL.match(label)  # upgrade pre-0.3.1 "3: pP" labels
                if not m:
                    continue  # manual label — leave it alone
                base = m.group(1)
            tab_panes = panes_by_tab.get(t.get("tab_id"), [])
            if len(tab_panes) == 1:
                new_label = f"{base}: {short(t['tab_id'])}: {short(tab_panes[0]['pane_id'])}"
            else:
                new_label = base
            if new_label != label:
                if run("tab", "rename", t["tab_id"], new_label) is not None:
                    logmsg(f"{t['tab_id']} '{label}' -> '{new_label}' ({len(tab_panes)} panes)")
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
