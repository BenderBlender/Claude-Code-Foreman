#!/usr/bin/env python3
"""Foreman (Прораб) — keeps a project's promises from getting lost between Claude Code sessions.

Why: an AI coding session forgets. A request made on Monday lives as prose in a chat; on Wednesday the context was compacted, the
session switched to a new ask, and the old one silently fell out. Foreman keeps ONE registry of the owner's asks — each with the
VERBATIM quote and machine PROBES — and computes what is really built from the probes, never from someone's word. Three Claude Code
hooks make it automatic: an ask is caught into the inbox, the end of a turn reminds once to triage it, and every session start / resume /
compaction gets a short brief from the registry (not from the summary). A thin «foreman» agent judges what probes cannot (done by meaning,
stale, contradictions) and writes the owner's one-screen status.

Files (in the project): .foreman/promises.jsonl  .foreman/inbox.jsonl  .foreman/STATUS.md  .foreman/config.json
A promise: {"id": "P-001", "date": "2026-11-01", "title": "…", "quote": "the owner's words, verbatim", "source": "…",
            "priority": "high|normal|later", "status": "todo|doing|waiting|parked|accepted|dropped", "next": "…", "waits": "…",
            "probes": ["file:src/app.py", "grep:src/app.py:def login", "nogrep:README.md:TODO", "doc:docs/api.md:login",
                       "get:http://localhost:8000/health", "cmd:pytest -q tests/test_login.py"], "touched": "2026-11-01"}
Probes (paths relative to the project root; file: takes globs): file · grep (regex in a file) · nogrep (the file exists and the line
is GONE) · doc (a word in a file, any case) · get (an HTTP GET answers < 400; a server that is down → «not checked») · cmd (a shell
command exits 0 — OFF unless config.json "allow_cmd": true, because it runs code). «built» is NEVER typed: it is the probes' result.
CONTROL: fake probes are run every time and MUST fail — a passing control means the checker is broken (exit 2).

  python .foreman/foreman.py brief | status | json | selftest
  python .foreman/foreman.py add '{"title": …, "quote": …, "probes": […]}'      → the next id
  python .foreman/foreman.py set P-003 status=parked next="…"                 (PARKING before a new ask mid-work)
  python .foreman/foreman.py take I-0002 --as P-007   |   skip I-0002 --why "a question, not a task"
  python .foreman/foreman.py hook inbox|stop|session        (Claude Code hooks; JSON on stdin, JSON on stdout)
COUNCIL — for hard items, a search with a kept leader (procedure: .claude/skills/foreman-council/SKILL.md):
  python .foreman/foreman.py check P-007 [--root ../cand-a]             the item's probes on any folder (e.g. a git worktree)
  python .foreman/foreman.py compare P-007 L=. A=../cand-a B=../cand-b  the same probes on every candidate, side by side
  python .foreman/foreman.py round P-007 '{"tried": ["L","A","B"], "winner": "A", "accepted": true, "why": "…"}'
  After the first logged round the item's probes and rubric are FROZEN (set refuses them without --force): the criteria are
  fixed before the search and never tailored to a candidate. «round» says when to stop: the BEST verified version wins, not the last.
Standard library only, Python 3.8+. Made by Claude (Anthropic) with a film producer, 2026-11-01 — see README.md."""
import datetime as dt
import glob
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
REG, INBOX, STATUS, CONFIG = (os.path.join(HERE, n) for n in ('promises.jsonl', 'inbox.jsonl', 'STATUS.md', 'config.json'))
OPEN = ('todo', 'doing', 'waiting', 'parked')
PRIO = {'high': 0, 'normal': 1, 'later': 2}
CONTROLS = [{'id': 'CTRL-1', 'probes': ['file:.foreman/__control_never_exists__.txt']},
            {'id': 'CTRL-2', 'probes': ['grep:.foreman/foreman.py:__CONTROL_NEVER_MATCHES_' + '7f3a__', 'nogrep:.foreman/foreman.py:def main']}]
ASK = {'ru': [r'сделай', r'сделайте', r'добавь', r'построй', r'настрой', r'переделай', r'создай', r'исправь', r'почини', r'внедри',
              r'доработай', r'подключи', r'перенеси', r'запусти', r'проверь', r'\bнадо\b', r'нужно', r'нужен', r'не забудь', r'потом сделай',
              r'продумай', r'обсуди', r'найди', r'проведи', r'\bдай(те)?\b', r'хочу, чтобы', r'хочу что бы'],
       'en': [r'\bmake\b', r'\badd\b', r'\bbuild\b', r'\bcreate\b', r'\bfix\b', r'\bimplement\b', r'\bchange\b', r'\bremove\b', r'\bset up\b',
              r'\bplease\b', r'\bwe need\b', r'\bi want\b', r'\bdon\'t forget\b', r'\bremember to\b', r'\bcould you\b', r'\bcan you\b']}
SHORT = re.compile(r'^(да|ок|окей|хорошо|отлично|продолжай|продолжи|yes|ok|okay|go on|continue|thanks|спасибо)[.!]?$', re.I)
AGENT_NOTE = re.compile(r'^(Another Claude session sent a message|\[SYSTEM NOTIFICATION|<task-notification|<agent-message|<cross-session-message)')

T = {
    'ru': {'head': 'ПРОРАБ ({when}; реестр .foreman/promises.jsonl): {n} пунктов · по пробам готово {ok} · частично {part} · нет {no}{unk} · ждут вас {wait}',
           'unk': ' · не проверено {n} (сервер не отвечает)', 'doing': 'В работе', 'next': 'Следующие по приоритету',
           'built': 'Пробы зелёные, а статус «todo/doing» — проверить и отметить «accepted»', 'red': 'КРАСНОЕ — «accepted», а пробы не сходятся',
           'stale': 'В работе без движения > {d} дн.', 'orphans': 'Сироты (файл, на который никто не ссылается)',
           'inbox': 'Входящие просьбы НЕ разобраны: {n} — {list} → foreman.py add {{…}} + take I-… --as P-…, или skip I-… --why «…»',
           'ctrl_ok': 'Контроль: ок (подставные пробы провалились)', 'ctrl_bad': 'Контроль СЛОМАН — подставная проба прошла, пробам не верить',
           'park': 'Парковка: новая просьба посреди работы → текущему пункту set P-… status=parked next="…", потом новое.',
           'status_title': '# Состояние проекта — {when}', 'status_lead': 'Реестр: {n} пунктов. По проверке: готово {ok}, частично {part}, не сделано {no}.',
           'waiting': 'Ждёт вашего слова', 'doing_h': 'В работе', 'next_h': 'Дальше по приоритету', 'built_h': 'Сделано, ждёт вашей приёмки',
           'lost_h': 'Забыто / брошено', 'ctrl_line_ok': 'Контроль проверки: в порядке.', 'ctrl_line_bad': 'Контроль проверки СЛОМАН — цифрам выше не верить.',
           'hook_inbox': ('ПРОРАБ: просьба записана во входящие {id}. До конца хода — разбор: если это работа → python .foreman/foreman.py add '
                          '\'{{"title": …, "quote": дословно, "probes": [file:/grep:/nogrep:/doc:/get:]}}\' и take {id} --as P-…; иначе skip {id} --why «…». '
                          'Если шла другая работа — ПАРКОВКА: set P-<текущий> status=parked next="<следующий шаг>".'),
           'hook_stop': ('ПРОРАБ: входящие просьбы не разобраны — {list}. Разберите каждую: работа → add {{…}} + take I-… --as P-…; не задача / уже есть пункт → '
                         'skip I-… --why «…» (или take на существующий P-…). Напоминание одно — дальше пункт виден в сводке.'),
           'compact': 'После сжатия контекста — состояние проекта из РЕЕСТРА (не из пересказа):',
           'council': 'Консилиум', 'council_item': '{id} раунд {n}/{max} · лидер {lead} · без улучшения {stale}', 'lead_initial': 'исходный',
           'council_go': 'Дальше: раунд {n}/{max}, кандидатов {k}. Пробы и рубрика заморожены — сравнивать по ним же.',
           'council_stop': 'СТОП консилиума ({why}): оставьте ЛУЧШЕГО ({lead}), а не последнего; уберите лишние worktree; '
                           'вкусовой выбор → set {id} status=waiting waits="финалисты: …".',
           'why_stale': '{s} раунд(а) подряд без улучшения', 'why_max': 'исчерпан предел раундов',
           'frozen': 'Пробы и рубрика {id} заморожены: идёт консилиум ({n} раунд(ов)). Критерии не подгоняют под кандидатов. '
                     'Если критерий ошибочен — скажите владельцу и повторите с --force.',
           'cmp_head': '{id}: сравнение по пробам (объективная часть; смысл и вкус оценивает слепой судья foreman-judge):',
           'cmp_best': 'Больше всего зелёных проб: {labels}', 'cmp_ctrl': 'контроль СЛОМАН — этой проверке не верить',
           'no_root': 'нет такой папки:'},
    'en': {'head': 'FOREMAN ({when}; registry .foreman/promises.jsonl): {n} items · by probes done {ok} · partly {part} · not {no}{unk} · waiting for you {wait}',
           'unk': ' · not checked {n} (server down)', 'doing': 'In progress', 'next': 'Next by priority',
           'built': 'Probes green but status «todo/doing» — verify and mark «accepted»', 'red': 'RED — «accepted» but the probes disagree',
           'stale': 'In progress with no move > {d} days', 'orphans': 'Orphans (a file nothing references)',
           'inbox': 'Unprocessed asks in the inbox: {n} — {list} → foreman.py add {{…}} + take I-… --as P-…, or skip I-… --why "…"',
           'ctrl_ok': 'Control: ok (the fake probes failed)', 'ctrl_bad': 'Control BROKEN — a fake probe passed, do not trust the probes',
           'park': 'Parking: a new ask mid-work → set P-… status=parked next="…" on the current item first, then the new one.',
           'status_title': '# Project status — {when}', 'status_lead': 'Registry: {n} items. By the check: done {ok}, partly {part}, not done {no}.',
           'waiting': 'Waiting for your word', 'doing_h': 'In progress', 'next_h': 'Next by priority', 'built_h': 'Built, waiting for your acceptance',
           'lost_h': 'Forgotten / abandoned', 'ctrl_line_ok': 'The check\'s control: fine.', 'ctrl_line_bad': 'The check\'s control is BROKEN — do not trust the numbers above.',
           'hook_inbox': ('FOREMAN: the ask was put into the inbox as {id}. Before the turn ends, triage it: real work → python .foreman/foreman.py add '
                          '\'{{"title": …, "quote": verbatim, "probes": [file:/grep:/nogrep:/doc:/get:]}}\' and take {id} --as P-…; otherwise skip {id} --why "…". '
                          'If other work was going on — PARKING: set P-<current> status=parked next="<next step>".'),
           'hook_stop': ('FOREMAN: unprocessed asks in the inbox — {list}. Triage each: work → add {{…}} + take I-… --as P-…; not a task / already an item → '
                         'skip I-… --why "…" (or take onto the existing P-…). One reminder only — after that the item shows in the brief.'),
           'compact': 'After the context compaction — the project state from the REGISTRY (not from the summary):',
           'council': 'Council', 'council_item': '{id} round {n}/{max} · leader {lead} · no gain {stale}', 'lead_initial': 'initial',
           'council_go': 'Next: round {n}/{max}, {k} candidates. Probes and rubric are frozen — compare by them.',
           'council_stop': 'COUNCIL STOP ({why}): keep the BEST ({lead}), not the latest; remove the spare worktrees; '
                           'a matter of taste → set {id} status=waiting waits="finalists: …".',
           'why_stale': '{s} round(s) in a row without a gain', 'why_max': 'the round limit is reached',
           'frozen': 'The probes and rubric of {id} are frozen: a council is running ({n} round(s)). Criteria are never tailored to '
                     'candidates. If a criterion is wrong, tell the owner and repeat with --force.',
           'cmp_head': '{id}: comparison by probes (the objective part; meaning and taste go to the blind judge foreman-judge):',
           'cmp_best': 'Most green probes: {labels}', 'cmp_ctrl': 'control BROKEN — do not trust this check',
           'no_root': 'no such folder:'},
}


def config():
    council = {'candidates': 2, 'max_rounds': 3, 'stop_after': 2}
    c = {'lang': 'ru', 'stale_days': 3, 'allow_cmd': False, 'orphans': {'candidates': [], 'corpus': []}, 'extra_ask_cues': []}
    try:
        c.update(json.load(io.open(CONFIG, encoding='utf-8')))
    except (OSError, ValueError):
        pass
    c['council'] = {**council, **(c.get('council') or {})}
    return c


CFG = config()
L = T.get(CFG.get('lang'), T['ru'])


def read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


def jsonl(p):
    out = []
    for line in read(p).splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({'id': '?', 'title': 'UNREADABLE LINE: ' + line[:80], 'probes': []})
    return out


def write_jsonl(p, rows):
    tmp = p + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, p)


def today():
    return dt.date.today().isoformat()


def path_of(p):
    return os.path.join(ROOT, p)


def set_root(path):
    global ROOT
    ROOT = os.path.abspath(path)


_server = {}


def probe(p):
    kind, _, rest = p.partition(':')
    try:
        if kind == 'file':
            return bool(glob.glob(path_of(rest), recursive=True))
        if kind in ('grep', 'nogrep'):
            f, _, rx = rest.partition(':')
            found = bool(re.search(rx, read(path_of(f))))
            return found if kind == 'grep' else (os.path.exists(path_of(f)) and not found)
        if kind == 'doc':
            f, _, word = rest.partition(':')
            return word.lower() in read(path_of(f)).lower()
        if kind == 'get':
            try:
                urllib.request.urlopen(rest, timeout=8)
                return True
            except urllib.error.HTTPError as e:
                return e.code < 400
            except Exception:
                return None                         # (down → «not checked», never «not built»)
        if kind == 'cmd':
            if not CFG.get('allow_cmd'):
                return None
            return subprocess.run(rest, shell=True, cwd=ROOT, capture_output=True, timeout=20).returncode == 0
    except (re.error, subprocess.TimeoutExpired, OSError):
        return False
    return False


def check_item(item):
    res = [(p, probe(p)) for p in item.get('probes', [])]
    vals = [v for _, v in res]
    if not vals:
        state = 'no-probes'
    elif all(v is True for v in vals):
        state = 'done'
    elif any(v is True for v in vals):
        state = 'partly'
    elif any(v is None for v in vals):
        state = 'unchecked'
    else:
        state = 'not'
    return state, res


def orphans():
    o = CFG.get('orphans') or {}
    cand = [f for g in o.get('candidates', []) for f in glob.glob(path_of(g), recursive=True) if os.path.isfile(f)]
    if not cand:
        return []
    corpus = {f: read(f) for g in o.get('corpus', []) for f in glob.glob(path_of(g), recursive=True)
              if os.path.isfile(f) and os.path.getsize(f) < 3_000_000}
    corpus[REG] = read(REG)
    out = []
    for c in cand:
        name, stem = os.path.basename(c), os.path.splitext(os.path.basename(c))[0]
        pat = re.compile(re.escape(name) + r'|\b(import|from|require)\s*\(?\s*[\'"]?[./\w]*' + re.escape(stem) + r'\b')
        if not any(pat.search(t) for f, t in corpus.items() if os.path.abspath(f) != os.path.abspath(c)):
            out.append(os.path.relpath(c, ROOT).replace('\\', '/'))
    return sorted(out)


def age(item):
    try:
        return (dt.date.today() - dt.date.fromisoformat((item.get('touched') or item.get('date') or '')[:10])).days
    except ValueError:
        return None


def probe_report(item, root):
    """the item's probes and the control, run against another folder (e.g. a candidate's git worktree)"""
    saved = ROOT
    set_root(root)
    try:
        state, res = check_item(item)
        ctrl = all(check_item(c)[0] == 'not' for c in CONTROLS)
    finally:
        set_root(saved)
    return state, res, ctrl


def council_state(item):
    rounds = item.get('rounds') or []
    stale = 0
    for r in reversed(rounds):
        if r.get('accepted'):
            break
        stale += 1
    lead = next((r.get('winner') for r in reversed(rounds) if r.get('accepted') and r.get('winner')), L['lead_initial'])
    return len(rounds), stale, lead


def council_line(item):
    n, stale, lead = council_state(item)
    return L['council_item'].format(id=item.get('id'), n=n, max=CFG['council']['max_rounds'], lead=lead, stale=stale)


def run():
    reg = jsonl(REG)
    for it in reg:
        it['_check'], it['_probes'] = check_item(it)
    control = [(c['id'], check_item(c)[0]) for c in CONTROLS]
    return {'when': dt.datetime.now().strftime('%d.%m %H:%M'), 'registry': reg, 'control_ok': all(s == 'not' for _, s in control),
            'orphans': orphans(), 'inbox_new': [i for i in jsonl(INBOX) if i.get('state', 'new') == 'new']}


def key(it):
    return (PRIO.get(it.get('priority'), 1), it.get('date') or '', it.get('id'))


def summary(r):
    live = [i for i in r['registry'] if i.get('status') != 'dropped']
    return dict(live=live, cnt=lambda s: sum(i['_check'] == s for i in live),
                doing=sorted([i for i in live if i.get('status') == 'doing'], key=key),
                waiting=sorted([i for i in live if i.get('status') == 'waiting'], key=key),
                nxt=sorted([i for i in live if i.get('status') in ('todo', 'parked') and i['_check'] != 'done'], key=key),
                red=[i for i in live if i.get('status') == 'accepted' and i['_check'] in ('not', 'partly')],
                built=[i for i in live if i.get('status') in ('todo', 'doing') and i['_check'] == 'done'],
                stale=[i for i in live if i.get('status') == 'doing' and (age(i) or 0) > CFG.get('stale_days', 3)],
                council=[i for i in live if i.get('rounds') and i.get('status') in OPEN])


def short(it, n=55):
    t = it.get('title', '')
    return f"{it.get('id')} «{t[:n]}{'…' if len(t) > n else ''}»"


def brief(r):
    s = summary(r)
    unk = s['cnt']('unchecked')
    out = [L['head'].format(when=r['when'], n=len(s['live']), ok=s['cnt']('done'), part=s['cnt']('partly'), no=s['cnt']('not'),
                            unk=L['unk'].format(n=unk) if unk else '', wait=len(s['waiting']))]
    if s['doing']:
        out.append(L['doing'] + ': ' + '; '.join(f"{short(i, 40)} → {(i.get('next') or '')[:70]}" for i in s['doing'][:4]))
    if s['council']:
        out.append(L['council'] + ': ' + '; '.join(council_line(i) for i in s['council'][:3]))
    if s['nxt']:
        out.append(L['next'] + ': ' + '; '.join(short(i, 40) for i in s['nxt'][:3]))
    if s['built']:
        out.append(L['built'] + ': ' + ', '.join(i['id'] for i in s['built'][:8]))
    if s['red']:
        out.append(L['red'] + ': ' + ', '.join(short(i, 30) for i in s['red'][:5]))
    if s['stale']:
        out.append(L['stale'].format(d=CFG.get('stale_days', 3)) + ': ' + ', '.join(i['id'] for i in s['stale']))
    if r['orphans']:
        out.append(L['orphans'] + ': ' + ', '.join(r['orphans'][:6]))
    if r['inbox_new']:
        out.append(L['inbox'].format(n=len(r['inbox_new']), list='; '.join(f"{i['id']}: «{i.get('text', '')[:60]}»" for i in r['inbox_new'][:3])))
    out.append(L['ctrl_ok'] if r['control_ok'] else L['ctrl_bad'])
    out.append(L['park'])
    return '\n'.join(out[:15])


def status_md(r):
    s = summary(r)
    lines = [L['status_title'].format(when=r['when']), '',
             L['status_lead'].format(n=len(s['live']), ok=s['cnt']('done'), part=s['cnt']('partly'), no=s['cnt']('not')), '']

    def block(title, items, fmt):
        if items:
            lines.extend([f'## {title}', ''] + [fmt(i) for i in items] + [''])
    block(L['waiting'], s['waiting'], lambda i: f"- **{i['id']}** {i.get('title')} — {i.get('waits') or i.get('next') or ''}")
    block(L['doing_h'], s['doing'], lambda i: f"- **{i['id']}** {i.get('title')} → {i.get('next') or ''}")
    block(L['council'], s['council'], lambda i: f"- **{i['id']}** {i.get('title')} — {council_line(i)}; {i['rounds'][-1].get('why') or ''}")
    block(L['next_h'], s['nxt'][:8], lambda i: f"- **{i['id']}** {i.get('title')} ({i.get('priority', '')}; {i.get('status')}; {i['_check']})")
    block(L['built_h'], s['built'], lambda i: f"- **{i['id']}** {i.get('title')}")
    block(L['lost_h'], r['orphans'], lambda o: f'- `{o}`')
    lines.append(L['ctrl_line_ok'] if r['control_ok'] else L['ctrl_line_bad'])
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- the hooks
def _stdin():
    # (bytes decoded as UTF-8: Claude Code sends UTF-8, but Python on Windows reads a pipe in the ANSI code page — the first test
    #  01.11 turned a Russian ask into mojibake, no ask cue matched and it silently never reached the inbox)
    try:
        raw = sys.stdin.buffer.read() if hasattr(sys.stdin, 'buffer') else sys.stdin.read().encode('utf-8')
        return json.loads(raw.decode('utf-8-sig', 'replace') or '{}')
    except ValueError:
        return {}


def _emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False))


def hook_inbox(inp):
    prompt = re.sub(r'<system-reminder[^>]*>[\s\S]*?</system-reminder[^>]*>', '', str(inp.get('prompt') or '')).strip()
    if not prompt or AGENT_NOTE.match(prompt) or '[Subagent hand-back]' in prompt[:400] or SHORT.match(prompt) or len(prompt) < 12:
        return
    p = prompt.lower()
    cues = ASK['ru'] + ASK['en'] + list(CFG.get('extra_ask_cues') or [])
    if not any(re.search(c, p) for c in cues):
        return
    rows = jsonl(INBOX)
    iid = 'I-' + str(len(rows) + 1).zfill(4)
    rows.append({'id': iid, 'ts': dt.datetime.now().isoformat(timespec='seconds'), 'text': prompt[:800], 'state': 'new'})
    write_jsonl(INBOX, rows)
    _emit({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': L['hook_inbox'].format(id=iid)}})


def hook_stop(inp):
    if inp.get('stop_hook_active'):
        return
    rows = jsonl(INBOX)
    fresh = [r for r in rows if r.get('state', 'new') == 'new' and not r.get('reminded')]
    if not fresh:
        return
    for r in fresh:
        r['reminded'] = dt.datetime.now().isoformat(timespec='seconds')
    write_jsonl(INBOX, rows)
    _emit({'decision': 'block', 'reason': L['hook_stop'].format(list='; '.join(f"{r['id']}: «{r['text'][:120]}»" for r in fresh))})


def hook_session(inp):
    text = brief(run())
    if inp.get('source') == 'compact':
        text = L['compact'] + '\n' + text
    _emit({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': text}})


# ---------------------------------------------------------------- the council
MARKS = {True: '✓', False: '✗', None: '?'}


def council_cmd(a):
    reg = jsonl(REG)
    it = next((i for i in reg if i.get('id') == a[1]), None) if len(a) > 1 else None
    if not it:
        print('no item', ' '.join(a[1:2])); return 1
    if a[0] == 'check':
        root = a[a.index('--root') + 1] if '--root' in a and a.index('--root') + 1 < len(a) else ROOT
        if not os.path.isdir(root):
            print(L['no_root'], root); return 1
        state, res, ctrl = probe_report(it, root)
        for p, v in res:
            print(f'  {MARKS[v]} {p}')
        print(f"{it['id']} @ {root}: {state} ({sum(v is True for _, v in res)}/{len(res)})" + ('' if ctrl else ' · ' + L['cmp_ctrl']))
        return 0 if ctrl else 2
    if a[0] == 'compare':
        cands = [x.partition('=') for x in a[2:] if '=' in x] or [('L', '=', '.')]
        print(L['cmp_head'].format(id=it['id']))
        scores = {}
        for label, _, root in cands:
            if not os.path.isdir(root):
                print(f'  {label}: {L["no_root"]} {root}'); continue
            state, res, ctrl = probe_report(it, root)
            green = sum(v is True for _, v in res)
            red = [p for p, v in res if v is False]
            if ctrl:
                scores[label] = green
            print(f'  {label} ({root}): {state} {green}/{len(res)}' + (f" · ✗ {'; '.join(red)}" if red else '')
                  + ('' if ctrl else ' · ' + L['cmp_ctrl']))
        if scores:
            top = max(scores.values())
            print(L['cmp_best'].format(labels=', '.join(k for k, v in scores.items() if v == top)))
        return 0
    rec = json.loads(a[2]) if len(a) > 2 else {}                # 'round'
    rounds = it.setdefault('rounds', [])
    rounds.append({'n': len(rounds) + 1, 'date': today(), **rec})
    it['touched'] = today()
    write_jsonl(REG, reg)
    n, stale, lead = council_state(it)
    cc = CFG['council']
    print(json.dumps(rounds[-1], ensure_ascii=False))
    print(council_line(it))
    why = L['why_stale'].format(s=stale) if stale >= cc['stop_after'] else (L['why_max'] if n >= cc['max_rounds'] else '')
    print(L['council_stop'].format(why=why, lead=lead, id=it['id']) if why
          else L['council_go'].format(n=n + 1, max=cc['max_rounds'], k=cc['candidates']))
    return 0


# ---------------------------------------------------------------- the commands
def main(a):
    if not os.path.exists(REG):
        io.open(REG, 'a', encoding='utf-8').close()
    if a[:1] == ['hook']:
        try:
            {'inbox': hook_inbox, 'stop': hook_stop, 'session': hook_session}[a[1]](_stdin())
        except Exception:                                   # (a hook must never break the session)
            pass
        return 0
    if a[:1] == ['add']:
        item = json.loads(a[1])
        reg = jsonl(REG)
        n = max([int(m.group(1)) for i in reg if (m := re.match(r'P-(\d+)$', str(i.get('id', ''))))] or [0]) + 1
        item = {'id': f'P-{n:03d}', 'date': today(), 'status': 'todo', 'priority': 'normal', **item, 'touched': today()}
        reg.append(item)
        write_jsonl(REG, reg)
        print(item['id'])
        return 0
    if a[:1] == ['set']:
        reg = jsonl(REG)
        it = next((i for i in reg if i.get('id') == a[1]), None)
        if not it:
            print('no item', a[1]); return 1
        pairs = [kv.partition('=') for kv in a[2:] if kv != '--force']
        if it.get('rounds') and '--force' not in a and any(k in ('probes', 'rubric') for k, _, _ in pairs):
            print(L['frozen'].format(id=it['id'], n=len(it['rounds']))); return 1
        for k, _, v in pairs:
            if k:
                it[k] = json.loads(v) if k in ('probes', 'rubric') else v
        it['touched'] = today()
        write_jsonl(REG, reg)
        print(json.dumps(it, ensure_ascii=False))
        return 0
    if a[:1] in (['take'], ['skip']):
        rows = jsonl(INBOX)
        it = next((i for i in rows if i.get('id') == a[1]), None)
        if not it:
            print('no inbox item', a[1]); return 1
        if a[0] == 'take':
            it.update(state='taken', promise=a[a.index('--as') + 1] if '--as' in a else '')
        else:
            it.update(state='skipped', why=a[a.index('--why') + 1] if '--why' in a else '')
        write_jsonl(INBOX, rows)
        print(json.dumps(it, ensure_ascii=False))
        return 0
    if a[:1] in (['check'], ['compare'], ['round']):
        return council_cmd(a)
    r = run()
    if a[:1] == ['json']:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    elif a[:1] == ['status']:
        io.open(STATUS, 'w', encoding='utf-8', newline='\n').write(status_md(r))
        print(STATUS)
        print(brief(r))
    elif a[:1] == ['selftest']:
        print('control:', 'ok — the fake probes failed' if r['control_ok'] else 'BROKEN')
        print(brief(r))
    else:
        print(brief(r))
    return 0 if r['control_ok'] else 2


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')            # (a Windows console prints Cyrillic only this way)
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
