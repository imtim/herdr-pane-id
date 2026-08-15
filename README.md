# herdr-pane-id

Herdr plugin that makes every newly created pane carry its pane ID, so you always
know which pane you are looking at (and can target it with `herdr pane run w1:p2 ...`).

What it does on each `pane.created` event:

1. **UI title** — renames the pane to `▍ <pane-id>` (visible in the herdr tab bar / pane header).
2. **Prompt prefix** — waits for the pane shell to reach its interactive prompt, then
   prepends `[<pane-id>] ` to `PS1` for that shell session (bash/zsh; session-local only,
   no rc files are modified).
3. **Banner** — prints a dim one-line banner `▍ pane <pane-id>` into the pane.

If the pane immediately runs a foreground command (e.g. an agent), steps 2–3 are
skipped; the UI title still gets set.

## Install

```bash
herdr plugin link ~/path/to/herdr-pane-id
```

The plugin is enabled by default after linking. Verify:

```bash
herdr plugin list
herdr plugin log list --plugin pane-id
```

Debug log (event payload, resolved pane id, foreground shell, herdr command errors):

```bash
cat "$(herdr plugin config-dir pane-id)/../state/pane-id.log"   # or:
herdr plugin log list --plugin pane-id
```

## Uninstall

```bash
herdr plugin unlink pane-id
```

## Notes

- Only newly created panes are labeled. Existing panes are left untouched so manual
  titles are not clobbered.
- If you prefer the ID inside the prompt everywhere (including agent panes), herdr
  already injects `HERDR_PANE_ID` into every pane's environment — add to `~/.zshrc`:

  ```zsh
  [[ -n "${HERDR_PANE_ID:-}" ]] && PROMPT="[%{$reset_color%}$HERDR_PANE_ID] $PROMPT"
  ```
