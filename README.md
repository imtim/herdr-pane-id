# herdr-pane-id

Herdr plugin that labels every pane with its pane ID, plus the agent name once
herdr detects an agent in the pane — so you always know which pane you are looking
at (and can target it with `herdr pane run w1:p2 ...` or `herdr agent prompt pi ...`).

## Behavior

Nothing is typed into the pane — labels are herdr-side only (`pane rename`), so the
screen stays completely clean.

| Event | Label |
| --- | --- |
| `pane.created` | `▍ <pane-id>` |
| `pane.agent_detected` (agent present) | `<agent-name> ▍ <pane-id>` |
| `pane.agent_detected` (released / gone) | `▍ <pane-id>` |

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
- `herdr agent rename` does not emit an event, so the label keeps the old name until
  the next detection event (e.g. agent exit or restart).
- Pane IDs change when a pane moves to another workspace; the label is not updated
  on move.
