# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Manual pane renames no longer leave the pane id hidden until the next
  `pane.agent_detected` event or restart: the detached watcher loop (the same
  one that follows workspace labels) now re-appends the `:pF` suffix to manual
  pane labels within a few seconds of a rename. herdr never emits an event and
  plugin v1 has no `pane.updated` hook for a manual `pane rename`, so the
  watcher is the only prompt path. Agent panes and auto-managed labels are
  untouched.

## [0.9.0] - 2026-08-18

### Added
- `format.tab.number_separator` config: separator between the tab number and
  the tab id (`1_t1:p1` with `_`, `1-t1:p1` with `-`).
- Seeded `config.toml` template now ships with full comments and examples for
  every option.
- Chinese documentation (`README.zh-CN.md`) with language switcher.

### Changed
- Own-format recognition and id-suffix checks accept any non-alphanumeric
  separator, so labels written under a previous custom separator migrate
  cleanly when the config changes back.

## [0.8.0] - 2026-08-18

### Added
- Per-type configuration: `behavior.workspace/tab/pane` (id visible after
  manual rename) and `format.workspace/tab/pane` separators, so styles can be
  mixed per label type.
- Pre-0.8 flat `always_visible` / `separator` keys still work and apply to all
  three types.

## [0.7.0] - 2026-08-18

### Added
- `config.toml` configuration file (herdr has no plugin settings API in v1):
  `behavior.always_visible` (keep ids visible after manual renames) and
  `format.separator` (`:wP` / `_wP` / ...), with an auto-seeded template.
- The watcher reloads the config on every poll cycle.

## [0.6.0] - 2026-08-18

### Added
- Tab ids stay visible after manual tab renames: `MyTab` -> `MyTab:t2`
  (via the new `tab.renamed` event hook).
- Pane ids stay visible after manual pane renames: `MyPane` -> `MyPane:pF`;
  manual pane names are never overwritten by agent labels.
- New startup hook `on-pane-event.sh --reconcile` appends the pane id to
  existing manual pane labels at boot (herdr emits no `pane.renamed` event).

## [0.5.0] - 2026-08-18

### Added
- Workspace labels follow the root pane's folder, using herdr's native
  derivation (enclosing git repo root name, else folder basename, `~` for
  `$HOME`), with the `:wP` suffix always visible.
- Manual workspace renames keep their base; the `:wP` suffix is re-appended.
- Detached watcher loop (spawned at startup, 5 s poll) because herdr emits no
  event on pane cwd changes; pid-file singleton, auto-exit when herdr is
  unreachable.
- `workspace-bases.json` state file tracks auto/manual mode per workspace.

### Changed
- `workspace-id-prefix.py` replaced by `workspace-sync.py` (reconciles on
  `workspace.created/renamed/updated`, `pane.closed/moved`, startup, watcher).
- Legacy `Name: id` / `id Name` workspace label formats migrated to `Name:id`.

## [0.4.0] - 2026-08-16

### Added
- Compact tab labels: single-pane tabs show `1_t1:p1` (number, tab id, pane
  id); tabs with two or more panes show the pane count (`1_t1(2)`).
- Workspace labels use the `Name:id` format (`Projects:wP`), with legacy
  formats migrated.

## [0.3.x] - 2026-08-16

### Changed
- Tab label format iterations: `3: pW` (pane id only), then `3: t5: pP`
  (tab id + pane id). Older formats are upgraded automatically by the
  current reconcile.

## [0.2.0] - 2026-08-15

### Added
- Agent-aware pane labels: `<agent-name> ▍ <pane-id>` on
  `pane.agent_detected`, back to the plain pane id when the agent is released.
- Fixed `json_get` stdin handling.

## [0.1.0] - 2026-08-15

### Added
- Initial plugin scaffold: label every pane with its short pane id.
- In-pane prompt prefix (opt-in) with pane id; zero-noise label-only mode.

[Unreleased]: https://github.com/imtim/herdr-pane-id/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/imtim/herdr-pane-id/releases/tag/v0.9.0
