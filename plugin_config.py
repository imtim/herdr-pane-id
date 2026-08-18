#!/usr/bin/env python3
"""Shared config loader for the pane-id plugin.

Reads "$HERDR_PLUGIN_CONFIG_DIR/config.toml" (the directory printed by
`herdr plugin config-dir pane-id`). Missing or invalid config falls back to
defaults; a commented template is seeded on first use. herdr has no built-in
plugin settings API (plugin v1), so this is the standard config-file pattern.

CLI:
    python3 plugin-config.py                print effective config as JSON
    python3 plugin-config.py get format.separator   print one value
"""
import json
import os
import sys

DEFAULTS = {
    "behavior": {
        "workspace": True,
        "tab": True,
        "pane": True,
    },
    "format": {
        "workspace": {"separator": ":"},
        "tab": {"separator": ":", "number_separator": "_"},
        "pane": {"separator": ":"},
    },
}

TYPES = ("workspace", "tab", "pane")

CONFIG_TEMPLATE = """# herdr-pane-id plugin configuration
# ==============================================================
# Seeded automatically; edits are picked up on the next event or watcher
# cycle (no herdr restart needed). Location: the directory printed by
# `herdr plugin config-dir pane-id` (env: $HERDR_PLUGIN_CONFIG_DIR).
#
# Every option has a per-type variant (workspace / tab / pane) so you can
# mix styles freely. Invalid or missing values fall back to the defaults
# shown here.

[behavior]
# Keep the id visible even after a manual rename?
#   true  -> the id is appended to your name: "MyName:wP" / "MyTab:t2" / "MyPane:pF"
#   false -> a manual rename hides the id; the label stays exactly as you set it
# Only manual labels are affected; auto-managed labels (pF, "pi | pF",
# "1_t1:p1", "<derived>:wP") always show the ids.
workspace = true    # example: manual rename "MyProject" stays "MyProject:wR"
tab = true          # example: manual rename "MyTab" stays "MyTab:t2"
pane = true         # example: manual rename "MyPane" stays "MyPane:pF"

# --- Example: hide the id only for panes, keep it for workspace and tab ---
# workspace = true
# tab = true
# pane = false

[format.workspace]
# Separator between the workspace name and its id.
separator = ":"     # "trading-manager:wR" (":"), "trading-manager_wR" ("_"), "trading-manager wR" (" ")

# --- Example: underscore-separated workspace labels ---
# separator = "_"

[format.tab]
# Separator between the tab name/id and the pane id.
separator = ":"     # "MyTab:t2" (manual), "1_t1:p1" (auto)
# Separator between the tab number and the tab id (auto labels).
number_separator = "_"   # "1_t1:p1" ("_"), "1-t1:p1" ("-"), "1 t1:p1" (" ")

# --- Example: tmux-like dash style ---
# separator = ":"
# number_separator = "-"    # "1-t1:p1"

[format.pane]
# Separator between the pane name and its id.
separator = ":"     # "MyPane:pF" (manual), "pi | pF" (auto, agent part unchanged)

# --- Example: underscore-separated pane labels ---
# separator = "_"    # "MyPane_pF"
"""


def config_path():
    d = os.environ.get("HERDR_PLUGIN_CONFIG_DIR", "")
    return os.path.join(d, "config.toml") if d else None


def seed_if_missing(path):
    try:
        if path and not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(CONFIG_TEMPLATE)
    except Exception:
        pass


def load():
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    path = config_path()
    if not path:
        return cfg
    seed_if_missing(path)
    try:
        import tomllib

        with open(path, "rb") as f:
            data = tomllib.load(f)
        behavior = data.get("behavior") or {}
        if isinstance(behavior, dict):
            legacy = behavior.get("always_visible")
            if isinstance(legacy, bool):  # pre-0.8 format: applies to all types
                for t in TYPES:
                    cfg["behavior"][t] = legacy
            for t in TYPES:
                if isinstance(behavior.get(t), bool):
                    cfg["behavior"][t] = behavior[t]
        fmt = data.get("format") or {}
        if isinstance(fmt, dict):
            legacy = fmt.get("separator")
            if isinstance(legacy, str):  # pre-0.8 format: applies to all types
                for t in TYPES:
                    cfg["format"][t]["separator"] = legacy
            for t in TYPES:
                v = fmt.get(t)
                if isinstance(v, dict):
                    for key in ("separator", "number_separator"):
                        if isinstance(v.get(key), str) and key in cfg["format"][t]:
                            cfg["format"][t][key] = v[key]
    except Exception:
        pass
    return cfg


def get_value(cfg, keys):
    node = cfg
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return None
        node = node[k]
    return node


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "get":
        keys = sys.argv[2].split(".") if "." in sys.argv[2] else sys.argv[2:]
        v = get_value(load(), keys)
        if v is None:
            return 1
        print(v)
        return 0
    print(json.dumps(load()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
