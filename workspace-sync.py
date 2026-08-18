#!/usr/bin/env python3
"""pane-id plugin workspace sync: keep every workspace label as "<name>:<id>".

Each workspace label is kept in the form "<base>:<ws-id>" (e.g. "Projects:wP"):

- Auto-managed bases follow the workspace's root pane folder, using the same
  derivation herdr uses natively: the enclosing git repo root name when the
  folder is inside a repo, otherwise the folder basename ("~" for $HOME).
- A manually renamed workspace keeps the user's base; only the ":<id>" suffix
  is re-appended (within the next reconcile).
- Legacy formats are migrated: "Name: id" and the old "id Name" both become
  "Name:id".

herdr emits no event when a pane's cwd changes (folder-following is a render
path concern there), so this script reconciles at startup, on
workspace.created / workspace.renamed / workspace.updated / pane.closed /
pane.moved events, and from a small detached watcher loop (--watch) spawned
by the startup run. The watcher polls every few seconds and covers plain
`cd`s. Disable it with HERDR_PANE_ID_WATCHER=0.

State: "$HERDR_PLUGIN_STATE_DIR/workspace-bases.json" records per-workspace
mode ("auto" | "manual") and the base this plugin last wrote, so manual names
survive reconciliation and auto names keep following the folder.

Usage:
    workspace-sync.py          one-shot reconcile (startup / event hooks)
    workspace-sync.py --watch detached watcher loop (spawned internally)
"""
import datetime
import fcntl
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plugin_config  # noqa: E402

HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")
STATE_DIR = os.environ.get("HERDR_PLUGIN_STATE_DIR", "/tmp")
LOG = os.path.join(STATE_DIR, "pane-id.log")
STATE_FILE = os.path.join(STATE_DIR, "workspace-bases.json")
LOCK_FILE = os.path.join(STATE_DIR, "workspace-sync.lock")
PID_FILE = os.path.join(STATE_DIR, "pane-id-watcher.pid")

_CFG = plugin_config.load()
WS_SEP = _CFG["format"]["workspace"]["separator"]   # ":wP" / "_wP" / ...
WS_AV = _CFG["behavior"]["workspace"]


def reload_config():
    """Re-read config.toml (the watcher is long-lived, so it reloads per poll)."""
    global _CFG, WS_SEP, WS_AV
    _CFG = plugin_config.load()
    WS_SEP = _CFG["format"]["workspace"]["separator"]
    WS_AV = _CFG["behavior"]["workspace"]

# herdr's public-id alphabet (encode_public_number in src/workspace.rs)
PANE_ALPHABET = "123456789ABCDEFGHJKMNPQRSTVWXYZ0"

_LOCK = None


def logmsg(msg):
    try:
        with open(LOG, "a") as f:
            f.write(f"{datetime.datetime.now():%F %T} {msg}\n")
    except Exception:
        pass


def cli(*args):
    r = subprocess.run([HERDR, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"herdr {' '.join(args)} failed: {r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout).get("result")
    except Exception as exc:
        raise RuntimeError(f"herdr {' '.join(args)} bad output: {exc}") from exc


# --- label derivation, mirroring herdr's src/workspace/git/discovery.rs ----

def git_dir_for_repo_root(repo_root):
    git_path = os.path.join(repo_root, ".git")
    if os.path.isdir(git_path):
        return git_path
    try:
        with open(git_path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
    except OSError:
        text = ""
    if text.startswith("gitdir:"):  # linked worktree
        rel = text[len("gitdir:"):].strip()
        return rel if os.path.isabs(rel) else os.path.join(repo_root, rel)
    # bare repository: HEAD + objects + refs, config marks bare
    if (
        os.path.isfile(os.path.join(repo_root, "HEAD"))
        and os.path.isdir(os.path.join(repo_root, "objects"))
        and os.path.isdir(os.path.join(repo_root, "refs"))
    ):
        try:
            with open(os.path.join(repo_root, "config"), encoding="utf-8", errors="replace") as f:
                cfg = f.read()
        except OSError:
            cfg = ""
        if re.search(r"(?im)^\s*bare\s*=\s*true\s*$", cfg):
            return repo_root
    return None


def git_repo_root(start):
    current = start if os.path.isdir(start) else os.path.dirname(start)
    while True:
        git_dir = git_dir_for_repo_root(current)
        if git_dir is not None and os.path.isfile(os.path.join(git_dir, "HEAD")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def derive_label(cwd):
    root = git_repo_root(cwd)
    if root is not None:
        return os.path.basename(root) or cwd
    home = os.environ.get("HOME")
    if home and os.path.normpath(cwd) == os.path.normpath(home):
        return "~"
    return os.path.basename(cwd) or cwd


# --- root pane of each workspace (first tab's root pane, like herdr) -------

def public_number(raw):
    n = 0
    for ch in raw:
        n = n * len(PANE_ALPHABET) + PANE_ALPHABET.index(ch) + 1
    return n


def tab_number(tab_id):
    try:
        return public_number(tab_id.split(":")[1][1:])  # after 't'
    except Exception:
        return 0x7FFFFFFF


def pane_number(pane_id):
    try:
        return public_number(pane_id.split(":")[1][1:])  # after 'p'
    except Exception:
        return 0x7FFFFFFF


def root_pane_cwd(panes):
    """cwd of the lowest-numbered pane in the lowest-numbered tab."""
    if not panes:
        return None
    root = min(panes, key=lambda p: (tab_number(p.get("tab_id", "")),
                                     pane_number(p.get("pane_id", ""))))
    return root.get("cwd") or None


# --- label parsing ---------------------------------------------------------

def split_label(label, ws_id, sep=":"):
    """Return (base, had_suffix). Accepts 'Name:id' (current separator or the
    historical ':' one) and legacy 'Name: id' / 'id Name'."""
    for s in (sep, ":", "_"):
        if label.endswith(s + ws_id):
            return label[: -len(ws_id) - len(s)], True
    if label.endswith(": " + ws_id):  # legacy 'Name: id'
        return label[: -len(ws_id) - 2], True
    if label.startswith(ws_id + " "):  # legacy 'id Name'
        return label[len(ws_id) + 1:], True
    return label, False


# --- state ----------------------------------------------------------------

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
    except Exception as exc:
        logmsg(f"state: save failed: {exc}")


def lock():
    global _LOCK
    try:
        _LOCK = open(LOCK_FILE, "w")
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        try:
            if _LOCK:
                _LOCK.close()
        except Exception:
            pass
        _LOCK = None
        return False


def unlock():
    global _LOCK
    if _LOCK:
        try:
            fcntl.flock(_LOCK, fcntl.LOCK_UN)
            _LOCK.close()
        except Exception:
            pass
        _LOCK = None


# --- reconcile ------------------------------------------------------------

def reconcile():
    """One pass over all workspaces. Returns number of renames (or -1 if skipped)."""
    if not lock():
        return -1  # another sync (event hook / watcher) is running
    try:
        workspaces = cli("workspace", "list").get("workspaces", [])
        panes = cli("pane", "list").get("panes", [])
        by_ws = {}
        for p in panes:
            by_ws.setdefault(p.get("workspace_id"), []).append(p)
        state = load_state()
        live_ids = {w.get("workspace_id") for w in workspaces}
        for stale in [k for k in state if k not in live_ids]:
            del state[stale]
        renames = 0
        for ws in workspaces:
            ws_id = ws.get("workspace_id")
            if not ws_id:
                continue
            label = ws.get("label") or ""
            suffix = WS_SEP + ws_id
            base, had_suffix = split_label(label, ws_id, WS_SEP)
            cwd = root_pane_cwd(by_ws.get(ws_id, []))
            derived = derive_label(cwd) if cwd else None

            st = state.get(ws_id)
            if st is None:
                # unknown: a label with our suffix (or matching the derived
                # name) is treated as auto; anything else is a manual name
                mode = "auto" if (had_suffix or (derived is not None and base == derived)) else "manual"
            else:
                mode = st.get("mode", "auto")
                if mode == "auto" and base != st.get("base", base):
                    # the label changed without this plugin -> manual rename
                    mode = "manual"

            if mode == "auto":
                desired = derived if derived is not None else base
                if not desired:
                    desired = ws_id
                new_label = desired if desired == ws_id else f"{desired}{suffix}"
            else:
                # manual: keep the user's name; add the id only when configured
                if WS_AV:
                    desired = base
                    if not desired:
                        desired = ws_id
                    new_label = desired if desired == ws_id else f"{desired}{suffix}"
                else:
                    desired = base
                    new_label = label  # manual rename hides the id

            state[ws_id] = {"mode": mode, "base": desired}
            if new_label != label:
                if cli("workspace", "rename", ws_id, new_label) is not None:
                    logmsg(f"workspace: {ws_id} '{label}' -> '{new_label}' (mode={mode})")
                    renames += 1
                else:
                    logmsg(f"workspace: rename failed for {ws_id}")
        save_state(state)
        return renames
    finally:
        unlock()


# --- watcher --------------------------------------------------------------

def spawn_watcher():
    if os.environ.get("HERDR_PANE_ID_WATCHER", "1") != "1":
        return False
    try:
        with open(PID_FILE, encoding="utf-8") as f:
            old = int(f.read().strip())
        os.kill(old, 0)  # still alive?
        out = subprocess.run(["ps", "-p", str(old), "-o", "command="],
                             capture_output=True, text=True).stdout
        if "workspace-sync.py" in out:
            return False  # already watching
    except (OSError, ValueError):
        pass
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--watch"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logmsg("watcher: spawned")
    return True


def watch_loop():
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    interval = float(os.environ.get("HERDR_PANE_ID_WATCH_INTERVAL", "5"))
    max_fails = int(os.environ.get("HERDR_PANE_ID_WATCH_MAX_FAILS", "60"))
    fails = 0
    while True:
        try:
            reload_config()
            reconcile()
            fails = 0
        except Exception as exc:
            logmsg(f"watcher: {exc}")
            fails += 1
            if fails >= max_fails:
                logmsg("watcher: giving up (herdr unreachable for too long)")
                break
        time.sleep(interval)


def main():
    if "--watch" in sys.argv:
        watch_loop()
        return 0
    if os.environ.get("HERDR_PLUGIN_EVENT", "") == "startup":
        spawn_watcher()
    try:
        renames = reconcile()
        if renames > 0:
            logmsg(f"sync: {renames} workspace(s) relabeled")
        return 0
    except Exception as exc:
        logmsg(f"sync: failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
