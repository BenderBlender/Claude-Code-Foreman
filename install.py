#!/usr/bin/env python3
"""Foreman (Прораб) installer — puts Foreman into ANY Claude Code project.

  python install.py [PROJECT_DIR] [--lang ru|en] [--modules promises,lessons] [--yes]   install (or update — your data is kept)
                                                                  --modules: promises (the asks), lessons (the rules, 2.0); both by default
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


def hooks_block(proj):
    py = sys.executable.replace('\\', '/')
    fm = os.path.join(proj, '.foreman', 'foreman.py').replace('\\', '/')
    cmd = lambda mode: f'"{py}" "{fm}" hook {mode}'           # noqa: E731
    return {'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': cmd('prompt'), 'timeout': 10}]}],
            'Stop': [{'hooks': [{'type': 'command', 'command': cmd('stop'), 'timeout': 10}]}],
            'SessionStart': [{'matcher': 'startup|resume|compact', 'hooks': [{'type': 'command', 'command': cmd('session'), 'timeout': 30}]}]}


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


def claude_section(proj, lang, remove=False):
    p = os.path.join(proj, 'CLAUDE.md')
    s = io.open(p, encoding='utf-8').read() if os.path.exists(p) else ''
    if (START in s) != (END in s):                          # (one mark without the other: never guess where the section ends)
        out(L['bad_marks']); return
    if START in s and END in s:
        a, b = s.index(START), s.index(END) + len(END)
        s = (s[:a].rstrip('\n') + ('\n\n' if s[:a].strip() else '') + s[b:].lstrip('\n')).rstrip('\n') + ('\n' if s.strip() else '')
    if not remove:
        sec = io.open(os.path.join(KIT, 'foreman', f'claude_section.{lang}.md'), encoding='utf-8').read().strip()
        s = (s.rstrip('\n') + '\n\n' if s.strip() else '') + START + '\n' + sec + '\n' + END + '\n'
    if s.strip() or os.path.exists(p):
        io.open(p, 'w', encoding='utf-8', newline='\n').write(s)


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
    for n in ('foreman.py', 'recall.py', 'lexicon.json'):
        if n != 'lexicon.json' or not os.path.exists(os.path.join(fdir, n)):     # (the owner's own words stay in his lexicon)
            put(os.path.join(KIT, 'foreman', n), os.path.join(fdir, n), bdir)
    cfg = read_json(os.path.join(fdir, 'config.json'), {})
    cfg = {'lang': lang, 'stale_days': 3, 'allow_cmd': False, 'orphans': {'candidates': [], 'corpus': []}, 'extra_ask_cues': [], **cfg, 'lang': lang}
    cfg['council'] = {'candidates': 2, 'max_rounds': 3, 'stop_after': 2, **(cfg.get('council') or {})}
    cfg['modules'] = {'promises': True, 'lessons': True, 'board': False, **(cfg.get('modules') or {})}
    if modules is not None:
        cfg['modules'] = {m: m in modules for m in ('promises', 'lessons', 'board')}
    cfg['budget'] = {'prompt_chars': 1200, 'session_chars': 2000, 'recall_hits': 3, 'recall_chars': 700, 'hot_rows': 5, **(cfg.get('budget') or {})}
    cfg['lessons'] = {'stop_gate': 'correction', 'extra_correction_cues': [], 'extra_teaching_cues': [], 'rules_extra': [],
                      'record_paths': [], 'memory_dir': 'auto', 'index_skills': True, **(cfg.get('lessons') or {})}
    write_json(os.path.join(fdir, 'config.json'), cfg)
    for n in ('promises.jsonl', 'inbox.jsonl', 'rules.jsonl', 'eval.jsonl', 'events.jsonl'):
        io.open(os.path.join(fdir, n), 'a', encoding='utf-8').close()
    if not os.path.exists(os.path.join(fdir, 'ledger.md')):
        io.open(os.path.join(fdir, 'ledger.md'), 'w', encoding='utf-8').write('# Ledger — kept | revised | dropped -> what -> evidence\n\n')
    agents = os.path.join(proj, '.claude', 'agents')
    os.makedirs(agents, exist_ok=True)
    put(os.path.join(KIT, 'foreman', 'agent_foreman.md'), os.path.join(agents, 'foreman.md'), bdir)
    put(os.path.join(KIT, 'foreman', 'agent_judge.md'), os.path.join(agents, 'foreman-judge.md'), bdir)
    skill = os.path.join(proj, '.claude', 'skills', 'foreman-council')
    os.makedirs(skill, exist_ok=True)
    put(os.path.join(KIT, 'foreman', 'skill_council.md'), os.path.join(skill, 'SKILL.md'), bdir)
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
    for ev, groups in hooks_block(proj).items():
        hooks.setdefault(ev, []).extend(groups)
    write_json(sp, settings)
    claude_section(proj, lang)
    out(L['done'])
    ok = selftest(proj)
    out(L['selftest_ok'] if ok else L['selftest_bad'])
    for line in L['next']:
        out('  • ' + line)
    return 0 if ok else 2


def selftest(proj):
    fm = os.path.join(proj, '.foreman', 'foreman.py')
    a = subprocess.run([sys.executable, fm, 'selftest'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    b = subprocess.run([sys.executable, fm, 'hook', 'session'], input='{"source": "startup"}', capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    try:
        ctx = json.loads(b.stdout)['hookSpecificOutput']['additionalContext']
    except (ValueError, KeyError, TypeError):
        ctx = ''
    if a.returncode != 0 or not ctx:
        out(a.stdout + a.stderr + b.stdout + b.stderr)
    return a.returncode == 0 and bool(ctx)


def uninstall(proj, purge, yes_all):
    if not ask(L['confirm_un'].format(p=proj), yes_all):
        out(L['cancel']); return 1
    sp = os.path.join(proj, '.claude', 'settings.local.json')
    if os.path.exists(sp):
        write_json(sp, strip_ours(read_json(sp, {})))
    for ag in ('foreman.md', 'foreman-judge.md'):
        ag = os.path.join(proj, '.claude', 'agents', ag)
        if os.path.exists(ag):
            os.remove(ag)
    skill = os.path.join(proj, '.claude', 'skills', 'foreman-council')
    if os.path.exists(os.path.join(skill, 'SKILL.md')):
        os.remove(os.path.join(skill, 'SKILL.md'))
        if not os.listdir(skill):
            os.rmdir(skill)
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
