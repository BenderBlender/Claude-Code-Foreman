# Changelog

## 2.6.2 — 2026-11-11 · A reader on the expensive model is noted

The council of 11.11: «readers — bulk reading, logs, repos — Sonnet / Haiku, never Opus»; on 10.11 two readers ran on Opus by default
(no `model` → the main session's) and the weekly limit ended. The owner: a warning, not a wall.
- `hook tool`, PreToolUse on Agent / Task: a READING brief (read / study / survey / inventory … in RU and EN) given to a generic agent
  (`contract.reader_types`: general-purpose, claude, Explore, Plan) that will run on an expensive model → one note: take
  `model: "sonnet"` / `"haiku"`, or say in the brief why Opus. The model = the call's `model`, else the agent definition's `model:`, else
  a built-in's (`contract.builtin_models`, Explore → haiku), else «inherit». Silent for the crew's own agent types, for the advisor's
  model, inside a subagent. Never a refusal; `contract.reader_note: false` switches it off.
- Tests: v25 K6–K9. All suites green.

## 2.6.1 — 2026-11-11 · An attempt's input may be a word

Reported the same evening by another session of the author's project: «variant 3» on `run_authors.cmd fox gnome` → `warrior` →
`ram hummingbird …` (three demos on three objects, all fine) and on `bench.py smoke` → `smoke` after a fix → `matrix audrey`; the
advisor's event 2 rode on it. The «input» was only a PATH argument, so bare-word objects and modes were «the same input».
- The input = the first POSITIONAL argument that looks like a PATH; with none, the first positional word (an object, a mode); with
  none, the first path given as an option's value that is not an output (as before). Options, their values, numbers are skipped; a
  `#` comment and a redirection (`2>&1`, `>`, `>>`, `<`, `&>`) end the arguments. The replay of 09.11 with the first draft: a
  redirection became «the input» of `parts_to_obj.py`, and `p3click.py prep | eval | vote glasses clicks.json` — one real loop — was
  split by its sub-commands; both fixed. `--target` / `--to` are no longer «outputs» (ambiguous; another target is another job).
- The exit code stays no criterion (the case of 09.11: all seven runs of the loop exited 0).
- Replay of the case's own transcript (09.11 · 09.11 evening · 10.11; 797 · 298 · 1 142 calls; with the heartbeat and the advisor
  ON): all notes 0.8 · 0 · 0.7 per 100 calls; refusals 1 (the real one) · 0 · 0; attempts 2 · 0 · 0, both real loops
  (`bands_to_groups.py` on one picture — its 3rd run; `p3click.py … glasses_clicks.json`); the advisor 2 (on those two loops) · 0 · 0;
  the heartbeat 2 · 0 · 7 (5 and 16 different rules); engines 1 · 0 · 1, both real runs.
- Tests: v25 116 (C19, C20). All suites 363, green.

## 2.6.0 — 2026-11-11 · The advisor's events

The model council of 11.11 (Fable 5.2 · Astra · Argon) on how to use a strong, expensive second opinion: the main session (Opus)
orchestrates; the advisor is called on events, with a brief ≤ 700 words and an output file, ≤ 3 times a day. Foreman — «a detector of
events, a budget counter and a journal, never the one who launches» (Fable); «only suggest; an automatic launch only after its accuracy
is measured» (Astra). The owner chose events 2, 3, 5 (the ones with a reliable signal).
- **Module `advisor`** (act.py, off by default) + config `advisor` (`name`, `models`, `day_max`, `brief_words`, `registries`, `mark`,
  `doing`):
  - event 2 — the attempt warning (3rd variant) gets the advisor's line with the brief's frame;
  - event 3 — an item of a registry (`advisor.registries`, JSONL) marked `advisor.mark` and in work → one note per item and session;
    the file is read again only when it changed;
  - event 5 — the prompt hook: a correction whose best matching rule failed ≥ 2 times by its own history («AGAIN», «TWICE», «THIRD»,
    `level`) → one note per rule a day. On the author's 414 real messages (34 corrections): 5 notes in five days, 4 to the point
    (partly hindsight — the rows' history was written after);
  - the calls of the advisor's model are counted (`adv_call`); past `day_max` or a brief over `brief_words` → a note. Never a refusal,
    never inside a subagent; a replay counts the events 2 (`advisor`), not 3 (a registry has no past).
- `foreman.py advisor [days]` — the journal. install.py writes the `advisor` section; rule 12 of CLAUDE.md names the advisor's note.
- Tests: v25 114 (E0–E10). All suites 361, green.

## 2.5.2 — 2026-11-11 · Environment launchers are unwrapped

Reported the same evening by another session of the author's project: «variant 3 in 20 min: `lab_env_run.cmd`» — three DIFFERENT
commands run through one environment launcher (`lab_env_run.cmd .venv\Scripts\python.exe …`); the signature was the `.cmd`, its
«input» the `python.exe`.
- A `.cmd` / `.bat` / `.sh` / `.ps1` whose FIRST argument is an interpreter or a launcher word (`python.exe`, `uv`, `env`, `call` …)
  is unwrapped to what it runs, like `act.wrappers`: the signature is the script run inside (`bootstrap.py`); a launcher running no
  script (`… python.exe -m pip install …`) runs nothing to count.
- Tests: v25 103 (C18). All suites 350, green.

## 2.5.1 — 2026-11-11 · The subagent contract per session

Found the same day on the author's machine, three sessions in one project: an Explore agent of one session stopped without its
output file, and ANOTHER session's Stop hook was told («the phase is NOT done — resume the same agent») — an agent it never started.
Its «seen» row then hid the news from the real parent. The bug came with 2.4.
- **Per session:** every contract event (`agent_start`, `agent_stop`, `agent_block`, `agent_artifact_missing` / `_old`) carries the
  parent's `session` (a subagent's hooks get the session_id of the conversation that started it); `contract_news(sid)` — the Stop
  hook and `PostToolUse(Agent)` — tells only that session. Old rows without a session are no one's news.
- **An agent that only reads** (`contract.readonly_types`: Explore, Plan …): its missing file is reported as «it could not write it —
  the result is in its answer», not «resume the same agent»; and a brief with an output file sent to such an agent is said BEFORE
  the run, in `hook tool` (a note, never a refusal).
- Tests: v25 102 (K1–K5). All suites green.

## 2.5.0 — 2026-11-11 · Knowledge at the moment of action (built 09.11, revised after a model council 11.11)

**Revised before the release** — a model council (Fable 5.2 · Astra / ChatGPT · Argon / Gemini, 11.11) read the code and the replay of
the case's OWN transcript (the session where 09.11 happened ran it: 09.11 in two windows and the ordinary day 10.11, 1 142 calls). The
replay found the noise and the false refusals; the council decided: A on; C without a refusal and without the wrappers; D a note only;
B and ♥ switched off until they are fixed and measured again.
- **What a command RUNS** (new in `act.py`: `runs()`): the command is split into simple commands outside quotes (`;` `|` `&&` `||`
  line ends); in each, the script after the interpreter (options and their bare values skipped — `python -X utf8 x.py`,
  `powershell -ExecutionPolicy Bypass -File x.ps1`, `blender -b a.blend --python x.py`), after `&` / `.`, or at the command's start;
  the code of `bash -lc '…'`, `powershell -Command …`, `cmd /c …` is read as a command line again (`python -c` code is code); a
  preceding `cd` gives a relative script its folder. 2.5 took the FIRST script file named anywhere in the line: on 10.11
  `gpu_guard.ps1 -Run "…"` counted as gpu_guard, `Get-Content a.py | python b.py` as a.py.
- **Wrappers:** a script whose QUOTED argument starts with a command is unwrapped to the script inside
  (`gpu_guard.ps1 -Run "wsl … bash run.sh"` → `run.sh`); `act.wrappers` names wrappers to unwrap even unquoted; a wrapper with no job
  inside (`gpu_guard.ps1 -Status`) runs nothing.
- **Bookkeeping** (`act.bookkeeping`, default Foreman itself; a project adds its registry and rule lookups): neither work (A), an
  attempt (C) nor an engine's use (D). 10.11: the registry was 5 of 18 «attempts» and the one false refusal of A. A script file named in
  a command (`Get-Content x.ps1`) is no longer «work» either.
- **C · attempts:** the signature is the script the command runs (above), and a variant is the same script ON THE SAME INPUT (its first
  path argument that is not an output — `--out`, `-o`, `--save` … skipped); a dry run (`-DryRun`, `--dry-run`, `-WhatIf`) and the real
  run are one variant; the project's looking tools (`act.look_tools`: measuring, sheets, pages, screen shots) never count; a script
  named in a variable (`F=…/x.py; sed -n … $F`) is not run. Fable counted 12 of 18 warnings of 10.11 false; the first revision (rc1)
  still gave 13 on 09.11 with 5 real loops — measure / sheet / page tools on new results, a dry run, a read through a variable.
- **D · engines:** an engine matches only the path of the script a command RUNS (with its `cd` folder) — never the description, a path
  in an argument, a reading, the body of a heredoc / here-string (`cat > run.sh <<'EOF' … EOF` writes a script, `python - <<EOF`
  feeds code: rc1 had 3 such notes of 4). 10.11's two refusals: «Measure the size of every Hunyuan folder» and a registry probe naming
  `p3sam_run.py`. The author's project dropped `deny_first`. A code file written from the shell (`cat > x.sh`, `Out-File x.py`) is
  still work for A.
- **B · recall by the action — a switch, OFF by default** (`modules.act_recall`). When on: the trigger is the situation WITHOUT its
  history (a dash before «failed …» / «CORRECTION …» / a date) + the Keys (its own cell, or borrowed from the same row in a card of
  `act.keys_books`); the BM25 block is built from the same; `recall_min_score` 10 (it was 0); silent when the rule has a guard of its
  own (`act.guard_marks`: a hook, a script that refuses) or the action already runs the tool the rule names (Fable: 17 of 60 notes of
  10.11 stood on the «seven views» tools). 10.11 measured 5.3 per 100 calls; the council's bar to switch it on: ≤ 1.5, ≥ 60 % to the point.
- **♥ · heartbeat — a switch, OFF by default** (`modules.heartbeat`). When on: right after a compaction, or when the owner has been
  silent ≥ `beat_silence_min` (30) and `beat_min` (45) passed since the last beat; WORKING calls only (never reading, a search, the
  plan — 14 of 42 beats of 10.11); rotation — the rules shown least today first (72 % of 10.11's beats were the same three rows); ≤
  `beat_day_max` (10) a day. The owner's silence comes from `owner.jsonl` (the prompt hook).
- **`replay --tools`:** sees the compactions in a transcript (the heartbeat's trigger); prints the total notes per 100 calls, the
  modules, a line per day, the attempts by script and the engines; `--show` prints the command and B's score.
- **Replay of the case's own transcript after the revision** (default modules: B and ♥ off; 09.11 12:00–17:40 · 17:40–20:45 · 10.11):
  - rc1: 797 · 298 · 1 142 calls; all notes 1.8 · 0.7 · 0.6 per 100; refusals 1 (real: the first working action after «study
    first» — writing a runner before the study) · 0 · 0; C 12 + 1 · 5 (real loops 5 of 13, 0 of 5 — failed); D 1 · 1 · 2 (1 to the
    point); the loop of 09.11 (`bands_to_groups.py`) warned on its 3rd real run;
  - **the release (rc2): all criteria met** — all notes 0.5 · 0 · 0.1 per 100 calls; refusals 1 (the same real one) · 0 · 0, no
    false refusal; C 2 · 0 · 0, both real loops (`bands_to_groups.py` on one picture — warned on its 3rd real run; the glasses' click
    loop of `p3click.py`); D 1 · 0 · 1, both real runs (P3-SAM under the GPU guard, «Замкнуть»); «study first» caught. The price:
    a sweep of settings over DIFFERENT inputs is no longer marked — by the definition of a variant that is right;
  - for information, B and ♥ on (rc1): B 1.3 · 2.3 · 2.5 per 100, to the point ~2/10 · ~4/7 · ~12/28, scores 14–79 — the bar does not
    separate (the highest note was false: product names like «Studio» in the triggers) → B stays off; ♥ 2 · 0 · 7 a day, 6 and 17
    different rules (its own criteria met; with ♥ on the total was 2.0 · 0.7 · 1.2 per 100).
- install.py / foreman.py: `act_recall` and `heartbeat` default to `false` (an update keeps what the project set); rule 12 of the
  CLAUDE.md section says the hot rule comes only if the owner switched it on.
- Tests: v25 97 (new: A26, B0, B9–B12, ♥ rewritten H1–H9, C9–C17, D13–D18, Q4, the install defaults); lessons: the new module
  defaults. All suites 344, green.

### As built on 09.11

The case (the author's project, 09.11): one autonomous turn of three hours — hundreds of tool calls, no new message, so no hook ever
reminded. Links the owner said to study FIRST were read after the work; a hot rule («never judge by one view») broke a third time; a
tool's documented click mode was forgotten; one script ran seven times in fifteen minutes. The knowledge existed — 2.0–2.4 bring it up
on the OWNER'S MESSAGE, and there was none. The plan was reviewed by Fable before any code (`FABLE_2.5_review.md` in the author's
project): its defaults are kept — notes on, refusals only where the owner said «first» or the project switched them on, the hot rules
only, a time budget per call.
- **`act.py`, one `PreToolUse` hook «tool»** on Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|Agent|Task. It also does the 2.4 path
  rule, so one process per call; no registry lock; `hook edit` still works for 2.4 settings. Journal `.foreman/act.jsonl` (per session,
  pruned to 3000 rows); every line shown is in `hooklog` as hook «tool».
- **A · materials** (`materials`):
  - a sentence of the owner's with a study verb AND a URL / path / `[Image #N]` / a web topic within ± 200 characters → `M-0001` in
    `.foreman/materials.jsonl` (+ the active item when promises are on);
  - «сначала / прежде / first / before» in that sentence → the first working action of the session is refused once (a program run,
    a code-file edit, an agent not read-only whose brief does not name the source);
  - `material read M-… --study <notes>`: every source named in the notes, «taken» and «not read» said, and — when the session's
    transcript is found — every source opened after the message (Read / fetch / browser / `git clone`); a web topic needs ≥ 2 links;
  - `material skip --why` (≥ 10 chars, a ledger line); `material list`;
  - Stop once per 20 min with «opened k/n»; the session brief lists what is not studied.
- **B · recall by the action** (`act_recall`):
  - the query: a program run's description + its scripts' names; an agent's description + 300 characters of the brief; an edit of a
    file named like a tool that LOOKS (`act.check_files`) + 300 characters of the new text;
  - only HOT rules: `rules.jsonl` level ≥ 2 + the table rows of `act.hot_books`;
  - a rule's trigger = its «when» without the owner's quotes; the generic verbs of descriptions and a rule's history words
    («correction», «the producer», «again», «failed») never count; ≥ 2 shared words, BM25 over the hot rules for the order;
  - prints the DO cell; ≤ 2 rules; one rule once per 30 min per session; reading / listing commands never searched.
- **♥ · heartbeat** (`heartbeat`): the session's first call starts the clock silently; every 20 min (and the call right after a
  compaction) the ≤ 3 hot rules nearest to the last ~40 actions, ≤ 650 chars.
- **C · attempts** (`attempts`):
  - the signature = the script after an interpreter; a variant = other arguments or a newer script mtime; the same command = the same
    attempt; the exit code is no criterion;
  - the 3rd variant in 20 min → «stop, 2–3 different approaches»;
  - `act.attempts_deny` (off) refuses the 5th once, until `OPTIONS*.md` (cwd or a folder the command names), `# options: …` in the
    command, or `attempts think <script> --options "…"`;
  - tests, npm / pip / make / `foreman.py` never count (`act.attempt_ignore`).
- **D · engines** (`engines`):
  - config `engines: [{name, match, doc, section, deny_first}]` — `doc` may be a list (all must be read; the section comes from the doc
    that has it), `section` a heading or a table row of a card; a use = the description and the PATHS the command runs (a ledger line
    that merely mentions the engine is none — measured);
  - the doc «read» = a Read / `cat` / `Get-Content` of it after the last compaction in the session's transcript;
  - not read → its section in front of Claude, once per session; `deny_first` → refused once instead;
  - `engine ack <name> --modes "…"` (≥ 15 chars) passes for `ack_hours` (12); `# engine-read: …` in the command passes.
- **`replay --tools <transcript> [--since] [--until] [--show] [--json]`**: B / ♥ / C / D and A's gate over a real session in its own
  time, nothing written; streamed line by line (a real transcript is hundreds of MB).
- **Measured** on the author's ordinary day (425 calls, no corrections):
  - recall by the action 0.9 per 100 calls — 5.7 before the history words and the quotes were taken out of the triggers;
  - the heartbeat 9×; attempt warnings 5 (each a real loop of three variants); refusals 0.
  - The modelled case: all four rows caught. Time per call: median ≈ 0.15 s ordinary, ≈ 0.3 s with a hot-rule search.
  - The replay of the case's own transcript was not run: Claude Code's protection stopped reading another session's transcript.
- **Fixed:** a rule book on another drive (`lessons.rules_extra` absolute) made `relpath` raise and took the whole recall down
  (`recall._rel`). `urllib` is imported only for a `get:` probe (−30–45 ms on every hook start).
- install.py: copies `act.py`; `act` / `engines` in config.json; `--modules` knows the five new modules; the CLAUDE.md section has rule
  12 «knowledge at the moment of action».
- Tests: v25 70 (install 4, A 25, B 8, ♥ 5, C 8, D 12, R 1, the replays 3, time 2); lessons: the modules dict. All suites 317.

## 2.4.1 — 2026-11-08 · The panel survives a Codex update; a semantic layer measured and not adopted

- **The panel finds a moved CLI.** `panel detect` writes the absolute path it found into config.json, and the Codex app moves
  `codex.exe` into a new build folder on every update — the first `panel run` after an update failed with «WinError 2». `ask_cli` now
  goes through `_resolve_exe()`: a path that no longer exists falls back to the program's name (PATH, npm's folder, the newest Codex
  build). Test: panel +1 (31).
- **Measured and NOT adopted** (the owner's rule: measure before building; numbers from the author's project — 362 recall blocks, its
  65 real situations, 358 hand-labelled owner messages, all on the CPU):
  - *A semantic layer for recall* — a council of three models (Claude Fable, ChatGPT, Gemini) proposed a multilingual embedder fused
    with BM25. Foreman 2.4 alone: the needed rule in the 3-line pack 81 % / 93 % (design / holdout). Three embedders, each first run on
    its model card's example — multilingual-e5-small, paraphrase-multilingual-MiniLM-L12-v2, bge-m3:
    - every fusion over the whole block text was worse;
    - bge-m3 «append only» fixed 2 of 29 holdout cases only at a cosine threshold that also woke 11–16 of 22 silent messages;
    - at a quiet threshold it changed nothing;
    - re-ranking moved 3 of 65 to first place — invisible in a 3-line pack.
  - *A learned correction detector* — logistic regression on embeddings vs the word lists, split by time: worse (F1 0.10–0.12 vs
    0.59; 39 positives — it learns the topic, not the tone).
  - *Indexing bold-lead paragraphs of the rule book* — noise: a long rule paragraph full of ordinary words answered «are you still
    working?». *The project's own ledger* — 165 of 358 packs changed, nothing fixed.
  - So the lexical recall stays. A project WITHOUT tuned Keys and a lexicon might gain more from an embedder — measure it on your own
    situations first.
- Tests: all suites 247 (board 29, council 28, lessons 45, panel 31, v21 49, v23 16, v24 49).

## 2.4 — 2026-11-07 · Proof that still holds: stamps, the subagent contract, rules with paths

From Claude-Code-Game-Studios (github.com/Donchitos/Claude-Code-Game-Studios, read 07.11 from its clone: `review-receipts.sh`,
`validate-agent-artifact.sh`, `error-recovery-protocol.md`, `.claude/rules/agent-memory.md`, `studio-tests/`, `test-evidence-review`).
The owner: «Внедряй все полезное в Прораба … Но сначала проконсультируйся с Fable по всем правкам» — the plan was reviewed by Fable
before any code (`Hollywood3/production/harness/foreman_v2/FABLE_2.4_review.md` in the author's project); the Claude Code facts the
hooks rely on were checked against the docs (hooks.md, memory.md).
- **Evidence stamps.** `accepted.stamp` — hashes of what the proof stands on, from ONE helper `stamp_of()` called by both acceptance
  paths (the CLI and the board): `grep:` → the matched lines ± 2, `doc:` → the enclosing heading section, `file:` / `fresh:` target /
  `evidence` → the whole file; text normalised (CRLF, BOM, trailing spaces); ≤ 20 files, ≤ 5 MB each; globs expanded only at stamp
  time. The brief / STATUS.md: «accepted, but files changed after the acceptance» (≤ 5 ids, «FILE GONE» for a deleted one, «not in
  the stamp» for evidence named later); `check P-…` prints the stamp. `stamp P-… --note "how"` re-stamps after a re-check (green probes
  only; a `restamp` event; the acceptance stands). An acceptance whose `evidence` finds no file is refused. `fresh:` keeps mtime (it asks
  order — documented). New item field `evidence` (`set P-… evidence=[…]`).
- **The subagent contract** (module `contract`, on): `hook subagent` (SubagentStop) reads the brief — the first user message of the
  subagent's transcript, line by line — for ``Output file: `…` ``, «``Файл результата: `…` ``», ``Write your full output to `…` ``
  (backticked; placeholders and «e.g. / например» examples skipped). Missing → one `decision: block` (once per agent id, also when
  `stop_hook_active` is absent); then `agent_artifact_missing`, told to the parent by `hook agent-done` (PostToolUse on Agent|Task) or the
  Stop hook, once (append-only «seen» rows). Older than the brief → advisory only. Read-only agent types (`contract.readonly_types`)
  never blocked; an empty agent_type (Claude Code's internal agents) silent. `hook subagent-start` logs the audit line. No registry lock.
- **Rules with paths** (module `rules_paths`, on): a rule's `paths` inside the project → `.claude/rules/foreman-R-….md` (generated,
  marked, re-written on `rule accept/set/drop/replace`, `foreman.py rules export`); outside the project → `hook edit` (PreToolUse on
  Edit|Write|MultiEdit|NotebookEdit), once per session and rule (`.foreman/rules_shown.jsonl`), never blocking.
- **Weak probes** in the brief and STATUS.md: accepted items whose probes are only `file:` / `doc:` — or none (invisible before).
- **«A temporary absence is not a durable fact»**: `rule add` / `lesson` warn on absence wording without `as_of`; recall marks such a
  rule «re-check» past `lessons.absence_days` (30). A narrow pattern — a bare «нет» is not one.
- install.py: the new hooks per module; `--modules` lists every module wanted; uninstall removes only the generated rules. The CLAUDE.md
  section: rule 3 tells about stamps, a new rule «a brief names its output file» (also for lessons-only projects).
- Deferred to 2.5: agent lint / behaviour specs (CCGS `studio-tests`).
- Tests: v24 49 (A 16, F 1, B 14, C 8, E 4, install 6); board +1 (the board's acceptance is stamped); lessons: the modules dict.

## 2.3 — 2026-11-05 · What Claude was shown, and a replay of the owner's messages

Two ideas from DeepSeek Harness (github.com/deepseek-ai/deepseek-harness, read 05.11: `AGENTS.md`, `docs/testing.md`):
- **«Model-visible means logged».** Every line a hook puts in front of Claude — the prompt hook's context, the session brief, a Stop
  block, a TaskCompleted refusal — is written to `.foreman/events.jsonl` (`kind: hook_out`, the hook, its characters, the text, the head
  of the message it answered). `foreman.py hooklog [--n] [--hook] [--grep]` reads it back: «why did Claude do that» is answered from
  the log. An ordinary message with no output writes nothing; only the oldest `hook_out` rows are pruned past 3 MB (the owner's board
  moves are kept); `"hook_log": false` switches it off.
- **Replay of the recorded messages.** `foreman.py replay` runs the owner's messages (`owner.jsonl`) through the prompt hook's detectors
  — the ask cues and the lessons classifier — with NO side effects, and compares them with a saved snapshot (`replay --save` →
  `.foreman/replay_baseline.json`): a cue or lexicon edit that changes how a PAST message reads («was a correction, now nothing» = a
  lost lesson; «was nothing, now an ask» = a new false alarm) is listed before it misleads a session; exit 1 when anything changed.
  Messages newer than the snapshot are counted, not called changes.
- Not taken: scheduled re-checks of the probes (their RFC 5545 schedule package) — on Windows it needs a persistent system scheduler,
  so it stays the owner's decision. Already had: `blocked_by`, owner commands without a model turn.
- Tests: v23 17; `test_panel.py`'s `alive()` reads `tasklist` as bytes (a Russian console's OEM code page made stdout None).

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
