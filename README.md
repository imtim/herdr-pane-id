# herdr-pane-id

Herdr plugin that labels every newly created pane with its pane ID, so you always
know which pane you are looking at (and can target it with `herdr pane run w1:p2 ...`).

## Behavior

On each `pane.created` event, the pane is renamed to `▍ <pane-id>` — the label is
shown in the herdr UI (pane list / layout). Nothing is typed into the pane, so the
screen stays completely clean.

## Zero-noise in-pane prompt (recommended)

Herdr already injects `HERDR_PANE_ID` into every pane's environment. Add one line to
`~/.zshrc` (or `~/.bashrc`) and every prompt shows its pane ID — no plugin event,
no typed commands, works in agent panes too:

```zsh
[[ -n "${HERDR_PANE_ID:-}" ]] && PROMPT="[%{$reset_color%}$HERDR_PANE_ID] $PROMPT"
```

## Optional: prompt prefix without editing rc files

The hook can also run `PS1='[<pane-id>] '...` via `pane run`. It works (bash/zsh),
but `pane run` simulates typing, so the pane shows **one typed command line** at
creation. Enable only if that trade-off is acceptable:

```bash
printf '1' > "$(herdr plugin config-dir pane-id)/prompt-prefix"
```

Disable again with:

```bash
printf '0' > "$(herdr plugin config-dir pane-id)/prompt-prefix"
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

Debug log (event payload, resolved pane id, failures):

```bash
cat ~/.local/state/herdr/plugins/pane-id/pane-id.log
```

## Uninstall

```bash
herdr plugin unlink pane-id
```

## Notes

- Only newly created panes are labeled; existing panes are left untouched so manual
  titles are not clobbered.
- Pane IDs change when a pane moves to another workspace; the label is not updated
  on move.
