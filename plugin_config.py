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
    "behavior": {"always_visible": True},
    "format": {"separator": ":"},
}

CONFIG_TEMPLATE = """# herdr-pane-id plugin configuration
# Seeded automatically; edits are picked up on the next event or watcher
# cycle (no herdr restart needed). Location: the directory printed by
# `herdr plugin config-dir pane-id` (env: $HERDR_PLUGIN_CONFIG_DIR)

[behavior]
# Keep the workspace/tab/pane id visible even after a manual rename:
#   true  -> "MyName:wP" / "MyTab:t2" / "MyPane:pF"   (default)
#   false -> a manual rename hides the id again
always_visible = true

[format]
# Separator between a name and its id: ":wP", "_wP", " wP", ...
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
        for section, values in data.items():
            if isinstance(values, dict) and isinstance(cfg.get(section), dict):
                cfg[section].update(
                    {k: v for k, v in values.items() if k in cfg[section]}
                )
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
