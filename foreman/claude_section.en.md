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
3. **Never type «done»** — the probes compute it. Statuses by hand: `todo · doing · waiting · parked · accepted` (after the owner accepted it) `· dropped` (only on the owner's word).
4. **Parking.** A new ask mid-work → first `set P-… status=parked next="the next step"` on the current item, then the new one.
5. **«What is the project status?» / «check-up»** → `python .foreman/foreman.py status` and the `foreman` agent: it judges what is done by meaning, what is forgotten, and the three next steps. Report on one screen, in plain words.
6. **The brief at a session start and after a compaction** is the source of truth about unfinished work. Start from it, not from the summary.
