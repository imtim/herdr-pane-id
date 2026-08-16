# herdr-pane-id

Herdr plugin that labels every pane with its short pane ID (e.g. `pF`), plus the
agent name once herdr detects an agent (`pi | pF`) — so you always know which pane
you are looking at (and can target it with `herdr pane run wP:pF ...` or
`herdr agent prompt pi ...`).

Tabs follow the same idea in a compact form: a tab with exactly one pane shows
`1_t1:p1` (number, tab id, pane id); once a second pane is added it switches to
`1_t1(2)` with the pane count. Workspaces show `Projects:wP` (name + id), also
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
| manual (non-numeric) label | untouched, always |

The base number always comes from the tab's own label, so `1_t1:p1` stays
consistent with what the tab bar already displayed; manual labels are never
clobbered. The reconcile (`tab-label.py`) is idempotent and self-heals: if the
single pane in a tab changes, the label is updated on the next event. Labels
from older plugin versions (`3: t5: pP`, `3: pP`) are upgraded automatically.

Workspace labels (startup + every `workspace.created` event):

| Workspace state | Workspace label |
| --- | --- |
| default | `Projects:wP` |
| label already ends with `:<id>` | untouched (idempotent) |
| legacy `Name: id` / `id Name` | migrated to `Name:id` |

A startup hook appends the workspace id to each workspace label (`Projects:wP`)
so the workspace id is always visible in the herdr UI. It is idempotent: labels
already ending with `:<id>` are left alone, and legacy `Name: id` / `id Name`
formats are migrated automatically. A `workspace.created` event hook does the
same for workspaces created after herdr started.

`<agent-name>` is the user-assigned name from `herdr agent start <name>` (what you
address with `herdr agent prompt <name>`), falling back to the detected agent kind
(`pi`, `codex`, ...) for unnamed agents.

## Zero-noise in-pane prompt (recommended, optional)

Herdr already injects `HERDR_PANE_ID` into every pane's environment. Add one line to
`~/.zshrc` (or `~/.bashrc`) and every prompt shows its pane ID — no plugin event,
no typed commands, works in agent panes too:

```zsh
[[ -n "${HERDR_PANE_ID:-}" ]] && PROMPT="[%{$reset_color%}$HERDR_PANE_ID] $PROMPT"
```

## Install

```bash
herdr plugin link ~/path/to/herdr-pane-id
```

Verify:

```bash
herdr plugin list
herdr plugin log list --plugin pane-id
```

Debug log (events, resolved pane id, agent name, rename failures):

```bash
cat ~/.local/state/herdr/plugins/pane-id/pane-id.log
```

## Uninstall

```bash
herdr plugin unlink pane-id
```

## Notes

- Only newly created panes are labeled; existing panes are left untouched so manual
  titles are not clobbered. Existing agent panes pick up the agent label on their
  next `pane.agent_detected` event.
- Tab labels are reconciled on `pane.created` / `pane.closed` / `pane.moved` /
  `tab.created` / `pane.agent_detected` and once at startup — the full reconcile
  covers panes moved between tabs as well.
- Workspace labels are reconciled on `workspace.created` and once at startup.
- `herdr agent rename` does not emit an event, so the label keeps the old name until
  the next detection event (e.g. agent exit or restart).
- Pane IDs change when a pane moves to another workspace; the label is not updated
  on move.
- Manifest changes (new event hooks) take effect after a herdr server restart;
  script changes apply immediately because hooks read the script per event.
