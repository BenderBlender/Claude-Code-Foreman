---
name: foreman-panel
description: Foreman's MODEL PANEL (консилиум моделей) — one self-contained brief to several AI models the owner has (Claude's own subagents of other models, Codex / Gemini / Qwen CLIs, OpenAI-compatible APIs, local Ollama / LM Studio, a web chat by hand), independent answers, then a checked DECISION. Use for decisions that are costly to get wrong (architecture, a data model, a public API, a process the team will live with), when stuck twice on the same problem, or when the owner says «консилиум моделей», «спроси другие нейросети», «собери мнения», "ask other models", "get a second opinion". Not for routine or cheap decisions. Only when the owner switched the module on.
---

# Model panel (консилиум моделей)

Several models answer ONE question independently; Claude checks their claims and decides with the owner. In practice all members agree
on the core and the value is in the differences (each brings 1–3 ideas the others missed); about one claim in twenty turns out wrong —
so every claim is checked against the code and the facts before it is used.

## 0. Is it on, and who is there?
`python .foreman/foreman.py panel detect` — the members, their kind (subagent / cli / api / manual) and whether each is on.
The module is off → do not run it; you may OFFER it once, in one line, when a decision is truly costly («Могу собрать консилиум моделей:
есть Codex и Gemini — включить?»). The owner decides; never switch it on yourself.

## 1. The brief (`panel new "<topic>"` → `.foreman/panel/<date>_<topic>/BRIEF.md`)
- Self-contained: a member does not see the project. Context, the VERIFIED facts with numbers, the owner's question VERBATIM,
  6–8 numbered questions, «cost and risk for each proposal», a word limit.
- Nothing private or secret: no keys, passwords, e-mails, personal data, private code the owner did not allow to share. The engine refuses
  a brief that looks like it carries secrets.
- `panel.ask_each_time: true` (the default) → before sending the brief OUTSIDE (cli / api members) ask the owner once: who gets it, why.

## 2. Answers — independent
- External members: `python .foreman/foreman.py panel run <folder>` (all on members in parallel; `--members a,b` to choose;
  `--stance codex=против` gives one member the critic's role so the panel does not agree out of politeness).
- Claude's own subagents of OTHER models (if the account has them): start each with the same BRIEF.md, tell it not to read `answer_*.md`,
  and have it write `answer_<model>.md`. Use one or two, not all.
- A manual member (a web chat): give the owner the brief to paste; the answer goes into `answer_<name>.md`.
- A member that failed leaves `answer_<name>.err.md`; go on with the rest.
- Optional second round for the most expensive decisions: `panel review <folder>` — every member sees all answers WITHOUT names
  (A, B, C…) and names the factual errors and a ranking; the letters' key is in `review_key.json` (for you, not for them).

## 3. Check, then decide (`DECISION.md` in the same folder)
1. **Verified by us** — every claim you are going to use, checked against the code / the files / a measurement (and the ones that failed).
2. **What all agree on.**
3. **Where they differ — what we chose and why** (a table: question · member → opinion · choice · the check behind it).
4. **Order, cost, risks.**
5. **What each member gave and where it erred** (so the owner learns whom to ask for what).
Show the decision to the owner BEFORE building, unless he said to go on alone.

## 4. Stop every process you started
A CLI member runs as a child process and ends with it; anything else you start for a check (a server, a watcher, a browser) — stop it
before the report and list it. A forgotten helper server keeps a port for hours.
