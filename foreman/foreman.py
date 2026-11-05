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
  python .foreman/foreman.py hook prompt|stop|session       (Claude Code hooks; JSON on stdin, JSON on stdout; «inbox» = old name of «prompt»)
  python .foreman/foreman.py comment P-003 "text"                              a comment on an item (the board shows them)
LESSONS (2.0, module «lessons», recall.py) — the owner's corrections become RULES, found again before the next action:
  python .foreman/foreman.py recall <words> · rule add|accept|set|drop|list · recall --eval · ledger "…" · lesson "…" · cues --stats
COUNCIL — for hard items, a search with a kept leader (procedure: .claude/skills/foreman-council/SKILL.md):
  python .foreman/foreman.py check P-007 [--root ../cand-a]             the item's probes on any folder (e.g. a git worktree)
  python .foreman/foreman.py compare P-007 L=. A=../cand-a B=../cand-b  the same probes on every candidate, side by side
  python .foreman/foreman.py round P-007 '{"tried": ["L","A","B"], "winner": "A", "accepted": true, "why": "…"}'
  After the first logged round the item's probes and rubric are FROZEN (set refuses them without --force): the criteria are
  fixed before the search and never tailored to a candidate. «round» says when to stop: the BEST verified version wins, not the last.
Standard library only, Python 3.8+. Made by Claude (Anthropic) with a film producer, 2026-11-01 (2.0 — 2026-11-04) — see README.md."""
import contextlib
import datetime as dt
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
PROJECT = ROOT          # (ROOT is swapped while a candidate's folder is checked; PROJECT never is)
REG, INBOX, STATUS, CONFIG = (os.path.join(HERE, n) for n in ('promises.jsonl', 'inbox.jsonl', 'STATUS.md', 'config.json'))
OWNER = os.path.join(HERE, 'owner.jsonl')                   # (the owner's last 50 messages verbatim — what «accepted» is checked against, 2.1)
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
           'unk': ' · неизвестно {n} (проба не смогла выполниться: check P-…)', 'doing': 'В работе', 'next': 'Следующие по приоритету',
           'built': 'Пробы зелёные, а статус «todo/doing» — проверить и отметить «accepted»', 'red': 'КРАСНОЕ — «accepted», а пробы не сходятся',
           'stale': 'В работе без движения > {d} дн.', 'orphans': 'Сироты (файл, на который никто не ссылается)',
           'inbox': 'Входящие просьбы НЕ разобраны: {n} — {list} → foreman.py add {{…}} + take I-… --as P-…, или skip I-… --why «…»',
           'ctrl_ok': 'Контроль: ок (подставные пробы провалились)', 'ctrl_bad': 'Контроль СЛОМАН — подставная проба прошла, пробам не верить',
           'quote_need': 'Принять можно только словами владельца: --quote "<его слова дословно>".',
           'quote_bad': 'Таких слов владельца нет в журнале (.foreman/owner.jsonl, 14 дней). Повторите его слова дословно — или спросите его ещё раз, назвав номер.',
           'accept_mixed': 'Принять и одновременно поменять пробы / цитату / критерии нельзя — сначала правка, потом приёмка словом владельца.',
           'accept_lock': 'Реестр занят другим процессом — приёмка без замка не пишется; повторите.',
           'unsigned': 'Принято без слова владельца (нет записи accepted)',
           'accept_void': 'ПРОРАБ: приёмка {id} снята — после неё изменено: {what}. Пункт снова «в работе»; принять заново может только владелец.',
           'task_red': 'ПРОРАБ: задача называет {id}, но у пункта красные пробы: {probes}. Доделай — или скажи владельцу, почему закрываешь.', 'why': {'down': 'не отвечает', 'cmd-off': 'cmd: выключен (config allow_cmd)', 'no-files': 'шаблон не нашёл ни одного файла', 'bad-regex': 'сломанная регулярка', 'timeout': 'таймаут', 'no-access': 'нет доступа', 'unknown-kind': 'неизвестный вид пробы'},
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
           'no_root': 'нет такой папки:',
           'cmp_none': 'Ни один кандидат не прошёл ни одной пробы.',
           'board_kit': 'Прораб', 'ev_comment': 'комментарий «{t}»', 'ev_priority': 'приоритет {t}', 'ev_accept': 'принято', 'ev_triage': '→ завести пункт',
           'ev_skip': 'не задача', 'ev_rank': 'порядок в колонках изменён — учесть при выборе следующего', 'ev_more': 'и ещё {n}',
           'blocked': 'ждёт {ids}', 'events': 'ПРОРАБ·доска (владелец): {list}', 'commented': 'комментарий записан: {id}',
           'lessons_line': 'Уроки: правил {n} · ждут вашего «да» {p} · горячих {h} · стражей красных {g}',
           'cmp_nc': 'не сравнимо на кандидатах (сервер лидера или абсолютный путь): {probes}',
           'need_eq': 'кандидаты пишутся как МЕТКА=ПАПКА (L=. A=../проект-a); без «=»: {args}',
           'bad_round': 'раунд — JSON-объект: "tried": [метки] и "accepted": true/false (при true — ещё "winner"); можно @файл.json',
           'stopped': 'Консилиум по {id} уже остановлен ({n} раунд(ов)). Новый раунд — только с --force и по слову владельца.',
           'guarded': 'Поле «{k}» ведёт сам Прораб; менять — только с --force (и тогда rounds — JSON-список).',
           'bad_json': 'не JSON: {err}'},
    'en': {'head': 'FOREMAN ({when}; registry .foreman/promises.jsonl): {n} items · by probes done {ok} · partly {part} · not {no}{unk} · waiting for you {wait}',
           'unk': ' · unknown {n} (a probe could not run: check P-…)', 'doing': 'In progress', 'next': 'Next by priority',
           'built': 'Probes green but status «todo/doing» — verify and mark «accepted»', 'red': 'RED — «accepted» but the probes disagree',
           'stale': 'In progress with no move > {d} days', 'orphans': 'Orphans (a file nothing references)',
           'inbox': 'Unprocessed asks in the inbox: {n} — {list} → foreman.py add {{…}} + take I-… --as P-…, or skip I-… --why "…"',
           'ctrl_ok': 'Control: ok (the fake probes failed)', 'ctrl_bad': 'Control BROKEN — a fake probe passed, do not trust the probes',
           'quote_need': 'Only the owner\'s words accept: --quote "<his words verbatim>".',
           'quote_bad': 'No such words of the owner in the log (.foreman/owner.jsonl, 14 days). Repeat his words verbatim — or ask him again, naming the id.',
           'accept_mixed': 'Accepting while changing the probes / quote / rubric is refused — edit first, then the owner accepts.',
           'accept_lock': 'The registry is busy — an acceptance is never written without the lock; try again.',
           'unsigned': 'Accepted without the owner\'s word (no accepted record)',
           'accept_void': 'FOREMAN: the acceptance of {id} is void — changed after it: {what}. The item is back in work; only the owner can accept it again.',
           'task_red': 'FOREMAN: the task names {id}, but the item has red probes: {probes}. Finish it — or tell the owner why you close it.', 'why': {'down': 'does not answer', 'cmd-off': 'cmd: is off (config allow_cmd)', 'no-files': 'the pattern found no file', 'bad-regex': 'a broken regex', 'timeout': 'timeout', 'no-access': 'no access', 'unknown-kind': 'an unknown probe kind'},
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
           'no_root': 'no such folder:',
           'cmp_none': 'No candidate passes any probe.',
           'board_kit': 'Foreman', 'ev_comment': 'comment «{t}»', 'ev_priority': 'priority {t}', 'ev_accept': 'accepted', 'ev_triage': '→ file an item',
           'ev_skip': 'not a task', 'ev_rank': 'column order changed — use it to pick the next', 'ev_more': 'and {n} more',
           'blocked': 'waits for {ids}', 'events': 'FOREMAN·board (owner): {list}', 'commented': 'comment saved: {id}',
           'lessons_line': 'Lessons: {n} rules · waiting for your «yes» {p} · hot {h} · red guards {g}',
           'cmp_nc': 'not comparable on candidates (the leader\'s server or an absolute path): {probes}',
           'need_eq': 'candidates are LABEL=FOLDER (L=. A=../project-a); without «=»: {args}',
           'bad_round': 'a round is a JSON object: "tried": [labels] and "accepted": true/false (with true also "winner"); @file.json works',
           'stopped': 'The council on {id} has stopped ({n} round(s)). A new round only with --force and on the owner\'s word.',
           'guarded': 'Foreman keeps the field «{k}» itself; change it only with --force (and then rounds is a JSON list).',
           'bad_json': 'not JSON: {err}'},
}


def config():
    council = {'candidates': 2, 'max_rounds': 3, 'stop_after': 2}
    c = {'lang': 'ru', 'stale_days': 3, 'allow_cmd': False, 'orphans': {'candidates': [], 'corpus': []}, 'extra_ask_cues': []}
    try:
        c.update(json.load(io.open(CONFIG, encoding='utf-8')))
    except (OSError, ValueError):
        pass
    c['council'] = {**council, **(c.get('council') or {})}
    # (2.0: modules switch whole parts on/off — an «off» module adds nothing to any hook; budgets are hard caps in characters)
    c['modules'] = {'promises': True, 'lessons': True, 'board': False, **(c.get('modules') or {})}
    c['budget'] = {'prompt_chars': 1200, 'session_chars': 2000, 'recall_hits': 3, 'recall_chars': 700, 'hot_rows': 5, **(c.get('budget') or {})}
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
    tmp = f'{p}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp'      # (a unique temp name: two writers never share one — council 04.11)
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, p)


@contextlib.contextmanager
def locked(wait=2.0):
    """one writer at a time — the CLI, the hooks, the board (2.1): .foreman/.lock; a lock older than 30 s is stale. After `wait`
    seconds it goes on rather than hang a hook, and it never removes a lock it does not hold"""
    p, t0, held = os.path.join(HERE, '.lock'), time.time(), False
    while True:
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd); held = True
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(p) > 30:
                    os.remove(p); continue
            except OSError:
                pass
            if time.time() - t0 > wait:
                break
            time.sleep(0.05)
        except OSError:
            break
    global LOCK_HELD
    LOCK_HELD = held
    try:
        yield held
    finally:
        LOCK_HELD = False
        if held:
            try:
                os.remove(p)
            except OSError:
                pass


_lessons = None
LOCK_HELD = False


def lessons():
    """the lessons module (recall.py), or None when it is off or not installed"""
    global _lessons
    if _lessons is None:
        _lessons = False
        if CFG['modules'].get('lessons') and os.path.exists(os.path.join(HERE, 'recall.py')):
            sys.path.insert(0, HERE)
            import recall
            recall.setup(CFG, CFG.get('lang', 'ru'))
            _lessons = recall
    return _lessons or None


def today():
    return dt.date.today().isoformat()


def path_of(p):
    return os.path.join(ROOT, p)


def set_root(path):
    global ROOT
    ROOT = os.path.abspath(path)


def cand_root(p):
    """a candidate's folder, relative to the PROJECT (not to wherever the command was typed); «.» is the project itself"""
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(PROJECT, p))


def arg_json(s):
    """a JSON argument, or @file.json (PowerShell 5.1 strips the inner quotes of a JSON argument)"""
    if s.startswith('@') and os.path.isfile(s[1:]):
        s = read(s[1:])
    return json.loads(s)


def rounds_of(item):
    """the council's rounds, whatever is stored (a hand-edited string must never break the brief or the hooks)"""
    r = item.get('rounds')
    return [x for x in r if isinstance(x, dict)] if isinstance(r, list) else []


_server = {}


WHY = {}                                                    # probe → why it is «unknown» (2.1: shown by check and the brief)


def _unknown(p, why):
    WHY[p] = why
    return None


def probe(p):
    kind, _, rest = p.partition(':')
    WHY.pop(p, None)
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
                return _unknown(p, 'down')                  # (down → «unknown», never «not built»)
        if kind == 'cmd':
            if not CFG.get('allow_cmd'):
                return _unknown(p, 'cmd-off')
            return subprocess.run(rest, shell=True, cwd=ROOT, capture_output=True, timeout=20).returncode == 0
        if kind == 'fresh':
            # fresh:<result>:<glob> — the result (a test report, a render, a build) is newer than every file of the glob: a test
            # counts only if it ran AFTER the last edit (AgentGate / claim-check «evidence freshness», 2.1)
            target, _, pattern = rest.partition(':')
            if not os.path.exists(path_of(target)):
                return False
            srcs = [f for f in glob.glob(path_of(pattern), recursive=True)
                    if os.path.isfile(f) and os.path.normcase(os.path.abspath(f)) != os.path.normcase(os.path.abspath(path_of(target)))]
            if not srcs:
                return _unknown(p, 'no-files')
            return os.path.getmtime(path_of(target)) >= max(os.path.getmtime(f) for f in srcs)
    except re.error:
        return _unknown(p, 'bad-regex')
    except subprocess.TimeoutExpired:
        return _unknown(p, 'timeout')
    except OSError:
        return _unknown(p, 'no-access')
    return _unknown(p, 'unknown-kind')


def check_item(item):
    res = [(p, probe(p)) for p in item.get('probes', [])]
    return state_of([v for _, v in res]), res


def state_of(vals):
    if not vals:
        state = 'no-probes'
    elif all(v is True for v in vals):
        state = 'done'
    elif any(v is False for v in vals):                     # (a real «no» outranks an «unknown»: 2.0 hid a red behind a grey)
        state = 'partly' if any(v is True for v in vals) else 'not'
    else:
        state = 'unchecked'                                 # (green + «unknown» is not «done»: 2.0 called it «partly»)
    return state


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
    """the item's probes and the control, run against another folder (a candidate's copy or git worktree). A probe that does
    not depend on the folder — `get:` asks the LEADER's server, an absolute path points at one place — is «not comparable» (?)
    on a candidate: it would pass for an empty folder (review 04.11)"""
    saved, other = ROOT, os.path.normcase(os.path.abspath(root)) != os.path.normcase(PROJECT)
    set_root(root)
    res, nc = [], []
    try:
        for p in item.get('probes', []):
            kind, _, rest = p.partition(':')
            target = rest.partition(':')[0] if kind in ('grep', 'nogrep', 'doc') else rest
            if other and (kind == 'get' or os.path.isabs(target)):
                res.append((p, None)); nc.append(p)
            else:
                res.append((p, probe(p)))
        ctrl = all(check_item(c)[0] == 'not' for c in CONTROLS)
    finally:
        set_root(saved)
    return state_of([v for _, v in res]), res, ctrl, nc


def council_state(item):
    rounds = rounds_of(item)
    stale = 0
    for r in reversed(rounds):
        if r.get('accepted') is True:
            break
        stale += 1
    lead = next((r.get('winner') for r in reversed(rounds) if r.get('accepted') is True and r.get('winner')), L['lead_initial'])
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
    rank = it.get('rank')
    return (rank if isinstance(rank, int) else 10 ** 6, PRIO.get(it.get('priority'), 1), it.get('date') or '', it.get('id'))


def blockers(it, reg):
    ids = it.get('blocked_by') or []
    ids = [ids] if isinstance(ids, str) else ids
    return [b for b in ids if any(x.get('id') == b and x.get('status') in OPEN for x in reg)]


def summary(r):
    live = [i for i in r['registry'] if i.get('status') != 'dropped']
    return dict(live=live, cnt=lambda s: sum(i['_check'] == s for i in live),
                doing=sorted([i for i in live if i.get('status') == 'doing'], key=key),
                waiting=sorted([i for i in live if i.get('status') == 'waiting'], key=key),
                nxt=sorted([i for i in live if i.get('status') in ('todo', 'parked') and i['_check'] != 'done' and not blockers(i, live)], key=key),
                red=[i for i in live if i.get('status') == 'accepted' and i['_check'] in ('not', 'partly')],
                unsigned=[i for i in live if i.get('status') == 'accepted' and not i.get('accepted')],
                built=[i for i in live if i.get('status') in ('todo', 'doing') and i['_check'] == 'done'],
                stale=[i for i in live if i.get('status') == 'doing' and (age(i) or 0) > CFG.get('stale_days', 3)],
                council=[i for i in live if rounds_of(i) and i.get('status') in OPEN and i.get('council') != 'stopped'])


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
    if s['unsigned']:
        out.append(L['unsigned'] + ': ' + ', '.join(i['id'] for i in s['unsigned'][:8]))
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
    block(L['council'], s['council'], lambda i: f"- **{i['id']}** {i.get('title')} — {council_line(i)}; {rounds_of(i)[-1].get('why') or ''}")
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


EVENTS = os.path.join(HERE, 'events.jsonl')


def append_event(row):
    with io.open(EVENTS, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'foreman', **row}, ensure_ascii=False) + '\n')


HOOK_LOG_KEEP = 2000                                         # (hook_out rows kept; the rest of events.jsonl is never pruned)


def log_hook(hook, text, **extra):
    """2.3 (deepseek-harness AGENTS.md: «Model-visible means logged»): every line a hook puts in front of Claude — or a stop it makes
    — becomes a durable event, so «why did Claude do that» is answered from the log, not from memory; `foreman.py hooklog` reads it.
    An ordinary message (no output) costs nothing. Off with config.json `"hook_log": false`."""
    if not text or CFG.get('hook_log') is False:
        return
    try:
        append_event({'kind': 'hook_out', 'hook': hook, 'chars': len(text), 'text': text[:4000], **extra})
        if os.path.getsize(EVENTS) > 3_000_000:              # (only the oldest hook_out rows go; the owner's board moves stay)
            rows = jsonl(EVENTS)
            hk = [n for n, r in enumerate(rows) if r.get('kind') == 'hook_out']
            drop = set(hk[:-HOOK_LOG_KEEP]) if len(hk) > HOOK_LOG_KEEP else set()
            if drop:
                write_jsonl(EVENTS, [r for n, r in enumerate(rows) if n not in drop])
    except OSError:
        pass


def owner_events():
    """the owner's unseen moves on the board (2.1) → one line, ≤ 300 chars, grouped by item, statuses in the registry's words;
    marked seen in the same call (DESIGN_board §3)"""
    rows = jsonl(EVENTS)
    new = [e for e in rows if e.get('by') in ('owner', 'owner-board') and not e.get('seen')]
    if not new:
        return ''
    for e in new:
        e['seen'] = True
    write_jsonl(EVENTS, rows)
    groups, order, ranks = {}, [], 0
    for e in new:
        if e.get('kind') == 'rank':
            ranks += 1
            continue
        k = (e.get('reg', 'kit'), e.get('id'))
        if k not in groups:
            groups[k] = []
            order.append(k)
        kind = e.get('kind')
        groups[k].append(f"→ {e['to']}" if kind == 'move' else L['ev_comment'].format(t=str(e.get('text', ''))[:60]) if kind == 'comment'
                         else L['ev_priority'].format(t=e.get('to', '')) if kind == 'priority' else L['ev_accept'] if kind == 'accept'
                         else L['ev_triage'] if kind == 'triage' else L['ev_skip'] if kind == 'skip'
                         else f"→ {e.get('to', '')}" if kind == 'rule' else str(kind))
    parts = [f"{'' if reg in ('kit', 'rules') else reg + ' '}{pid} " + ', '.join(dict.fromkeys(v)) for (reg, pid), v in
             ((k, groups[k]) for k in order)]
    if ranks:
        parts.append(L['ev_rank'])
    out, used = [], 0
    for n, p in enumerate(parts):
        if used + len(p) > 240:
            out.append(L['ev_more'].format(n=len(parts) - n))
            break
        out.append(p)
        used += len(p) + 2
    return L['events'].format(list='; '.join(out))[:300]


def fit(parts, budget):
    """the sections in priority order; the last ones are cut first; the whole ≤ budget characters"""
    out = []
    for p in parts:
        if not p:
            continue
        room = budget - sum(len(x) + 1 for x in out)
        if room < 80:
            break
        out.append(p if len(p) <= room else p[:room - 1] + '…')
    return '\n'.join(out)


def hook_prompt(inp):
    """UserPromptSubmit: an ask → the inbox; a correction → the lesson protocol; the rules that fit the message; the owner's board
    moves. An ordinary message costs 0 characters (dsh-superagent: take as little attention as possible)"""
    prompt = re.sub(r'<system-reminder[^>]*>[\s\S]*?</system-reminder[^>]*>', '', str(inp.get('prompt') or '')).strip()
    if not prompt or AGENT_NOTE.match(prompt) or '[Subagent hand-back]' in prompt[:400]:
        return
    owner_log(prompt, inp)                                  # (a short «да» counts here: it may be the yes to an «accept?»)
    if SHORT.match(prompt) or len(prompt) < 12:
        return
    events = owner_events() if CFG['modules'].get('board') else ''
    note = ''
    if CFG['modules'].get('promises'):
        p = prompt.lower()
        cues = ASK['ru'] + ASK['en'] + list(CFG.get('extra_ask_cues') or [])
        if any(re.search(c, p) for c in cues):
            rows = jsonl(INBOX)
            iid = 'I-' + str(len(rows) + 1).zfill(4)
            # (the WHOLE ask: 1.1 cut it at 800 characters and the quote stopped being verbatim — council 04.11)
            rows.append({'id': iid, 'ts': dt.datetime.now().isoformat(timespec='seconds'), 'text': prompt[:20000], 'state': 'new'})
            write_jsonl(INBOX, rows)
            note = L['hook_inbox'].format(id=iid)[:320]
    reflect = pk = ''
    R = lessons()
    if R:
        cls = R.classify(prompt)
        R.log_cue(cls)
        reflect = R.reflector(cls)[:450]
        if len(cls['text']) >= 25:
            pk = R.pack(cls['text'][:600])
    text = fit([events, note, reflect, pk], CFG['budget']['prompt_chars'])
    if text:
        log_hook('prompt', text, head=prompt[:120])
        _emit({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': text}})


hook_inbox = hook_prompt                                    # (1.1 settings call «hook inbox» — still works)


def owner_log(text, inp=None):
    """the owner's message verbatim + `prev`, the start of the assistant reply it answers (a «да» to «принять R-003?» binds to R-003);
    the last 500 messages (Fable's review 04.11, 1.1 / 1.8)"""
    inp = inp or {}
    rows = jsonl(OWNER)[-499:]
    rows.append({'ts': dt.datetime.now().isoformat(timespec='seconds'), 'session_id': str(inp.get('session_id') or ''),
                 'text': text[:20000], 'prev': _prev_reply(inp.get('transcript_path'))[:300], 'via': 'hook'})
    write_jsonl(OWNER, rows)


def _prev_reply(path, tail=1024 * 1024):
    """the text of the last assistant message in the transcript's tail ('' when there is none)"""
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            f.seek(max(0, size - tail))
            lines = f.read().decode('utf-8', 'replace').splitlines()
    except (OSError, TypeError):
        return ''
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('type') == 'assistant':
            c = (e.get('message') or {}).get('content')
            text = c if isinstance(c, str) else ' '.join(b.get('text') or '' for b in c or [] if isinstance(b, dict) and b.get('type') == 'text')
            if text.strip():
                return text.strip()
    return ''


def _norm(s):
    return re.sub(r'\s+', ' ', re.sub('[«»"\'“”„]', '', str(s).lower().replace('ё', 'е'))).strip()


def owner_says(ids, quote):
    """→ (True, the message's ts) when the owner said it: the quote (≥ 12 chars, normalised) is a verbatim part of one of his
    messages of the last `accept_days` days, or a short answer («да», «принимаю») to a reply that named every id; several ids at once
    must each be named (in that reply or in his message). A paraphrase is refused — that is the point (Fable's review 1.2)"""
    q = _norm(quote)
    if not q:
        return False, L['quote_need']
    since = (dt.datetime.now() - dt.timedelta(days=int(CFG.get('accept_days', 14)))).isoformat(timespec='seconds')
    named = lambda row: all(re.search(r'\b' + re.escape(i) + r'\b', f"{row.get('prev', '')} {row.get('text', '')}") for i in ids)
    for row in reversed(jsonl(OWNER)):
        if str(row.get('ts', '')) < since:
            break
        t = _norm(row.get('text', ''))
        if len(q) >= 12 and q in t and (len(ids) == 1 or named(row)):
            return True, row.get('ts')
        if len(q) < 12 and q == t and named(row):           # (a short «да» only as the answer to a reply that named the id)
            return True, row.get('ts')
    return False, L['quote_bad']


def hook_task(inp):
    """TaskCompleted (Claude Code's own task list, wherever Claude uses its task tools): a task that names P-… closes
    only when that item has no red probe; exit 2 + the reason on stderr keeps it open (Claude Code hooks docs, checked 04.11)"""
    if not CFG['modules'].get('promises'):
        return 0
    ids = sorted(set(re.findall(r'\bP-\d+\b', f"{inp.get('task_subject') or ''} {inp.get('task_description') or ''}")))
    reg = {i.get('id'): i for i in jsonl(REG)}
    bad = []
    for pid in ids:
        if pid in reg:
            state, res = check_item(reg[pid])
            if state in ('not', 'partly'):
                bad.append(L['task_red'].format(id=pid, probes='; '.join(p for p, v in res if v is False)[:300]))
    if bad:
        log_hook('task', '\n'.join(bad)[:1500], ids=ids)
        sys.stderr.write('\n'.join(bad)[:1500] + '\n')
        return 2
    return 0


def hook_stop(inp):
    """Stop: ONE block at most — the untriaged asks, a correction that left no record, a guard that just turned red"""
    if inp.get('stop_hook_active'):
        return
    reasons = []
    if CFG['modules'].get('promises'):
        rows = jsonl(INBOX)
        fresh = [r for r in rows if r.get('state', 'new') == 'new' and not r.get('reminded')]
        if fresh:
            for r in fresh:
                r['reminded'] = dt.datetime.now().isoformat(timespec='seconds')
            write_jsonl(INBOX, rows)
            reasons.append(L['hook_stop'].format(list='; '.join(f"{r.get('id', '?')}: «{str(r.get('text', ''))[:120]}»" for r in fresh)))
    R = lessons()
    if R:
        last = str(inp.get('last_assistant_message') or '')
        reasons.append(R.lesson_gate(inp.get('transcript_path'), last))
        reasons.append(R.edit_gate(inp.get('transcript_path'), last))
        newly, _ = R.guards(probe)
        reasons.append(R.guard_reason(newly))
    text = fit(reasons, 1200)
    if text:
        log_hook('stop', text)
        _emit({'decision': 'block', 'reason': text})


def lessons_lines():
    R = lessons()
    if not R:
        return []
    rules = [r for r in R.jsonl(R.RULES) if r.get('status') not in ('dropped', 'replaced')]
    if not rules:
        return []
    _, red = R.guards(probe, log=False)
    out = [L['lessons_line'].format(n=len(rules), p=len(R.proposed()), h=len(R.hot_lines()), g=len(red))]
    hot = R.hot_lines()
    if hot:
        out.append(R.LX['hot'] + ': ' + ' · '.join(hot))
    if red:
        out.append(R.LX['guards_red'] + ': ' + ', '.join(f"{r['id']} {r['guard']}" for r in red))
    old = R.stale()
    if old:
        out.append(R.LX['stale'].format(days=R.CFG['lessons'].get('confirm_days', 60)) + ': ' + ', '.join(r['id'] for r in old[:8]))
    dfr = R.deferred()
    if dfr:
        week = (dt.datetime.now() - dt.timedelta(days=7)).isoformat(timespec='seconds')
        out.append(R.LX['deferred_line'].format(n=len(dfr), old=sum(str(e.get('ts', '')) < week for e in dfr)))
    uns = R.unsigned_rules()
    if uns:
        out.append(L['unsigned'] + ': ' + ', '.join(r['id'] for r in uns[:8]))
    return out


def hook_session(inp):
    text = brief(run()) if CFG['modules'].get('promises') else ''   # (promises off — e.g. a project with its own registry: no empty brief)
    if inp.get('source') == 'compact' and text:
        text = L['compact'] + '\n' + text
    text = fit([text[:1200]] + lessons_lines() + [owner_events() if CFG['modules'].get('board') else ''], CFG['budget']['session_chars'])
    if text:
        log_hook('session', text, source=inp.get('source'))
        _emit({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': text}})


# ---------------------------------------------------------------- the council
MARKS = {True: '✓', False: '✗', None: '?'}


def council_cmd(a):
    reg = jsonl(REG)
    it = next((i for i in reg if i.get('id') == a[1]), None) if len(a) > 1 else None
    if not it:
        print('no item', ' '.join(a[1:2])); return 1
    if a[0] == 'check':
        if '--root' in a and a.index('--root') + 1 >= len(a):
            print(L['no_root'], '--root ?'); return 1
        root = cand_root(a[a.index('--root') + 1]) if '--root' in a else PROJECT
        if not os.path.isdir(root):
            print(L['no_root'], root); return 1
        state, res, ctrl, nc = probe_report(it, root)
        for p, v in res:
            print(f'  {MARKS[v]} {p}' + (f"  ({L['why'].get(WHY[p], WHY[p])})" if v is None and WHY.get(p) else ''))
        if nc:
            print('  ' + L['cmp_nc'].format(probes='; '.join(nc)))
        print(f"{it['id']} @ {root}: {state} ({sum(v is True for _, v in res)}/{len(res)})" + ('' if ctrl else ' · ' + L['cmp_ctrl']))
        return 2 if not ctrl else 0 if state == 'done' else 1
    if a[0] == 'compare':
        loose = [x for x in a[2:] if '=' not in x]
        if loose:
            print(L['need_eq'].format(args=' '.join(loose))); return 1
        cands = [x.partition('=') for x in a[2:]] or [('L', '=', '.')]
        print(L['cmp_head'].format(id=it['id']))
        scores, missing, nc_all = {}, False, set()
        for label, _, raw in cands:
            root = cand_root(raw)
            if not os.path.isdir(root):
                print(f'  {label}: {L["no_root"]} {root}'); missing = True; continue
            state, res, ctrl, nc = probe_report(it, root)
            nc_all.update(nc)
            green = sum(v is True for _, v in res)
            red = [p for p, v in res if v is False]
            if ctrl:
                scores[label] = green
            print(f'  {label} ({raw}): {state} {green}/{len(res)}' + (f" · ✗ {'; '.join(red)}" if red else '')
                  + ('' if ctrl else ' · ' + L['cmp_ctrl']))
        if nc_all:
            print('  ' + L['cmp_nc'].format(probes='; '.join(sorted(nc_all))))
        top = max(scores.values()) if scores else 0
        print(L['cmp_best'].format(labels=', '.join(k for k, v in scores.items() if v == top)) if top > 0 else L['cmp_none'])
        return 1 if missing else 0
    try:                                                         # 'round'
        rec = arg_json(a[2]) if len(a) > 2 else None
    except ValueError as e:
        print(L['bad_json'].format(err=e)); return 1
    if (not isinstance(rec, dict) or not isinstance(rec.get('tried'), list) or not rec['tried']
            or not isinstance(rec.get('accepted'), bool) or (rec['accepted'] and not rec.get('winner'))):
        print(L['bad_round']); return 1
    if it.get('council') == 'stopped' and '--force' not in a:
        print(L['stopped'].format(id=it['id'], n=len(rounds_of(it)))); return 1
    rounds = rounds_of(it)
    it['rounds'] = rounds + [{**rec, 'n': len(rounds) + 1, 'date': today()}]   # (the record cannot rewrite its own n / date)
    it['touched'] = today()
    n, stale, lead = council_state(it)
    cc = CFG['council']
    why = L['why_stale'].format(s=stale) if stale >= cc['stop_after'] else (L['why_max'] if n >= cc['max_rounds'] else '')
    if why:
        it['council'] = 'stopped'
    elif it.get('council') == 'stopped':
        it.pop('council')
    write_jsonl(REG, reg)
    print(json.dumps(it['rounds'][-1], ensure_ascii=False))
    print(council_line(it))
    print(L['council_stop'].format(why=why, lead=lead, id=it['id']) if why
          else L['council_go'].format(n=n + 1, max=cc['max_rounds'], k=cc['candidates']))
    return 0


# ---------------------------------------------------------------- the commands
def main(a):
    if not os.path.exists(REG):
        io.open(REG, 'a', encoding='utf-8').close()
    if a[:1] == ['panel']:                                 # (the model panel, 2.2 — panel.py next to this file)
        sys.path.insert(0, HERE)
        import panel
        return panel.main(sys.modules[__name__], a[1:])
    if a[:1] == ['board']:                                 # (the owner's task board, 2.1 — board.py next to this file)
        sys.path.insert(0, HERE)
        import board
        return board.serve(sys.modules[__name__], a[1:])
    if a[:1] == ['hook']:
        try:
            with locked():
                code = {'prompt': hook_prompt, 'inbox': hook_prompt, 'stop': hook_stop, 'session': hook_session,
                        'task': hook_task}[a[1]](_stdin())
            return 2 if code == 2 else 0                    # (only TaskCompleted blocks by an exit code)
        except Exception:                                   # (a hook must never break the session)
            pass
        return 0
    if a[:1] in (['recall'], ['rule'], ['ledger'], ['lesson'], ['cues']):
        R = lessons()
        if not R:
            print('the lessons module is off (config.json → modules.lessons) or recall.py is missing'); return 1
        if a[0] == 'recall':
            return R.recall_cmd(a[1:])
        if a[0] == 'lesson':
            return R.lesson_cmd(a[1:])
        if a[0] == 'cues':
            return R.cues_cmd(a[1:])
        with locked():
            if a[0] == 'ledger':
                R.ledger_add(' '.join(a[1:])); print(R.LX['ledger_ok'].format(line=' '.join(a[1:]))); return 0
            return R.rule_cmd(a[1:], quote_check=owner_says if LOCK_HELD else None)
    if a[:1] == ['comment'] and len(a) > 2:
        with locked():
            reg = jsonl(REG)
            it = next((i for i in reg if i.get('id') == a[1]), None)
            if not it:
                print('no item', a[1]); return 1
            it.setdefault('comments', []).append({'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'agent', 'text': ' '.join(a[2:])})
            it['touched'] = today()
            write_jsonl(REG, reg)
        print(L['commented'].format(id=a[1])); return 0
    if a[:1] == ['hooklog']:
        return hooklog_cmd(a[1:])
    if a[:1] == ['replay']:
        return replay_cmd(a[1:])
    if a[:1] in (['add'], ['set'], ['take'], ['skip'], ['round']):
        with locked():
            return commands(a)
    return commands(a)


def hooklog_cmd(a):
    """foreman.py hooklog [--n 20] [--hook prompt|stop|session|task] [--grep TEXT] — what the hooks showed Claude, newest last (2.3)"""
    n = int(a[a.index('--n') + 1]) if '--n' in a else 20
    hook = a[a.index('--hook') + 1] if '--hook' in a else None
    pat = a[a.index('--grep') + 1].lower() if '--grep' in a else None
    rows = [r for r in jsonl(EVENTS) if r.get('kind') == 'hook_out' and (not hook or r.get('hook') == hook)
            and (not pat or pat in str(r.get('text', '')).lower() or pat in str(r.get('head', '')).lower())]
    for r in rows[-n:]:
        head = f" <- «{str(r['head'])[:70]}»" if r.get('head') else ''
        print(f"{r.get('ts')} {r.get('hook')} {r.get('chars')} ch{head}")
        print('  ' + str(r.get('text', '')).replace('\n', '\n  ')[:900])
    print(f'{len(rows)} hook outputs logged' + (f' (showing the last {min(n, len(rows))})' if rows else ''))
    return 0


REPLAY = os.path.join(HERE, 'replay_baseline.json')


def replay_classify(text):
    """the SAME detectors the prompt hook runs, with no side effects (no inbox row, no cue event, no owner log)"""
    t = re.sub(r'<system-reminder[^>]*>[\s\S]*?</system-reminder[^>]*>', '', str(text or '')).strip()
    if not t or AGENT_NOTE.match(t) or SHORT.match(t) or len(t) < 12:
        return None
    low = t.lower()
    cues = ASK['ru'] + ASK['en'] + list(CFG.get('extra_ask_cues') or [])
    ask = next((c for c in cues if re.search(c, low)), None)
    R = lessons()
    cls = R.classify(t) if R else {'correction': None, 'teaching': None}
    return {'ask': ask, 'correction': cls.get('correction'), 'teaching': cls.get('teaching')}


def replay_cmd(a):
    """foreman.py replay [--save] [--show] — 2.3 (deepseek-harness docs/testing.md: a recorded session «serves as the expected
    persisted result»): the owner's recorded messages (owner.jsonl) through the prompt hook's detectors, compared with the saved
    snapshot (replay_baseline.json). A cue or lexicon edit that changes how a PAST message is read shows up here before it misleads a
    session: «was a correction, now is not» = a lost lesson; «was nothing, now an ask» = a new false alarm. --save writes the snapshot
    (after you accept the changes); exit 1 when something changed against it."""
    import hashlib
    now = {}
    for m in jsonl(OWNER):
        c = replay_classify(m.get('text'))
        if c is None:
            continue
        k = hashlib.sha1(str(m.get('text')).encode('utf-8')).hexdigest()[:12]
        now[k] = dict(c, ts=m.get('ts'), head=str(m.get('text'))[:90].replace('\n', ' '))
    count = lambda d, f: sum(1 for v in d.values() if v.get(f))
    print(f"{len(now)} owner messages replayed: asks {count(now, 'ask')}, corrections {count(now, 'correction')}, "
          f"teachings {count(now, 'teaching')}")
    if '--show' in a:
        for v in now.values():
            tags = ', '.join(f'{f}: {v[f]}' for f in ('ask', 'correction', 'teaching') if v.get(f))
            print(f"  {v['ts']} «{v['head']}» — {tags or '-'}")
    if '--save' in a:
        json.dump(now, io.open(REPLAY, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('snapshot saved:', REPLAY)
        return 0
    if not os.path.exists(REPLAY):
        print('no snapshot yet — run `foreman.py replay --save` once the classification looks right')
        return 0
    base = json.load(io.open(REPLAY, encoding='utf-8'))
    changed = 0
    for k, v in now.items():
        b = base.get(k)
        if not b:
            continue                                         # (a message newer than the snapshot: nothing to compare)
        diffs = [f"{f}: {b.get(f) or '-'} -> {v.get(f) or '-'}" for f in ('ask', 'correction', 'teaching') if bool(b.get(f)) != bool(v.get(f))]
        if diffs:
            changed += 1
            print(f"  CHANGED {v['ts']} «{v['head']}»: " + '; '.join(diffs))
    new = sum(1 for k in now if k not in base)
    print(f'{changed} changed against the snapshot, {new} new message(s) not in it' + (' — `--save` to extend it' if new else ''))
    return 1 if changed else 0


def commands(a):
    if a[:1] == ['add']:
        try:
            item = arg_json(a[1])
        except (ValueError, IndexError) as e:
            print(L['bad_json'].format(err=e)); return 1
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
        quote = a[a.index('--quote') + 1] if '--quote' in a and a.index('--quote') + 1 < len(a) else None
        rest = [x for i, x in enumerate(a[2:], 2) if x not in ('--force', '--quote') and not (i > 2 and a[i - 1] == '--quote')]
        pairs = [kv.partition('=') for kv in rest]
        force = '--force' in a
        wants = dict((k, v) for k, _, v in pairs)
        if wants.get('status') == 'accepted' and it.get('status') != 'accepted':
            if any(k in wants for k in ('probes', 'quote', 'rubric')):
                print(L['accept_mixed']); return 1             # (one command must not swap the probes and accept them)
            if not LOCK_HELD:
                print(L['accept_lock']); return 1
            ok, ts = owner_says([it['id']], quote or '')
            if not ok:
                print(ts); return 1
            it['accepted'] = {'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'owner-quote', 'quote': quote, 'msg_ts': ts}
        if rounds_of(it) and not force and any(k in ('probes', 'rubric') for k, _, _ in pairs):
            print(L['frozen'].format(id=it['id'], n=len(rounds_of(it)))); return 1
        for k, _, _ in pairs:
            if k in ('id', 'rounds', 'council') and not force:      # (review 04.11: «set rounds=…» unfroze and broke the brief)
                print(L['guarded'].format(k=k)); return 1
        was = {k: it.get(k) for k in ('status', 'quote', 'probes', 'rubric')}
        try:
            for k, _, v in pairs:
                if k:
                    it[k] = arg_json(v) if k in ('probes', 'rubric', 'rounds', 'rank', 'comments', 'blocked_by', 'tags') else v
        except ValueError as e:
            print(L['bad_json'].format(err=e)); return 1
        changed = [k for k in ('quote', 'probes', 'rubric') if it.get(k) != was[k]]
        if was['status'] == 'accepted' and changed and it.get('status') == 'accepted':
            # (an acceptance covers THAT quote with THOSE probes — VisionForge: edited after it, the item is back in work, 2.1)
            it['status'] = 'doing'
            it.pop('accepted', None)
            it['accept_void'] = f"{today()}: {', '.join(changed)}"
            append_event({'kind': 'unaccept', 'id': it['id'], 'changed': changed})
            print(L['accept_void'].format(id=it['id'], what=', '.join(changed)))
        if 'rounds' in it and not isinstance(it['rounds'], list):
            print(L['guarded'].format(k='rounds')); return 1
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
        R = lessons()
        if R:
            R.render_rules_md()
            print('\n'.join(lessons_lines()))
    elif a[:1] == ['selftest']:
        print('control:', 'ok — the fake probes failed' if r['control_ok'] else 'BROKEN')
        print(brief(r))
    else:
        print(brief(r))
    return 0 if r['control_ok'] else 2


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')            # (a Windows console prints Cyrillic only this way)
        sys.stderr.reconfigure(encoding='utf-8')            # (TaskCompleted's reason goes to stderr: cp1251 there reached Claude garbled)
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
