"""recall.py — Foreman's LESSONS module (2.0): the owner's rulings and corrections as RULES, found again before the next
action. Promises say WHAT the owner asked (closed by probes); lessons say HOW the owner wants things done (in force at a level).
Ported from the «Harness²» memory of the project Foreman was born in (stemmed RU/EN BM25 recall with a trigger field, the
lesson protocol on a correction cue, a Stop gate, a ledger) and decided by a council of three models on 2026-11-04.

Files in .foreman/: rules.jsonl (the rules), ledger.md (kept / revised / dropped -> what -> evidence), eval.jsonl (recall test
cases that grow from corrections), events.jsonl (cue statistics, guard states, board events), lexicon.json (RU<->EN concept groups),
RULES.md (rendered for people). Read-only sources: CLAUDE.md, Claude Code's own memory folder, .claude/skills/*/SKILL.md, and
`lessons.rules_extra` globs (markdown tables / ### sections of an existing rule book).

A rule: {"id": "R-003", "when": "<the situation, its SHAPE>", "do": "<the operation, checkable>", "quote": "<the owner, verbatim>",
  "keys": "RU/EN words to find it", "level": 0..3, "status": "proposed|active|dropped", "situation": "<the owner's message>",
  "not_situation": "<a message it must NOT fire on>", "guard": "file:/grep:/nogrep:/doc: probe" (level 3), "source", "date"}
  level 0 note (ledger only) · 1 row (recalled by words) · 2 hot (always in the session brief) · 3 guard (a probe checked at Stop).
  A rule is born «proposed» (recalled as a hint); the OWNER's word makes it «active» (`rule accept`); only an active rule may be
  hot or a guard — an agent's guess is never a law.

  python .foreman/foreman.py recall <words of what you are about to do> [--top 5] [--json] [--explain]
  python .foreman/foreman.py rule add '{"when": …, "do": …, "quote": …, "keys": …}' [--situation "…"] [--not "…"]   (or @file.json)
  python .foreman/foreman.py rule accept R-003 | set R-003 level=2 keys="…" | drop R-003 --why "…" | list [R-003|--hot|--guards|--proposed]
  python .foreman/foreman.py recall --eval          recall@3 on eval.jsonl + false positives + every miss
  python .foreman/foreman.py ledger "revised -> R-003 keys -> recall missed «grid»"
  python .foreman/foreman.py lesson "<the owner's message>"      the protocol filled in for this message
  python .foreman/foreman.py cues --stats           how often each correction / teaching cue fired
Standard library only, Python 3.8+."""
import datetime as dt
import glob
import io
import json
import math
import os
import re
import sys
import uuid
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
RULES, LEDGER, EVAL, EVENTS, LEXICON, RULES_MD = (os.path.join(HERE, n) for n in
                                                  ('rules.jsonl', 'ledger.md', 'eval.jsonl', 'events.jsonl', 'lexicon.json', 'RULES.md'))
DEFAULTS = {'stop_gate': 'correction', 'extra_correction_cues': [], 'extra_teaching_cues': [], 'rules_extra': [],
            'record_paths': [], 'record_hint': '', 'confirm_days': 60, 'edit_gate': 'on', 'guard_paths': [], 'memory_dir': 'auto',
            'index_skills': True, 'absence_days': 30}
# (2.4, CCGS .claude/rules/agent-memory.md, read 07.11: «Never record a temporary absence as a durable fact» — «X is not installed»
#  is true the day it is written and harmful later; a narrow pattern (Fable 07.11: a bare «нет» is everywhere in Russian), warn only)
ABSENCE = re.compile(r"не установлен|отсутству|not installed|does(?:n't| not) exist|\bнет (?:весов|модели|файла|папки|доступа|поддержки)"
                     r"|\bno \w+ yet\b|\b(?:ещё|еще|пока) нет\b|isn't (?:installed|available)", re.I)
BUDGET = {'prompt_chars': 1200, 'session_chars': 2000, 'recall_hits': 3, 'recall_chars': 700, 'hot_rows': 5}
CFG, LANG, LX = {'lessons': dict(DEFAULTS), 'budget': dict(BUDGET)}, 'ru', {}


def setup(cfg, lang):
    """called by foreman.py with its merged config"""
    global CFG, LANG, LX
    CFG = {**cfg, 'lessons': {**DEFAULTS, **(cfg.get('lessons') or {})}, 'budget': {**BUDGET, **(cfg.get('budget') or {})}}
    LANG = lang if lang in TXT else 'ru'
    LX = TXT[LANG]


# ---------------------------------------------------------------- texts (RU / EN)
TXT = {
    'ru': {'reflect_c': ('ПРОРАБ·урок: похоже на ПОПРАВКУ («{cue}»). До конца хода: (1) правило уже есть? (recall) — назови, почему не '
                         'сработало; (2) корень причины; (3) где ещё повторится; (4) повтор → уровень выше; (5) ОДНО правило: python '
                         '.foreman/foreman.py rule add \'{{"when", "do", "quote": дословно, "keys"}}\' --situation "<это сообщение>". В конце '
                         'ответа — «записано: R-…» (после записи) или «не поправка: <почему>».'),
           'reflect_t': ('ПРОРАБ·урок: похоже на УЧЁБУ — приём или предпочтение (сработало «{cue}»). Если это стоит запомнить — rule add '
                         '(уровень 1, статус «предложено» до слова владельца); иначе ответь «не поправка: <почему>».'),
           'reflect_c_own': ('ПРОРАБ·урок: похоже на ПОПРАВКУ («{cue}»). До конца хода: (1) правило уже есть? (recall) — назови, почему не '
                             'сработало; (2) корень причины; (3) где ещё повторится; (4) повтор → уровень выше; (5) запись: {hint}. В конце '
                             'ответа — «записано: <где>» (после записи) или «не поправка: <почему>».'),
           'reflect_t_own': ('ПРОРАБ·урок: похоже на УЧЁБУ — приём или предпочтение (сработало «{cue}»). Если это стоит запомнить — '
                             'запись: {hint}; иначе ответь «не поправка: <почему>».'),
           'gate_own': 'Запись в этом проекте: {hint}.',
           'pack_head': 'ПРОРАБ·память (по сообщению):', 'pack_more': 'Больше: python .foreman/foreman.py recall <что собираюсь сделать>',
           'gate': ('ПРОРАБ·урок (Stop): последнее сообщение владельца похоже на {kind} (сработало «{cue}»): «{text}». С тех пор ничего не '
                    'записано в правила / журнал / память, а в ответе нет «не поправка: <почему>» или «уже записано: R-…». Перед остановкой: '
                    'протокол урока (правило уже есть? корень, где ещё, ОДНО правило rule add … --situation) и строка «записано: R-…» — '
                    'или «не поправка: <почему>», если это не урок.'),
           'kind_c': 'ПОПРАВКУ', 'kind_t': 'УЧЁБУ', 'bad_level': 'уровень — число 0…3',
           'accept_lock': 'Правила заняты другим процессом — приёмка без замка не пишется; повторите.',
           'edit_gate': ('ПРОРАБ·правка проверок (Stop): за этот ход правились файлы самого Прораба / настройки хуков / охраняемые пути '
                         'или вызывалась доска: {what}. Если это по слову владельца или нужно для работы — скажи это строкой '
                         '«правка проверок: <почему>»; если нет — верни как было.'),
           'stale': 'Правила давно не подтверждались (> {days} дн.; rule confirm / replace)',
           'deferred_line': 'Отложенные уроки за 30 дней: {n}, из них старше недели (решите): {old} — python .foreman/foreman.py cues --deferred',
           'guard': 'ПРОРАБ·страж: правило {id} («{when}») нарушено: {probe} красная. Исправь или скажи владельцу.',
           'hot': 'Горячие правила', 'guards_red': 'Стражи красные', 'proposed': 'Правила ждут вашего «да» (rule accept)',
           'added': 'записано: {id} (статус «предложено» — станет «принято» словом владельца: rule accept {id})',
           'refuse': 'правилу нужны непустые when, do и quote (дословно); можно @файл.json',
           'absence_warn': 'внимание: правило говорит о том, чего НЕТ («{m}») — со временем это станет неправдой. Добавьте "as_of": "ГГГГ-ММ-ДД" (на какой день верно) или пробу вместо слов.',
           'absence_mark': ' · проверить: «{m}» — на {d}',
           'keys_long': 'внимание: в keys больше 12 слов — правило будет находиться где не надо',
           'guard_kind': 'страж — только проба file:/grep:/nogrep:/doc: (get:/cmd: — нет)',
           'only_active': 'горячим (уровень 2) и стражем (уровень 3) бывает только правило, принятое владельцем (rule accept)',
           'no_rule': 'нет правила', 'eval_head': 'Поиск по eval.jsonl: {n} случаев · recall@3 {r3} · ложных срабатываний {fp}',
           'eval_none': 'eval.jsonl пуст — случаи появляются с rule add --situation', 'miss': '  промах', 'fp': '  ложное',
           'ledger_ok': 'журнал: {line}', 'nothing': '(ничего не найдено — правил нет или слова не совпали)',
           'rules_title': '# Правила владельца — {when}', 'cues_head': 'Сработавшие признаки (events.jsonl):'},
    'en': {'reflect_c': ('FOREMAN·lesson: looks like a CORRECTION («{cue}»). Before the turn ends: (1) already a rule? (recall) — name it, why it '
                         'did not fire; (2) the root cause; (3) where else it repeats; (4) a repeat → a level up; (5) ONE rule: python '
                         '.foreman/foreman.py rule add \'{{"when", "do", "quote": verbatim, "keys"}}\' --situation "<this message>". End the '
                         'reply with «recorded: R-…» (after writing it) or «not a correction: <why>».'),
           'reflect_t': ('FOREMAN·lesson: this looks like a TEACHING — a technique or a preference (cue «{cue}»). Worth keeping → rule add '
                         '(level 1, «proposed» until the owner says yes); otherwise answer «not a correction: <why>».'),
           'reflect_c_own': ('FOREMAN·lesson: looks like a CORRECTION («{cue}»). Before the turn ends: (1) already a rule? (recall) — name it, '
                             'why it did not fire; (2) the root cause; (3) where else it repeats; (4) a repeat → a level up; (5) record: {hint}. '
                             'End the reply with «recorded: <where>» (after writing it) or «not a correction: <why>».'),
           'reflect_t_own': ('FOREMAN·lesson: this looks like a TEACHING — a technique or a preference (cue «{cue}»). Worth keeping → '
                             'record: {hint}; otherwise answer «not a correction: <why>».'),
           'gate_own': 'In this project the record goes: {hint}.',
           'pack_head': 'FOREMAN·recall (by the message):', 'pack_more': 'More: python .foreman/foreman.py recall <what I am about to do>',
           'gate': ('FOREMAN·lesson (Stop): the owner\'s last message looks like a {kind} (cue «{cue}»): «{text}». Nothing was written to '
                    'the rules / ledger / memory since, and the reply has no «not a correction: <why>» or «already recorded: R-…». Before '
                    'stopping: the lesson protocol (already a rule? root cause, where else, ONE rule add … --situation) and the line '
                    '«recorded: R-…» — or «not a correction: <why>» if it is not a lesson.'),
           'kind_c': 'CORRECTION', 'kind_t': 'TEACHING', 'bad_level': 'the level is a number 0…3',
           'accept_lock': 'The rules are busy — an acceptance is never written without the lock; try again.',
           'edit_gate': ('FOREMAN·checks edited (Stop): this turn edited Foreman\'s own files / the hook settings / guarded paths or drove '
                         'the board: {what}. If the owner asked for it or the work needs it, say so in a line «checks edited: <why>»; '
                         'if not, undo it.'),
           'stale': 'Rules not confirmed for long (> {days} days; rule confirm / replace)',
           'deferred_line': 'Deferred lessons in 30 days: {n}, older than a week (decide): {old} — python .foreman/foreman.py cues --deferred',
           'guard': 'FOREMAN·guard: rule {id} («{when}») is broken: {probe} is red. Fix it or tell the owner.',
           'hot': 'Hot rules', 'guards_red': 'Red guards', 'proposed': 'Rules waiting for your «yes» (rule accept)',
           'added': 'recorded: {id} (status «proposed» — the owner\'s word makes it «active»: rule accept {id})',
           'refuse': 'a rule needs non-empty when, do and quote (verbatim); @file.json works',
           'absence_warn': 'note: the rule states that something is ABSENT («{m}») — that turns false with time. Add "as_of": "YYYY-MM-DD" (the day it was true) or a probe instead of words.',
           'absence_mark': ' · re-check: «{m}» — as of {d}',
           'keys_long': 'note: more than 12 words in keys — the rule will fire where it should not',
           'guard_kind': 'a guard is a file:/grep:/nogrep:/doc: probe only (no get:/cmd:)',
           'only_active': 'only a rule the owner accepted (rule accept) may be hot (level 2) or a guard (level 3)',
           'no_rule': 'no rule', 'eval_head': 'Recall on eval.jsonl: {n} cases · recall@3 {r3} · false positives {fp}',
           'eval_none': 'eval.jsonl is empty — cases come with rule add --situation', 'miss': '  miss', 'fp': '  false',
           'ledger_ok': 'ledger: {line}', 'nothing': '(nothing found — no rules yet, or no words matched)',
           'rules_title': '# The owner\'s rules — {when}', 'cues_head': 'Cues that fired (events.jsonl):'},
}
LX = TXT['ru']


# ---------------------------------------------------------------- files (the same lock as foreman.py: .foreman/.lock)
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
                pass
    return out


def write_text(p, text):
    tmp = f'{p}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp'      # (a unique temp name: two writers never share one)
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, p)


def write_jsonl(p, rows):
    write_text(p, ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))


def append_jsonl(p, row):
    with io.open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def today():
    return dt.date.today().isoformat()


def arg_json(s):
    if s.startswith('@') and os.path.isfile(s[1:]):
        s = read(s[1:])
    return json.loads(s)


# ---------------------------------------------------------------- tokens and stems (from Harness² recall_v2)
RU_SUFFIXES = sorted(['иями', 'ями', 'ами', 'ого', 'его', 'ому', 'ему', 'ыми', 'ими', 'ешь', 'ете', 'ите', 'ишь',
                      'ым', 'им', 'ых', 'их', 'ою', 'ею', 'ись', 'ась', 'ясь', 'ься',
                      'ует', 'уют', 'ает', 'яет', 'ают', 'яют', 'ала', 'ила', 'ыла', 'ать', 'ять', 'ить', 'еть',
                      'ая', 'яя', 'ое', 'ее', 'ые', 'ие', 'ой', 'ей', 'ый', 'ий', 'ую', 'юю', 'ом', 'ем', 'ах', 'ях',
                      'ов', 'ев', 'ам', 'ям', 'ут', 'ют', 'ит', 'ат', 'ят', 'ал', 'ил', 'ла', 'ли', 'ло', 'ть',
                      'у', 'ю', 'а', 'я', 'о', 'е', 'ы', 'и', 'ь', 'й'], key=len, reverse=True)
EN_SUFFIXES = ['ations', 'ation', 'ingly', 'ings', 'ing', 'edly', 'ness', 'ies', 'ied', 'ers', 'ed', 'es', 'ly', 's']
STOP = set('''the a an of to in on for and or is are be was were it its this that with as at by from not no
into than then so if we our their his her he she they them you your i me my do did does done have has had can
could would should may might will shall just only also very more most such per each every any all some one two
и в во на с со к ко по из за от до у о об обо для при про над под без через это этот эта эти тот та те как что
чтобы что бы же ли не ни да нет а но или либо уже ещё еще тоже также так там тут здесь если то тогда когда где
куда откуда потом сначала сейчас есть был была было были быть будет буду будем мне меня мной мы нас нам
ты тебя тебе вы вас вам он она оно они его её их ему ей им них нём ней ими сам сама само сами свой своя свое
свои весь вся всё все очень можно нужно надо пусть ну вот ведь'''.split())
CYR = re.compile(r'[а-яё][а-яё\-]*')
TOKEN = re.compile(r'[a-z0-9][a-z0-9_\-\.]*|[а-яё][а-яё\-]*')


def stem(word):
    """to a fixpoint: one pass is not idempotent (результаты → результат → результ), and a rule's keys and the owner's phrasing
    must meet whatever form each was written in (review 04.11)"""
    w = word.lower().strip('.-_')
    if not w or w in STOP:
        return ''
    for _ in range(3):
        s = _stem1(w)
        if s == w:
            break
        w = s
    return w


def _stem1(w):
    if CYR.fullmatch(w):
        if len(w) <= 4:
            return w
        for suf in RU_SUFFIXES:
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[: -len(suf)]
                break
        if len(w) > 5 and w[-1] in 'иыаяуюое':           # (a second short ending after a long one)
            w = w[:-1]
        if len(w) > 5 and w[-2:] in ('ок', 'ек'):         # (the fleeting vowel: ошибок → ошибк, like ошибка)
            w = w[:-2] + 'к'
        if len(w) >= 5 and w[-4:-3] in 'ае' and w.endswith('мен'):   # (время / времени, пламя / пламени meet: врем, плам)
            w = w[:-2]
        return w
    if len(w) <= 3:
        return w
    for suf in EN_SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def tokens(text):
    return [s for s in (stem(t) for t in TOKEN.findall(str(text).lower().replace('ё', 'е'))) if s and len(s) >= 2]


def lexicon():
    """→ ({concept: [stemmed phrases]}, {law: {concept: weight}}) — RU<->EN words of one idea (a query word pulls its partners in at
    weight 0.55) and, optionally, the concepts that point at a law of a rule book (`"triggers"`, as in Harness²)"""
    try:
        raw = json.load(io.open(LEXICON, encoding='utf-8'))
    except (OSError, ValueError):
        raw = {}
    concepts = {cid: [' '.join(tokens(p)) for p in group if tokens(p)] for cid, group in (raw.get('concepts') or {}).items()}
    return concepts, raw.get('triggers') or {}


def concepts_in(query_text, concepts):
    low = ' '.join(tokens(query_text))
    return {cid for cid, group in concepts.items()
            if any((p in low) if ' ' in p else re.search(r'(^| )' + re.escape(p) + r'( |$)', low) for p in group)}


def expand(q_tokens, found, concepts):
    weights = {t: 1.0 for t in q_tokens}
    for cid in found:
        for p in concepts[cid]:
            for t in p.split():
                weights.setdefault(t, 0.55)
    return weights


# ---------------------------------------------------------------- the sources (all read-only except rules.jsonl)
class Block:
    __slots__ = ('kind', 'src', 'ref', 'text', 'tf', 'length', 'trigger', 'label', 'tags', 'law')

    def __init__(self, kind, src, ref, text, trigger_text, label, tags=(), law=''):
        self.kind, self.src, self.ref, self.text, self.label = kind, src, ref, text, label
        self.tags, self.law = list(tags), law          # (a rule book's row tagged [P2·P1] / a law section «### P2 · …»)
        self.tf = Counter(tokens(text))
        self.length = sum(self.tf.values())
        self.trigger = Counter(tokens(trigger_text))


def memory_dir():
    m = CFG['lessons'].get('memory_dir') or 'auto'
    if m != 'auto':
        return m if os.path.isabs(m) else os.path.join(ROOT, m)
    slug = re.sub(r'[^A-Za-z0-9]', '-', ROOT)      # (Claude Code's own memory: ~/.claude/projects/<slug>/memory)
    d = os.path.join(os.path.expanduser('~'), '.claude', 'projects', slug, 'memory')
    return d if os.path.isdir(d) else os.path.join(ROOT, 'memory')


def frontmatter(text, key):
    m = re.search(r'^' + key + r':\s*(.+)$', text[:2000], re.M)
    return m.group(1).strip().strip('"\'') if m else ''


def absence_mark(r):
    """a rule about something ABSENT, older than lessons.absence_days (from its as_of, else its date) → «re-check» in recall (2.4)"""
    m = ABSENCE.search(f"{r.get('when', '')} {r.get('do', '')}")
    if not m:
        return ''
    d = str(r.get('as_of') or r.get('date') or '')[:10]
    try:
        old = (dt.date.today() - dt.date.fromisoformat(d)).days > int(CFG['lessons'].get('absence_days', 30))
    except ValueError:
        old = True
    return LX['absence_mark'].format(m=m.group(0), d=d or '?') if old else ''


def rule_blocks():
    out = []
    for r in jsonl(RULES):
        if r.get('status') in ('dropped', 'replaced') or not r.get('when'):
            continue
        text = f"{r.get('when')} → {r.get('do')} «{r.get('quote', '')}» {r.get('keys', '')} {' '.join(r.get('tags') or [])}"
        label = f"{r['id']} {'' if r.get('status') == 'active' else '(предл.) ' if LANG == 'ru' else '(proposed) '}" \
                f"{r.get('when')} → {r.get('do')}" + (f" («{r['quote'][:60]}»)" if r.get('quote') else '') + absence_mark(r)
        out.append(Block('rule', RULES, r['id'], text, f"{r.get('when')} {r.get('keys', '')}", label))
    return out


def _rel(f):
    """the path relative to the project — or the absolute one: a rule book on another drive has no relative path (2.5: relpath raised
    and took the whole recall down)"""
    try:
        return os.path.relpath(f, ROOT).replace('\\', '/')
    except ValueError:
        return f.replace('\\', '/')


def extra_blocks():
    """an existing rule book, read as it is: every markdown table row (its first cell and a Keys cell are the trigger) and every
    ### section (its heading and **Test:** / **Keys** lines)"""
    out = []
    for g in CFG['lessons'].get('rules_extra') or []:
        for f in sorted(glob.glob(g if os.path.isabs(g) else os.path.join(ROOT, g), recursive=True)):
            text, rel = read(f), _rel(f)
            for i, line in enumerate(text.splitlines(), 1):
                if line.startswith('| ') and not re.match(r'^\|[\s\-|:]+\|?$', line) and line.count(' | ') >= 2:
                    cells = [c.strip() for c in line.strip().strip('|').split(' | ')]
                    tags = re.findall(r'P\d+', re.match(r'^(\[[^\]]*\])?', cells[0]).group(0) or '')
                    when = re.sub(r'^\[[^\]]*\]\s*', '', cells[0])
                    if when.lower() in ('when', 'когда', 'что', 'кто', 'вопрос'):
                        continue
                    keys = cells[-1] if cells[-1].lower().startswith(('keys', 'ключи')) or len(cells) >= 4 else ''
                    out.append(Block('rule', f, f'{rel}:{i}', line, f'{when} {keys}', f'{rel}:{i} {when[:110]}', tags))
            for m in re.finditer(r'^###\s+(.+?)$(.*?)(?=^#{2,3}\s|\Z)', text, re.M | re.S):
                head, body = m.group(1), m.group(2)
                trig = head + ' ' + ' '.join(re.findall(r'\*\*(?:Test|Keys)[^*]*\*\*:?\s*(.*)', body))
                law = re.match(r'(P\d+)\b', head)
                out.append(Block('rule', f, f'{rel}#{head[:30]}', head + ' ' + body[:3000], trig, f'{rel} — {head[:110]}',
                                 law=law.group(1) if law else ''))
    return out


def file_blocks():
    out = []
    for line in read(LEDGER).splitlines():
        if line.startswith('- '):
            out.append(Block('ledger', LEDGER, 'ledger', line, '', 'ledger: ' + line[2:150]))
    md = memory_dir()
    for f in sorted(glob.glob(os.path.join(md, '*.md'))):
        if os.path.basename(f) == 'MEMORY.md':
            continue
        t = read(f)
        desc = frontmatter(t, 'description')
        out.append(Block('memory', f, 'memory/' + os.path.basename(f), t[:6000], frontmatter(t, 'name') + ' ' + desc,
                         'memory/' + os.path.basename(f) + ' — ' + desc[:110]))
    if CFG['lessons'].get('index_skills', True):
        for f in sorted(glob.glob(os.path.join(ROOT, '.claude', 'skills', '*', 'SKILL.md'))):
            t = read(f)
            name = os.path.basename(os.path.dirname(f))
            out.append(Block('skill', f, 'skill ' + name, t[:6000], name + ' ' + frontmatter(t, 'description'),
                             f'skill {name} — ' + frontmatter(t, 'description')[:110]))
    cm = os.path.join(ROOT, 'CLAUDE.md')
    for i, para in enumerate(re.split(r'\n\s*\n', read(cm))):
        if len(para.strip()) > 40:
            out.append(Block('claude', cm, f'CLAUDE.md §{i + 1}', para, para[:160], 'CLAUDE.md: ' + para.strip()[:110]))
    return out


def all_blocks():
    return rule_blocks() + extra_blocks() + file_blocks()


# ---------------------------------------------------------------- search (BM25 with a trigger field — Harness² recall_v2)
def search(query, blocks=None, top=8):
    blocks = blocks if blocks is not None else all_blocks()
    q = tokens(query)
    if not q or not blocks:
        return []
    concepts, triggers = lexicon()
    found = concepts_in(query, concepts)
    terms = expand(q, found, concepts)
    top_laws = laws(blocks, q, found, triggers)
    n = len(blocks)
    df, tdf = Counter(), Counter()
    for b in blocks:
        df.update(t for t in b.tf if t in terms)
        tdf.update(t for t in b.trigger if t in terms)
    avg = sum(b.length for b in blocks) / max(n, 1)
    tavg = sum(sum(b.trigger.values()) for b in blocks) / max(1, sum(1 for b in blocks if b.trigger))
    k1, bb, out = 1.4, 0.75, []
    for b in blocks:
        s, trig_hit = 0.0, False
        for t, w in terms.items():
            tf = b.tf.get(t, 0)
            if tf:
                s += w * math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * tf * (k1 + 1) / (tf + k1 * (1 - bb + bb * b.length / avg))
            tt = b.trigger.get(t, 0)
            if tt:
                tl = sum(b.trigger.values())
                s += 1.6 * w * math.log(1 + (n - tdf[t] + 0.5) / (tdf[t] + 0.5)) * tt * (k1 + 1) / (tt + k1 * (1 - bb + bb * tl / max(tavg, 1)))
                trig_hit = trig_hit or w >= 1.0           # (a synonym only re-ranks: as a trigger it let «README» call a «docs»
                                                          #  rule — measured 04.11: false positives 1/4 → 2/4, our pack 0.91 → 0.89)
        if s <= 0:
            continue
        own = len({t for t in q if b.tf.get(t) or b.trigger.get(t)})
        s *= 1.15 if b.kind == 'rule' else 0.9 if b.kind == 'ledger' else 1.0
        if top_laws:                                  # (the family of the law the situation falls under — Harness²: +0.45 / +0.25)
            s *= 1.0 + (0.45 if b.tags and b.tags[0] == top_laws[0] else 0.25 if set(b.tags) & set(top_laws) else 0.0)
        out.append({'score': s, 'block': b, 'own': own, 'trig': trig_hit})
    out.sort(key=lambda h: -h['score'])
    return out[:top] if top else out


def laws(blocks, q, found, triggers):
    """a rule book with LAWS («### P1 · …» sections, rows tagged [P1]): which law does the situation fall under? BM25 of the query
    against each law's document (its section + the When cells of its rows ×2) + the lexicon's action triggers → up to 2 laws
    scoring ≥ half the best. Nothing when the rule book has no laws (a stranger's project)."""
    docs = {}
    for b in blocks:
        if b.law:
            docs.setdefault(b.law, Counter()).update(b.tf)
    if not docs:
        return []
    for b in blocks:
        for t in b.tags:
            if t in docs:
                docs[t].update({k: 2 * v for k, v in b.trigger.items()})
    n, df = len(docs), Counter()
    for d in docs.values():
        df.update(d.keys())
    avg = sum(sum(d.values()) for d in docs.values()) / n
    scores = {}
    for law, d in docs.items():
        dl = sum(d.values())
        sc = sum(math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * d[t] * 2.2 / (d[t] + 1.2 * (0.25 + 0.75 * dl / avg))
                 for t in set(q) if t in d)
        sc += 3.0 * sum(w for c, w in (triggers.get(law) or {}).items() if c in found)
        scores[law] = sc
    best = max(scores.values())
    return [k for k, v in sorted(scores.items(), key=lambda kv: -kv[1]) if best > 0 and v >= 0.5 * best][:2]


def gate(hits, n_query):
    """what keeps the pack quiet: the situation must match what an entry is FOR (its trigger), with ≥ 2 own words, and be near the best"""
    if not hits:
        return [], []
    best, keep, drop, seen = hits[0]['score'], [], [], set()
    for h in hits:
        b = h['block']
        # (one own word is enough once it hits the TRIGGER: «≥ 2» dropped the rules' own situations — recall@3 3/10 → 7/10 with the
        #  fixpoint stem, our 65 cases 0.82 → 0.91, review 04.11)
        why = ('no_trigger_match' if not h['trig'] else 'few_words' if h['own'] < 1 else
               'low_score' if h['score'] < 0.35 * best else 'same_file' if b.kind in ('memory', 'skill') and b.src in seen else '')
        (drop if why else keep).append((h, why))
        if not why:
            seen.add(b.src)
    return [h for h, _ in keep], [(h, w) for h, w in drop]


def pack(query):
    """the recall pack for a message: ≤ recall_hits lines of ≤ 180 chars, ≤ recall_chars in all; '' when nothing passes the gate"""
    bud = CFG['budget']
    hits, _ = gate(search(query, top=20), len(set(tokens(query))))
    lines = []
    for h in hits[:bud['recall_hits']]:
        line = '  ' + h['block'].label[:178]
        if sum(len(x) + 1 for x in lines) + len(line) > bud['recall_chars'] - len(LX['pack_head']) - len(LX['pack_more']) - 4:
            break
        lines.append(line)
    return '\n'.join([LX['pack_head']] + lines + [LX['pack_more']]) if lines else ''


# ---------------------------------------------------------------- cues: is this message a correction or a teaching?
def _W(s):
    return re.compile(r'(?<![а-яёa-z0-9])' + s + r'(?![а-яёa-z0-9])')


def _L(s):
    return re.compile(r'(?<![а-яёa-z0-9])' + s)


CORRECTION = [re.compile(x) if isinstance(x, str) else x for x in [
    # RU — measured on 358 real messages of the project Foreman was born in (precision first)
    r'забыл[аи]?', _W('опять'), _W('снова'), r'не похож', r'на глаз', r'неприемлем', r'я (же |тебе )?(говорил|просил|учил)',
    r'помнишь', r'запомни', r'не использ(уешь|овала|уй)', r'сколько можно', r'ошиб(ка|ки|ок|лась|ся|очно)', r'перестань',
    r'никогда не', _L('не делай'), r'на будущее', r'не угадыв', r'не спеши', r'памятк', _W('правил[оа]'), r'неправильн',
    r'не соответств', r'не то, что', r'халтур', r'нужно обязательно', r'обязательно провер', _L('всегда (использ|делай|провер|сначала)'),
    r'почему .{0,40}(такой|такая|такие|странн|плох)', r'что-то не то', r'не годится', r'это плохо', r'много ошибок',
    # EN starter, precision first
    r'you forgot', r'\bagain\b(?! (try|run))', r'i (told|asked) you', r"don'?t ever", r'never do', r"that'?s (not what|wrong)",
    r'stop doing', r'from now on', r'always .{0,30} first', r'not acceptable', r'not what i asked']]
TEACHING = [re.compile(x) if isinstance(x, str) else x for x in [
    _W('приём'), _W('приемы?'), r'можно (попросить|поручать|поручить|передать)', r'лучше (сначала|попроси|подготовь)',
    r'нужно (сказать|говорить|передавать|просить)', r'обычно использ', r'всегда (можешь|можно)', r'с осторожн', r'быть осторожн',
    r'я тестировал', r'на мой вкус', r'лучше всего (подходит|делать)', r'пригодится',
    r'\btip:', r'\ba trick\b', r'you can ask', r'\bbetter to\b', r'usually (i|we)\b', r'be careful with', r'i tested', r'in my experience']]
SHORT = re.compile(r'^(да|ок|окей|хорошо|отлично|продолжай|продолжи|yes|ok|okay|go on|continue|thanks|спасибо)[.!]?$', re.I)
AGENT_NOTE = re.compile(r'^(Another Claude session sent a message|\[SYSTEM NOTIFICATION|<task-notification|<agent-message|<cross-session-message)')
REMINDER = re.compile(r'<system-reminder[^>]*>[\s\S]*?</system-reminder[^>]*>')


def owner_text(text):
    """the owner's own words: the app's <system-reminder> blocks cut; a subagent's hand-back or a background notice is not the owner"""
    t = REMINDER.sub('', str(text or '')).strip()
    if not t or AGENT_NOTE.match(t) or '[Subagent hand-back]' in t[:400] or re.match(r'^<(local-command|command-name|task-notification)', t):
        return ''
    return t


def classify(text):
    t = owner_text(text)
    if not t or SHORT.match(t) or len(t) < 12:
        return {'correction': None, 'teaching': None, 'text': t}
    low = t.lower()
    extra_c = [re.compile(x) for x in CFG['lessons'].get('extra_correction_cues') or []]
    extra_t = [re.compile(x) for x in CFG['lessons'].get('extra_teaching_cues') or []]
    hit = lambda cues: next((m.group(0) for m in (c.search(low) for c in cues) if m), None)
    return {'correction': hit(CORRECTION + extra_c), 'teaching': hit(TEACHING + extra_t), 'text': t}


def reflector(cls):
    hint = str(CFG['lessons'].get('record_hint') or '')[:160]     # (a project with its own rule book: one book, not two)
    own = '_own' if hint else ''
    if cls['correction']:
        return LX['reflect_c' + own].format(cue=cls['correction'], hint=hint)
    if cls['teaching']:
        return LX['reflect_t' + own].format(cue=cls['teaching'], hint=hint)
    return ''


def log_cue(cls):
    kind = 'correction' if cls['correction'] else 'teaching' if cls['teaching'] else ''
    if kind:
        append_jsonl(EVENTS, {'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'detector', 'kind': 'cue', 'cue_kind': kind,
                              'cue': cls['correction'] or cls['teaching'], 'head': cls['text'][:80]})


# ---------------------------------------------------------------- the Stop gate: a correction must leave a RECORD
KNOWLEDGE = re.compile(r'rules\.jsonl|ledger\.md|lexicon\.json|eval\.jsonl|foreman\.py[\'"]? (rule|ledger)|[\\/]memory[\\/][^\\/]+\.md|'
                       r'SKILL\.md|CLAUDE\.md', re.I)
REFUSE = re.compile(r'не поправка:|не правка:|not a correction:', re.I)
DEFER = re.compile(r'(?:отложено|deferred):\s*(.{10,200})', re.I)   # (a reason of ≥ 10 characters, or it is no deferral)
# (a shell command counts only when it WRITES: the engine's rule / ledger commands, a redirect, a copy, an in-place edit — review 04.11)
WRITE_CMD = re.compile(r'foreman\.py[\'"]?\s+(rule\s+(add|accept|set|drop)|ledger|lesson)|(?<![0-9&])>>?\s*[^\s&|>]|\btee\b|'
                       r'Set-Content|Add-Content|Out-File|\bsed\s+-i|\b(cp|mv|copy|move)\b|Copy-Item|Move-Item', re.I)
ALREADY = re.compile(r'(?:уже записано|already recorded):?\s*(R-\d+)', re.I)


def read_transcript(path, tail=4 * 1024 * 1024, cap=64 * 1024 * 1024):
    """the transcript's tail, doubled backwards until it holds a row of the owner's (one big tool result fills 4 MB alone: 28 of 102
    turns of a real session — review 04.11), at most 64 MB"""
    out, n = [], tail
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            while True:
                f.seek(max(0, size - n))
                data = f.read().decode('utf-8', 'replace')
                if size > n:
                    data = data[data.find('\n') + 1:]       # (the first line is cut in the middle)
                out = []
                for line in data.splitlines():
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
                if size <= n or n >= cap or any(_said(e) is not None for e in out):
                    return out
                n *= 2
    except OSError:
        return out


def _said(e):
    """→ the text of a user row that a person or the app typed into the chat ('' for a reminder-only row); None for a tool result,
    the hook's own feedback (isMeta) and the compaction summary — none of them is the owner (review 04.11)"""
    if e.get('type') != 'user' or e.get('isMeta') or e.get('isCompactSummary'):
        return None
    c = _content(e)
    if any(b.get('type') == 'tool_result' for b in c):
        return None
    return REMINDER.sub('', ' '.join(b.get('text') or '' for b in c if b.get('type') == 'text')).strip()


def _content(e):
    c = (e.get('message') or {}).get('content')
    return c if isinstance(c, list) else [{'type': 'text', 'text': c}] if isinstance(c, str) else []


def _ts(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def lesson_gate(transcript_path, last_msg=''):
    """→ a block reason, or ''. A correction (a teaching too with stop_gate «all») in the owner's last message must leave a REAL
    record since — a write to the rules / ledger / memory / a skill / CLAUDE.md (a tool call, or the file's time) — or the reply says
    «не поправка: …» / «уже записано: R-N» with an existing R-N. The words «записано: …» alone are not a record (council 04.11)."""
    mode = CFG['lessons'].get('stop_gate', 'correction')
    if mode == 'off' or not transcript_path or not os.path.isfile(transcript_path):
        return ''
    ev = read_transcript(transcript_path)
    idx, cls, ts = -1, None, None
    for i in range(len(ev) - 1, -1, -1):
        raw = _said(ev[i])
        if not raw:                                         # (a tool result, the hook's feedback, the summary, a bare reminder)
            continue
        t = owner_text(raw)
        if not t:              # (a background notice / a hand-back / a command began THIS turn: the owner's older message was judged
            return ''          #  at the end of its own turn — re-judging it blocked every notification turn, review 04.11)
        idx, cls, ts = i, classify(t), _ts(ev[i].get('timestamp'))
        break
    if idx < 0 or not (cls['correction'] or (mode == 'all' and cls['teaching'])):
        return ''
    recorded, last_text = False, ''
    # (a project with its own rule book: writing into it counts as a record too — `lessons.record_paths`, regexes)
    extra = [re.compile(x, re.I) for x in CFG['lessons'].get('record_paths') or []]
    for e in ev[idx + 1:]:
        if e.get('type') != 'assistant':
            continue
        for b in _content(e):
            if b.get('type') == 'tool_use' and b.get('name') in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash', 'PowerShell'):
                inp = b.get('input') or {}
                target = str(inp.get('file_path') or inp.get('path') or inp.get('command') or '')
                shell = b.get('name') in ('Bash', 'PowerShell')
                if (KNOWLEDGE.search(target) or any(x.search(target) for x in extra)) and (not shell or WRITE_CMD.search(target)):
                    recorded = True
            elif b.get('type') == 'text' and b.get('text'):
                last_text = b['text']
    if not recorded and ts:
        recorded = any(os.path.exists(f) and os.path.getmtime(f) > ts for f in (RULES, LEDGER))
    last_text = f'{last_msg}\n{last_text}' if last_msg else last_text   # (the transcript may lack the last reply — Stop docs)
    if recorded or REFUSE.search(last_text):
        return ''
    d = DEFER.search(last_text)
    if d:                                                   # (a lesson put off WITH a reason: logged once, shown in the brief)
        key = str(ev[idx].get('timestamp') or cls['text'][:80])
        if not any(e.get('kind') == 'lesson_deferred' and e.get('key') == key for e in jsonl(EVENTS)):
            append_jsonl(EVENTS, {'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'foreman', 'kind': 'lesson_deferred',
                                  'key': key, 'head': cls['text'][:120], 'why': d.group(1).strip()[:200]})
            ledger_add(f"deferred -> «{cls['text'][:80]}» -> {d.group(1).strip()[:120]}")
        return ''
    m = ALREADY.search(last_text)
    if m and any(r.get('id') == m.group(1) for r in jsonl(RULES)):
        return ''
    kind = LX['kind_c'] if cls['correction'] else LX['kind_t']
    hint = str(CFG['lessons'].get('record_hint') or '')[:160]
    return LX['gate'].format(kind=kind, cue=cls['correction'] or cls['teaching'], text=cls['text'][:160].replace('\n', ' ')) + \
        (' ' + LX['gate_own'].format(hint=hint) if hint else '')


# ---------------------------------------------------------------- guards (level 3) and hot rules (level 2)
def guards(probe, log=True):
    """→ (newly red, red): every active level-3 rule's probe; a guard red that was green at the last check blocks the Stop ONCE;
    one red from the start only shows in the brief (a bad guard never locks a stranger out). Only the Stop hook logs the state
    (log=True): a status or a brief in between swallowed the block (review 04.11)"""
    rules = [r for r in jsonl(RULES) if r.get('status') == 'active' and int(r.get('level') or 0) >= 3 and r.get('guard')][:20]
    if not rules:
        return [], []
    last = {}
    for e in jsonl(EVENTS):
        if e.get('kind') == 'guard':
            last[e.get('id')] = e.get('ok')
    newly, red = [], []
    for r in rules:
        v = probe(r['guard'])
        if v is None:                                       # («unknown» is neither red nor a change — review 04.11, 2.2)
            continue
        ok = v is True
        if not ok:
            red.append(r)
            if last.get(r['id']) is True:
                newly.append(r)
        if log and last.get(r['id']) != ok:
            append_jsonl(EVENTS, {'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'foreman', 'kind': 'guard', 'id': r['id'], 'ok': ok})
    return newly, red


def guard_reason(newly):
    return '\n'.join(LX['guard'].format(id=r['id'], when=r.get('when', '')[:80], probe=r['guard']) for r in newly)


def hot_lines():
    rows = [r for r in jsonl(RULES) if r.get('status') == 'active' and int(r.get('level') or 0) >= 2]
    return [f"{r['id']} {r.get('when')} → {r.get('do')}"[:120] for r in rows[:CFG['budget']['hot_rows']]]


# ---------------------------------------------------------------- the edit gate (2.1, Fable's review 1.5): who checks the checker
EDIT_FILE = re.compile(r'(?:^|[\\/\'"\s=])\.foreman[\\/](?:(?:promises|inbox|rules|events|owner|eval)\.jsonl|config\.json|foreman\.py|'
                       r'recall\.py|board\.py|board\.html|lexicon\.json)|(?:^|[\\/\'"\s=])\.claude[\\/]settings(?:\.local)?\.json', re.I)
# (the board's API lives under /fm/api/ — a plain /api/ is every other local server, e.g. a studio's; the kit's installer is known
#  by its own flags — «install.py» alone is half the world's setup scripts)
EDIT_SHELL = re.compile(r'foreman\.py[\'"]?[^\n|;&]*--force|foreman\.py[\'"]?\s+board\b|--token-file|/fm/api/|'
                        r'install\.py[^\n]*\s--(?:uninstall|modules|lang|purge)\b', re.I)
COMMIT_MSG = re.compile(r'\bgit\s+commit\b[^\n]*?\s-(?:m|F)\s[\s\S]*', re.I)   # (the message to the end of the command)
ENGINE_CALL = re.compile(r'\S*foreman\.py[\'"]?\s+(?:rule|set|add|take|skip|comment|round|ledger|lesson|recall|check|compare|brief|status|json|'
                         r'selftest|cues|hook|panel)\b', re.I)   # (the panel's own commands write only its folder — 2.2)
PY_WRITE = re.compile(r'open\([^)]*[\'"][wa]\+?[\'"]|write_text\(|\.write\(|json\.dump\(', re.I)
EDIT_OK = re.compile(r'(?:правка проверок|checks edited):\s*.{10,}', re.I)


ASSIGN = re.compile(r'(?:^|[\s;&(])([A-Za-z_]\w*)=(?:"([^"]*)"|\'([^\']*)\'|([^\s;&]+))')


def _expand(c):
    """$NAME / ${NAME} from the command's own assignments, in order (S="C:/x"; P="$S/y"; cp a "$P/.foreman/") and the environment"""
    env = dict(os.environ)
    sub = lambda t: re.sub(r'\$\{?([A-Za-z_]\w*)\}?', lambda m: env.get(m.group(1), m.group(0)), t)   # noqa: E731
    for m in ASSIGN.finditer(c):
        env[m.group(1)] = sub(next(g for g in m.groups()[1:] if g is not None))
    return sub(c)


CD = re.compile(r'\bcd\s+(?:/d\s+)?(?:"([^"]+)"|\'([^\']+)\'|([^\s&;|]+))')


def _here_is_elsewhere(c, i):
    """the last `cd` before position i went to a folder outside this project — a relative path there is not this project's"""
    last = None
    for m in CD.finditer(c[:i]):
        last = next(g for g in m.groups() if g is not None)
    return bool(last) and _elsewhere(last)


def _elsewhere(path):
    """an absolute path outside this project (a test copy, another project) — not this project's checks"""
    p = path.strip('"\'').replace('\\', '/')
    if not re.match(r'^(?:[A-Za-z]:/|/)', p):
        return False
    root = os.path.normcase(os.path.abspath(ROOT)).replace('\\', '/').rstrip('/') + '/'
    return not os.path.normcase(p).replace('\\', '/').startswith(root)


def _token_before(c, i):
    j = i
    while j > 0 and c[j - 1] not in ' \t\n"\'=;&|(':
        j -= 1
    return c[j:i + 1]


def edit_gate(transcript_path, last_msg=''):
    """→ a block reason or '': this TURN (since the last row a person or the app typed) wrote Foreman's own files, the hook settings
    or `lessons.guard_paths` directly, ran the installer / a forced edit / the board, or called the board's API — judged by the
    TEXT of the tool calls, never by file times (the engine's own commands write rules.jsonl legitimately). Once per turn; the line
    «правка проверок: <why ≥ 10 chars>» in the reply lets it pass"""
    if CFG['lessons'].get('edit_gate', 'on') == 'off' or not transcript_path or not os.path.isfile(transcript_path):
        return ''
    ev = read_transcript(transcript_path)
    start = next((i for i in range(len(ev) - 1, -1, -1) if _said(ev[i]) is not None), -1)
    key = str(ev[start].get('timestamp') or start) if start >= 0 else ''
    guard = [re.compile(x, re.I) for x in CFG['lessons'].get('guard_paths') or []]
    what, last_text = [], ''
    for e in ev[start + 1:]:
        if e.get('type') != 'assistant':
            continue
        for b in _content(e):
            if b.get('type') == 'text' and b.get('text'):
                last_text = b['text']
            if b.get('type') != 'tool_use':
                continue
            inp = b.get('input') or {}
            name = b.get('name')
            if name in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
                f = str(inp.get('file_path') or inp.get('notebook_path') or '')
                if (EDIT_FILE.search(f) or any(g.search(f) for g in guard)) and not _elsewhere(f):
                    what.append(os.path.basename(f))
            elif name in ('Bash', 'PowerShell'):
                c = _expand(COMMIT_MSG.sub(' git commit ', str(inp.get('command') or '')))   # (a commit message NAMING the board is no edit)
                plain = ENGINE_CALL.sub(' ', c)              # (the engine's own commands write through its checks — not an edit)
                hits = [h for rx in [EDIT_FILE] + guard for h in rx.finditer(plain)]
                def outside(h):                          # (an absolute path by itself; a relative one by the last `cd` before it)
                    tok = _token_before(plain, h.start()).strip('"\'').replace('\\', '/')
                    return _elsewhere(tok) if re.match(r'^(?:[A-Za-z]:/|/)', tok) else _here_is_elsewhere(plain, h.start())
                names = any(not outside(h) for h in hits)
                shell = EDIT_SHELL.search(c)
                if shell and 'install' in shell.group(0).lower():   # (the kit's installer run on a test copy elsewhere)
                    target = re.search(r'install\.py["\']?\s+["\']?([^"\'\s]+)', c)
                    if target and _elsewhere(target.group(1)):
                        shell = None
                if shell or (names and (WRITE_CMD.search(plain) or PY_WRITE.search(plain))):
                    what.append(c.strip().splitlines()[0][:60])
    if not what or EDIT_OK.search(f'{last_msg}\n{last_text}'):
        return ''
    if any(e.get('kind') == 'edit_gate' and e.get('key') == key for e in jsonl(EVENTS)):
        return ''                                           # (once per turn)
    append_jsonl(EVENTS, {'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'foreman', 'kind': 'edit_gate', 'key': key,
                          'what': what[:5]})
    return LX['edit_gate'].format(what='; '.join(dict.fromkeys(what))[:300])


def unsigned_rules():
    return [r for r in jsonl(RULES) if r.get('status') == 'active' and not r.get('accepted')]


def stale():
    """active rules not confirmed for `lessons.confirm_days` days (Copilot Memory: a fact unconfirmed for long is checked, not
    trusted forever) — the date of the owner's accept, of `rule confirm`, else of the rule itself"""
    days = int(CFG['lessons'].get('confirm_days') or 0)
    if days <= 0:
        return []
    limit = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    return [r for r in jsonl(RULES) if r.get('status') == 'active' and str(r.get('confirmed') or r.get('date') or '9') < limit]


def deferred(days=30):
    """lessons the reply deferred («отложено: …») in the last `days` days"""
    since = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec='seconds')
    return [e for e in jsonl(EVENTS) if e.get('kind') == 'lesson_deferred' and str(e.get('ts', '')) >= since]


def proposed():
    return [r for r in jsonl(RULES) if r.get('status') == 'proposed']


# ---------------------------------------------------------------- the registry commands
def ledger_add(line):
    head = '# Ledger — kept | revised | dropped -> what -> evidence\n\n'
    body = read(LEDGER)
    body = body[len(head):] if body.startswith(head) else body.lstrip('\n')
    write_text(LEDGER, head + f'- {today()} {line}\n' + body)


def next_id(rows):
    n = max([int(m.group(1)) for r in rows if (m := re.match(r'R-(\d+)$', str(r.get('id', ''))))] or [0]) + 1
    return f'R-{n:03d}'


def rule_cmd(a, probe_kinds=('file', 'grep', 'nogrep', 'doc', 'fresh'), quote_check=None):
    sub = a[0] if a else 'list'
    rows = jsonl(RULES)
    if sub == 'add':
        try:
            r = arg_json(a[1]) if len(a) > 1 else None
        except ValueError:
            r = None
        if not isinstance(r, dict) or not all(str(r.get(k) or '').strip() for k in ('when', 'do', 'quote')):
            print(LX['refuse']); return 1
        if len(str(r.get('keys', '')).split()) > 12:
            print(LX['keys_long'])
        ab = ABSENCE.search(f"{r.get('when', '')} {r.get('do', '')}")
        if ab and not r.get('as_of'):
            print(LX['absence_warn'].format(m=ab.group(0)))
        r = {'id': next_id(rows), 'date': today(), 'level': 1, 'tags': [], **{k: v for k, v in r.items() if k not in ('id', 'status')},
             'status': 'proposed', 'touched': today()}
        r['level'] = min(int(r.get('level') or 1), 1)        # (hot / guard only after the owner's «yes»)
        r.pop('guard', None)
        for flag, key in (('--situation', 'situation'), ('--not', 'not_situation')):
            if flag in a and a.index(flag) + 1 < len(a):
                r[key] = a[a.index(flag) + 1]
        before = eval_score()[1] if r.get('situation') else None
        rows.append(r)
        write_jsonl(RULES, rows)
        ledger_add(f"kept -> {r['id']} {r['when'][:80]} (level {r['level']}, proposed) -> «{r['quote'][:100]}»")
        print(LX['added'].format(id=r['id']))
        if r.get('situation'):
            print(f"recall@3: {before if before is not None else '—'} → {eval_score()[1]}")
        return 0
    if sub == 'accept':
        ids = [x for x in a[1:] if re.match(r'R-\d+$', x)]
        quote = a[a.index('--quote') + 1] if '--quote' in a and a.index('--quote') + 1 < len(a) else ''
        its = [next((x for x in rows if x.get('id') == i), None) for i in ids]
        if not ids or None in its:
            print(LX['no_rule'], ids); return 1
        if quote_check is None:
            print(LX['accept_lock']); return 1
        ok, ts = quote_check(ids, quote)
        if not ok:
            print(ts); return 1
        for it in its:
            it['_was'] = it.get('status')
            it.update(status='active', confirmed=today(), touched=today(),
                      accepted={'ts': dt.datetime.now().isoformat(timespec='seconds'), 'by': 'owner-quote', 'quote': quote, 'msg_ts': ts})
            ledger_add(f"kept -> {it['id']} accepted by the owner («{quote[:60]}»)" + (' — REVIVED from dropped' if it.get('_was') == 'dropped' else '')
                       + f" -> {it.get('when', '')[:80]}")
            it.pop('_was', None)
        write_jsonl(RULES, rows)
        print(' '.join(json.dumps(it, ensure_ascii=False) for it in its))
        return 0
    if sub in ('set', 'drop', 'confirm', 'replace'):
        it = next((x for x in rows if x.get('id') == (a[1] if len(a) > 1 else '')), None)
        if not it:
            print(LX['no_rule'], a[1:2]); return 1
        if sub == 'confirm':                              # (still true? — the date the brief's «not confirmed for N days» counts from)
            if it.get('status') != 'active':
                print(LX['only_active']); return 1
            it['confirmed'] = today()
            ledger_add(f"kept -> {it['id']} confirmed -> {it.get('when', '')[:80]}")
        elif sub == 'replace':                              # (a rule that stopped being true is marked, never erased — Graphiti)
            new = a[a.index('--by') + 1] if '--by' in a and a.index('--by') + 1 < len(a) else ''
            if new == it['id'] or not any(x.get('id') == new for x in rows):
                print(LX['no_rule'], new or '--by ?'); return 1
            it['status'], it['replaced_by'] = 'replaced', new
            ledger_add(f"revised -> {it['id']} replaced by {new} -> {it.get('when', '')[:80]}")
        elif sub == 'drop':
            it['status'] = 'dropped'
            why = a[a.index('--why') + 1] if '--why' in a and a.index('--why') + 1 < len(a) else ''
            ledger_add(f"dropped -> {it['id']} {it.get('when', '')[:60]} -> {why}")
        else:
            for kv in a[2:]:
                k, _, v = kv.partition('=')
                if not k or k in ('id', 'status'):
                    continue
                if k == 'level':
                    if not v.strip().isdigit() or not 0 <= int(v) <= 3:
                        print(LX['bad_level']); return 1
                    v = int(v)
                    if v >= 2 and it.get('status') != 'active':
                        print(LX['only_active']); return 1
                if k == 'guard' and v.partition(':')[0] not in probe_kinds:
                    print(LX['guard_kind']); return 1
                if k == 'hot':
                    k, v = 'level', 2 if v.lower() in ('1', 'true', 'yes', 'да') else min(int(it.get('level') or 1), 1)
                    if v >= 2 and it.get('status') != 'active':
                        print(LX['only_active']); return 1
                it[k] = v
            ledger_add(f"revised -> {it['id']} {' '.join(a[2:])[:100]}")
        it['touched'] = today()
        write_jsonl(RULES, rows)
        print(json.dumps(it, ensure_ascii=False))
        return 0
    want = a[1] if len(a) > 1 and not a[1].startswith('--') else None
    for r in rows:
        if (want and r.get('id') != want) or ('--hot' in a and int(r.get('level') or 0) < 2) or ('--guards' in a and not r.get('guard')) \
                or ('--proposed' in a and r.get('status') != 'proposed'):
            continue
        print(json.dumps(r, ensure_ascii=False) if want else f"{r['id']} [{r.get('status')}, ур. {r.get('level')}] {r.get('when')} → {r.get('do')}")
    return 0


def eval_cases():
    """the owner's own test set: every rule's situation must find it in the top 3; its not_situation must not bring it into the pack"""
    rows = jsonl(RULES)
    live = [r for r in rows if r.get('status') not in ('dropped', 'replaced')]
    cases = [(r['situation'], r['id'], True) for r in live if r.get('situation')]
    cases += [(r['not_situation'], r['id'], False) for r in live if r.get('not_situation')]
    cases += [(r['situation'], r['replaced_by'], True) for r in rows if r.get('status') == 'replaced' and r.get('situation')
              and r.get('replaced_by')]                     # (the situation that made the old rule now tests its successor)
    cases += [(c['situation'], c.get('expect'), not c.get('forbid')) for c in jsonl(EVAL) if c.get('situation')]
    return cases


def eval_score():
    cases, blocks = eval_cases(), all_blocks()
    pos = [c for c in cases if c[2]]
    if not cases:
        return 0, None, 0, []
    found, fp, misses = 0, 0, []
    for text, rid, should in cases:
        hits, _ = gate(search(text, blocks, top=20), len(set(tokens(text))))
        ids = [h['block'].ref for h in hits[:CFG['budget']['recall_hits']]]
        if should:
            found += rid in ids
            if rid not in ids:
                misses.append((LX['miss'], rid, text[:80]))
        elif rid in ids:
            fp += 1
            misses.append((LX['fp'], rid, text[:80]))
    return len(cases), round(found / max(1, len(pos)), 2), fp, misses


def recall_cmd(a):
    if '--eval' in a:
        n, r3, fp, misses = eval_score()
        if not n:
            print(LX['eval_none']); return 0
        print(LX['eval_head'].format(n=n, r3=r3, fp=fp))
        for kind, rid, text in misses:
            print(f'{kind} {rid}: «{text}»')
        return 0
    words = ' '.join(x for x in a if not x.startswith('--'))
    top = int(a[a.index('--top') + 1]) if '--top' in a else 5
    hits = search(words, top=40)
    keep, drop = gate(hits, len(set(tokens(words))))
    if '--json' in a:
        print(json.dumps([{'ref': h['block'].ref, 'kind': h['block'].kind, 'score': round(h['score'], 3), 'label': h['block'].label}
                          for h in keep[:top]], ensure_ascii=False, indent=1))
        return 0
    if not keep:
        print(LX['nothing'])
    for h in keep[:top]:
        print(f"{h['score']:5.2f}  {h['block'].label[:200]}")
    if '--explain' in a:
        for h, why in drop[:10]:
            print(f"  – {why}: {h['block'].label[:120]}")
    return 0


def cues_cmd(a):
    if '--deferred' in a:
        for e in deferred(3650):
            print(f"{e.get('ts', '')[:16]}  «{e.get('head', '')}» — {e.get('why', '')}")
        return 0
    c = Counter((e.get('cue_kind'), e.get('cue')) for e in jsonl(EVENTS) if e.get('kind') == 'cue')
    print(LX['cues_head'])
    for (kind, cue), n in c.most_common(20):
        print(f'  {n:4d}  {kind:10s} «{cue}»')
    return 0


def lesson_cmd(a):
    text = ' '.join(a)
    cls = classify(text)
    print(reflector(cls) or '—')
    ab = ABSENCE.search(text)
    if ab:
        print(LX['absence_warn'].format(m=ab.group(0)))
    p = pack(text)
    if p:
        print(p)
    return 0


def render_rules_md():
    rows = [r for r in jsonl(RULES) if r.get('status') != 'dropped']
    out = [LX['rules_title'].format(when=dt.datetime.now().strftime('%d.%m %H:%M')), '']
    for r in rows:
        out.append(f"- **{r['id']}** [{r.get('status')}, {r.get('level')}] {r.get('when')} → {r.get('do')} — «{r.get('quote', '')}»"
                   + (f" · страж `{r['guard']}`" if r.get('guard') else ''))
    write_text(RULES_MD, '\n'.join(out) + '\n')


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    try:
        _c = json.load(io.open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
    except (OSError, ValueError):
        _c = {}
    setup(_c, _c.get('lang', 'ru'))
    sys.exit(recall_cmd(sys.argv[1:]))
