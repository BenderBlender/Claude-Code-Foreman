## Foreman — the project's promises don't get lost

This project runs Foreman: ONE registry of the owner's asks, `.foreman/promises.jsonl`. Each item holds the owner's words VERBATIM and machine probes. `.foreman/foreman.py` computes what is built from the probes, never from anyone's word. The hooks do this automatically:
- every ask of the owner goes into the inbox `.foreman/inbox.jsonl`;
- the end of a turn reminds you once to triage it;
- a session start and a context compaction bring a brief from the registry.

Rules for Claude:
1. **A new ask about the work** → `python .foreman/foreman.py add '{"title": "…", "quote": "verbatim", "priority": "high|normal|later", "next": "…", "probes": ["file:…", "grep:file:regex"]}'`, then `take I-… --as P-…`. Not a task → `skip I-… --why "…"`.
2. **Probes** — 1–3 per item, that turn green ONLY when the promise is really kept. Kinds:
   - `file:path` (globs work);
   - `grep:file:regex` / `nogrep:file:regex`;
   - `doc:file:word`;
   - `get:http://…`;
   - `cmd:…` — only if the owner set `allow_cmd` in `.foreman/config.json`.
3. **Never type «done»** — the probes compute it. Statuses by hand: `todo · doing · waiting · parked · accepted` (after the owner accepted it) `· dropped` (only on the owner's word). On acceptance Foreman STAMPS what the proof stands on: the probes' files and the `evidence` (a screenshot, a report, a render — `set P-… evidence=["…"]` before the acceptance). The yellow line «files changed after the acceptance» is a question, not a verdict: re-check it the way the owner would, then `stamp P-… --note "how it was checked"`.
4. **Parking.** A new ask mid-work → first `set P-… status=parked next="the next step"` on the current item, then the new one.
5. **«What is the project status?» / «check-up»** → `python .foreman/foreman.py status` and the `foreman` agent: it judges what is done by meaning, what is forgotten, and the three next steps. Report on one screen, in plain words.
6. **The brief at a session start and after a compaction** is the source of truth about unfinished work. Start from it, not from the summary.
7. **A council for hard cases.** A `high` item failed its probes twice, a decision is costly to get wrong (architecture, data, public API), or the owner asks for a «council» / to «think it through» → the `foreman-council` skill: freeze the probes and rubric first, then 2–3 different candidates in git worktrees, `foreman.py compare`, the blind judge `foreman-judge`, the log `foreman.py round`. Keep the BEST verified version, not the latest. Simple tasks need no council.
8. **The owner's correction → a lesson.** A message that looks like a correction ("again", "you forgot", "I told you"…) → the lesson protocol: already a rule? (`python .foreman/foreman.py recall …`); the root cause; where else it repeats; ONE rule `rule add '{"when", "do", "quote": verbatim, "keys"}' --situation "<the message>"`. End the reply with «recorded: R-…» (after writing it) or «not a correction: <why>». A rule is born «proposed»; only the owner's word makes it «active» (`rule accept`). Only an active rule may be hot or a guard.
9. **Before an unfamiliar action** — `python .foreman/foreman.py recall <what I am about to do>`. The owner's rulings go to `rules.jsonl` with their words; your own working notes go to Claude Code's own memory; Foreman only reads it.
