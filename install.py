#!/usr/bin/env python3
"""Foreman (Прораб) installer — puts Foreman into ANY Claude Code project.

  python install.py [PROJECT_DIR] [--lang ru|en] [--modules promises,lessons] [--yes]   install (or update — your data is kept)
                                                                  --modules: promises (the asks), lessons (the rules, 2.0); both by default
                                                                  2.4: contract (a subagent's output file is checked), rules_paths
                                                                  (rules with paths: .claude/rules + the edit hook) — both on by default;
                                                                  a --modules list names EVERY module wanted (the rest are off)
  python install.py [PROJECT_DIR] --uninstall [--purge] [--yes]   remove the hooks, the agent and the CLAUDE.md section;
                                                                  --purge also moves .foreman/ aside (.foreman_removed_<time>), never deletes
Windows: double-click install.bat (or drag the project folder onto it). macOS / Linux: ./install.sh
What it does (nothing outside PROJECT_DIR is touched):
  PROJECT/.foreman/            foreman.py (the engine), config.json, promises.jsonl, inbox.jsonl — your data, kept on update
  PROJECT/.claude/agents/foreman.md            the thin «foreman» agent (judges, writes the one-screen status)
  PROJECT/.claude/agents/foreman-judge.md      the blind judge of the council (ranks anonymous candidates by a frozen rubric)
  PROJECT/.claude/skills/foreman-council/      the council procedure for hard items (a search that keeps the best verified version)
  PROJECT/.claude/settings.local.json          three hooks (UserPromptSubmit «inbox», Stop «stop», SessionStart «session») —
                                               the LOCAL settings file (personal, not committed); the old file is backed up first
  PROJECT/CLAUDE.md                            a section between <!-- foreman:start --> and <!-- foreman:end --> (the rules)
Standard library only, Python 3.8+."""
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
MARK = '.foreman/foreman.py'
START, END = '<!-- foreman:start -->', '<!-- foreman:end -->'

TXT = {
    'ru': {'ask_dir': 'Перетащите сюда папку проекта (или впишите путь) и нажмите Enter: ', 'no_dir': 'Нет такой папки: {p}',
           'confirm': 'Установить Прораба в «{p}»? [д/н] ', 'confirm_un': 'Убрать Прораба из «{p}»? [д/н] ', 'cancel': 'Отменено.',
           'py': 'Нужен Python 3.8 или новее (сейчас {v}).', 'done': 'Готово. Прораб установлен.',
           'next': ['Перезапустите Claude Code в этом проекте (или откройте /hooks и примите изменения) — хуки подхватятся.',
                    'Пишите просьбы как обычно: каждая попадёт во «входящие», а Claude заведёт по ней пункт с проверками.',
                    'Спросите «что у нас по проекту?» — Claude покажет сводку и позовёт агента foreman для подробного отчёта.',
                    'Сложный пункт? Скажите «консилиум по P-…» — Claude сравнит 2–3 варианта и оставит лучший проверенный, а не последний.',
                    'Реестр: .foreman/promises.jsonl · сводка вручную: python .foreman/foreman.py brief'],
           'next_lessons': ['Перезапустите Claude Code в этом проекте (или откройте /hooks и примите изменения) — хуки подхватятся.',
                            'Поправляйте и учите как обычно: ход не закончится, пока урок не записан (правило, журнал, память, навык).',
                            'Правила: python .foreman/foreman.py rule list · поиск: python .foreman/foreman.py recall <слова>'],
           'kept_own': 'Оставлен ваш файл (он отличается от копии набора): {p}',
           'panel_found': 'Консилиум моделей (2.2): на важные решения Claude может собирать мнения нескольких нейросетей — тех, что у вас есть. Найдено:',
           'panel_none': '  внешних нейросетей не найдено (Codex / Gemini / Qwen CLI, ключи OPENAI_API_KEY / GEMINI_API_KEY / OPENROUTER_API_KEY…, Ollama, LM Studio); субагенты Claude других моделей есть всегда',
           'panel_ask': 'Включить консилиум моделей? Бриф уходит выбранным нейросетям; перед каждой отправкой Claude спросит вас. [д/н] ',
           'contract_rule': ('{n}. **Задание субагенту — с файлом результата.** Бриф агенту, который должен что-то записать, кончается строкой '
                             '«Файл результата: `путь`». Прораб проверит файл, когда агент остановится: нет файла → агент продолжит и запишет; '
                             'если так и не записал — вам скажут «этап НЕ сделан»: продолжите ТОГО ЖЕ агента (SendMessage), не запускайте нового.'),
           'panel_rule': ('10. **Важное, дорогое решение → консилиум моделей** (модуль panel, его включил владелец). Навык `foreman-panel`: один бриф '
                          'без секретов → независимые ответы (`python .foreman/foreman.py panel run …` + свои субагенты других моделей) → проверка '
                          'утверждений → `DECISION.md` → владельцу до сборки. Перед отправкой брифа наружу — спросить владельца.'),
           'own_note': 'Прораб здесь ведёт только УРОКИ (модуль lessons) по книге правил самого проекта.',
           'own_8': ('8. **Поправка владельца → урок.** Сообщение похоже на поправку («опять», «забыл», «я же просил»…) → протокол урока: '
                     'правило уже есть? (`python .foreman/foreman.py recall …`); корень причины; где ещё повторится; запись: {hint}. В конце '
                     'ответа — «записано: <где>» (после записи) или «не поправка: <почему>»: ход не закончится, пока запись не сделана.'),
           'own_9': ('9. **Перед незнакомым действием** — `python .foreman/foreman.py recall <что собираюсь сделать>` (книга правил проекта, '
                     'память, навыки). Решения владельца живут там же: {hint}; Прораб их только читает.'),
           'selftest_ok': 'Самопроверка: контроль сработал (подставные пробы провалились), хук сводки отвечает.',
           'selftest_bad': 'ВНИМАНИЕ: самопроверка не прошла — пришлите вывод выше разработчику.',
           'backup': 'Копия прежних настроек: {p}', 'un_done': 'Прораб убран (хуки, агенты, навык консилиума, раздел CLAUDE.md).',
           'un_kept': 'Ваши данные остались в .foreman/ (удалить: --purge — папка будет отложена в сторону, не стёрта).',
           'purged': 'Папка .foreman отложена: {p}', 'yes': ('д', 'да', 'y', 'yes'),
           'bad_settings': 'Не читается {p} ({err}). Поправьте файл (или переименуйте его) и запустите установку снова — ничего не изменено.',
           'bad_marks': 'В CLAUDE.md есть только одна из меток раздела Прораба — раздел не тронут, поправьте метки вручную.'},
    'en': {'ask_dir': 'Drag the project folder here (or type its path) and press Enter: ', 'no_dir': 'No such folder: {p}',
           'confirm': 'Install Foreman into "{p}"? [y/n] ', 'confirm_un': 'Remove Foreman from "{p}"? [y/n] ', 'cancel': 'Cancelled.',
           'py': 'Python 3.8 or newer is needed (this is {v}).', 'done': 'Done. Foreman is installed.',
           'next': ['Restart Claude Code in this project (or open /hooks and accept the changes) — the hooks will load.',
                    'Ask for things as usual: every ask goes into the inbox and Claude files a promise with checks for it.',
                    'Ask "what is the project status?" — Claude shows the brief and calls the foreman agent for a full report.',
                    'A hard item? Say "council on P-…" — Claude compares 2–3 versions and keeps the best verified one, not the latest.',
                    'Registry: .foreman/promises.jsonl · brief by hand: python .foreman/foreman.py brief'],
           'next_lessons': ['Restart Claude Code in this project (or open /hooks and accept the changes) — the hooks will load.',
                            'Correct and teach as usual: the turn does not end until the lesson is recorded (a rule, the ledger, memory, a skill).',
                            'Rules: python .foreman/foreman.py rule list · search: python .foreman/foreman.py recall <words>'],
           'kept_own': 'Your own file is kept (it differs from the kit copy): {p}',
           'panel_found': 'Model panel (2.2): for important decisions Claude can gather the opinions of several AI models — the ones you have. Found:',
           'panel_none': '  no outside models found (Codex / Gemini / Qwen CLI, keys OPENAI_API_KEY / GEMINI_API_KEY / OPENROUTER_API_KEY…, Ollama, LM Studio); Claude\'s own subagents of other models are always there',
           'panel_ask': 'Switch the model panel on? The brief goes to the chosen models; Claude asks you before each sending. [y/n] ',
           'contract_rule': ('{n}. **A brief to a subagent names its output file.** A brief for an agent that must write something ends with '
                             '«Output file: `path`». Foreman checks the file when the agent stops: missing → the agent goes on and writes it; '
                             'still missing → you are told «the phase is NOT done»: resume THE SAME agent (SendMessage), do not spawn a new one.'),
           'panel_rule': ('10. **An important, costly decision → the model panel** (module panel, switched on by the owner). Skill `foreman-panel`: one '
                          'brief without secrets → independent answers (`python .foreman/foreman.py panel run …` + own subagents of other models) → '
                          'check the claims → `DECISION.md` → to the owner before building. Ask the owner before the brief leaves the machine.'),
           'own_note': "Foreman runs only LESSONS here (module lessons), over the project's own rule book.",
           'own_8': ("8. **The owner's correction → a lesson.** A message that looks like a correction (\"again\", \"you forgot\", \"I told you\"…) "
                     '→ the lesson protocol: already a rule? (`python .foreman/foreman.py recall …`); the root cause; where else it repeats; '
                     'record: {hint}. End the reply with «recorded: <where>» (after writing it) or «not a correction: <why>»: the turn does '
                     'not end until the record is made.'),
           'own_9': ('9. **Before an unfamiliar action** — `python .foreman/foreman.py recall <what I am about to do>` (the project\'s rule '
                     "book, memory, skills). The owner's decisions live there too: {hint}; Foreman only reads them."),
           'selftest_ok': 'Self-test: the control worked (the fake probes failed), the session hook answers.',
           'selftest_bad': 'WARNING: the self-test failed — send the output above to the developer.',
           'backup': 'Previous settings backed up: {p}', 'un_done': 'Foreman removed (hooks, agents, the council skill, CLAUDE.md section).',
           'un_kept': 'Your data stays in .foreman/ (to remove: --purge — the folder is moved aside, not erased).',
           'purged': 'The .foreman folder moved aside: {p}', 'yes': ('y', 'yes', 'д', 'да'),
           'bad_settings': 'Cannot read {p} ({err}). Fix (or rename) the file and run the installer again — nothing was changed.',
           'bad_marks': 'CLAUDE.md has only one of the Foreman section marks — the section was left alone; fix the marks by hand.'},
}

SPLASH = r"""
        _______
     __/  ___  \__        ╔═══════════════════════════════════════╗
    |__  |___|  __|       ║   ПРОРАБ  ·  FOREMAN                  ║
       \_______/          ║   обещания проекта не теряются        ║
     .-'  ___  '-.        ║   a project's promises don't get lost ║
    /    [ ✓ ]    \       ╚═══════════════════════════════════════╝
   |   [ ✓ ][   ]  |
    \____[   ]____/      для Claude Code · for Claude Code
"""


def out(s=''):
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode('ascii', 'replace').decode('ascii'))


def ask(q, yes_all):
    if yes_all:
        return True
    try:
        return input(q).strip().lower() in L['yes']
    except EOFError:
        return False


def read_json(p, default):
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    io.open(tmp, 'w', encoding='utf-8', newline='\n').write(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, p)


def stamp():
    return dt.datetime.now().strftime('%Y%m%d_%H%M%S')


def hooks_block(proj, promises=True, contract=True, rules_paths=True):
    py = sys.executable.replace('\\', '/')
    fm = os.path.join(proj, '.foreman', 'foreman.py').replace('\\', '/')
    cmd = lambda mode: f'"{py}" "{fm}" hook {mode}'           # noqa: E731
    return {'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': cmd('prompt'), 'timeout': 10}]}],
            'Stop': [{'hooks': [{'type': 'command', 'command': cmd('stop'), 'timeout': 10}]}],
            'SessionStart': [{'matcher': 'startup|resume|compact', 'hooks': [{'type': 'command', 'command': cmd('session'), 'timeout': 30}]}],
            # (the CLI's own task list: a task naming P-… closes only without red probes — 2.1)
            **({'TaskCompleted': [{'hooks': [{'type': 'command', 'command': cmd('task'), 'timeout': 30}]}]} if promises else {}),
            # (2.4: the subagent contract — a brief's «Файл результата: `…`» must exist when the subagent stops; the parent hears it)
            **({'SubagentStop': [{'hooks': [{'type': 'command', 'command': cmd('subagent'), 'timeout': 10}]}],
                'SubagentStart': [{'hooks': [{'type': 'command', 'command': cmd('subagent-start'), 'timeout': 10}]}],
                'PostToolUse': [{'matcher': 'Agent|Task', 'hooks': [{'type': 'command', 'command': cmd('agent-done'), 'timeout': 10}]}]}
               if contract else {}),
            # (2.4: a rule whose paths lie OUTSIDE the project — shown before an edit of a matching file; inside → .claude/rules)
            **({'PreToolUse': [{'matcher': 'Edit|Write|MultiEdit|NotebookEdit',
                                'hooks': [{'type': 'command', 'command': cmd('edit'), 'timeout': 10}]}]} if rules_paths else {})}


def strip_ours(settings):
    """the settings without any hook entry whose command runs .foreman/foreman.py"""
    hooks = settings.get('hooks') or {}
    for ev in list(hooks):
        kept = []
        for group in hooks[ev]:
            hs = [h for h in group.get('hooks', []) if MARK not in str(h.get('command', '')).replace('\\', '/')]
            if hs:
                kept.append({**group, 'hooks': hs})
        if kept:
            hooks[ev] = kept
        else:
            del hooks[ev]
    if hooks:
        settings['hooks'] = hooks
    else:
        settings.pop('hooks', None)
    return settings


def claude_section(proj, lang, remove=False, promises=True, hint='', panel=False, contract=False):
    p = os.path.join(proj, 'CLAUDE.md')
    s = io.open(p, encoding='utf-8').read() if os.path.exists(p) else ''
    if (START in s) != (END in s):                          # (one mark without the other: never guess where the section ends)
        out(L['bad_marks']); return
    if START in s and END in s:
        a, b = s.index(START), s.index(END) + len(END)
        s = (s[:a].rstrip('\n') + ('\n\n' if s[:a].strip() else '') + s[b:].lstrip('\n')).rstrip('\n') + ('\n' if s.strip() else '')
    if not remove:
        sec = io.open(os.path.join(KIT, 'foreman', f'claude_section.{lang}.md'), encoding='utf-8').read().strip()
        if not promises:                                    # (lessons only — a project with its own registry: no promise rules here)
            head, _, rest = sec.partition('\n')
            keep = [l for l in rest.splitlines() if l[:3] in ('8. ', '9. ')]
            note = ('Прораб здесь ведёт только УРОКИ (модуль lessons): правила владельца в `.foreman/rules.jsonl`.' if lang == 'ru' else
                    "Foreman runs only LESSONS here (module lessons): the owner's rules in `.foreman/rules.jsonl`.")
            sec = head + '\n\n' + (TXT[lang]['own_note'] if hint else note) + '\n\n' + '\n'.join(keep)
        if hint:                                            # (the project's own rule book: one book, not two — 04.11)
            sec = '\n'.join(TXT[lang]['own_8'].format(hint=hint) if l[:3] == '8. ' else TXT[lang]['own_9'].format(hint=hint)
                             if l[:3] == '9. ' else l for l in sec.splitlines())
        if panel:
            sec += '\n' + TXT[lang]['panel_rule']
        if contract:                                        # (2.4: the subagent contract — the marker the hook looks for)
            sec += '\n' + TXT[lang]['contract_rule'].format(n=11 if panel else 10)
        s = (s.rstrip('\n') + '\n\n' if s.strip() else '') + START + '\n' + sec + '\n' + END + '\n'
    if s.strip() or os.path.exists(p):
        io.open(p, 'w', encoding='utf-8', newline='\n').write(s)


def mark_legacy(fdir):
    """2.1 accepts only with the owner's logged words; what was accepted BEFORE is marked {"legacy": true} once, so the brief tells it
    apart from an acceptance that went around the check (Fable's review 1.3)"""
    for n, done in (('promises.jsonl', 'accepted'), ('rules.jsonl', 'active')):
        p = os.path.join(fdir, n)
        rows = []
        for line in io.open(p, encoding='utf-8'):
            try:
                rows.append(json.loads(line))
            except ValueError:
                rows.append(line.rstrip('\n'))           # (an unreadable line is kept as it is)
        hit = 0
        for r in rows:
            if isinstance(r, dict) and r.get('status') == done and not r.get('accepted'):
                r['accepted'] = {'legacy': True}
                hit += 1
        if hit:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(''.join((json.dumps(r, ensure_ascii=False) if isinstance(r, dict) else r)
                                                                         + '\n' for r in rows))


KIT_FILES = [('agent_foreman.md', 'agents/foreman.md', 'promises'), ('agent_judge.md', 'agents/foreman-judge.md', 'promises'),
             ('skill_council.md', 'skills/foreman-council/SKILL.md', 'promises'),
             ('skill_panel.md', 'skills/foreman-panel/SKILL.md', 'panel')]   # (kit file → its place under .claude/ → the module it needs)


def panel_offer(proj, fdir, cfg, yes_all, modules):
    """2.2 — the model panel is OFFERED, the owner decides: the members found here are shown and stored (so he can edit them), the
    question asked interactively; a silent install (--yes) leaves it off unless --modules names it"""
    r = subprocess.run([sys.executable, os.path.join(fdir, 'foreman.py'), 'panel', 'detect', '--json'], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=60)
    try:
        found = json.loads(r.stdout)
    except ValueError:
        found = []
    keep = ('name', 'kind', 'label', 'enabled', 'cmd', 'stdin', 'strip_env', 'args', 'base_url', 'key_env', 'model', 'models', 'params',
            'num_ctx', 'note')
    outside = [m for m in found if m.get('kind') != 'subagent']
    said_yes = modules is not None and 'panel' in modules  # (the owner named it — or answers «yes» below; otherwise nothing is switched on)
    if modules is None and not cfg['modules'].get('panel') and not yes_all and (not cfg['panel'].get('offered') or '--ask-panel' in sys.argv):
        out(L['panel_found'])
        for m in found:
            out(f"  • {m.get('label', m['name'])} — {m.get('how', '')}" + (f" ({m['note']})" if m.get('note') else ''))
        if not outside:
            out(L['panel_none'])
        said_yes = cfg['modules']['panel'] = ask(L['panel_ask'], False)
        cfg['panel']['offered'] = dt.date.today().isoformat()   # (asked once; an update does not ask again — `--ask-panel` does)
    known = {m.get('name') for m in (cfg['panel'].get('members') or []) if isinstance(m, dict)}
    for m in outside:                                     # (a member found NOW is on only if the owner said yes now — review M2)
        if m['name'] not in known:
            m['enabled'] = bool(said_yes and m.get('ready'))
    cfg['panel']['members'] = [{k: m[k] for k in keep if k in m} for m in outside]
    write_json(os.path.join(fdir, 'config.json'), cfg)


def put(src, dst, bdir):
    """copy a kit file over a project file; the old one, if different, goes to .foreman/backup/<stamp>/ first (2.0)"""
    if os.path.exists(dst) and io.open(dst, 'rb').read() != io.open(src, 'rb').read():
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(dst, os.path.join(bdir, os.path.basename(os.path.dirname(dst)) + '__' + os.path.basename(dst)))
    shutil.copy2(src, dst)


def install(proj, lang, yes_all, modules=None):
    if not ask(L['confirm'].format(p=proj), yes_all):
        out(L['cancel']); return 1
    fdir = os.path.join(proj, '.foreman')
    os.makedirs(fdir, exist_ok=True)
    bdir = os.path.join(fdir, 'backup', stamp())
    for n in ('foreman.py', 'recall.py', 'board.py', 'board.html', 'panel.py', 'lexicon.json'):
        if n != 'lexicon.json' or not os.path.exists(os.path.join(fdir, n)):     # (the owner's own words stay in his lexicon)
            put(os.path.join(KIT, 'foreman', n), os.path.join(fdir, n), bdir)
    cfg = read_json(os.path.join(fdir, 'config.json'), {})
    cfg = {'lang': lang, 'stale_days': 3, 'allow_cmd': False, 'orphans': {'candidates': [], 'corpus': []}, 'extra_ask_cues': [], **cfg, 'lang': lang}
    cfg['council'] = {'candidates': 2, 'max_rounds': 3, 'stop_after': 2, **(cfg.get('council') or {})}
    cfg['modules'] = {'promises': True, 'lessons': True, 'board': False, 'panel': False, 'contract': True, 'rules_paths': True,
                      **(cfg.get('modules') or {})}
    if modules is not None:
        cfg['modules'] = {m: m in modules for m in ('promises', 'lessons', 'board', 'panel', 'contract', 'rules_paths')}
    cfg['panel'] = {'ask_each_time': True, 'timeout_s': 600, 'members': [], **(cfg.get('panel') or {})}
    cfg['board'] = {'port': 8765, 'poll_s': 3, 'token_file': '', 'registries': [], **(cfg.get('board') or {})}
    cfg['budget'] = {'prompt_chars': 1200, 'session_chars': 2000, 'recall_hits': 3, 'recall_chars': 700, 'hot_rows': 5, **(cfg.get('budget') or {})}
    cfg['lessons'] = {'stop_gate': 'correction', 'extra_correction_cues': [], 'extra_teaching_cues': [], 'rules_extra': [],
                      'record_paths': [], 'record_hint': '', 'confirm_days': 60, 'memory_dir': 'auto', 'index_skills': True, **(cfg.get('lessons') or {})}
    write_json(os.path.join(fdir, 'config.json'), cfg)
    panel_offer(proj, fdir, cfg, yes_all, modules)
    for n in ('promises.jsonl', 'inbox.jsonl', 'rules.jsonl', 'eval.jsonl', 'events.jsonl', 'owner.jsonl'):
        io.open(os.path.join(fdir, n), 'a', encoding='utf-8').close()
    mark_legacy(fdir)
    if cfg['modules'].get('board'):                       # (a double-click opens the board: a console window is the owner's terminal)
        io.open(os.path.join(fdir, 'board.bat'), 'w', encoding='utf-8', newline='\r\n').write(   # (newline= makes each \n a \r\n)
            f'@echo off\nchcp 65001 >nul\ncd /d "%~dp0.."\n"{sys.executable}" "%~dp0foreman.py" board\npause\n')
        io.open(os.path.join(fdir, 'board.sh'), 'w', encoding='utf-8', newline='\n').write(
            f'#!/bin/sh\ncd "$(dirname "$0")/.." && exec "{sys.executable}" .foreman/foreman.py board\n')
    if not os.path.exists(os.path.join(fdir, 'ledger.md')):
        io.open(os.path.join(fdir, 'ledger.md'), 'w', encoding='utf-8').write('# Ledger — kept | revised | dropped -> what -> evidence\n\n')
    for src, dst, mod in KIT_FILES:                        # (lessons only: the promise-side agents and skill are not ours to write)
        if cfg['modules'].get(mod):
            dst = os.path.join(proj, '.claude', dst)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            put(os.path.join(KIT, 'foreman', src), dst, bdir)
    if os.path.isdir(bdir):
        out(L['backup'].format(p=bdir))
    sp = os.path.join(proj, '.claude', 'settings.local.json')
    if os.path.exists(sp):
        try:                                                # (review 04.11: an unreadable file was silently replaced)
            json.load(io.open(sp, encoding='utf-8'))
        except ValueError as e:
            out(L['bad_settings'].format(p=sp, err=e)); return 1
        os.makedirs(os.path.join(fdir, 'backup'), exist_ok=True)
        bk = os.path.join(fdir, 'backup', f'settings.local.json.{stamp()}')
        shutil.copy2(sp, bk)
        out(L['backup'].format(p=bk))
    settings = strip_ours(read_json(sp, {}))
    hooks = settings.setdefault('hooks', {})
    for ev, groups in hooks_block(proj, cfg['modules'].get('promises', True), cfg['modules'].get('contract', True),
                                  cfg['modules'].get('rules_paths', True)).items():
        hooks.setdefault(ev, []).extend(groups)
    write_json(sp, settings)
    if cfg['modules'].get('rules_paths', True) and cfg['modules'].get('lessons', True):   # (the active rules with paths → .claude/rules)
        subprocess.run([sys.executable, os.path.join(fdir, 'foreman.py'), 'rules', 'export'], capture_output=True)
    claude_section(proj, lang, promises=cfg['modules'].get('promises', True), hint=str(cfg['lessons'].get('record_hint') or '')[:160],
                   panel=cfg['modules'].get('panel', False), contract=cfg['modules'].get('contract', True))
    out(L['done'])
    promises = cfg['modules'].get('promises', True)
    ok = selftest(proj, promises)
    out(L['selftest_ok'] if ok else L['selftest_bad'])
    for line in L['next'] if promises else L['next_lessons']:
        out('  • ' + line)
    return 0 if ok else 2


def selftest(proj, promises=True):
    fm = os.path.join(proj, '.foreman', 'foreman.py')
    run = lambda *a, inp=None: subprocess.run([sys.executable, fm, *a], input=inp, capture_output=True, text=True, encoding='utf-8',
                                              errors='replace')
    a = run('selftest')
    b = run('hook', 'session', inp='{"source": "startup"}')
    try:
        ctx = json.loads(b.stdout)['hookSpecificOutput']['additionalContext']
    except (ValueError, KeyError, TypeError):
        ctx = ''
    if promises:
        good = a.returncode == 0 and bool(ctx)
    else:                                                   # (lessons only: a quiet session is right; the recall must answer)
        c = run('recall', 'test')
        good = a.returncode == 0 and b.returncode == 0 and c.returncode == 0
        b = c if b.returncode == 0 else b
    if not good:
        out(a.stdout + a.stderr + b.stdout + b.stderr)
    return good


def uninstall(proj, purge, yes_all):
    if not ask(L['confirm_un'].format(p=proj), yes_all):
        out(L['cancel']); return 1
    sp = os.path.join(proj, '.claude', 'settings.local.json')
    if os.path.exists(sp):
        write_json(sp, strip_ours(read_json(sp, {})))
    skill = os.path.join(proj, '.claude', 'skills', 'foreman-council')
    for src, dst, _ in KIT_FILES:
        dst = os.path.join(proj, '.claude', dst)
        if os.path.exists(dst):                           # (only the kit's own unchanged copy goes; an adapted one is the owner's)
            if io.open(dst, 'rb').read() == io.open(os.path.join(KIT, 'foreman', src), 'rb').read():
                os.remove(dst)
            else:
                out(L['kept_own'].format(p=dst))
    for d in (skill, os.path.join(proj, '.claude', 'skills', 'foreman-panel'), os.path.dirname(skill), os.path.join(proj, '.claude', 'agents')):
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
    rd = os.path.join(proj, '.claude', 'rules')               # (2.4: only the rules Foreman generated — marked in the file)
    for name in (os.listdir(rd) if os.path.isdir(rd) else []):
        p = os.path.join(rd, name)
        if name.startswith('foreman-') and name.endswith('.md') and '<!-- generated by Foreman' in io.open(p, encoding='utf-8', errors='replace').read():
            os.remove(p)
    if os.path.isdir(rd) and not os.listdir(rd):
        os.rmdir(rd)
    claude_section(proj, 'ru', remove=True)
    out(L['un_done'])
    fdir = os.path.join(proj, '.foreman')
    if purge and os.path.isdir(fdir):
        aside = os.path.join(proj, f'.foreman_removed_{stamp()}')
        shutil.move(fdir, aside)
        out(L['purged'].format(p=aside))
    elif os.path.isdir(fdir):
        out(L['un_kept'])
    return 0


def main(argv):
    global L
    lang = argv[argv.index('--lang') + 1] if '--lang' in argv and argv.index('--lang') + 1 < len(argv) else 'ru'
    L = TXT.get(lang, TXT['ru'])
    out(SPLASH)
    if sys.version_info < (3, 8):
        out(L['py'].format(v=sys.version.split()[0])); return 1
    pos = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] not in ('--lang', '--modules'))]
    proj = pos[0] if pos else ''
    if not proj:
        try:
            proj = input(L['ask_dir'])
        except EOFError:
            proj = ''
    proj = os.path.abspath(proj.strip().strip('"').strip("'"))
    if not os.path.isdir(proj):
        out(L['no_dir'].format(p=proj)); return 1
    if '--lang' not in argv:                                # (an update keeps the project's language — review 04.11)
        lang = read_json(os.path.join(proj, '.foreman', 'config.json'), {}).get('lang') or lang
        L = TXT.get(lang, TXT['ru'])
    if '--uninstall' in argv:
        return uninstall(proj, '--purge' in argv, '--yes' in argv)
    mods = None
    if '--modules' in argv and argv.index('--modules') + 1 < len(argv):
        mods = {m.strip() for m in argv[argv.index('--modules') + 1].split(',') if m.strip()}
    return install(proj, lang, '--yes' in argv, mods)


L = TXT['ru']
if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
