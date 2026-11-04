# Changelog

## 2.2.2 — 2026-11-04

- Edit gate: a relative `.foreman/…` path after a `cd` to another project is that project's (variables expanded in order: `S=…; P="$S/x"; cd "$P"`). Tests: v21 49.

## 2.2.1 — 2026-11-04 · The review's last items

- Panel: Ollama through its own `/api/chat` with `num_ctx` (32768 by default — its OpenAI-compatible address cannot set the context, a
  long brief was cut silently); a CLI member's own flags (`args`); one deadline for the whole round; an answer written whole or not at
  all; the installer asks about the panel once and remembers a «no» (`--ask-panel` to ask again); `panel.py` copied once.
- The edit gate judges THIS project only: writing another project's `.foreman` (a test copy) — through a path, a shell variable or the
  kit installer aimed elsewhere — is no longer «checks edited»; the same command aimed at this project still is. The panel's own commands
  are the engine's.
- A rule taken back from «dropped» is marked «REVIVED» in the ledger.
- Tests: panel 30, v21 48.

## 2.2 — 2026-11-04 · Model panel (консилиум моделей)

- **Model panel** (module `panel`, OFF by default — offered at install, the owner decides): one self-contained brief to several AI
  models the owner has — Claude's own subagents of other models, CLIs (Codex — also in the Codex app's folder, Gemini, Qwen Code, `llm`),
  OpenAI-compatible APIs by the key variable's name, local Ollama / LM Studio, a web chat by hand. `panel detect | new | run | review`;
  answers in parallel, each in its own file with a header; a critic's stance; a second round without names; a failed member never
  stops the others.
- Safeguards (after Fable's review): a brief with keys / tokens / passwords / e-mails / user paths is not sent; it leaves only on the
  owner's words checked against his log (`--owner-ok`); members off unless he switched them on (a CLI found later joins off;
  `--members` cannot pick a switched-off one); a CLI member runs in an empty temporary folder with `strip_env` (Codex without
  `OPENAI_API_KEY` / `OPENAI_BASE_URL`); a hung member is killed with its children (`taskkill /T`); self-written members need
  `allow_cmd`; no key over plain http to another machine; member `params`; English texts; the sending logged in events.jsonl.
- Skill `foreman-panel` (the procedure: brief → independent answers → checked claims → DECISION.md → the owner before building);
  CLAUDE.md rule 10 when the module is on.
- Tests: panel 27 (fake CLI and shim, fake OpenAI-compatible server); every suite passes on a cp1251 console; the engine writes stderr in UTF-8 (TaskCompleted's reason).

## 2.1.1 — 2026-11-04 · The board starts by double-click on Windows

- The board takes its port EXCLUSIVELY: http.server's default SO_REUSEADDR let it bind a port another local server already
  listened on (Windows), and the browser reached that server instead (a directory listing). A busy configured port → the next
  free one, printed in the console.
- `.foreman/board.bat` had doubled carriage returns (CR CR LF); fixed.
- Tests: board 28.

## 2.1 — 2026-11-04 · The board and who checks the checker

- **The board** (`foreman.py board`, `board.py` + `board.html`, standard library, offline): every item on one page; drag between
  columns = status, order in a column = priority (`rank`, followed by the brief); «Waiting for you» and «What is broken» strips; an
  item panel with the quote, probes, comments, history; accept = the owner's word. Several registries on one board through the «cli»
  adapter; each written through its own command. A start key printed only to the owner's terminal, 127.0.0.1, Host / Origin checks,
  CSP; 409 on a conflict with Claude's write, 503 while the lock is held. The owner's moves reach the next prompt hook (≤ 300 chars).
- **«Accepted» only with the owner's words** (`--quote`, checked verbatim against `.foreman/owner.jsonl`); an acceptance is void once
  the quote / probes / rubric change; earlier acceptances marked `legacy`; acceptances without the record listed in the brief.
- **The edit gate** at Stop: direct edits of Foreman's own files / the hook settings / guarded paths, a forced edit, the kit installer
  or the board's API in a turn → one block until «правка проверок: <why>».
- **«Unknown»** with a reason for a probe that could not run; a real «no» outranks it; new probe `fresh:<result>:<glob>`.
- **Rules age honestly**: `confirmed` date, `rule confirm`, `rule replace --by` (kept, not recalled), a stale list in the brief;
  lessons may be deferred with a reason («отложено: …»).
- **TaskCompleted** hook: a task of Claude Code's own list that names `P-…` stays open while the item has red probes.
- An «unknown» guard changes nothing; markers are read from the Stop input's `last_assistant_message` too.
- Tests: council 28, lessons 45, v21 46, board 26.
- Design and plan review: Fable 5.1.

## 2.0 — 2026-11-04 · Lessons (уроки)

Foreman now keeps a second registry beside your promises: **how** you want things done. A correction or a teaching becomes a rule
that is found again before the next action, and the turn cannot end until the lesson is really written down.

- **Rules** in `.foreman/rules.jsonl`: *when* → *do* + your words verbatim + RU/EN keys. Born «proposed»; only your
  `rule accept R-…` makes a rule active. A ladder for repeats: 1 rule → 2 hot (in every session brief) → 3 guard (a probe checked at
  every Stop; it blocks once when it turns red).
- **Recall**: stemmed Russian and English (to a fixpoint), BM25 with a trigger field, a lexicon of concepts (synonyms re-rank), an
  optional law layer for rule books with `### P1 · …` sections and rows tagged `[P1]`; your memory folder and skills are searched too.
  `recall --eval` measures recall@3 and false positives on the rules' own situations.
- **The Stop gate** passes only on a real record: a write to the rules, the ledger, memory, a skill, CLAUDE.md or your own rule book
  (`lessons.record_paths`), or «не поправка: …» / «уже записано: R-N» with an existing R-N. Reads do not count. The compaction
  summary, background notices and the hook's own feedback are never taken for the owner. A turn with a huge tool result is read back
  far enough (up to 64 MB).
- **One hook per event**: `hook prompt | stop | session` (`hook inbox` still works). Hard budgets: an ordinary message costs 0
  characters, a message ≤ 1,200, the session brief ≤ 2,000.
- **Modules**: `install.py --modules promises,lessons,board`. A lessons-only install leaves the project's own agents and council skill
  alone and its self-test does not ask for a promises brief; `lessons.record_hint` points the lesson notes at your own rule book.
- **Safety**: one lock (`.foreman/.lock`) for every writer, unique temp files, the whole ask kept verbatim (up to 20,000 characters),
  a corrupted inbox line no longer silences the Stop hook, `--uninstall` removes only the kit's own unchanged files, an update without
  `--lang` keeps the project's language, the installer backs up every file it replaces.
- **Council fixes** (1.1 reviewed): candidate paths independent of the working folder, `get:` and absolute probes marked «not
  comparable», frozen fields guarded, `round` validated and stopped, a non-git fallback, a blind judge.
- Tests: `tests/test_council.py` (28 checks), `tests/test_lessons.py` (44 checks).

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
