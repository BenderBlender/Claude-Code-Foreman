# Changelog

## 1.1 — 2026-11-03 · Council (консилиум)

For hard items: a bounded search that keeps the best **verified** solution, not the latest one.

- `foreman.py check P-… --root DIR`: an item's probes on any folder, e.g. a candidate's git worktree.
- `foreman.py compare P-… L=. A=DIR B=DIR`: the same probes on every candidate, side by side, with the control run in each.
- `foreman.py round P-… '{…}'`: a journal of council rounds; it reports the leader and calls STOP after `stop_after` rounds without a gain or after `max_rounds`.
- Probes and rubric are frozen once a round is logged (`set` refuses them without `--force`): criteria are fixed before the search.
- New `rubric` field on items (soft criteria in the owner's priority order).
- New skill `.claude/skills/foreman-council/` with the procedure, and a blind judge agent `.claude/agents/foreman-judge.md` that ranks anonymous candidates by the frozen rubric.
- The brief and `STATUS.md` show running councils; the installer installs and removes the new files; `config.json` gets `council` defaults.

## 1.0 — 2026-11-01

First public version: the registry of the owner's promises, six probe types with a self-checking control, three Claude Code hooks, the `foreman` agent, the installer for Windows, macOS and Linux.
