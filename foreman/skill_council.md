---
name: foreman-council
description: Foreman's COUNCIL (консилиум) for hard items — a bounded search that keeps the best VERIFIED solution, not the latest. Use when a high-priority promise failed its probes twice, when a decision is costly to get wrong (architecture, data model, public API), or when the owner says «консилиум», «подумай как следует», «think it through», «compare options». Not for simple, cheap or already-verified tasks.
---

# Council: a search with a kept leader

More rewriting is not more quality. With a weak judge, more rounds only mean more confidence in a mistake. So the council does three things: it **fixes the criteria before the search**, it **keeps the leader** unless a candidate is verifiably better, and it **returns the best version found, not the last one**.

Talk to the owner in their language (`.foreman/config.json` → `lang`). Settings: `.foreman/config.json` → `council` (`candidates` 2, `max_rounds` 3, `stop_after` 2).

## 0. Is a council worth it?

It costs about `candidates × max_rounds` extra passes. Run it only for the cases in the description above. Tell the owner in one line: «Консилиум по P-007: 2 варианта × до 3 раундов, критерии — пробы и рубрика ниже».

## 1. Freeze the criteria first

- The item has 1–3 **probes** that turn green only when the promise is kept (the objective part).
- Add a **rubric**: 3–5 soft criteria in the owner's priority order, from the owner's words where possible:
  `python .foreman/foreman.py set P-007 rubric='["solves the case the owner described", "no new dependencies", "simple to maintain"]'`
- Note the **hard constraints** (what must not break, what is forbidden) in `next` or the rubric.

After the first logged round, `foreman.py` refuses to change probes or rubric without `--force`. Never tailor the criteria to a candidate. If a criterion turns out to be wrong, say so to the owner first.

## 2. The leader

The current state of the project (or your first solution) is candidate **L**. It takes part in every comparison.

## 3. Each round: K substantially different candidates

- Different *approaches*, not cosmetic variants of one idea. Novelty is not a merit.
- **Code in a git repository:** each candidate in its own git worktree, branched from the leader:
  `git worktree add ../<project>-p007-a -b council/P-007-a`
- **Not a git repository** (many projects aren't): never modify the leader in place. Copy only the part the item touches
  (the folders its probes and the change need) next to the project — `python -c "import shutil; shutil.copytree('src', '../cand-a/src')"`
  or `robocopy src ..\cand-a\src /E` — and make each candidate in its copy. For a large project, candidates may be **diffs or
  plans** instead of copies; apply only the winner, once.
- Candidate paths in `check` / `compare` are relative to the **project folder**, wherever you type the command; `L=.` is the project.
- **Irreversible actions** (deploys, migrations on shared data, deletions, sending messages, payments): candidates are **plans only**. Improve the plan, then execute once. Never execute several times "to compare".

## 4. The objective check

```bash
python .foreman/foreman.py compare P-007 L=. A=../<project>-p007-a B=../<project>-p007-b
```

Also run the project's own tests in each worktree. A candidate with red probes, failing tests or a broken hard constraint is out. If every candidate fails, compare by the number of green probes and say so.

## 5. The blind judgment

For what probes cannot see (meaning, clarity, taste, risk), call the **`foreman-judge`** agent. Blindness is easy to break, so:

- put the frozen rubric, the hard constraints and the owner's **language inline in the task** — the judge must not read `.foreman/`
  (the rounds journal there names the leader and the winners);
- give it **neutral copies** of the valid candidates under random labels — e.g. folders `../judge/X`, `../judge/Y`, `../judge/Z` with the
  changed files, or diffs/texts — **not** the live worktrees (their names, branches and `git log` reveal the leader and the order);
- add each candidate's probe and test results, under the same labels;
- nothing about which one is the leader, which one you wrote last, or which one you prefer.

## 6. Accept a new leader only if

- its probes are all green (or more green than the leader's), and no test regressed;
- the judge prefers it on the top rubric criteria ("clearly" or "marginally better", not "tie");
- nothing the leader already did well got lost;
- the gain is worth the cost.

A tie, a doubt or a split verdict: **keep the leader**.

## 7. Log every round

```bash
python .foreman/foreman.py round P-007 '{"tried": ["L","A","B"], "winner": "A", "accepted": true, "why": "A: all probes green; judge: clearly better on criterion 1"}'
```

`tried` (a list) and `accepted` (true/false) are required; with `true`, also `winner`. In Windows PowerShell 5.1 the quotes inside
a JSON argument are stripped — write the JSON to a file and pass `@round.json`. `foreman.py` answers with the next round or a STOP;
after a STOP the item is marked `council: stopped` and further rounds are refused without `--force`.

## 8. Stop and report

Stop after `stop_after` rounds without an accepted gain, after `max_rounds`, or as soon as quality is clearly sufficient. Then:

1. Keep the **best** candidate: merge only its branch; remove the others (`git worktree remove …`, `git branch -D council/P-007-…`).
2. A matter of taste (texts, design, wording, UX)? Don't decide for the owner: `set P-007 status=waiting waits="finalists A / B: …"` and show both.
3. Tell the owner on one screen: what was tried, what was rejected and why, what the probes and the judge said, and what remains uncertain.

## Honesty rules

- Your own comparison is not independent; the judge is the same model family in a fresh context. Call its verdict "a blind assessment", not "an independent evaluation".
- Count only explicit candidates. Don't claim internal thinking cycles.
- "Done" is still never typed: the probes decide, and acceptance is the owner's word.
