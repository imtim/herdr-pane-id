# herdr-pane-id

[English](README.md) | [中文](README.zh-CN.md)

Herdr plugin that labels every pane with its short pane ID (e.g. `pF`), plus the
agent name once herdr detects an agent (`pi | pF`) — so you always know which pane
you are looking at, and can target it from anywhere: `herdr pane run wP:pF ...`,
`herdr agent prompt pi ...`, or from another agent pane (pairs with the
[herdr agent skill](https://herdr.dev/docs/agent-skill/)).

Tabs follow the same idea in a compact form: a tab with exactly one pane shows
`1_t1:p1` (number, tab id, pane id); once a second pane is added it switches to
`1_t1(2)` with the pane count. Manual tab names keep the name with the tab id
appended (`MyTab:t2`). Workspaces show `Projects:wP` (name + id), also
for workspaces created after herdr started.

## Behavior

Nothing is typed into the pane — labels are herdr-side only (`pane rename` /
`tab rename` / `workspace rename`), so the screen stays completely clean.

| Event | Label |
| --- | --- |
| `pane.created` | `pF` |
| `pane.agent_detected` (agent present) | `<agent-name> | pF` |
| `pane.agent_detected` (released / gone) | `pF` |

Tab labels (reconciled on every pane/tab event and at startup):

| Tab state | Tab label |
| --- | --- |
| exactly one pane, default numbering | `1_t1:p1` |
| two or more panes | `1_t1(2)` (pane count) |
| manual (non-numeric) label | `Name:tN` (name kept, tab id appended) |

The base number always comes from the tab's own label, so `1_t1:p1` stays
consistent with what the tab bar already displayed. The reconcile
(`tab-label.py`) is idempotent and self-heals: if the single pane in a tab
changes, the label is updated on the next event. Labels from older plugin
versions (`3: t5: pP`, `3: pP`) are upgraded automatically. A manual rename
is picked up on the `tab.renamed` event and gets the `:tN` id appended
immediately.

Workspace labels (reconciled at startup, on `workspace.created` /
`workspace.renamed` / `workspace.updated` / `pane.closed` / `pane.moved`, and by
a small watcher loop every few seconds):

| Workspace state | Workspace label |
| --- | --- |
| auto-managed | `<derived>:wP` |
| manually renamed | `<your-name>:wP` (suffix re-appended) |
| legacy `Name: id` / `id Name` | migrated to `Name:id` |

The auto-managed base follows the root pane's folder, using the same derivation
herdr uses natively: the enclosing git repo root name when the folder is inside
a repo, otherwise the folder basename (`~` for `$HOME`). herdr itself only
follows the folder while the label is not a custom name — once renamed, it pins
the label forever. This plugin re-derives instead: it keeps the `:wP` suffix
visible in every state, and a manual rename keeps your base while the suffix is
re-appended within seconds.

Why a watcher loop: herdr emits no event when a pane's cwd changes (OSC 7 `cd`
reports update the render path only), so folder-following cannot be purely
event-driven. `workspace-sync.py` reconciles on every workspace/pane event it
can hook, and a detached watcher (`--watch`) spawned by the startup hook polls
every 5 seconds to catch plain `cd`s. The watcher exits on its own when herdr
is unreachable for a while and is re-spawned at the next startup; it never
duplicates (pid file check). Disable it with `HERDR_PANE_ID_WATCHER=0`, tune it
with `HERDR_PANE_ID_WATCH_INTERVAL` (seconds) and
`HERDR_PANE_ID_WATCH_MAX_FAILS`.

`<agent-name>` is the user-assigned name from `herdr agent start <name>` (what you
address with `herdr agent prompt <name>`), falling back to the detected agent kind
(`pi`, `codex`, ...) for unnamed agents.

Pane labels keep the pane id visible in every state: plugin-managed panes show
`pF` / `<agent> | pF`, and a manual pane rename keeps your name with the pane id
appended (`MyPane:pF`). herdr emits no event when a pane is renamed manually, so
the id is re-appended on that pane's next `pane.agent_detected` event or at the
next startup (`on-pane-event.sh --reconcile`); the agent name is only injected
into plugin-managed labels, never into manual ones.

## Zero-noise in-pane prompt (recommended, optional)

Herdr already injects `HERDR_PANE_ID` into every pane's environment. Add one line to
`~/.zshrc` (or `~/.bashrc`) and every prompt shows its pane ID — no plugin event,
no typed commands, works in agent panes too:

```zsh
[[ -n "${HERDR_PANE_ID:-}" ]] && PROMPT="[%{$reset_color%}$HERDR_PANE_ID] $PROMPT"
```

## Configuration

herdr has no built-in plugin settings API (plugin v1), so this plugin reads a
`config.toml` from its config directory (printed by `herdr plugin config-dir
pane-id`; env: `$HERDR_PLUGIN_CONFIG_DIR`). A fully commented template with
examples is seeded there on first use, and edits are picked up on the next
event or watcher cycle — no restart needed.

```toml
[behavior]
# Keep the id visible even after a manual rename?
#   true  -> "MyName:wP" / "MyTab:t2" / "MyPane:pF"   (default)
#   false -> a manual rename hides the id again
workspace = true
tab = true
pane = true

[format.workspace]
separator = ":"          # "trading-manager:wR" / "trading-manager_wR" / ...

[format.tab]
separator = ":"          # "1_t1:p1" (between tab id and pane id)
number_separator = "_"    # "1_t1:p1" (between number and tab id, "-" gives "1-t1:p1")

[format.pane]
separator = ":"          # "MyPane:pF"
```

Every `always_visible`/`separator` is per-type, so styles can be mixed, e.g.
`workspace = false` hides the workspace id after a manual rename while tab and
pane keep theirs. `false` only affects manual labels: auto-managed labels
(`pF`, `pi | pF`, `1_t1:p1`, `<derived>:wP`) keep showing the ids. Pre-0.8
configs using flat `always_visible` / `separator` keys still work and apply
to all three types; labels written under a previous custom separator migrate
automatically when the config changes.

## Requirements

- herdr >= 0.8.0
- python3 (for `tab-label.py` and `workspace-sync.py`)

## Install

From GitHub:

```bash
herdr plugin install imtim/herdr-pane-id
```

Local development (edits apply immediately, no reinstall needed):

```bash
git clone https://github.com/imtim/herdr-pane-id.git
herdr plugin link /path/to/herdr-pane-id
```

Verify:

```bash
herdr plugin list
herdr plugin log list --plugin pane-id
```

Debug log (events, resolved pane id, agent name, rename failures, watcher)
and sync state (per-workspace `mode: auto|manual` + last base written by the
plugin, so manual names survive reconciliation) live in the plugin state
directory, usually `~/.local/state/herdr/plugins/pane-id/` on macOS/Linux:

```bash
cat "${HERDR_PLUGIN_STATE_DIR:-~/.local/state/herdr/plugins/pane-id}"/pane-id.log
cat "${HERDR_PLUGIN_STATE_DIR:-~/.local/state/herdr/plugins/pane-id}"/workspace-bases.json
```

## Publishing to the herdr marketplace

The herdr marketplace automatically indexes public GitHub repositories tagged
with the `herdr-plugin` topic (refresh every 30 minutes). To make this plugin
installable as `herdr plugin install <user>/herdr-pane-id`, add that topic in
the repository settings after publishing.

## Uninstall

```bash
herdr plugin unlink pane-id
```

## Notes

- Only newly created panes are labeled with the plain id; existing panes are left untouched so manual
  titles are not clobbered. Existing agent panes pick up the agent label on their
  next `pane.agent_detected` event. Manual pane names get `:pF` appended (startup
  reconcile or next agent event) and are never overwritten.
- Tab labels are reconciled on `pane.created` / `pane.closed` / `pane.moved` /
  `tab.created` / `tab.renamed` / `pane.agent_detected` and once at startup — the full reconcile
  covers panes moved between tabs as well. Manual tab names get `:tN` appended.
- Workspace labels are reconciled on `workspace.created` / `workspace.renamed` /
  `workspace.updated` / `pane.closed` / `pane.moved`, once at startup, and by the
  watcher loop (default every 5 s). A manual rename keeps the base and gets the
  `:wP` suffix re-appended on the `workspace.renamed` event (immediately).
- The auto base is derived from the root pane (lowest-numbered pane of the
  first tab), which matches herdr's own identity source.
- `herdr agent rename` does not emit an event, so the label keeps the old name until
  the next detection event (e.g. agent exit or restart).
- Pane IDs change when a pane moves to another workspace; the label is not updated
  on move.
- Manifest changes (new event hooks) are picked up on the next event dispatch (herdr re-reads
  the plugin registry before running hooks), but `[[startup]]` hooks only run at server start:
  after installing or updating the plugin, restart herdr once so the workspace watcher spawns.
  Script changes apply immediately because hooks read the script per event.
