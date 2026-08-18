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
        "tab": {"separator": ":"},
        "pane": {"separator": ":"},
    },
}

TYPES = ("workspace", "tab", "pane")

CONFIG_TEMPLATE = """# herdr-pane-id plugin configuration
# Seeded automatically; edits are picked up on the next event or watcher
# cycle (no herdr restart needed). Location: the directory printed by
# `herdr plugin config-dir pane-id` (env: $HERDR_PLUGIN_CONFIG_DIR)

[behavior]
# Keep the id visible even after a manual rename, per label type:
#   true  -> "MyName:wP" / "MyTab:t2" / "MyPane:pF"   (default)
#   false -> a manual rename hides the id again
workspace = true
tab = true
pane = true

[format.workspace]
# Separator between the workspace name and its id: ":wP", "_wP", " wP", ...
separator = ":"

[format.tab]
# Separator between the tab name and its id: ":t2", "_t2", ...
separator = ":"

[format.pane]
# Separator between the pane name and its id: ":pF", "_pF", ...
separator = ":"
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
                if isinstance(v, dict) and isinstance(v.get("separator"), str):
                    cfg["format"][t]["separator"] = v["separator"]
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
