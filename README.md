<p align="center">
  <img src="assets/foreman-banner.webp" alt="Foreman (Прораб): a project's promises don't get lost. For Claude Code." width="100%">
</p>

<h1 align="center">Foreman · Прораб</h1>

<p align="center">
  <b>Your project's promises don't get lost.</b><br>
  The site foreman for Claude Code: it writes down every request you make, word for word,<br>
  attaches machine checks to it and keeps asking <i>"is it really built?"</i> until the answer is yes.
</p>

<p align="center">
  <img alt="For Claude Code" src="https://img.shields.io/badge/for-Claude%20Code-A8361F">
  <img alt="Python 3.8+" src="https://img.shields.io/badge/python-3.8%2B-2F5370">
  <img alt="Zero dependencies" src="https://img.shields.io/badge/dependencies-0-2F6B2F">
  <img alt="English and Russian" src="https://img.shields.io/badge/lang-EN%20%7C%20RU-6E5A49">
  <img alt="MIT License" src="https://img.shields.io/badge/license-MIT-5A4636">
</p>

<p align="center">
  <a href="#install-in-2-minutes"><b>Install in 2 minutes</b></a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#foreman-vs-the-alternatives">Foreman vs. the alternatives</a> ·
  <a href="#faq">FAQ</a> ·
  <a href="README.ru.md">Русская версия</a>
</p>

---

## The problem: long projects leak promises

You ask Claude for something on Monday. On Wednesday the context gets compacted, a newer request takes the spotlight, and Monday's ask quietly falls out. Nobody decided to drop it. It just got lost.

On a project that runs for weeks this keeps happening, and you find out at the worst moment: in a demo, in a release, in front of a client. Foreman was born after an audit of one such project found **seven lost promises of the same kind**.

<p align="center">
  <img src="assets/infographic-problem.svg" alt="One request, two endings: without Foreman it is lost by Friday; with Foreman it is captured, survives compaction and is proven done." width="100%">
</p>

## Meet Foreman

Foreman keeps **one registry of everything you asked for**, in your own words, and computes what is really done from machine checks instead of anyone's memory.

| | |
|---|---|
| **Catches every ask, automatically.**<br>A Claude Code hook files each request into an inbox, word for word. You don't fill in forms or learn commands; you just talk. | **Proof, not promises.**<br>Every promise carries 1–3 *probes*: "this file exists", "this function is in the code", "this page answers". "Done" is computed, never typed. |
| **Survives context compaction.**<br>After every session start, resume and compaction, Claude gets a brief from the registry, not from a lossy recap. | **A checker that checks itself.**<br>Fake probes run on every check and must fail. If one ever passes, Foreman says the checker is broken instead of showing false greens. |
| **Parks work instead of dropping it.**<br>A new ask mid-task? The current item is parked with a written next step first, then the new one starts. | **Catches regressions.**<br>If something you already accepted stops passing its probes, it lights up **RED** in the next brief. |
| **A foreman, not a bricklayer.**<br>The `foreman` agent judges what probes can't: is it done by meaning, what was forgotten, the three next steps by your priorities. One screen, plain words. | **Tiny, local, private.**<br>One Python file, standard library only. No API keys, no servers, no telemetry. Your registry is plain JSONL in your repo. |

<p align="center">
  <img src="assets/infographic-at-a-glance.svg" alt="Foreman at a glance: 3 hooks, 6 probe types, 1 Python file, 0 dependencies, 2 minutes to install, English and Russian." width="100%">
</p>

## How it works

<p align="center">
  <img src="assets/infographic-how-it-works.svg" alt="How Foreman works: you ask, the inbox hook catches it, the stop hook reminds once to triage, the registry keeps the promise with probes, the session hook re-briefs Claude after start, resume and compaction." width="100%">
</p>

Three Claude Code hooks do the bookkeeping, so neither you nor Claude has to remember to:

| # | Hook | When it fires | What it does |
|---|---|---|---|
| 1 | `UserPromptSubmit` | you send a message | Recognises a request ("add", "fix", "please", "сделай", "нужно"…) and files it verbatim into `.foreman/inbox.jsonl`. Small talk ("ok", "thanks") is ignored. |
| 2 | `Stop` | Claude finishes its turn | Reminds Claude **once** to triage new asks: file a promise with probes, attach it to an existing one, or mark it "not a task". |
| 3 | `SessionStart` | start, resume, **compaction** | Injects a short brief computed from the registry: what is in progress, what is next, what is built and waiting for you, what turned red. |

## Proof, not promises

<p align="center">
  <img src="assets/infographic-proof.svg" alt="A promise card: the owner's quote, three probes (two pass, one fails), status partly; the lifecycle from todo to accepted; regressions flagged red; control probes must fail." width="100%">
</p>

A promise is kept when its probes turn green. Six kinds of probes cover most of what "built" means:

| Probe | Turns green when | Example |
|---|---|---|
| `file:path` | the file exists (globs work) | `file:src/export/*.py` |
| `grep:file:regex` | the code contains the pattern | `grep:src/app.py:def login` |
| `nogrep:file:regex` | the file exists **and** the pattern is gone | `nogrep:README.md:TODO` |
| `doc:file:word` | a word appears in the docs (any case) | `doc:docs/api.md:export` |
| `get:url` | an HTTP GET answers below 400. A server that is down counts as "not checked", never as "not built" | `get:http://localhost:8000/health` |
| `cmd:command` | a shell command exits with 0. **Off by default** because it runs code; enable it with `allow_cmd` | `cmd:pytest -q tests/test_login.py` |

Statuses you (or Claude, on your word) set by hand: `todo` · `doing` · `waiting` (for you) · `parked` · `accepted` (after **you** accept it) · `dropped` (only on your word). "Done" is never one of them: the probes decide.

## Foreman vs. the alternatives

**Foreman is not another task manager.** Task managers track the work an agent plans. Foreman guards the promises *you* made, in your own words, and proves they were kept. It's the part that's missing when the plan is fine but Monday's request still disappears.

| | **Foreman** | Claude Code's built-in task list | [Task Master](https://github.com/eyaltoledano/claude-task-master) | [Backlog.md](https://github.com/MrLesk/Backlog.md) |
|---|---|---|---|---|
| Captures your requests automatically | ✅ every message, via a hook | ➖ Claude builds its own list from a plan | ➖ tasks generated from a PRD | ➖ tasks created via CLI or MCP |
| Keeps your exact words | ✅ verbatim quote in every item | ❌ Claude's own wording | ❌ generated wording | ➖ whatever was typed in |
| "Done" is proven by machine checks | ✅ six probe types | ❌ set by the agent | ❌ set by the agent or you | ❌ set by the agent or you |
| The checker verifies itself | ✅ control probes must fail | ❌ | ❌ | ❌ |
| Restores open work after compaction | ✅ automatic, `SessionStart` hook | ➖ within its own session | ➖ when the agent queries it | ➖ when the agent reads it |
| Flags regressions in accepted work | ✅ RED in the next brief | ❌ | ❌ | ❌ |
| Planning, task breakdown, kanban | ❌ not its job | ➖ a simple checklist | ✅ PRD → tasks with dependencies | ✅ kanban board and web UI |
| What you install | one Python file, standard library | nothing, it's built in | Node.js package + a model provider or the Claude Code CLI | npm/bun/Homebrew/Nix package |

<sub>✅ yes · ➖ partly or indirectly · ❌ no. Based on each project's public documentation as of November 2026; if something here is out of date, please <a href="https://github.com/BenderBlender/Claude-Code-Foreman/issues">open an issue</a>.</sub>

**Why people pick Foreman:**

- **Zero effort.** You don't change how you talk to Claude. The hooks do the bookkeeping.
- **Honest by construction.** Nobody can mark a promise "done" to look good. Probes decide, and the control keeps the probes honest.
- **Built for long projects.** Weeks of sessions, dozens of compactions, requests made in passing: that's exactly where things get lost, and where Foreman helps most.
- **Plays well with others.** Keep Task Master or Backlog.md for planning. Foreman sits next to them and makes sure nothing you asked for falls through the cracks.
- **Safe to try.** It touches only your project folder, backs up your settings first and uninstalls cleanly while keeping your data.

## Install in 2 minutes

**You need:** [Claude Code](https://claude.com/claude-code) and [Python 3.8+](https://www.python.org/downloads/) (on Windows, tick *"Add python.exe to PATH"*).

**1. Get Foreman**

```bash
git clone https://github.com/BenderBlender/Claude-Code-Foreman.git
```

or click **Code → Download ZIP** on this page and unpack it.

**2. Install it into your project**

<table>
<tr><th>macOS / Linux</th><th>Windows</th></tr>
<tr>
<td>

```bash
cd Claude-Code-Foreman
./install.sh /path/to/your/project --lang en
```

</td>
<td>

Double-click `install.bat`, drag your project folder into the window and press **Enter**. Or from a terminal:

```bat
install.bat "C:\path\to\project" --lang en
```

</td>
</tr>
</table>

**3. Restart Claude Code in that project** (or open `/hooks` and accept the changes). That's it.

The installer runs a self-test before it finishes:

```text
Done. Foreman is installed.
Self-test: the control worked (the fake probes failed), the session hook answers.
```

<details>
<summary><b>What exactly changes in your project</b></summary>

Nothing outside the project folder is touched.

| What | Where | Notes |
|---|---|---|
| The engine and your data | `.foreman/` (`foreman.py`, `promises.jsonl`, `inbox.jsonl`, `config.json`) | your registry is kept on every update |
| Three hooks | `.claude/settings.local.json` | your personal settings file, usually not committed; the previous version is backed up to `.foreman/backup/` and your own hooks are kept |
| The `foreman` agent | `.claude/agents/foreman.md` | |
| A rules section | `CLAUDE.md`, between `<!-- foreman:start -->` and `<!-- foreman:end -->` | the rest of the file is left alone |

</details>

## Using it

**Just talk.** Ask for things the way you always do. Claude files each request as a promise with your quote and probes.

**Ask "What's the project status?"** You get the brief, plus a one-screen report from the `foreman` agent: done since last time, in progress, waiting for you, forgotten or stuck, and the three next steps.

A brief looks like this:

```text
FOREMAN (01.11 19:50; registry .foreman/promises.jsonl): 12 items · by probes done 7 · partly 2 · not 3 · waiting for you 1
In progress: P-009 «CSV export for reports» → add the Export button to web/reports.html
Next by priority: P-011 «Rate limits per plan»; P-012 «Dark theme»
Probes green but status «todo/doing» — verify and mark «accepted»: P-010
RED — «accepted» but the probes disagree: P-004 «Health endpoint»
Control: ok (the fake probes failed)
Parking: a new ask mid-work → set P-… status=parked next="…" on the current item first, then the new one.
```

**Accept the work** by telling Claude "P-007 accepted". Its status becomes `accepted`, and from then on the probes guard it against regressions.

**By hand**, if you like:

```bash
python .foreman/foreman.py brief            # the short brief
python .foreman/foreman.py status           # full report into .foreman/STATUS.md
python .foreman/foreman.py add '{"title": "…", "quote": "…", "probes": ["file:…"]}'
python .foreman/foreman.py set P-003 status=parked next="…"
python .foreman/foreman.py take I-0002 --as P-007     # or: skip I-0002 --why "a question, not a task"
python .foreman/foreman.py selftest
```

## Configuration

`.foreman/config.json`:

| Key | Default | Meaning |
|---|---|---|
| `lang` | `"ru"` | language of messages: `"ru"` or `"en"` (set by `--lang` at install) |
| `stale_days` | `3` | after how many days without movement an item in progress counts as stuck |
| `allow_cmd` | `false` | allow `cmd:` probes (they run shell commands) |
| `orphans` | empty | find abandoned files nothing references, e.g. `{"candidates": ["src/**/*.py"], "corpus": ["**/*.py", "**/*.md"]}` |
| `extra_ask_cues` | `[]` | your own regex cues that mark a message as a request |

## Uninstall

```bash
./install.sh /path/to/project --uninstall --lang en    # Windows: install.bat "C:\path\to\project" --uninstall --lang en
```

This removes the hooks, the agent and the `CLAUDE.md` section. **Your data in `.foreman/` stays.** Add `--purge` to move `.foreman/` aside as `.foreman_removed_<time>`. It is never erased.

## FAQ

<details>
<summary><b>Does Foreman send my code or prompts anywhere?</b></summary>

No. Everything runs locally as a small Python script. The only network calls are the `get:` probes you write yourself, against URLs you choose.
</details>

<details>
<summary><b>Will it slow Claude down or break my session?</b></summary>

The hooks are short local Python runs with hard timeouts (10 seconds for the inbox and reminder hooks, 30 for the brief, which runs your probes). A hook that fails is silently ignored, because a hook must never break the session.
</details>

<details>
<summary><b>I already have hooks in my project.</b></summary>

The installer merges with them. Your hooks stay, only Foreman's own entries are added or replaced, and the old settings file is backed up first.
</details>

<details>
<summary><b>Can my team share the registry?</b></summary>

Yes. `.foreman/promises.jsonl` is plain text in your repo; commit it to keep history and share it. The hooks live in each person's `.claude/settings.local.json`, so everyone who wants the automation runs the installer once.
</details>

<details>
<summary><b>My messages are in English. Does request detection work?</b></summary>

Yes. Request cues are built in for both English and Russian, whatever the message language setting is, and you can add your own with `extra_ask_cues`.
</details>

<details>
<summary><b>The server was down and my <code>get:</code> probe failed. Is the item now "not built"?</b></summary>

No. A server that doesn't answer makes the probe "not checked", never "not built". Foreman won't call your work missing just because a server is offline.
</details>

## The story

Foreman was built by Claude together with a film producer who was building a 3D previsualisation studio with Claude Code, in November 2026. An audit of that project found seven lost promises of the same kind. The design was chosen by a panel of four models (Fable, a Claude critic, ChatGPT and Gemini), and all four said the same thing: a separate "boss" that reads the same notes would lose things the same way. What you need is a registry where *readiness is computed by a check, not by memory*.

Other tools manage tasks. Foreman keeps **a person's promises, verbatim**, and checks for itself whether they were kept.

## License

[MIT](LICENSE) © 2026 BenderBlender. Bug reports and ideas are welcome in [Issues](https://github.com/BenderBlender/Claude-Code-Foreman/issues).
