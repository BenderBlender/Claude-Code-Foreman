"""act.py — Foreman 2.5: knowledge at the moment of ACTION (the case of 09.11).

Why: 2.0–2.4 surface the rules and the owner's materials when the OWNER WRITES. The errors of 09.11 happened inside ONE long
autonomous turn (three hours, hundreds of tool calls, no new message → no reminder): the owner's «first study …» links were read after
the work, a rule hot for weeks («never judge by one view») was broken again, a tool's documented click mode was forgotten, the same
script ran seven times in a quarter of an hour. So the knowledge has to come on the ACTION (PreToolUse), each piece once and with a
visible exit — others' limits are advice, not walls (the owner, 31.10). Fable's review of the plan (09.11) set the defaults: notes on,
refusals only where the owner said «first» or a project switched them on, the hot rules only, and a budget of time per call.

  A  materials — a sentence of the owner's with «study / read / look at» AND a link / a path / an image / a web topic → M-… in
     .foreman/materials.jsonl. «first / before» in that sentence → the first WORKING action before the study is refused once.
     Studied = opened (the transcript shows a Read / fetch / clone of each source) AND noted (the notes file names every source and
     says what was taken and what was not read): `foreman.py material read M-… --study <notes>`; or `material skip M-… --why "…"`.
  B  recall by the action (module act_recall, OFF by default since the council of 11.11) — a program run, an agent's brief or the
     edit of a checking tool is searched against the HOT rules only (rules.jsonl level ≥ 2 + the rows of act.hot_books); a rule's
     trigger is its situation WITHOUT its history plus its Keys (the row's own Keys cell, else the Keys of the same row in a card of
     act.keys_books); it shows when it shares ≥ 2 words with the action and scores ≥ recall_min_score, once per 30 minutes, ≤ 2
     rules, what to DO, not its heading — and never when the rule has a guard of its own (a hook / a script that refuses) or the
     action already runs the tool the rule names.
  ♥  heartbeat (module heartbeat, OFF by default) — right after a compaction, or when the owner has been silent ≥ beat_silence_min
     and a working action goes on (never on reading or the plan): the ≤ 3 hot rules nearest to the last actions, rotated (the
     least shown first), ≤ beat_day_max a day — a rule fades in a long turn by itself, without any word that would call it.
  C  attempts — the same script ON THE SAME INPUT (its first path argument that is not an output) in other variants (other arguments
     or a newer script; a dry run and the real run are one) within 20 minutes: the 3rd → «stop and think»; the project's looking tools
     (act.look_tools) never count;
     with act.attempts_deny the 5th is refused once until the options are written (OPTIONS*.md next to the work, «# options: …» in
     the command, `foreman.py attempts think <script> --options "…"`). The script is the one the command RUNS — after the
     interpreter, inside «bash -c '…'» / «powershell -Command …», through a wrapper («gpu_guard.ps1 -Run "python x.py"») — and the
     bookkeeping (act.bookkeeping: Foreman, the project's own registry) is neither work nor an attempt.
  D  engines — config «engines»: [{"name", "match": regex, "doc", "section", "deny_first"}]; the first RUN of an engine's script in
     a session (a path in an argument, a reading, a description are no use of it) whose doc was not read since the last compaction →
     the doc's section in front of Claude (deny_first: refused once instead). `foreman.py engine ack <name> --modes "…"` names the
     modes and lets it pass.

  E  the advisor (module advisor, 2.6, OFF by default; the council of 11.11: «Foreman — a detector of events, a budget counter and a
     journal, never the one who launches»): the events where a strong second opinion pays — 2 a sub-goal failed twice (with the
     attempt warning), 3 a costly decision (an item of a registry in config «advisor.registries» marked «advisor.mark» and in work),
     5 the third repeat of one correction (the owner's correction matches a rule whose history says it failed twice already) — get
     ONE note each, with the brief's frame and «calls today n / day_max»; a call of the advisor's model (Agent «model»: fable …) is
     counted, and past day_max or a brief over brief_words a note says so. Never a refusal, never inside a subagent.
     `foreman.py advisor [days]` — the journal.

Files: .foreman/materials.jsonl (the owner's materials) · .foreman/act.jsonl (what was shown / refused / counted, per session; pruned).
One hook process per tool call (PreToolUse), no registry lock: the materials file is rewritten only by the prompt / stop hooks and the
CLI (under the lock); this hook only appends. `foreman.py replay --tools <transcript.jsonl>` runs B / ♥ / C / D over a real session
without writing anything — the quietness check."""
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re

FM = None                      # (the foreman module — set by setup())
HERE = os.path.dirname(os.path.abspath(__file__))
MATERIALS = os.path.join(HERE, 'materials.jsonl')
ACT = os.path.join(HERE, 'act.jsonl')
DEFAULTS = {'hot_books': [], 'recall_every_min': 30, 'recall_rules': 2, 'recall_min_trigger': 2,
            # (a BM25 score over the hot rules, history-free; its scale grows with the book: a 7-row book scores a true hit 10–15, the
            #  project's 36 hot rows 22–100 — tune it per project from `replay --tools … --show` (it prints each note's score);
            #  10.11 with no bar: 5.3 notes per 100 calls, the council's limit is 1.5)
            'recall_min_score': 10,
            # (the books whose rows carry Keys cells — a hot row without its own Keys borrows the Keys of the same row there;
            #  None = the lessons' rules_extra books)
            'keys_books': None,
            # (a rule with a guard of its own — a hook, a script that refuses — is not repeated by B: the guard speaks at the right
            #  moment; Fable 11.11: 17 of 60 notes of 10.11 stood on the «seven views» tools that already do what the rule asks)
            'guard_marks': r'\b[\w\-]+_(?:hook|guard)\.(?:mjs|js|py|ps1)\b|enforced by a hook|\b(?:refuses?|denies)\b',
            # (the tools that LOOK for us — 09.11's views_sheet drew one camera and fixed the error in place; «check» / «eval» were
            #  too wide on a real day: memory_index_check, eval_search are no eyes)
            'check_files': r'view|render|sheet|judge|contact|preview|look|compare|turntable|overlay',
            # (♥ after the council of 11.11: 42 beats on 10.11, 72 % of them the same three rows, 14 on reading / the plan)
            'beat_min': 45, 'beat_silence_min': 30, 'beat_day_max': 10, 'beat_rules': 3, 'beat_chars': 650,
            'attempt_window_min': 20, 'attempt_warn': 3, 'attempt_block': 5, 'attempts_deny': False,
            'attempt_ignore': [r'\bpytest\b', r'\bunittest\b', r'\bnpm\b', r'\bnpx\b', r'\bjest\b', r'\btsc\b', r'\bcargo\b', r'\bmake\b',
                               r'py_compile', r'\bpip3?\b', r'foreman\.py'],
            # (bookkeeping — neither work (A) nor an attempt (C) nor an engine's use (D): Foreman itself always; a project adds its own
            #  registry / rule lookups. 10.11: the registry's runs were 5 of 18 «attempts» and one false refusal of A)
            'bookkeeping': [r'foreman\.py'],
            # (wrappers that run the real job given as their argument: unwrapped to it even when the command is not quoted; a script
            #  whose QUOTED argument starts with a command is unwrapped anyway — gpu_guard.ps1 -Run "python x.py")
            'wrappers': [],
            # (the project's tools that LOOK at results — measure, draw sheets, build pages, shoot the screen: run again on every new
            #  result by design, never an attempt; rc1's replay: 8 of 13 warnings of 09.11 stood on them)
            'look_tools': [],
            'gate_hours': 8, 'remind_min': 20, 'ack_hours': 12}
# (B and ♥ are switches, off until the owner turns them on — the council of 11.11: on a real day they were the noise; A, C, D on;
#  E the advisor is the owner's decision too — its events and its ceiling are his)
MODULE_DEFAULT = {'act_recall': False, 'heartbeat': False, 'advisor': False}
# (config «advisor»: who the advisor is (the name in the notes — the owner changes it when the plan changes), the model names of its
#  calls, the day's ceiling, the brief's size, the registries whose marked items in work are «costly decisions»)
ADV_DEFAULTS = {'name': 'советник', 'models': ['fable'], 'day_max': 3, 'brief_words': 700, 'registries': [], 'mark': 'costly',
                'doing': ['doing', 'в работе']}
ADV = dict(ADV_DEFAULTS)

TXT = {
    'ru': {'mat_new': ('ПРОРАБ·материалы {id} ({n}{first}): изучи САМИ источники до работы (не страницу продукта) → разбор в файл: что '
                       'взято, что не прочитано → python .foreman/foreman.py material read {id} --study <файл>.{gate}'),
           'mat_topic': 'тема для поиска в сети', 'mat_src': 'источников: {n}', 'mat_first': ', СНАЧАЛА',
           'mat_gate': ' Рабочее действие до разбора будет остановлено один раз.',
           'mat_deny': ('ПРОРАБ·материалы: владелец сказал изучить СНАЧАЛА — {id} «{quote}» ещё не разобран ({src}). Сначала источники '
                        '(Read / WebFetch / браузер), разбор в файл → python .foreman/foreman.py material read {id} --study <файл>. '
                        'Если это действие и есть изучение или откладывание оправдано — повтори его (отказ один раз) или добавь в команду '
                        '«# materials-later: <почему>».'),
           'mat_stop': 'ПРОРАБ·материалы не изучены: {list} → material read M-… --study <файл> (или material skip M-… --why «…»).',
           'mat_opened': 'открыто {o}/{n}', 'mat_brief': 'Материалы владельца не изучены: {list}',
           'mat_read_ok': '{id}: изучено ({opened}) — разбор {study}',
           'mat_read_miss': '{id}: в разборе {study} не названы источники: {miss}. Разбор называет КАЖДЫЙ.',
           'mat_marks': ('{id}: в разборе {study} нет {what}. Разбор говорит, что взято и что НЕ прочитано (честно: «не прочитано: …» '
                         'или «прочитано всё»).'),
           'mat_mark_taken': '«взято / берём»', 'mat_mark_unread': '«не прочитано»',
           'mat_not_opened': ('{id}: в расшифровке сессии нет открытия источников: {miss} (Read / WebFetch / браузер / git clone после '
                              'сообщения владельца). Сначала открыть, потом разбор.'),
           'mat_no_tr': 'расшифровка сессии не найдена — проверен только разбор',
           'mat_topic_miss': '{id}: тема для поиска — в разборе {study} нужно ≥ 2 ссылок на прочитанные источники (найдено {n}).',
           'mat_no_file': 'нет файла разбора: {study}', 'mat_skip_ok': '{id}: отложено — {why}', 'mat_why': 'нужна причина: --why "…" (≥ 10 знаков)',
           'mat_none': 'нет такого материала: {id}', 'mat_list_none': 'материалов нет',
           'recall': 'ПРОРАБ·к действию — горячее правило:', 'beat': 'ПРОРАБ·горячие правила (идёт долгая работа — сверься):',
           'att_warn': ('ПРОРАБ·вариант {n} за {m} мин: `{sig}`. Правило: после второй неудачи — остановись. Что именно не так? 2–3 разных '
                        'подхода (другой путь, а не другой параметр) → OPTIONS.md рядом с работой или «# options: …» в команде; что '
                        'известно об инструменте — recall <инструмент>.'),
           'att_deny': ('ПРОРАБ·вариант {n} за {m} мин: `{sig}` — стоп. Варианты не записаны: 2–3 разных подхода (OPTIONS.md рядом с '
                        'работой, «# options: <варианты>» в команде или python .foreman/foreman.py attempts think {sig} --options "…"), '
                        'выбери один — потом запуск. Отказ один раз.'),
           'att_think': '{sig}: варианты записаны — счёт начат заново', 'att_none': 'попыток нет', 'att_opts': '--options "…" (≥ 20 знаков: 2–3 разных подхода)',
           'eng_note': ('ПРОРАБ·движок {name}: первое применение в этой сессии, а его разбор с последнего сжатия не читан — {doc}{sec}'),
           'eng_deny': ('ПРОРАБ·движок {name}: первое применение в этой сессии, а его разбор не читан — прочитай {doc} (режимы, щелчки, '
                        'спутники, ловушки){sec}. Знаешь его — python .foreman/foreman.py engine ack {key} --modes "…" или «# engine-read: '
                        '<почему>» в команде. Отказ один раз.'),
           'eng_ack': '{name}: режимы названы — проходит ({h} ч)', 'eng_ack_need': '--modes "…" — перечисли режимы движка (≥ 15 знаков): это и есть знание',
           'eng_none': 'нет такого движка в config.json → "engines": {name}',
           'adv_2': ('ПРОРАБ·{name} (повод 2 — вторая неудача подцели): выбор дорогой или неясный → {name}: бриф ≤ {w} слов — цель, что '
                     'не вышло и почему (числа), 3–5 путей, что исключено, «Файл результата»; усилие high. Вызовов сегодня {n}/{max}.'),
           'adv_3': ('ПРОРАБ·{name} (повод 3 — дорогое решение): {id} «{title}» помечен «{why}» и в работе → до сборки консилиум (xhigh) '
                     'или {name}: бриф ≤ {w} слов, 3–5 путей, что исключено, «Файл результата». Вызовов сегодня {n}/{max}.'),
           'adv_5': ('ПРОРАБ·{name} (повод 5 — третий повтор поправки): похоже на правило, которое нарушалось уже {k} раз(а) — «{rule}». '
                     'Кроме записи урока — {name}: почему защита не сработала (бриф ≤ {w} слов, усилие high). Вызовов сегодня {n}/{max}.'),
           'adv_over': 'ПРОРАБ·{name}: это {n}-й вызов сегодня при потолке {max} — дальше Opus xhigh в чистом контексте или слово владельца.',
           'adv_long': 'ПРОРАБ·{name}: бриф {words} слов при потолке {w} — сократите: цель, что исключено, 3–5 путей, «Файл результата».',
           'adv_head': 'Советник за {d} дн.: поводов {e} ({by}), вызовов {c}; по дням: {days}', 'adv_none': 'советник: событий нет',
           'rp_head': 'Повтор по расшифровке {f}: вызовов {n} (Bash / PowerShell {b}), сообщений владельца {o}',
           'rp_line': '  {k:<10} {n:>4}  ({per:.1f} на 100 вызовов)', 'rp_top': '  чаще всего: {list}'},
    'en': {'mat_new': ('FOREMAN·materials {id} ({n}{first}): study the SOURCES themselves before the work (not a product page) → notes in '
                       'a file: what was taken, what was not read → python .foreman/foreman.py material read {id} --study <file>.{gate}'),
           'mat_topic': 'a topic to search the web for', 'mat_src': '{n} source(s)', 'mat_first': ', FIRST',
           'mat_gate': ' A working action before the study will be refused once.',
           'mat_deny': ('FOREMAN·materials: the owner said to study FIRST — {id} «{quote}» is not studied yet ({src}). Sources first '
                        '(Read / WebFetch / the browser), notes in a file → python .foreman/foreman.py material read {id} --study <file>. '
                        'If this action IS the study, or the delay is justified — repeat it (refused once only) or add '
                        '«# materials-later: <why>» to the command.'),
           'mat_stop': 'FOREMAN·materials not studied: {list} → material read M-… --study <file> (or material skip M-… --why "…").',
           'mat_opened': 'opened {o}/{n}', 'mat_brief': 'The owner\'s materials not studied: {list}',
           'mat_read_ok': '{id}: studied ({opened}) — notes {study}',
           'mat_read_miss': '{id}: the notes {study} do not name the sources: {miss}. The notes name EACH.',
           'mat_marks': ('{id}: the notes {study} have no {what}. The notes say what was taken and what was NOT read (honestly: «not read: …» '
                         'or «all read»).'),
           'mat_mark_taken': '«taken / we take»', 'mat_mark_unread': '«not read»',
           'mat_not_opened': ('{id}: the session transcript shows no opening of: {miss} (Read / WebFetch / the browser / git clone after the '
                              'owner\'s message). Open first, then the notes.'),
           'mat_no_tr': 'the session transcript was not found — only the notes were checked',
           'mat_topic_miss': '{id}: a web topic — the notes {study} need ≥ 2 links to sources read (found {n}).',
           'mat_no_file': 'no notes file: {study}', 'mat_skip_ok': '{id}: deferred — {why}', 'mat_why': 'a reason is needed: --why "…" (≥ 10 chars)',
           'mat_none': 'no such material: {id}', 'mat_list_none': 'no materials',
           'recall': 'FOREMAN·for this action — a hot rule:', 'beat': 'FOREMAN·hot rules (a long piece of work — check against them):',
           'att_warn': ('FOREMAN·variant {n} in {m} min: `{sig}`. The rule: after the second failure, stop. What exactly is wrong? 2–3 different '
                        'approaches (another way, not another parameter) → OPTIONS.md next to the work or «# options: …» in the command; '
                        'what is known about the tool — recall <tool>.'),
           'att_deny': ('FOREMAN·variant {n} in {m} min: `{sig}` — stop. No options written: 2–3 different approaches (OPTIONS.md next to the '
                        'work, «# options: <options>» in the command or python .foreman/foreman.py attempts think {sig} --options "…"), '
                        'pick one — then run. Refused once.'),
           'att_think': '{sig}: options written — the count starts again', 'att_none': 'no attempts', 'att_opts': '--options "…" (≥ 20 chars: 2–3 different approaches)',
           'eng_note': 'FOREMAN·engine {name}: its first use in this session, and its notes were not read since the last compaction — {doc}{sec}',
           'eng_deny': ('FOREMAN·engine {name}: its first use in this session, and its notes were not read — read {doc} (modes, clicks, '
                        'companions, traps){sec}. You know it — python .foreman/foreman.py engine ack {key} --modes "…" or «# engine-read: '
                        '<why>» in the command. Refused once.'),
           'eng_ack': '{name}: modes named — it passes ({h} h)', 'eng_ack_need': '--modes "…" — list the engine\'s modes (≥ 15 chars): that IS the knowledge',
           'eng_none': 'no such engine in config.json → "engines": {name}',
           'adv_2': ('FOREMAN·{name} (event 2 — a sub-goal failed twice): a costly or unclear choice → the {name}: a brief ≤ {w} words — the '
                     'goal, what failed and why (numbers), 3–5 ways, what is ruled out, «Output file»; effort high. Calls today {n}/{max}.'),
           'adv_3': ('FOREMAN·{name} (event 3 — a costly decision): {id} «{title}» is marked «{why}» and in work → before building, a council '
                     '(xhigh) or the {name}: a brief ≤ {w} words, 3–5 ways, what is ruled out, «Output file». Calls today {n}/{max}.'),
           'adv_5': ('FOREMAN·{name} (event 5 — the third repeat of a correction): it looks like a rule that failed {k} time(s) already — '
                     '«{rule}». Besides the lesson record — the {name}: why the guard did not hold (a brief ≤ {w} words, effort high). '
                     'Calls today {n}/{max}.'),
           'adv_over': 'FOREMAN·{name}: call {n} today with a ceiling of {max} — from here Opus xhigh in a clean context, or the owner\'s word.',
           'adv_long': 'FOREMAN·{name}: the brief has {words} words, the ceiling is {w} — cut it: the goal, what is ruled out, 3–5 ways, «Output file».',
           'adv_head': 'The advisor in {d} day(s): events {e} ({by}), calls {c}; per day: {days}', 'adv_none': 'advisor: no events',
           'rp_head': 'Replay of {f}: {n} tool calls (Bash / PowerShell {b}), owner messages {o}',
           'rp_line': '  {k:<10} {n:>4}  ({per:.1f} per 100 calls)', 'rp_top': '  most often: {list}'},
}
LX = TXT['ru']
CFG = dict(DEFAULTS)

# ---------------------------------------------------------------- replay: an in-memory journal and a clock (nothing is written)
DRY = None                     # (a list → act rows go here, not to act.jsonl; the replay of a transcript)
CLOCK = None                   # (a datetime → «now» of the replay)


def now_dt():
    return CLOCK or dt.datetime.now()


def now():
    return now_dt().isoformat(timespec='seconds')


def _age_min(ts):
    try:
        t = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        if t.tzinfo:
            t = t.astimezone().replace(tzinfo=None)
        return (now_dt() - t).total_seconds() / 60
    except ValueError:
        return 1e9


def setup(fm):
    global FM, CFG, LX, ADV
    FM = fm
    CFG = {**DEFAULTS, **(fm.CFG.get('act') or {})}
    ADV = {**ADV_DEFAULTS, **(fm.CFG.get('advisor') or {})}
    LX = TXT.get(fm.CFG.get('lang'), TXT['ru'])


def on(module):
    return bool(FM.CFG['modules'].get(module, MODULE_DEFAULT.get(module, True)))


_ROWS = None                   # (act.jsonl read once per hook process; this process's own rows are appended to it)


def log(row):
    """one row to act.jsonl (no lock: one short line, appended); past 1.5 MB the file keeps its last 3000 rows"""
    row = {'ts': now(), **row}
    if DRY is not None:
        DRY.append(row); return
    if _ROWS is not None:
        _ROWS.append(row)
    try:
        with io.open(ACT, 'a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
        if os.path.getsize(ACT) > 1_500_000:
            FM.write_jsonl(ACT, FM.jsonl(ACT)[-3000:])
    except OSError:
        pass


def acts(session=None, minutes=None):
    global _ROWS
    if DRY is not None:
        rows = DRY
    else:
        if _ROWS is None:
            _ROWS = FM.jsonl(ACT)
        rows = _ROWS
    return [r for r in rows if (session is None or r.get('session') == session) and (minutes is None or _age_min(r.get('ts')) <= minutes)]


# ---------------------------------------------------------------- the transcript
def transcript_of(sid):
    """the session's transcript by its id: ~/.claude/projects/<the project path, every non-alphanumeric → '-'>/<id>.jsonl"""
    slug = re.sub(r'[^A-Za-z0-9]', '-', FM.PROJECT)
    base = os.environ.get('FOREMAN_TRANSCRIPTS') or os.path.join(os.path.expanduser('~'), '.claude', 'projects')   # (tests point it elsewhere)
    p = os.path.join(base, slug, f'{sid}.jsonl')
    return p if sid and os.path.exists(p) else None


class Upto:
    """the replay's transcript «so far» without copying it on every call: sliced only when a check really reads it"""
    def __init__(self, rows, n):
        self.rows, self.n = rows, n


def rows_of(src, mb=16):
    """the transcript's rows (the replay's rows so far, else the tail of the file)"""
    if isinstance(src, Upto):
        return src.rows[:src.n]
    if isinstance(src, list):
        return src
    R = FM.lessons()
    if not src or not R:
        return []
    return R.read_transcript(src, tail=mb * 1024 * 1024, cap=mb * 1024 * 1024)


def tool_uses(rows, since=None, after_compact=False):
    """(name, input, ts) of the assistant's tool calls — after `since` (ts) and, if asked, after the last compaction"""
    start = 0
    if after_compact:
        for n, e in enumerate(rows):
            if e.get('isCompactSummary'):
                start = n + 1
    out = []
    for e in rows[start:]:
        if e.get('type') != 'assistant' or (since and str(e.get('timestamp') or '') and _cmp_ts(e.get('timestamp'), since) < 0):
            continue
        for b in (e.get('message') or {}).get('content') or []:
            if isinstance(b, dict) and b.get('type') == 'tool_use':
                out.append((b.get('name') or '', b.get('input') or {}, e.get('timestamp')))
    return out


def _cmp_ts(a, b):
    def f(x):
        try:
            t = dt.datetime.fromisoformat(str(x).replace('Z', '+00:00'))
            return t.astimezone().replace(tzinfo=None) if t.tzinfo else t
        except ValueError:
            return None
    x, y = f(a), f(b)
    return 0 if x is None or y is None else (x > y) - (x < y)


# ---------------------------------------------------------------- A: the owner's materials
STUDY = re.compile(r'изуч|посмотр|разбер|разбор|ознаком|прочита|почита|прочти|глянь|взгляни|исследу|\bstudy|\bread\b|\blook (?:at|into|through)|'
                   r'have a look|check out|\breview|\bresearch|go through', re.I)
FIRST = re.compile(r'сначала|прежде|перед тем|для начала|до того как|\bfirst\b|\bbefore (?:you|we|starting|doing|any|the work)', re.I)
WEB = re.compile(r'в интернете|в сети|на гитхаб|github|готовые решения|\bonline\b|on the web|the internet|prior art', re.I)
URL = re.compile(r'https?://[^\s<>«»"\'`)\]]+')
WINPATH = re.compile(r'(?<![\w/])[A-Za-z]:[\\/][^\s«»"<>|*?`]+')
POSIXPATH = re.compile(r'(?<![\w:/.])/(?:[\w.\-]+/)+[\w.\-]+\.\w{1,5}\b')
ATPATH = re.compile(r'(?:^|\s)@([\w.\-/\\:]+\.\w{1,6}|[\w.\-]+[\\/][\w.\-/\\]+)')
IMAGE = re.compile(r'\[Image #\d+\]')
SENT = re.compile(r'(?<=[.!?…\n])\s+')
TAKEN = re.compile(r'взят|берём|берем|возьм|взяли|применим|\btaken\b|\btake\b|\badopt|we use', re.I)
UNREAD = re.compile(r'не прочита|не читал|не изуч|не открыв|прочитано всё|прочитано все|not read|unread|all read|not opened', re.I)


def sources_in(text):
    out = []
    for rx in (URL, WINPATH, POSIXPATH, IMAGE):
        out += [m.group(0).rstrip('.,;:!?»)') for m in rx.finditer(text)]
    out += [m.group(1).rstrip('.,;:!?') for m in ATPATH.finditer(text)]
    return list(dict.fromkeys(s for s in out if len(s) > 4))


def material_of(prompt):
    """→ a material (without id) when a SENTENCE of the message has a study verb and a source / a web topic in reach (± 200 chars);
    «first» counts only in such a sentence. A path that is merely the object of an edit («поправь F:\\…\\x.py») is no material."""
    src, topic, first, quote = [], False, False, []
    for s in SENT.split(prompt):
        for m in STUDY.finditer(s):
            win = s[max(0, m.start() - 200):m.end() + 200]
            here = sources_in(win)
            web = not here and bool(WEB.search(win))
            if here or web:
                src += here
                topic = topic or web
                first = first or bool(FIRST.search(win))
                quote.append(s.strip())
                break
    src = list(dict.fromkeys(src))
    if not src and not topic:
        return None
    return {'quote': prompt[:2000], 'sources': src[:30], 'topic': topic and not src, 'first': first, 'state': 'new'}


def on_prompt(prompt, inp):
    """the prompt hook (under the lock): a material → materials.jsonl + one line for Claude"""
    if not on('materials'):
        return ''
    m = material_of(prompt)
    if not m:
        return ''
    rows = FM.jsonl(MATERIALS)
    mid = 'M-' + str(len(rows) + 1).zfill(4)
    item = ''
    if FM.CFG['modules'].get('promises'):
        doing = [i for i in FM.jsonl(FM.REG) if i.get('status') == 'doing']
        item = doing[-1].get('id', '') if doing else ''
    rows.append({'id': mid, 'ts': now(), 'session': str(inp.get('session_id') or ''), **({'item': item} if item else {}), **m})
    FM.write_jsonl(MATERIALS, rows)
    n = LX['mat_topic'] if m['topic'] else LX['mat_src'].format(n=len(m['sources']))
    return LX['mat_new'].format(id=mid, n=n, first=LX['mat_first'] if m['first'] else '', gate=LX['mat_gate'] if m['first'] else '')[:420]


def open_materials():
    return [r for r in FM.jsonl(MATERIALS) if r.get('state') == 'new']


def _short(r, n=70):
    return re.sub(r'\s+', ' ', str(r.get('quote', '')))[:n]


def _keys(src):
    """what stands for a source in notes and in tool calls: a URL → host+path (no scheme, no trailing slash) and its last two parts
    (owner/repo); a path → its file / folder name"""
    s = src.replace('\\', '/').rstrip('/')
    if re.match(r'https?://', s):
        bare = re.sub(r'^https?://(www\.)?', '', s).lower()
        parts = [p for p in bare.split('/') if p]
        keys = [bare]
        if len(parts) >= 3:
            keys.append('/'.join(parts[-2:]))
        elif len(parts) == 2:
            keys.append(parts[-1])
        return keys
    return [os.path.basename(s).lower()]


def _checkable(src):
    return not IMAGE.fullmatch(src)


def opened(r, rows):
    """→ (opened sources, all checkable sources): a tool call after the owner's message whose input names the source"""
    srcs = [s for s in r.get('sources') or [] if _checkable(s)]
    if not srcs:
        return [], []
    calls = [json.dumps(ti, ensure_ascii=False).lower().replace('\\\\', '/').replace('\\', '/') for _, ti, _ in tool_uses(rows, since=r.get('ts'))]
    return [s for s in srcs if any(k in c for c in calls for k in _keys(s))], srcs


def stop_reason(inp):
    """the Stop hook (under the lock): materials not studied, each reminded at most once per remind_min; «opened k/n» from the
    transcript"""
    if not on('materials'):
        return ''
    rows = FM.jsonl(MATERIALS)
    due = [r for r in rows if r.get('state') == 'new' and _age_min(r.get('reminded') or '1970-01-01T00:00:00') >= CFG['remind_min']]
    if not due:
        return ''
    tr = rows_of(inp.get('transcript_path'), mb=8)
    for r in due:
        r['reminded'] = now()
    FM.write_jsonl(MATERIALS, rows)
    parts = []
    for r in due[:4]:
        o, n = opened(r, tr) if tr else ([], [])
        parts.append(f"{r['id']} «{_short(r, 60)}»" + (f" ({LX['mat_opened'].format(o=len(o), n=len(n))})" if n else ''))
    return LX['mat_stop'].format(list='; '.join(parts))


def brief_line():
    op = open_materials() if on('materials') else []
    return LX['mat_brief'].format(list='; '.join(f"{r['id']} «{_short(r, 50)}»" for r in op[:5])) if op else ''


def material_cmd(a):
    """material list | read M-… --study <file> | skip M-… --why "…" """
    if not a or a[0] == 'list':
        rows = FM.jsonl(MATERIALS)
        if not rows:
            print(LX['mat_list_none']); return 0
        for r in rows[-30:]:
            print(f"{r['id']} {r.get('state')}{' first' if r.get('first') else ''} {r.get('ts', '')[:16]} «{_short(r, 80)}»"
                  + (f"\n   {', '.join(r.get('sources') or [])[:300]}" if r.get('sources') else '')
                  + (f"\n   → {r.get('study') or r.get('why')}" if r.get('study') or r.get('why') else ''))
        return 0
    if len(a) < 2 or a[0] not in ('read', 'skip'):
        print(material_cmd.__doc__); return 1
    with FM.locked():
        rows = FM.jsonl(MATERIALS)
        r = next((x for x in rows if x.get('id') == a[1]), None)
        if not r:
            print(LX['mat_none'].format(id=a[1])); return 1
        if a[0] == 'skip':
            why = a[a.index('--why') + 1] if '--why' in a and a.index('--why') + 1 < len(a) else ''
            if len(why.strip()) < 10:
                print(LX['mat_why']); return 1
            r.update(state='skipped', why=why, done=now())
            FM.write_jsonl(MATERIALS, rows)
            R = FM.lessons()
            if R:
                R.ledger_add(f"{r['id']} отложен: {why} («{_short(r, 80)}»)")
            print(LX['mat_skip_ok'].format(id=r['id'], why=why)); return 0
        study = a[a.index('--study') + 1] if '--study' in a and a.index('--study') + 1 < len(a) else ''
        f = study if os.path.isabs(study) else os.path.join(FM.PROJECT, study)
        if not study or not os.path.isfile(f):
            print(LX['mat_no_file'].format(study=study or '?')); return 1
        text = FM.read(f)
        low = text.lower().replace('\\', '/')
        if r.get('topic'):
            n = len(set(URL.findall(text)))
            if n < 2:
                print(LX['mat_topic_miss'].format(id=r['id'], study=study, n=n)); return 1
        else:
            miss = [s for s in r.get('sources') or [] if _checkable(s) and not any(k in low for k in _keys(s))]
            if miss:
                print(LX['mat_read_miss'].format(id=r['id'], study=study, miss=', '.join(miss)[:600])); return 1
        lack = [LX[k] for k, rx in (('mat_mark_taken', TAKEN), ('mat_mark_unread', UNREAD)) if not rx.search(text)]
        if lack:
            print(LX['mat_marks'].format(id=r['id'], study=study, what=' и '.join(lack) if LX is TXT['ru'] else ' and '.join(lack))); return 1
        tp = transcript_of(r.get('session'))
        note = LX['mat_no_tr']
        if tp:
            o, n = opened(r, rows_of(tp))
            if n and len(o) < len(n):
                print(LX['mat_not_opened'].format(id=r['id'], miss=', '.join(s for s in n if s not in o)[:600])); return 1
            note = LX['mat_opened'].format(o=len(o), n=len(n))
        r.update(state='read', study=study, done=now())
        FM.write_jsonl(MATERIALS, rows)
        print(LX['mat_read_ok'].format(id=r['id'], study=study, opened=note))
        return 0


# ---------------------------------------------------------------- what an action is
# (a WORKING action is a program run or a code edit; reading, listing, fetching and Foreman itself are not work)
# (a script file named anywhere in a command is no run of it — «Get-Content x.ps1» reads; the scripts RUN come from runs() below)
WORK_CMD = re.compile(r'(?:^|[\s;&|(\'"])(?:python3?|py|node|npx|npm|pnpm|yarn|bun|deno|blender(?:\.exe)?|pip3?|uv|conda|cargo|go|make|'
                      r'cmake|dotnet|java|gradle|mvn|ffmpeg|wsl)(?:\.exe)?(?=[\s"\']|$)|'
                      r'\bpowershell(?:\.exe)?\s[^|;&]*-File\b|\bgit\s+(?:commit|push|merge|rebase|reset|checkout|apply|am)\b|'
                      r'\b(?:Start-Process|Invoke-Expression|iex)\b|python\.exe', re.I)
FOREMAN_CMD = re.compile(r'foreman\.py', re.I)
CODE_EXT = ('.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.json', '.ps1', '.bat', '.cmd', '.sh', '.glsl', '.hlsl', '.wgsl',
            '.html', '.css', '.c', '.cc', '.cpp', '.h', '.hpp', '.rs', '.go', '.java', '.cs', '.lua', '.yaml', '.yml', '.toml', '.ipynb')
TEST_FILE = re.compile(r'(?:^|[\\/])(?:test_[\w\-]*|[\w\-]*_test|[\w\-]*\.test|[\w\-]*\.spec)\.\w+$|(?:^|[\\/])tests?[\\/]', re.I)
TOOL_NAME = re.compile(r'[\w\-]+\.(?:py|mjs|cjs|js|ts|ps1|sh|bat|cmd)\b', re.I)
MARK_LATER = re.compile(r'#\s*materials-later:\s*\S.{8,}', re.I)
MARK_OPTIONS = re.compile(r'#\s*options:\s*\S.{18,}', re.I)
MARK_ENGINE = re.compile(r'#\s*engine-read:\s*\S.{8,}', re.I)
# (generic words of tool-call descriptions: they touch every rule a little and decide nothing — measured 09.11 on the project's rule
#  book: «Show git status» → «Long work», «List files» → a memory note; with them removed and ≥ 2 trigger words, ordinary commands
#  got nothing and the case's actions got their rules)
GENERIC = ('run runs running rerun show list check checks checking start stop edit add create file files directory folder dir install copy '
           'move test tests python node npm script scripts update read write open make use using new project server tool tools output '
           'input result results build step steps the a an of in on to for with from into this that it its and or all again via by then '
           'print get set save load call execute command commands status log logs verify find search after before remain remaining end ending three both built edit edits fix fixed mark model models candidate request requests line lines one two first last '
           'запусти запуск запустить показать список проверить проверка создать файл файлы папка папку скрипт сохранить открыть найти '
           'поиск вывод результат шаг')


# ---------------------------------------------------------------- what a command RUNS (after the council of 11.11)
# (2.5 took the FIRST script file in the command line: on 10.11 «gpu_guard.ps1 -Run "…p3sam_run.py"» counted as gpu_guard, the
#  registry «promises_check.py --set … probes=…p3sam_run.py» as an attempt and as a use of P3-SAM, «Get-Content a.py | python b.py»
#  as a.py. Now: the command is split into simple commands outside quotes, and in each the script after the interpreter is taken.)
# (spaces: a quoted path; «=»: an assignment «F=…/x.py; sed -n … $F» names a script, it does not run it — rc1's replay)
SCRIPT_TOKEN = re.compile(r'^[^*?<>|"\'`\n=]+\.(?:py|js|mjs|cjs|ts|ps1|sh|bat|cmd)$', re.I)
# (a heredoc / a PowerShell here-string is TEXT handed to a program — «cat > run.sh <<'EOF' … python engine.py … EOF» writes a script,
#  «python - <<EOF … EOF» feeds code: rc1's replay counted three engine «uses» out of such texts)
HEREDOC = re.compile(r'<<-?[ \t]*([\'"]?)([A-Za-z_]\w*)\1([^\n]*)\n.*?(?:^[ \t]*\2[ \t]*$|\Z)', re.M | re.S)
HERESTRING = re.compile(r'@([\'"])\r?\n.*?\r?\n\1@', re.S)


def strip_heredocs(c):
    """the command line without the bodies of its heredocs and here-strings (the rest of the marker's line is kept)"""
    c = HERESTRING.sub("''", str(c or ''))
    return HEREDOC.sub(lambda m: m.group(3), c)
INTERP_TOKEN = re.compile(r'^(?:.*[\\/])?(python[\d.]*|py|node|deno|bun|bash|sh|zsh|pwsh|powershell|blender|cmd)(?:\.exe)?$', re.I)
# (words that run what follows them: «env A=1 python …», «wsl -d X -- bash …», «timeout 60 node …», «call x.bat»)
PREFIXES = ('env', 'timeout', 'nohup', 'time', 'sudo', 'wsl', 'wsl.exe', 'start', 'exec', 'call', 'xvfb-run', 'conda', 'uv')
CD_WORDS = ('cd', 'chdir', 'pushd', 'set-location', 'sl')


def split_cmd(c):
    """a command line → its simple commands: cut at ; | && || and line ends, never inside quotes"""
    out, cur, q, i, c = [], [], '', 0, str(c or '')
    while i < len(c):
        ch = c[i]
        if q:
            cur.append(ch)
            if ch == q:
                q = ''
        elif ch in '"\'':
            q = ch
            cur.append(ch)
        elif ch in ';\n\r|' or (ch == '&' and c[i + 1:i + 2] == '&'):
            out.append(''.join(cur))
            cur = []
            i += ch == '&'
        else:
            cur.append(ch)
        i += 1
    out.append(''.join(cur))
    return [s.strip() for s in out if s.strip()]


def split_words(seg):
    out, cur, q = [], [], ''
    for ch in seg:
        if q:
            cur.append(ch)
            if ch == q:
                q = ''
        elif ch in '"\'':
            q = ch
            cur.append(ch)
        elif ch.isspace():
            if cur:
                out.append(''.join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append(''.join(cur))
    return out


def unq(t):
    t = str(t).strip().strip('(){}')
    return t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in '"\'' else t


def bookkeeping(text):
    """Foreman and the project's own bookkeeping (act.bookkeeping) — never work, an attempt or an engine's use"""
    return bool(FOREMAN_CMD.search(text)) or any(re.search(x, text, re.I) for x in CFG.get('bookkeeping') or [])


def _join(here, p):
    p = p.replace('\\', '/')
    if not here or re.match(r'^(?:[A-Za-z]:)?/', p):
        return p
    return here.rstrip('/') + '/' + p


def _starts_command(text):
    w = split_words(text)
    t = unq(w[0]) if w else ''
    return bool(t) and (bool(INTERP_TOKEN.match(t)) or bool(SCRIPT_TOKEN.match(t)) or t.lower() in PREFIXES or t == '&')


def _script(t, args, here, depth):
    """a script found in a run: the wrapper's inner job when it has one, else the script itself"""
    if bookkeeping(t):
        return []
    wrap = any(re.search(x, os.path.basename(t.replace('\\', '/')), re.I) for x in CFG.get('wrappers') or [])
    # (2.5.2: an environment launcher — a .cmd / .bat / .sh / .ps1 whose FIRST argument is an interpreter or a launcher word:
    #  «lab_env_run.cmd .venv\Scripts\python.exe bootstrap.py». 11.11: three different commands through one such .cmd were
    #  «variant 3» of the .cmd, its «input» the python.exe)
    first = unq(args[0]) if args else ''
    envwrap = bool(re.search(r'\.(?:cmd|bat|sh|ps1)$', t, re.I)) and bool(first) and \
        (bool(INTERP_TOKEN.match(first)) or first.lower() in PREFIXES)
    inner = []
    for a in args:                                    # (a QUOTED argument that is itself a command: gpu_guard.ps1 -Run "python x.py")
        if a[:1] in '"\'' and _starts_command(unq(a)):
            inner += runs(unq(a), here, depth + 1)
    if not inner and (wrap or envwrap):
        inner = runs(' '.join(args), here, depth + 1)
    if inner or wrap or envwrap:
        return inner
    return [(t, _join(here, t), list(args))]


def _interp_runs(name, rest, here, depth):
    """the script an interpreter runs: its first positional word that is a script (options and their bare values skipped); the code
    of «bash -c '…'», «powershell -Command …», «cmd /c …» is read as a command line again; «python -c» / «node -e» code is code"""
    name = name.lower()
    fam = ('python' if name.startswith('py') else 'node' if name in ('node', 'deno', 'bun') else 'sh' if name in ('bash', 'sh', 'zsh')
           else 'ps' if name in ('pwsh', 'powershell') else name)
    prev_opt = False
    for j, tok in enumerate(rest):
        t = unq(tok)
        tl = t.lower()
        if ((fam == 'python' and tl == '-c') or (fam == 'node' and tl in ('-e', '--eval', '-p', '--print'))
                or (fam == 'sh' and re.fullmatch(r'-[a-z]*c[a-z]*', tl)) or (fam == 'ps' and tl in ('-c', '-command'))
                or (fam == 'cmd' and tl in ('/c', '/k'))):
            code = rest[j + 1:]
            if fam in ('python', 'node') or not code:
                return []
            return runs(unq(code[0]) if fam == 'sh' or len(code) == 1 else ' '.join(code), here, depth + 1)
        if (fam == 'python' and tl in ('-m', '-')) or (fam == 'ps' and tl in ('-encodedcommand', '-ec')) or \
                (fam == 'blender' and tl in ('--', '--python-expr', '--python-text')):
            return []
        if t.startswith('-') or (fam == 'cmd' and t.startswith('/')):
            prev_opt = True
            continue
        if SCRIPT_TOKEN.match(t):
            return _script(t, rest[j + 1:], here, depth)
        if fam == 'blender' or (prev_opt and not re.search(r'[\\/.]', t)):
            prev_opt = False                          # (a .blend file; an option's bare value: -X utf8, -ExecutionPolicy Bypass)
            continue
        return []
    return []


def runs(c, here='', depth=0):
    """→ [(the script as written, its path for matching — a preceding «cd» joined, its arguments)] of the scripts a command line RUNS:
    the script after an interpreter, after the call operator «&» or «.», a script at a command's start; a wrapper is unwrapped;
    bookkeeping is skipped; heredoc bodies are text, not commands"""
    out = []
    if depth > 4:
        return out
    for seg in split_cmd(strip_heredocs(c)):
        if bookkeeping(seg):
            continue
        w = split_words(seg)
        if not w:
            continue
        if unq(w[0]).lower() in CD_WORDS:             # (the folder a following relative script lives in — «cd …/P3-SAM && python demo/x.py»)
            d = next((unq(x) for x in reversed(w[1:]) if not unq(x).startswith(('-', '/d', '/D'))), '')
            here = _join(here, d) if d else here
            continue
        cmdpos = True
        for i, tok in enumerate(w):
            t = unq(tok)
            if t in ('&', '.', '--'):
                cmdpos = True
                continue
            m = INTERP_TOKEN.match(t)
            if m:
                out += _interp_runs(m.group(1), w[i + 1:], here, depth)
                break
            if cmdpos and SCRIPT_TOKEN.match(t):
                out += _script(t, w[i + 1:], here, depth)
                break
            if not (cmdpos and (t.lower() in PREFIXES or ('=' in t and not t.startswith('-')))):
                cmdpos = False
    return out


def _shell_kept(c):
    """the command without its bookkeeping simple commands"""
    return ' ; '.join(s for s in split_cmd(c) if not bookkeeping(s))


# (a code file written from the shell — «cat > run.sh <<'EOF'», «… | Out-File x.py» — is a code edit, i.e. work; its TEXT runs nothing)
CODE_WRITE = re.compile(r'>{1,2}\s*["\']?[^\s"\'|;&>]+\.(?:py|js|mjs|cjs|ts|ps1|sh|bat|cmd)\b|'
                        r'\b(?:Set-Content|Add-Content|Out-File)\b[^|;]*\.(?:py|js|mjs|cjs|ts|ps1|sh|bat|cmd)\b', re.I)


def is_work(tool, ti):
    if tool in ('Bash', 'PowerShell'):
        c = _shell_kept(str(ti.get('command') or ''))
        return bool(runs(c)) or bool(WORK_CMD.search(c)) or bool(CODE_WRITE.search(c))
    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        return str(ti.get('file_path') or ti.get('notebook_path') or '').lower().endswith(CODE_EXT)
    if tool in ('Agent', 'Task'):
        return str(ti.get('subagent_type') or '') not in (FM.CFG.get('contract') or {}).get('readonly_types', []) + ['web-fetch']
    return False


def material_gate(tool, ti, sid):
    """A: a «first» material not studied yet, from this session (or the last gate_hours when the session is unknown) → refuse the
    first working action once per material. An agent whose brief names the material's source is the study itself."""
    if not on('materials') or not is_work(tool, ti):
        return ''
    text = f"{ti.get('command') or ''} {ti.get('description') or ''}"
    if MARK_LATER.search(text):
        return ''
    gated = {r.get('material') for r in acts(sid) if r.get('kind') == 'mat_gate'}
    brief = str(ti.get('prompt') or '').lower().replace('\\', '/')
    for r in open_materials():
        if not r.get('first') or r['id'] in gated:
            continue
        if (r.get('session') and sid and r['session'] != sid) or _age_min(r.get('ts')) > 60 * CFG['gate_hours']:
            continue
        if brief and any(k in brief for s in r.get('sources') or [] for k in _keys(s)):
            continue
        log({'kind': 'mat_gate', 'session': sid, 'material': r['id'], 'tool': tool})
        src = LX['mat_topic'] if r.get('topic') else ', '.join(r.get('sources') or [])[:200]
        return LX['mat_deny'].format(id=r['id'], quote=_short(r, 90), src=src)
    return ''


# ---------------------------------------------------------------- B + ♥: the hot rules
_HOT = None


# (a rule's «when» carries its history too — «CORRECTION 09.11: «…the owner's words…»», «failed AGAIN 05.11 (the glasses judged
#  from ONE front picture)». The concrete past situations are the best match for a similar action, so they stay; the owner's quotes
#  go (his words, not the situation), and the history's own words are generic (HISTORY_WORDS): on a real day «Count producer messages
#  and flagged corrections» met rows only through «producer», «correction».)
QUOTED = re.compile(r'«[^»]*»?|"[^"]*"')
HISTORY_WORDS = ('producer owner correction corrections teaching ruling failed fails again twice third times time repeat repeated rule '
                 'rules row rows hook hooks message messages said asked hour day enforced same own any anything every always never '
                 'session')


# (the history of a rule — «— failed AGAIN 05.11 (…)», «— CORRECTION 09.11: …», «(01.11: 7 losses …)» — is where it came from, not
#  when it applies: the council of 11.11 cut the triggers to the situation and the Keys)
#  (a dash cuts only before history: «— a part, a view, a sheet; ESPECIALLY Nano Banana» is still the situation)
HISTORY_CUT = re.compile(r'\s[—–]\s*(?=(?:failed|fails|CORRECTION|TEACHING|RULING|a repeat|ENFORCED|\d{1,2}\.\d{1,2}))|'
                         r'\b(?:CORRECTION|TEACHING|RULING)\b|\bfailed\s+(?:AGAIN|TWICE|THREE|\d)|\(\d{1,2}\.\d{1,2}\b')


def situation(when):
    s = QUOTED.sub(' ', re.sub(r'^\[[^\]]*\]\s*', '', str(when)))
    m = HISTORY_CUT.search(s)
    return s[:m.start()] if m and m.start() > 3 else s


def _cells(line):
    return [c.strip() for c in str(line).strip().strip('|').split(' | ')]


def _keys_cell(cells):
    k = cells[-1] if len(cells) > 1 and (len(cells) >= 4 or cells[-1].lower().startswith(('keys', 'ключи'))) else ''
    return re.sub(r'^\W*(?:keys|ключи)\W*', '', k, flags=re.I)


def _keys_index(R):
    """[(tag, head words, Keys)] of the rows that carry a Keys cell in act.keys_books (default: the lessons' rule books)"""
    books = CFG.get('keys_books') or R.CFG['lessons'].get('rules_extra') or []
    keep = R.CFG['lessons'].get('rules_extra')
    R.CFG['lessons']['rules_extra'] = books
    try:
        out = []
        for b in R.extra_blocks():
            if '#' in b.ref:
                continue
            cells = _cells(b.text)
            k = _keys_cell(cells)
            if k:
                tag = re.match(r'^\[[^\]]*\]', cells[0])
                out.append((tag.group(0) if tag else '', set(R.tokens(situation(cells[0]))), k))
        return out
    finally:
        R.CFG['lessons']['rules_extra'] = keep


def _borrow_keys(idx, tag, head, R):
    """the Keys of the same row in a card: the same law tag, the head's words overlapping ≥ 50 % (the hot copy keeps the card's head)"""
    hw = set(R.tokens(head))
    best, keys = 0.0, ''
    for t, w, k in idx:
        if not hw or not w or (tag and t and t != tag):
            continue
        j = len(hw & w) / len(hw | w)
        if j > best:
            best, keys = j, k
    return keys if best >= 0.5 else ''


def hot():
    """[(block, do, trigger words, guarded, tools)] — rules.jsonl active with level ≥ 2, and the table rows of act.hot_books (the 2nd
    cell is the «do»); the trigger = the situation of the «when» without its history + the Keys; the block BM25 ranks is built
    from the same (situation, do, Keys); guarded = the rule has a guard of its own; tools = the scripts the rule names"""
    global _HOT
    if _HOT is not None:
        return _HOT
    R, out = FM.lessons(), []
    if not R:
        _HOT = []
        return _HOT
    gen = set(R.tokens(GENERIC + ' ' + HISTORY_WORDS))
    trig = lambda text: {t for t in R.tokens(text) if t not in gen and len(t) > 2}       # noqa: E731
    guard = re.compile(CFG.get('guard_marks') or r'(?!)', re.I)

    def add(b, tag, when, do, keys, whole):
        head = situation(when)
        nb = R.Block('rule', b.src, b.ref, f'{head} {QUOTED.sub(" ", do)} {keys}', f'{head} {keys}', b.label, b.tags)
        out.append((nb, f"{tag}{do}", trig(f'{head} {keys}'), bool(guard.search(whole)),
                    {t.lower() for t in TOOL_NAME.findall(do)}))

    lv = {r['id']: r for r in R.jsonl(R.RULES) if r.get('status') == 'active' and int(r.get('level') or 0) >= 2}
    for b in R.rule_blocks():
        if b.ref in lv:
            r = lv[b.ref]
            add(b, f'{b.ref}: ', r.get('when', ''), str(r.get('do', '')), str(r.get('keys', '')), f"{r.get('when', '')} {r.get('do', '')}")
    if CFG.get('hot_books'):
        keep = R.CFG['lessons'].get('rules_extra')
        R.CFG['lessons']['rules_extra'] = CFG['hot_books']
        try:
            rows = [b for b in R.extra_blocks() if '#' not in b.ref]       # (a «### law» section — not a row)
        finally:
            R.CFG['lessons']['rules_extra'] = keep
        idx = None
        for b in rows:
            cells = _cells(b.text)
            tag = re.match(r'^\[[^\]]*\]', cells[0])
            tag = tag.group(0) if tag else ''
            keys = _keys_cell(cells)
            if not keys:
                idx = _keys_index(R) if idx is None else idx
                keys = _borrow_keys(idx, tag, situation(cells[0]), R)
            add(b, f'{tag} ' if tag else '', cells[0], cells[1] if len(cells) > 1 else cells[0], keys, b.text)
    _HOT = out
    return out


def _qtokens(text):
    R = FM.lessons()
    gen = set(R.tokens(GENERIC + ' ' + HISTORY_WORDS))
    return [t for t in dict.fromkeys(R.tokens(text)) if t not in gen and len(t) > 2]


def _rank(qt, need, floor=True, band=0.35):
    """→ [(score, block, do, guarded, tools)]: the hot rules whose trigger shares ≥ need of the query's words, by BM25 over the hot
    rules, within `band` of the best and at or above recall_min_score (floor); [] fast when none is touched"""
    H = hot()
    if not H or len(qt) < need:
        return []
    cand = [h for h in H if len({t for t in qt if t in h[2]}) >= need]
    if not cand:
        return []                                    # (the pre-filter: most calls end here, without BM25)
    R = FM.lessons()
    score = {h['block'].ref: h['score'] for h in R.search(' '.join(qt), blocks=[h[0] for h in H], top=0)}
    cand = [(score.get(b.ref, 0), b, d, g, tl) for b, d, _, g, tl in cand]
    best = max((c[0] for c in cand), default=0)
    bar = float(CFG.get('recall_min_score') or 0) if floor else 0
    return [c for c in sorted(cand, key=lambda x: -x[0]) if c[0] > 0 and c[0] >= band * best and c[0] >= bar]


def action_text(tool, ti):
    """what an action says about itself: a program run → its description + the scripts' names; an agent → its description + the start
    of the brief; the edit of a CHECKING tool (a view / render / sheet … file) → the file's name + the start of the new text"""
    if tool in ('Bash', 'PowerShell'):
        if not is_work(tool, ti):
            return ''                                # (reading, listing, git status, bookkeeping … — never searched)
        names = ' '.join(os.path.splitext(os.path.basename(p.replace('\\', '/')))[0].replace('_', ' ')
                         for p, *_ in runs(str(ti.get('command') or '')))
        return f"{ti.get('description') or ''} {names}"
    if tool in ('Agent', 'Task'):
        return f"{ti.get('description') or ''} {str(ti.get('prompt') or '')[:300]}"
    if tool in ('Write', 'Edit', 'MultiEdit'):
        f = os.path.basename(str(ti.get('file_path') or ''))
        if not f.lower().endswith(CODE_EXT) or not re.search(CFG['check_files'], f, re.I):
            return ''
        body = ti.get('content') or ti.get('new_string') or ' '.join(str(e.get('new_string', '')) for e in ti.get('edits') or [])
        return f"{os.path.splitext(f)[0].replace('_', ' ')} {str(body)[:300]}"
    return ''


def _acted(tool, ti):
    """the tool names an action already runs / writes / hands over — a rule that names one of them is being followed"""
    text = ' '.join(str(ti.get(k) or '') for k in ('command', 'file_path', 'prompt'))
    return {t.lower() for t in TOOL_NAME.findall(text)}


def action_recall(tool, ti, sid):
    if not on('act_recall'):
        return ''
    q = action_text(tool, ti)
    if not q.strip() or not FM.lessons():
        return ''
    hits = _rank(_qtokens(q), CFG['recall_min_trigger'])
    if not hits:
        return ''
    done = _acted(tool, ti)
    # (silent when the rule has a guard of its own, or the action already runs the tool the rule names — Fable 11.11)
    hits = [h for h in hits if not h[3] and not (h[4] & done)]
    recent = {r.get('rule') for r in acts(sid, CFG['recall_every_min']) if r.get('kind') in ('shown', 'beat_rule')}
    out = [(b, d, s) for s, b, d, _, _ in hits if b.ref not in recent][:CFG['recall_rules']]
    if not out:
        return ''
    for b, _, s in out:
        log({'kind': 'shown', 'session': sid, 'rule': b.ref, 'tool': tool, 'q': q[:160], 'score': round(s, 1)})
    return '\n'.join([LX['recall']] + [f"  {d[:240]}  [{b.ref}]" for b, d, _ in out])


REPLAY_OWNER = None            # (the replay: the time of the owner's last message so far)


def owner_silence(sid, clock_start):
    """minutes since the owner's last message in this session (owner.jsonl of the prompt hook); none logged → since the clock start"""
    if DRY is not None:
        last = REPLAY_OWNER
    else:
        last = next((r.get('ts') for r in reversed(FM.jsonl(FM.OWNER)) if str(r.get('session_id') or '') == sid), None)
    return _age_min(last or clock_start)


def heartbeat(sid, transcript, tool='', ti=None):
    """♥: the first call of a session starts the clock silently; then, on a WORKING action only, right after a compaction or when
    the owner has been silent ≥ beat_silence_min (and beat_min since the last beat): the ≤ beat_rules hot rules nearest to the last
    ~40 actions, the least shown first; ≤ beat_day_max a day"""
    if not on('heartbeat'):
        return ''
    mine = [r for r in acts(sid) if r.get('kind') in ('beat', 'beat_reset')]
    if not mine:
        log({'kind': 'beat', 'session': sid, 'silent': True})
        return ''
    if not is_work(tool, ti or {}):
        return ''                                    # (never on reading, a search, the plan)
    if mine[-1].get('kind') != 'beat_reset':
        if _age_min(mine[-1].get('ts')) < CFG['beat_min'] or owner_silence(sid, mine[0].get('ts')) < CFG['beat_silence_min']:
            return ''                                # (the clocks first: the hot rules are built only when a beat is due)
    day = now_dt().date().isoformat()
    if sum(1 for r in acts(None, 24 * 60) if r.get('kind') == 'beat' and r.get('rules') and str(r.get('ts', ''))[:10] == day) \
            >= CFG['beat_day_max']:
        return ''
    if not hot():
        return ''
    calls = tool_uses(rows_of(transcript, mb=4))[-40:]
    q = ' '.join(action_text(n, t) or str(t.get('description') or '') for n, t, _ in calls)
    # (a wider band than B's: the heartbeat reminds of the rules NEAR the work, and the rotation needs more than the top three)
    hits = _rank(_qtokens(q), 1, floor=False, band=0.15) if q.strip() else []
    # (rotation: the rules this session's beats showed least today first, then the nearest; 10.11: 72 % of the beats were 3 rows)
    seen = {}
    for r in acts(sid, 24 * 60):
        if r.get('kind') == 'beat_rule':
            seen[r.get('rule')] = seen.get(r.get('rule'), 0) + 1
    hits = sorted(hits, key=lambda h: (seen.get(h[1].ref, 0), -h[0]))[:CFG['beat_rules']]
    log({'kind': 'beat', 'session': sid, 'rules': [h[1].ref for h in hits]})
    if not hits:
        return ''
    lines, used = [LX['beat']], len(LX['beat'])
    for _, b, d, _, _ in hits:
        line = f"  {d[:220]}  [{b.ref}]"
        if used + len(line) > CFG['beat_chars']:
            break
        lines.append(line)
        used += len(line) + 1
        log({'kind': 'beat_rule', 'session': sid, 'rule': b.ref})
    return '\n'.join(lines) if len(lines) > 1 else ''


def compacted(sid):
    """the session hook after a compaction: the next tool call beats at once"""
    if on('heartbeat'):
        log({'kind': 'beat_reset', 'session': sid})


# ---------------------------------------------------------------- C: variants of the same script
# (a dry run and the same run for real are one variant — 10.11: «delete … -DryRun» then the planned run counted as two)
DRY_FLAG = re.compile(r'(?<!\S)(?:-DryRun|--dry-?run|-WhatIf|--what-?if)(?::\$?\w+)?(?!\S)', re.I)
# (an option whose value is where a script WRITES — not its input)
# («--target» / «--to» are not here: ambiguous, and another target is another job — parts_to_obj.py --target …, the 09.11 replay)
OUT_OPT = re.compile(r'^-{1,2}(?:o|out|output|outdir|out[-_]?dir|out[-_]?file|dst|dest|destination|save|save[-_]?to|log|report)$', re.I)
NUMBER = re.compile(r'^[-+]?\d+(?:[.,]\d+)?(?:e[-+]?\d+)?%?$', re.I)


def _pathlike(t):
    return bool(t) and not NUMBER.match(t) and bool(re.search(r'[\\/]', t) or (re.search(r'\.[A-Za-z]\w{0,5}$', t) and not re.search(r'\s', t)))


def script_input(args):
    """what the run works ON: its first POSITIONAL argument (not an option, not an option's value, not a number) — an object, a mode,
    a file; else the first path given as an option's value that is not an output. rc1's replay: a «variant» on ANOTHER input is another
    job (measure_round3 on three results, gen.py on another picture); 2.6.1: inputs named by bare words — «run_authors.cmd fox gnome»,
    then «warrior», then «ram …»; «bench.py smoke», then «matrix audrey» — were «variant 3» (the Pixel Match session, 11.11)"""
    # (2.6.1 rc2, the replay of 09.11: a redirection «2>&1» became the «input» of parts_to_obj.py; p3click.py's sub-commands
    #  prep / eval / vote split one real loop on «glasses p3click/glasses_clicks.json» — so: a positional PATH first, then a word)
    pathval, words, prev_opt, prev_out = '', [], False, False
    for tok in args:
        t = unq(tok)
        if tok.startswith('#') or re.match(r'^(?:\d*>>?|\d*<|&>|\d*>&)', tok):
            break                                     # (a shell comment or a redirection — no argument from here on)
        if t.startswith('-') and not NUMBER.match(t):
            k, eq, v = t.partition('=')
            out = bool(OUT_OPT.match(k))
            if eq:
                if not out and not pathval and _pathlike(unq(v)):
                    pathval = unq(v)
                prev_opt = prev_out = False
            else:
                prev_opt, prev_out = True, out
            continue
        if prev_opt:                                  # (an option's value: --mesh granny.glb, --thr 0.3, --mode fast)
            if not prev_out and not pathval and _pathlike(t):
                pathval = t
            prev_opt = prev_out = False
            continue
        if t and not NUMBER.match(t):
            words.append(t)
    pick = next((w for w in words if _pathlike(w)), None) or (words[0] if words else '') or pathval
    return pick.replace('\\', '/').rstrip('/').lower()


def signature(cmd, cwd=None):
    """→ (the file name of the script the command RUNS, the variant key, its input) or ('', '', '') — the script after the interpreter,
    through a wrapper; Foreman, the bookkeeping, tests, the ignore list and the project's LOOKING tools (act.look_tools — run on every
    new result by design) are never counted"""
    c = str(cmd or '')
    if any(re.search(x, c, re.I) for x in CFG.get('attempt_ignore') or []):
        return '', '', ''
    for path, full, args in runs(c):
        base = os.path.basename(path.replace('\\', '/'))
        if TEST_FILE.search(path.replace('\\', '/')) or any(re.search(x, base, re.I) for x in CFG.get('look_tools') or []):
            continue
        real = full if os.path.isabs(full) else os.path.join(cwd or FM.PROJECT, full)
        try:
            mt = str(int(os.path.getmtime(real)))
        except (OSError, ValueError):
            mt = ''
        norm = re.sub(r'\s+', ' ', DRY_FLAG.sub(' ', strip_heredocs(c).split('#')[0])).strip()
        key = hashlib.sha1((norm + '|' + mt).encode('utf-8', 'replace')).hexdigest()[:12]
        return base, key, script_input(args)
    return '', '', ''


def _options_written(since_ts, cwd, cmd):
    """an OPTIONS*.md newer than the window's first variant: in the cwd, or a folder the command names"""
    try:
        t0 = dt.datetime.fromisoformat(since_ts).timestamp() if since_ts else 0
    except ValueError:
        t0 = 0
    dirs = [cwd or FM.PROJECT]
    for m in re.finditer(r'([A-Za-z]:[\\/][^\s"\';&|]+|[\w.\-]+(?:[\\/][\w.\-]+)+)', str(cmd)):
        p = m.group(1) if os.path.isabs(m.group(1)) else os.path.join(cwd or FM.PROJECT, m.group(1))
        dirs.append(p if os.path.isdir(p) else os.path.dirname(p))
    for d in list(dict.fromkeys(dirs))[:12]:
        for f in glob.glob(os.path.join(d, 'OPTIONS*.md')):
            try:
                if os.path.getmtime(f) >= t0 - 1:
                    return True
            except OSError:
                pass
    return False


def attempts(tool, ti, sid, cwd):
    """C, counted BEFORE the run (one hook process per call): → ('warn' | 'deny' | '', text). A variant = other arguments or a newer
    script; the exact same command again is the same attempt. The exit code is no criterion — 09.11's seven runs all exited 0."""
    if not on('attempts') or tool not in ('Bash', 'PowerShell'):
        return '', ''
    cmd = str(ti.get('command') or '')
    sig, key, inp = signature(cmd, cwd)
    if not sig:
        return '', ''
    win = CFG['attempt_window_min']
    # (this session's rows of the same script ON THE SAME INPUT, plus a `think` — written from the CLI it knows no session and no input)
    rows = [r for r in acts(None, win) if r.get('sig') == sig and (
        (r.get('session') == sid and (r.get('inp') or '') == inp) or (r.get('kind') == 'think' and (not r.get('session') or
                                                                                                    r.get('session') == sid)))]
    last = max((n for n, r in enumerate(rows) if r.get('kind') in ('think', 'att_deny')), default=-1)
    seen = list(dict.fromkeys(r.get('key') for r in rows[last + 1:] if r.get('kind') == 'run'))
    run = {'kind': 'run', 'session': sid, 'sig': sig, 'key': key, **({'inp': inp} if inp else {})}
    if MARK_OPTIONS.search(f"{cmd} {ti.get('description') or ''}"):
        log({'kind': 'think', 'session': sid, 'sig': sig, 'how': 'mark'})
        log(run)
        return '', ''
    if key in seen:
        log(run)
        return '', ''
    n = len(seen) + 1
    if CFG.get('attempts_deny') and n >= CFG['attempt_block']:
        first = next((r['ts'] for r in rows[last + 1:] if r.get('kind') == 'run'), None)
        if not _options_written(first, cwd, cmd):
            log({'kind': 'att_deny', 'session': sid, 'sig': sig, 'n': n, **({'inp': inp} if inp else {})})
            return 'deny', LX['att_deny'].format(n=n, m=win, sig=sig)
    log(run)
    if n == CFG['attempt_warn']:
        log({'kind': 'att_warn', 'session': sid, 'sig': sig, 'n': n, **({'inp': inp} if inp else {})})
        text = LX['att_warn'].format(n=n, m=win, sig=sig)
        if on('advisor'):                             # (E, event 2: the second failure of a sub-goal — the advisor if the choice is costly)
            log({'kind': 'adv_note', 'session': sid, 'event': 2, 'sig': sig})
            text += '\n' + _adv('adv_2')
        return 'warn', text
    return '', ''


def attempts_cmd(a):
    """attempts [list] | think <script> --options "…" """
    if a[:1] == ['think'] and len(a) > 1:
        opts = a[a.index('--options') + 1] if '--options' in a and a.index('--options') + 1 < len(a) else ''
        if len(opts.strip()) < 20:
            print(LX['att_opts']); return 1
        log({'kind': 'think', 'session': '', 'sig': a[1], 'how': 'cli', 'options': opts[:600]})
        print(LX['att_think'].format(sig=a[1])); return 0
    rows = [r for r in FM.jsonl(ACT) if r.get('kind') == 'run' and _age_min(r.get('ts')) <= 24 * 60]
    if not rows:
        print(LX['att_none']); return 0
    count = {}
    for r in rows:
        count.setdefault(r['sig'], set()).add(r.get('key'))
    for s, k in sorted(count.items(), key=lambda kv: -len(kv[1]))[:20]:
        print(f'{len(k):4} {s}')
    return 0


# ---------------------------------------------------------------- D: an engine's notes before its first use
def engines():
    return [e for e in FM.CFG.get('engines') or [] if isinstance(e, dict) and e.get('match') and e.get('doc')]


def docs_of(e):
    """an engine's notes: one path or several (09.11: «Замкнуть» needs its authors' run AND the list of the owner's optimizers)"""
    d = e.get('doc')
    return [str(x) for x in (d if isinstance(d, list) else [d]) if x]


def _doc_path(doc):
    return doc if os.path.isabs(doc) else os.path.join(FM.PROJECT, doc)


def read_since_compact(rows, doc):
    """the doc was read after the last compaction — a Read of it, or a shell print of it (a subagent's reading does not count)"""
    name = os.path.basename(str(doc)).lower()
    full = os.path.normcase(os.path.abspath(_doc_path(doc))).replace('\\', '/')
    for tool, ti, _ in tool_uses(rows, after_compact=True):
        if tool == 'Read':
            if os.path.normcase(os.path.abspath(str(ti.get('file_path') or ''))).replace('\\', '/') == full:
                return True
        elif tool in ('Bash', 'PowerShell'):
            c = str(ti.get('command') or '').lower().replace('\\', '/')
            if name in c and re.search(r'\b(cat|type|get-content|gc|head|tail|less|more|sed)\b', c):
                return True
    return False


def section(doc, head, strict=False):
    """≤ 600 chars of the doc's section whose heading contains `head` (any level); else the first line holding `head` (a rule
    book's table row — «Image → 3D» in a card); else the doc's start ('' when strict)"""
    text = FM.read(_doc_path(doc))
    if not text:
        return ''
    m = re.search(r'^#{1,4}[^\n]*' + re.escape(head) + r'[^\n]*\n(.*?)(?=^#{1,4}\s|\Z)', text, re.M | re.S | re.I) if head else None
    if m:
        body = m.group(1)
    else:
        row = next((l for l in text.splitlines() if head and head.lower() in l.lower()), None) if head else None
        if row is None and strict:
            return ''
        body = row if row is not None else text
    return re.sub(r'\n{2,}', '\n', body.strip())[:600]


def engine_gate(tool, ti, sid, transcript):
    """D: → ('deny' | 'note' | '', text); once per engine and session"""
    if not on('engines') or tool not in ('Bash', 'PowerShell') or not engines():
        return '', ''
    cmd = str(ti.get('command') or '')
    if MARK_ENGINE.search(cmd):
        return '', ''
    # (only what the command RUNS — the scripts after the interpreters, a preceding «cd» joined, a wrapper unwrapped; never the
    #  description, a path in an argument or a reading: on 09.11 a ledger line that only MENTIONED P3-SAM counted as a use of it, on
    #  10.11 «Measure the size of every Hunyuan folder» and a registry probe naming p3sam_run.py — two false refusals)
    text = ' '.join(full for _, full, *_ in runs(cmd))
    if not text:
        return '', ''
    done = None
    for e in engines():
        try:
            if not re.search(e['match'], text, re.I):
                continue
        except re.error:
            continue
        key = e.get('name') or e['match']
        if done is None:
            done = {r.get('engine') for r in acts(sid) if r.get('kind') in ('eng_gate', 'eng_seen')} | \
                   {r.get('engine') for r in acts(None, 60 * CFG['ack_hours']) if r.get('kind') == 'eng_ack'}
        if key in done:
            continue
        rows = rows_of(transcript)
        docs = docs_of(e)
        unread = [d for d in docs if not read_since_compact(rows, d)]
        if not unread:
            log({'kind': 'eng_seen', 'session': sid, 'engine': key, 'read': True})
            continue
        head = e.get('section') or ''                # (the doc that HAS the section; else the first doc's start)
        sec = next((s for s in (section(d, head, strict=True) for d in docs) if s), '') if head else ''
        sec = sec or section(docs[0], '')
        sec = f"\n{sec}" if sec else ''
        doc = ' + '.join(unread)
        if e.get('deny_first'):
            log({'kind': 'eng_gate', 'session': sid, 'engine': key})
            return 'deny', LX['eng_deny'].format(name=key, doc=doc, sec=sec, key=key)
        log({'kind': 'eng_seen', 'session': sid, 'engine': key})
        return 'note', LX['eng_note'].format(name=key, doc=doc, sec=sec)
    return '', ''


def engine_cmd(a):
    """engine ack <name> --modes "…" | engine list"""
    if a[:1] == ['ack'] and len(a) > 1:
        e = next((x for x in engines() if (x.get('name') or x['match']).lower() == a[1].lower()), None)
        if not e:
            print(LX['eng_none'].format(name=a[1])); return 1
        modes = a[a.index('--modes') + 1] if '--modes' in a and a.index('--modes') + 1 < len(a) else ''
        if len(modes.strip()) < 15:
            print(LX['eng_ack_need']); return 1
        key = e.get('name') or e['match']
        log({'kind': 'eng_ack', 'session': '', 'engine': key, 'modes': modes[:600]})
        print(LX['eng_ack'].format(name=key, h=CFG['ack_hours'])); return 0
    for e in engines():
        print(f"{e.get('name') or '?'}: /{e['match']}/ → {' + '.join(docs_of(e))}" + (f" §{e['section']}" if e.get('section') else '')
              + (' · deny_first' if e.get('deny_first') else ''))
    return 0


# ---------------------------------------------------------------- E: the advisor's events (2.6, the council of 11.11)
def _today():
    return now_dt().date().isoformat()


def adv_calls_today():
    return sum(1 for r in acts(None, 24 * 60) if r.get('kind') == 'adv_call' and str(r.get('ts', ''))[:10] == _today())


def _adv(key, **kw):
    return LX[key].format(name=ADV['name'], w=ADV['brief_words'], n=adv_calls_today(), max=ADV['day_max'], **kw)


def advisor_call(tool, ti, sid):
    """an Agent call of the advisor's model → counted; past the day's ceiling or with a brief too long → a note (never a refusal)"""
    if not on('advisor') or tool not in ('Agent', 'Task'):
        return ''
    model = str(ti.get('model') or '').lower()
    if not model or not any(str(m).lower() in model for m in ADV['models']):
        return ''
    log({'kind': 'adv_call', 'session': sid, 'desc': str(ti.get('description') or '')[:80]})
    notes, n = [], adv_calls_today()
    if n > int(ADV['day_max']):
        notes.append(LX['adv_over'].format(name=ADV['name'], n=n, max=ADV['day_max']))
    words = len(str(ti.get('prompt') or '').split())
    if words > int(ADV['brief_words']):
        notes.append(LX['adv_long'].format(name=ADV['name'], words=words, w=ADV['brief_words']))
    return '\n'.join(notes)


def advisor_registry(sid):
    """event 3: an item of a registry (advisor.registries — JSONL files) marked advisor.mark and in work → one note per item and
    session; the file is read again only when it changed"""
    if not on('advisor') or not ADV['registries'] or DRY is not None:     # (a replay cannot know the registry of that day)
        return ''
    noted = {r.get('item') for r in acts(sid) if r.get('kind') == 'adv_note' and r.get('event') == 3}
    doing = {str(d).lower() for d in ADV['doing']}
    out = []
    for reg in ADV['registries']:
        f = reg if isinstance(reg, str) else (reg or {}).get('file')
        if not f:
            continue
        p = _doc_path(f)
        try:
            mt = int(os.path.getmtime(p))
        except OSError:
            continue
        if any(r.get('kind') == 'adv_reg' and r.get('file') == f and r.get('mt') == mt for r in acts(sid)):
            continue                                  # (unchanged since this session last looked)
        log({'kind': 'adv_reg', 'session': sid, 'file': f, 'mt': mt})
        for it in FM.jsonl(p):
            why = it.get(ADV['mark'])
            if not why or str(why).strip().lower() in ('0', 'false', 'no', 'нет') or it.get('id') in noted:
                continue
            if str(it.get('status') or '').lower() not in doing:
                continue
            log({'kind': 'adv_note', 'session': sid, 'event': 3, 'item': it.get('id')})
            noted.add(it.get('id'))
            out.append(_adv('adv_3', id=it.get('id'), title=str(it.get('title') or '')[:70],
                            why=f"{ADV['mark']}: {why}"[:90] if why is not True else ADV['mark']))
    return '\n'.join(out[:2])


REPEAT_N = {'TWICE': 2, 'THREE': 3, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5, 'дважды': 2, 'трижды': 3}


def prior_failures(text):
    """how many times a rule failed already, from its own history: «failed TWICE», «AGAIN … AGAIN», «a THIRD time», «a repeat of …»"""
    t = str(text)
    k = 1 + len(re.findall(r'\bAGAIN\b|\ba repeat of\b|\bповтор(?:ение)? ', t))
    for w, n in REPEAT_N.items():
        if re.search(r'\b' + w + r'\b', t):
            k = max(k, n)
    for m in re.finditer(r'\b(\d)\s*(?:times|раза?)\b', t):
        k = max(k, int(m.group(1)))
    return k


def advisor_prompt(cls, inp):
    """event 5 (the prompt hook): the owner's CORRECTION matches a rule whose history says it failed ≥ 2 times already → this is at
    least the third — the advisor on why the guard did not hold; once per rule a day"""
    if not on('advisor') or not cls or not cls.get('correction'):
        return ''
    R = FM.lessons()
    if not R:
        return ''
    hits, _ = R.gate(R.search(str(cls.get('text') or '')[:600], top=20), 0)
    h = next((x for x in hits if x['block'].kind == 'rule'), None)
    if not h:
        return ''
    b = h['block']
    lv = next((r for r in R.jsonl(R.RULES) if r.get('id') == b.ref), None)
    k = int(lv.get('level') or 0) if lv else prior_failures(b.text)
    if k < 2:
        return ''
    sid = str(inp.get('session_id') or '')
    if any(r.get('kind') == 'adv_note' and r.get('event') == 5 and r.get('rule') == b.ref and str(r.get('ts', ''))[:10] == _today()
           for r in acts(None, 24 * 60)):
        return ''
    log({'kind': 'adv_note', 'session': sid, 'event': 5, 'rule': b.ref})
    return _adv('adv_5', k=k, rule=re.sub(r'\s+', ' ', situation(_cells(b.text)[0] if b.text.startswith('|') else
                                                                 (lv or {}).get('when', b.label)))[:110])


def advisor_cmd(a):
    """advisor [days] — the journal: the events noted and the calls counted"""
    d = int(a[0]) if a and a[0].isdigit() else 7
    rows = [r for r in FM.jsonl(ACT) if r.get('kind') in ('adv_note', 'adv_call') and _age_min(r.get('ts')) <= d * 24 * 60]
    if not rows:
        print(LX['adv_none']); return 0
    ev = [r for r in rows if r['kind'] == 'adv_note']
    by = {}
    for r in ev:
        by[r.get('event')] = by.get(r.get('event'), 0) + 1
    days = {}
    for r in rows:
        days.setdefault(str(r.get('ts', ''))[:10], [0, 0])[r['kind'] == 'adv_call'] += 1
    print(LX['adv_head'].format(d=d, e=len(ev), by=', '.join(f'{k}: {v}' for k, v in sorted(by.items(), key=lambda kv: str(kv[0]))),
                                c=sum(1 for r in rows if r['kind'] == 'adv_call'),
                                days='; '.join(f'{k} {v[0]}/{v[1]}' for k, v in sorted(days.items()))))
    for r in rows[-20:]:
        print(f"  {str(r.get('ts', ''))[:16]} {r['kind']} {r.get('event', '')} {r.get('item') or r.get('rule') or r.get('desc') or r.get('sig') or ''}")
    return 0


# ---------------------------------------------------------------- the hook
def hook_act(inp, extra='', log_hook=True):
    """PreToolUse: one refusal at most (materials, an engine with deny_first, attempts with attempts_deny), otherwise the notes
    (an engine's section, the attempt warning, the hot rules for this action, the heartbeat, `extra` = the 2.4 path rule) → the JSON
    for Claude Code, or None"""
    tool = str(inp.get('tool_name') or '')
    ti = inp.get('tool_input') or {}
    sid = str(inp.get('session_id') or '')
    tr = inp.get('_rows') if inp.get('_rows') is not None else inp.get('transcript_path')
    deny = material_gate(tool, ti, sid)
    ek, et = ('', '') if deny else engine_gate(tool, ti, sid, tr)
    deny = deny or (et if ek == 'deny' else '')
    ak, at = ('', '') if deny else attempts(tool, ti, sid, inp.get('cwd'))
    deny = deny or (at if ak == 'deny' else '')
    if deny:
        if log_hook:
            FM.log_hook('tool', deny, tool=tool, decision='deny')
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': deny}}
    notes = [extra, et if ek == 'note' else '', at if ak == 'warn' else '', action_recall(tool, ti, sid), heartbeat(sid, tr, tool, ti)]
    if not (inp.get('agent_id') or inp.get('agent_type')):      # (E: the main session only — a subagent never calls for an advisor)
        notes += [advisor_call(tool, ti, sid), advisor_registry(sid)]
    text = FM.fit(notes, 1100)
    if not text:
        return None
    if log_hook:
        FM.log_hook('tool', text, tool=tool)
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': text}}


# ---------------------------------------------------------------- the quietness check
def _stream(path, since=None, until=None):
    """the transcript's rows read line by line (a real one is hundreds of MB): only the window [since, until] (local ISO times), only
    what the replay needs — the owner's text, the assistant's tool calls, the compaction marks; tool results are dropped"""
    lo = dt.datetime.fromisoformat(since) if since else None
    hi = dt.datetime.fromisoformat(until) if until else None
    out = []
    with io.open(path, 'rb') as f:
        for raw in f:
            if b'"tool_use"' not in raw and b'"type":"user"' not in raw and b'"type": "user"' not in raw:
                continue
            try:
                e = json.loads(raw.decode('utf-8', 'replace'))
            except ValueError:
                continue
            ts = e.get('timestamp')
            if (lo or hi) and ts:
                try:
                    t = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
                except ValueError:
                    continue
                if (lo and t < lo) or (hi and t > hi):
                    continue
            c = (e.get('message') or {}).get('content')
            if e.get('type') == 'assistant':
                uses = [b for b in c or [] if isinstance(b, dict) and b.get('type') == 'tool_use']
                if uses:
                    out.append({'type': 'assistant', 'timestamp': ts, 'message': {'content': uses}})
            elif e.get('type') == 'user':
                if e.get('isCompactSummary'):
                    out.append({'type': 'user', 'isCompactSummary': True, 'timestamp': ts, 'message': {'content': ''}})
                elif not (isinstance(c, list) and any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in c)):
                    out.append(e)
    return out


def replay_tools(path, a=()):
    """foreman.py replay --tools <transcript.jsonl> [--since 2026-11-09T12:00] [--until …] [--show] [--json]: B / ♥ / C / D (and A's
    gate on the owner's own messages in it) over every tool call of a real session, in the session's own time — nothing is written;
    → the numbers per 100 calls and the most frequent rules"""
    global DRY, CLOCK, REPLAY_OWNER
    opt = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None   # noqa: E731
    rows = _stream(path, opt('--since'), opt('--until')) if FM.lessons() and os.path.isfile(path) else []
    if not rows:
        print('no transcript rows:', path); return 1
    R = FM.lessons()
    DRY, mats, count, top, n, nb, no = [], [], {}, {}, 0, 0, 0
    sigs, engs, days = {}, {}, {}
    save_m = globals()['open_materials']
    globals()['open_materials'] = lambda: [m for m in mats if m.get('state') == 'new']
    try:
        for i, e in enumerate(rows):
            ts = e.get('timestamp')
            try:
                CLOCK = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00')).astimezone().replace(tzinfo=None) if ts else CLOCK
            except ValueError:
                pass
            if e.get('isCompactSummary'):
                compacted('replay')                  # (the session hook after a compaction — the heartbeat's first trigger)
                continue
            said = R._said(e)
            if said:
                no += 1
                REPLAY_OWNER = now()
                m = material_of(said) if on('materials') else None
                if m:
                    mats.append({'id': f'M-{len(mats) + 1:04}', 'ts': now(), 'session': 'replay', **m})
            if e.get('type') != 'assistant':
                continue
            for b in (e.get('message') or {}).get('content') or []:
                if not (isinstance(b, dict) and b.get('type') == 'tool_use'):
                    continue
                n += 1
                nb += b.get('name') in ('Bash', 'PowerShell')
                before = len(DRY)
                out = hook_act({'tool_name': b.get('name'), 'tool_input': b.get('input') or {}, 'session_id': 'replay',
                                '_rows': Upto(rows, i + 1), 'cwd': FM.PROJECT}, log_hook=False) or {}
                hs = out.get('hookSpecificOutput') or {}
                if hs.get('permissionDecision') == 'deny':
                    count['deny'] = count.get('deny', 0) + 1
                for r in DRY[before:]:
                    kind = r.get('kind')
                    k = ('recall' if kind == 'shown' else 'engine' if kind == 'eng_gate' or (kind == 'eng_seen' and not r.get('read'))
                         else 'materials' if kind == 'mat_gate' else 'attempts' if kind in ('att_warn', 'att_deny')
                         else 'heartbeat' if kind == 'beat' and r.get('rules') else 'advisor' if kind == 'adv_note' else '')
                    if k:
                        count[k] = count.get(k, 0) + 1
                        day = str(CLOCK.date()) if CLOCK else '?'
                        days.setdefault(day, {})[k] = days.setdefault(day, {}).get(k, 0) + 1
                        sg = f"{r.get('sig')}" + (f" @ {r['inp']}" if r.get('inp') else '')
                        if k == 'attempts':
                            sigs[sg] = sigs.get(sg, 0) + 1
                        if k == 'engine':
                            engs[r.get('engine')] = engs.get(r.get('engine'), 0) + 1
                        if '--show' in a:
                            what = r.get('rule') or r.get('rules') or (sg if r.get('sig') else '') or r.get('engine') or r.get('material')
                            sc = f" score={r['score']}" if r.get('score') is not None else ''
                            print(f"  {str(e.get('timestamp', ''))[:19]} {k}: {what}{sc} ← {b.get('name')} "
                                  f"«{str((b.get('input') or {}).get('description') or '')[:70]}» "
                                  f"cmd=«{str((b.get('input') or {}).get('command') or '')[:160]}» q=«{str(r.get('q') or '')[:110]}»")
                    if kind in ('shown', 'beat_rule'):
                        top[r['rule']] = top.get(r['rule'], 0) + 1
    finally:
        DRY, CLOCK, REPLAY_OWNER = None, None, None
        globals()['open_materials'] = save_m
    # (the advisor's event 2 rides on an attempt warning — the same note, not a second one)
    notes = sum(count.get(k, 0) for k in ('recall', 'heartbeat', 'attempts', 'engine', 'materials'))
    print(LX['rp_head'].format(f=os.path.basename(str(path)), n=n, b=nb, o=no))
    for k in ('recall', 'heartbeat', 'attempts', 'engine', 'materials', 'advisor', 'deny'):
        print(LX['rp_line'].format(k=k, n=count.get(k, 0), per=100.0 * count.get(k, 0) / max(n, 1)))
    print(LX['rp_line'].format(k='ALL notes', n=notes, per=100.0 * notes / max(n, 1)))
    print('  modules: ' + ', '.join(f"{m}={'on' if on(m) else 'off'}"
                                    for m in ('materials', 'act_recall', 'heartbeat', 'attempts', 'engines', 'advisor')))
    for day, c in sorted(days.items()):
        print(f'  {day}: ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())))
    if sigs:
        print('  attempts: ' + ', '.join(f'{k} ×{v}' for k, v in sorted(sigs.items(), key=lambda kv: -kv[1])))
    if engs:
        print('  engines: ' + ', '.join(f'{k} ×{v}' for k, v in sorted(engs.items(), key=lambda kv: -kv[1])))
    if top:
        print(LX['rp_top'].format(list=', '.join(f'{k} ×{v}' for k, v in sorted(top.items(), key=lambda kv: -kv[1])[:10])))
    if '--json' in a:
        print(json.dumps({'calls': n, 'bash': nb, 'owner': no, **count, 'notes': notes, 'days': days, 'attempt_sigs': sigs,
                          'engines': engs, 'top': top}, ensure_ascii=False))
    return 0
