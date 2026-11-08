"""panel.py — Foreman's MODEL PANEL (2.2): one self-contained brief to several AI models the owner HAS, independent answers in one
folder, then Claude checks the claims and writes the decision. Offered at install; the owner decides whether to use it at all, which
members take part (config.json → panel.members, `enabled`) and — with `ask_each_time` — every sending outside (`--owner-ok "<his words>"`,
checked against .foreman/owner.jsonl like an acceptance).

Members, all optional:
  subagent — Claude's own subagents of other models (always there; Claude starts them itself — nothing leaves the machine);
  cli      — a program that takes the question and prints an answer: Codex CLI, Gemini CLI, Qwen Code, `llm`… found in PATH, in npm's
             folder or in the Codex app's folder; it runs in an EMPTY temporary folder outside the project (it sees no project file, no
             other answer), with the API keys it must not use taken out of its environment;
  api      — any OpenAI-compatible address: OpenAI, Gemini, OpenRouter, DeepSeek, xAI, Mistral, a local Ollama / LM Studio; the key is
             read from an environment variable by its NAME and never printed or written;
  manual   — a web chat of the owner's (ChatGPT, AI Studio…): Foreman writes the brief, the answer goes into answer_<name>.md by hand.
A member the engine did not find itself (a command or an address written into config.json) runs only with `allow_cmd: true`.

  python .foreman/foreman.py panel detect                       who is available, who is switched on
  python .foreman/foreman.py panel new "<topic>"                .foreman/panel/<date>_<topic>/ with BRIEF.md and DECISION.md
  python .foreman/foreman.py panel run <folder> [--members a,b] [--stance a=против] --owner-ok "<his words>" [--allow-sensitive]
  python .foreman/foreman.py panel review <folder> [--members a,b] --owner-ok "<his words>"   a second round: every answer without names
Standard library only. The procedure for Claude: .claude/skills/foreman-panel/SKILL.md."""
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

FM = None
LIMIT = 60000

# ---------------------------------------------------------------- what can be found
CLIS = [   # (name, executable, the call; {out} / {dir} are filled in; stdin = the prompt goes to stdin)
    # (Codex: «PROMPT … Use - to pipe the prompt from stdin»; -C = an empty sandbox folder, never the project — its AGENTS.md would ride along)
    {'name': 'codex', 'exe': 'codex', 'label': 'OpenAI Codex CLI',
     'cmd': ['{exe}', 'exec', '--skip-git-repo-check', '-C', '{dir}', '-s', 'read-only', '-o', '{out}', '-'], 'stdin': True,
     'strip_env': ['OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL']},   # (the ChatGPT sign-in, never a paid key — codex_task.ps1)
    {'name': 'gemini', 'exe': 'gemini', 'label': 'Google Gemini CLI', 'cmd': ['{exe}', '-p', 'Answer the text given on standard input.'],
     'stdin': True},
    {'name': 'qwen', 'exe': 'qwen', 'label': 'Qwen Code', 'cmd': ['{exe}', '-p', 'Answer the text given on standard input.'], 'stdin': True},
    {'name': 'llm', 'exe': 'llm', 'label': 'llm (Simon Willison)', 'cmd': ['{exe}'], 'stdin': True},
]
APIS = [   # (name, the key's variable(s), the OpenAI-compatible address)
    ('openai', ('OPENAI_API_KEY',), 'https://api.openai.com/v1'),
    ('gemini-api', ('GEMINI_API_KEY', 'GOOGLE_API_KEY'), 'https://generativelanguage.googleapis.com/v1beta/openai'),
    ('openrouter', ('OPENROUTER_API_KEY',), 'https://openrouter.ai/api/v1'),
    ('deepseek', ('DEEPSEEK_API_KEY',), 'https://api.deepseek.com/v1'),
    ('xai', ('XAI_API_KEY',), 'https://api.x.ai/v1'),
    ('mistral', ('MISTRAL_API_KEY',), 'https://api.mistral.ai/v1'),
]
LOCAL = [('ollama', 'http://127.0.0.1:11434/v1'), ('lmstudio', 'http://127.0.0.1:1234/v1')]
SECRETS = [
    ('key', r'\bsk-[A-Za-z0-9_\-]{20,}'), ('key', r'\bAIza[0-9A-Za-z_\-]{30,}'),
    ('token', r'\b(?:ghp|gho|ghs)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}'), ('token', r'\bxox[abpr]-[A-Za-z0-9\-]{10,}'),
    ('token', r'\b(?:hf|xai|gsk|glpat|npm|pypi)[_\-][A-Za-z0-9_\-]{16,}'), ('key', r'\bAKIA[0-9A-Z]{16}\b'),
    ('private key', r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), ('JWT', r'\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.'),
    ('token', r'\b\d{8,10}:AA[A-Za-z0-9_\-]{30,}'),
    ('key assignment', r'(?i)\b\w*(?:api[_\-]?key|secret|token|passw)\w*\s*[:=]\s*["\']?[A-Za-z0-9_\-./+]{16,}'),
    ('password', r'(?i)\b(?:password|passwd|пароль)\s*[:=]\s*\S+'),
    ('e-mail', r'[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)*\.[A-Za-z]{2,}\b(?!:[\w./~\-])'),   # (not react@18.3.1, python@3.10, git@host:org/repo — S1)
]
PATHS = ('user path', r'(?i)\b[a-z]:\\Users\\[^\\\s]+|/home/[^/\s]+|/Users/[^/\s]+')   # (allowed in bulk by panel.allow_paths)

T = {
    'ru': {'head': 'Консилиум моделей — кто доступен:', 'on': 'модуль включён', 'off': 'модуль выключен (решает владелец: config.json → modules.panel)',
           'en': 'включён', 'dis': 'выключен', 'nr': 'не готов', 'strip': 'не передаётся ребёнку: {v}',
           'need_model': 'впишите model (и, если надо, params) в config.json → panel.members',
           'ollama_ctx': 'контекст Ollama задайте в Modelfile / OLLAMA_CONTEXT_LENGTH ≥ 24k — иначе длинный бриф обрежется',
           'off_run': ('Консилиум моделей выключен. Включает только владелец: install.py … --modules …,panel или config.json → modules.panel = '
                       'true. Сначала: foreman.py panel detect — кто доступен.'),
           'no_brief': 'нет брифа: {p} (panel new "<тема>")', 'long': 'бриф длиннее {n} символов — сократите',
           'secret': ('В брифе похоже на личное или секретное: {k}. Наружу не отправлено. Уберите это из брифа — или, если владелец разрешил, '
                      '--allow-sensitive (пути с именем пользователя — panel.allow_paths: true).'),
           'owner_ok': ('Перед отправкой брифа наружу нужен ответ владельца (panel.ask_each_time): спросите его — кому и зачем — и передайте '
                        'его слова: --owner-ok "<его слова дословно>". {why}'),
           'none': 'Внешних участников нет или все выключены владельцем (config.json → panel.members). Субагентов Claude запускает сам.',
           'disabled': 'участник {n} выключен владельцем (config.json → panel.members → enabled)', 'unknown': 'нет такого участника: {n}',
           'notready': 'участник {n} не готов: {why}', 'cmd_off': 'участник {n} не найден движком (своя команда / адрес) — нужен allow_cmd: true',
           'plain_key': 'участник {n}: ключ по http:// не на этот компьютер — отказ (ключ ушёл бы открытым текстом)',
           'sending': 'отправляю: {n} → {to}', 'timeout': 'таймаут (процесс остановлен)', 'empty': 'пустой ответ', 'failed': 'не ответил',
           'review_need': 'для второго круга нужно ≥ 2 ответов', 'review_long': 'ответы слишком длинные для второго круга',
           'review_ask': ('Второй круг консилиума. Ниже бриф и ответы участников БЕЗ имён (A, B, C…). Для каждого ответа: фактические ошибки и '
                          'непроверенные утверждения; что в нём самое ценное; затем общий рейтинг от лучшего к худшему с причиной. Свой прежний '
                          'ответ не защищай — оценивай по существу.'),
           'answer': 'Ответ', 'brief_h': 'Бриф', 'answers_h': 'Ответы',
           'head_prompt': ('Ты — независимый эксперт консилиума. Ниже бриф. Ответь самостоятельно (другие участники отвечают отдельно, их ответов '
                           'ты не видишь). Отделяй проверенное от предположений, у каждого предложения назови цену и риск. Отвечай на языке брифа.\n\n'),
           'limit': 'лимит исчерпан', 'login': 'нужен вход', 'topic': 'тема: panel new "<тема>"'},
    'en': {'head': 'Model panel — who is available:', 'on': 'the module is on', 'off': 'the module is off (the owner decides: config.json → modules.panel)',
           'en': 'on', 'dis': 'off', 'nr': 'not ready', 'strip': 'not passed to the child: {v}',
           'need_model': 'write model (and params if needed) into config.json → panel.members',
           'ollama_ctx': 'set Ollama\'s context in the Modelfile / OLLAMA_CONTEXT_LENGTH ≥ 24k — a long brief is cut otherwise',
           'off_run': ('The model panel is off. Only the owner switches it on: install.py … --modules …,panel or config.json → modules.panel = '
                       'true. First: foreman.py panel detect — who is available.'),
           'no_brief': 'no brief: {p} (panel new "<topic>")', 'long': 'the brief is longer than {n} characters — shorten it',
           'secret': ('The brief seems to carry something private or secret: {k}. Nothing was sent. Take it out — or, if the owner allowed it, '
                      '--allow-sensitive (paths with a user name — panel.allow_paths: true).'),
           'owner_ok': ('Sending the brief outside needs the owner\'s answer (panel.ask_each_time): ask him — to whom and why — and pass his '
                        'words: --owner-ok "<his words verbatim>". {why}'),
           'none': 'No outside members, or the owner switched them all off (config.json → panel.members). Claude starts its own subagents itself.',
           'disabled': 'member {n} is switched off by the owner (config.json → panel.members → enabled)', 'unknown': 'no such member: {n}',
           'notready': 'member {n} is not ready: {why}', 'cmd_off': 'member {n} was not found by the engine (its own command / address) — needs allow_cmd: true',
           'plain_key': 'member {n}: a key over http:// to another machine — refused (the key would travel in clear text)',
           'sending': 'sending: {n} → {to}', 'timeout': 'timeout (the process was stopped)', 'empty': 'an empty answer', 'failed': 'did not answer',
           'review_need': 'the second round needs ≥ 2 answers', 'review_long': 'the answers are too long for a second round',
           'review_ask': ('The panel\'s second round. Below are the brief and the members\' answers WITHOUT names (A, B, C…). For each answer: its '
                          'factual errors and unchecked claims; what is most valuable in it; then a ranking from best to worst with the reason. '
                          'Do not defend your own earlier answer — judge on the merits.'),
           'answer': 'Answer', 'brief_h': 'Brief', 'answers_h': 'Answers',
           'head_prompt': ('You are an independent expert on a panel. The brief follows. Answer on your own (the others answer separately; you do '
                           'not see them). Separate what is known from guesses; give each proposal its cost and risk. Answer in the brief\'s language.\n\n'),
           'limit': 'usage limit reached', 'login': 'sign-in needed', 'topic': 'topic: panel new "<topic>"'},
}
STANCE = {'против': 'Твоя роль в этом консилиуме — КРИТИК: ищи слабые места, риски и доводы против; не соглашайся из вежливости.\n\n',
          'за': 'Твоя роль в этом консилиуме — ЗАЩИТНИК: найди самые сильные доводы за предложенное направление и как его довести.\n\n',
          'against': 'Your role on this panel is the CRITIC: look for weak points, risks and arguments against; do not agree to be polite.\n\n',
          'for': 'Your role on this panel is the ADVOCATE: find the strongest arguments for the proposed direction and how to make it work.\n\n'}
BRIEF = {'ru': """# Бриф консилиума: {topic}

Один и тот же бриф получает каждый участник; ответы независимы — чужих ответов не читайте.

## Контекст (самодостаточно: участник не видит наш проект; картинки — словами)
…

## Что проверено (факты с числами, ссылками, замерами)
- …

## Вопрос владельца (дословно)
«…»

## Вопросы
1. …
2. …

## Как отвечать
- По каждому предложению: цена (время, деньги, сложность) и риск.
- Отделяйте известное от предположений («предполагаю: …»).
- Не больше 900 слов. Язык ответа — язык этого брифа.
""", 'en': """# Panel brief: {topic}

Every member gets the same brief; answers are independent — do not read the others' answers.

## Context (self-contained: a member does not see our project; pictures described in words)
…

## What is verified (facts with numbers, links, measurements)
- …

## The owner's question (verbatim)
"…"

## Questions
1. …
2. …

## How to answer
- For each proposal: its cost (time, money, effort) and risk.
- Separate what is known from guesses ("I assume: …").
- At most 900 words. Answer in the brief's language.
"""}
DECISION = {'ru': """# Решение консилиума: {topic}

Участники и настройки (модель, усилие; кто заменён и кем): …

## Проверено нами (факты, которыми сверены утверждения участников)
- …

## В чём согласны все
- …

## Где разошлись — что выбрали и почему
| вопрос | участник → мнение | выбор | почему (проверка) |
|---|---|---|---|

## Порядок, цена, риски
…

## Оценка участников (что дал каждый, где ошибся; идей / подтвердилось)
…
""", 'en': """# Panel decision: {topic}

Members and settings (model, effort; who was replaced by whom): …

## Verified by us (the facts the members' claims were checked against)
- …

## What all agree on
- …

## Where they differ — what we chose and why
| question | member → opinion | choice | why (the check) |
|---|---|---|---|

## Order, cost, risks
…

## The members (what each gave, where each erred; ideas / confirmed)
…
"""}


def tx(name, **kw):
    return T['en' if (FM.CFG.get('lang') == 'en') else 'ru'][name].format(**kw)


def lang():
    return 'en' if FM.CFG.get('lang') == 'en' else 'ru'


def _which(exe):
    """PATH, npm's folder on Windows, the Codex app's own folder (%LOCALAPPDATA%\\OpenAI\\Codex\\bin\\<build>\\codex.exe — the newest)"""
    p = shutil.which(exe)
    if p:
        return p
    if os.name == 'nt':
        c = os.path.join(os.environ.get('APPDATA', ''), 'npm', exe + '.cmd')
        if os.path.isfile(c):
            return c
        if exe == 'codex':
            builds = glob.glob(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'OpenAI', 'Codex', 'bin', '**', 'codex.exe'), recursive=True)
            if builds:
                return max(builds, key=os.path.getmtime)
    return None


def _resolve_exe(cmd0):
    """(2.4.1) the program to start. config.json keeps the absolute path `panel detect` found, but the Codex app moves codex.exe into a
    new build folder on every update — 08.11 the first run after an update failed with «WinError 2» on the old path. A path that no
    longer exists falls back to the program's NAME: PATH, npm's folder, the newest Codex build."""
    exe = _which(cmd0) or cmd0
    if os.path.isabs(str(exe)) and not os.path.exists(exe):
        exe = _which(os.path.splitext(os.path.basename(str(cmd0)))[0]) or exe
    return exe


def _get_json(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def detect(probe_local=True):
    """→ the members that can be used here. A member the owner has in config.json keeps HIS settings (enabled, model…); one found
    only now is listed switched OFF — nothing new joins the panel without the owner (review M2)"""
    have = {m.get('name'): m for m in (FM.CFG.get('panel') or {}).get('members') or [] if isinstance(m, dict) and m.get('name')}
    found = [{'name': 'subagents', 'kind': 'subagent', 'label': 'Claude subagents of other models (Opus / Sonnet / Haiku…)',
              'how': 'Claude Code', 'ready': True, 'enabled': True}]
    for c in CLIS:
        p = _which(c['exe'])
        if p:
            found.append({'name': c['name'], 'kind': 'cli', 'label': c['label'], 'how': p, 'ready': True, 'found': True,
                          'cmd': [p if x == '{exe}' else x for x in c['cmd']], 'stdin': c['stdin'], 'strip_env': c.get('strip_env', [])})
    for name, keys, base in APIS:
        key = next((k for k in keys if os.environ.get(k)), None)
        if key:
            found.append({'name': name, 'kind': 'api', 'label': f'{name} ({key})', 'how': key, 'base_url': base, 'key_env': key,
                          'model': '', 'ready': False, 'found': True, 'note': tx('need_model')})
    if probe_local:
        for name, base in LOCAL:
            d = _get_json(base.replace('/v1', '/api/tags') if name == 'ollama' else base + '/models')
            models = [m.get('name') or m.get('id') for m in ((d or {}).get('models') or (d or {}).get('data') or [])]
            if models:
                found.append({'name': name, 'kind': 'api', 'label': f'{name} (local)', 'how': base, 'base_url': base, 'key_env': '',
                              'model': models[0], 'models': models[:12], 'ready': True, 'found': True,
                              **({'num_ctx': 32768} if name == 'ollama' else {})})
    out, names = [], set()
    for f in found:
        m = dict(f, **have[f['name']]) if f['name'] in have else dict(f, enabled=f.get('enabled', False))
        if m.get('kind') == 'api' and m.get('key_env'):
            m['ready'] = bool(m.get('model'))
        out.append(m)
        names.add(f['name'])
    for n, m in have.items():
        if n not in names:                                  # (written by the owner, not found by the engine: needs allow_cmd to run)
            out.append(dict(m, how=m.get('how', 'config.json'), found=False,
                            ready=m.get('kind') in ('manual', 'subagent') or bool(m.get('cmd') or (m.get('base_url') and m.get('model')))))
    return out


def detect_cmd(a):
    rows = detect(probe_local='--no-local' not in a)
    if '--json' in a:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print(tx('head'))
    for m in rows:
        state = (tx('en') if m.get('enabled') else tx('dis')) if m.get('ready') else tx('nr')
        strip = [v for v in m.get('strip_env') or [] if os.environ.get(v)]
        print(f"  {m.get('name', '?'):12s} {m.get('kind', '?'):8s} {state:9s} {m.get('label', '')} — {m.get('how', '')}"
              + (f" ({m['note']})" if m.get('note') else '') + (f" · {tx('strip', v=', '.join(strip))}" if strip else ''))
    print(tx('on' if (FM.CFG.get('modules') or {}).get('panel') else 'off'))
    return 0


# ---------------------------------------------------------------- a new panel folder
def slug(t):
    s = re.sub(r'[^\w\-]+', '_', t.strip().lower(), flags=re.U).strip('_')
    return s[:48] or 'topic'


def new_cmd(a):
    topic = ' '.join(x for x in a if not x.startswith('--')).strip()
    if not topic:
        print(tx('topic')); return 1
    d = os.path.join(FM.HERE, 'panel', f"{dt.date.today().isoformat()}_{slug(topic)}")
    os.makedirs(d, exist_ok=True)
    for n, tpl in (('BRIEF.md', BRIEF[lang()]), ('DECISION.md', DECISION[lang()])):
        p = os.path.join(d, n)
        if not os.path.exists(p):
            io.open(p, 'w', encoding='utf-8', newline='\n').write(tpl.format(topic=topic))
    print(d)
    return 0


# ---------------------------------------------------------------- the gate: the module, the owner's word, the brief
def sensitive(text):
    """→ the kinds of secrets / private data in the brief (never the values themselves)"""
    kinds = [name for name, rx in SECRETS if re.search(rx, text)]
    if not ((FM.CFG if FM else {}).get('panel') or {}).get('allow_paths') and re.search(PATHS[1], text):
        kinds.append(PATHS[0])
    for k, v in os.environ.items():
        if len(v) >= 16 and re.search(r'(?i)key|token|secret|pass', k) and v in text:
            kinds.append(f'the value of {k}')
    return list(dict.fromkeys(kinds))


def flag(a, name):
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else None


def positional(a):
    """the first argument that is neither a flag nor a flag's value"""
    skip = False
    for x in a:
        if skip:
            skip = False
            continue
        if x in ('--members', '--stance', '--owner-ok'):
            skip = True
            continue
        if not x.startswith('--'):
            return x
    return ''


def _gate(a, folder):
    if not (FM.CFG.get('modules') or {}).get('panel'):
        print(tx('off_run')); return None
    if not os.path.isdir(folder) or not os.path.exists(os.path.join(folder, 'BRIEF.md')):
        print(tx('no_brief', p=os.path.join(folder, 'BRIEF.md'))); return None
    brief = io.open(os.path.join(folder, 'BRIEF.md'), encoding='utf-8').read()
    if len(brief) > LIMIT:
        print(tx('long', n=LIMIT)); return None
    kinds = sensitive(brief)
    if kinds and '--allow-sensitive' not in a:
        print(tx('secret', k=', '.join(kinds))); return None
    return brief


def owner_ok(a):
    """panel.ask_each_time (on by default): a brief leaves the machine only on the owner's own words — --owner-ok "<his words>", ≥ 12
    characters, verbatim in .foreman/owner.jsonl (the prompt hook logs every message of his), as with an acceptance (review M2 d)"""
    if not (FM.CFG.get('panel') or {}).get('ask_each_time', True):
        return True, ''
    quote = flag(a, '--owner-ok') or ''
    if len(FM._norm(quote)) < 12:
        return False, ''
    ok, why = FM.owner_says(['panel'], quote)
    return ok, ('' if ok else why)


def members_for(a):
    """→ (members, problems): only the owner's switched-on members; --members picks among THEM (never a switched-off one); a member the
    engine did not find itself runs only with allow_cmd (review M2, S2)"""
    rows = [m for m in detect(probe_local=False) if m.get('kind') in ('cli', 'api')]
    by = {m['name']: m for m in rows}
    want = [x.strip() for x in (flag(a, '--members') or '').split(',') if x.strip()]
    problems, out = [], []
    for name in want or [m['name'] for m in rows if m.get('enabled')]:
        m = by.get(name)
        if not m:
            problems.append(tx('unknown', n=name)); continue
        if not m.get('enabled'):
            problems.append(tx('disabled', n=name)); continue
        if not m.get('ready'):
            problems.append(tx('notready', n=name, why=m.get('note', ''))); continue
        if not m.get('found') and not FM.CFG.get('allow_cmd'):
            problems.append(tx('cmd_off', n=name)); continue
        if m['kind'] == 'api' and m.get('key_env') and urllib.parse.urlparse(m.get('base_url', '')).scheme == 'http' \
                and urllib.parse.urlparse(m.get('base_url', '')).hostname not in ('127.0.0.1', 'localhost', '::1'):
            problems.append(tx('plain_key', n=name)); continue
        out.append(m)
    return out, problems


# ---------------------------------------------------------------- asking one member
def _why(log):
    """the reason a CLI gave, without its plumbing noise: a usage limit / a sign-in first, else its last «ERROR» lines"""
    lines = [l.strip() for l in str(log).splitlines() if l.strip()]
    for key, say in (('usage limit', 'limit'), ('quota', 'limit'), ('not logged in', 'login'), ('please log in', 'login'),
                     ('sign in', 'login'), ('codex login', 'login')):
        hit = next((l for l in lines if key in l.lower()), None)
        if hit:
            return f'{tx(say)}: {hit[:300]}'
    errs = [l for l in lines if 'error' in l.lower() and 'transport' not in l.lower()]
    return ' | '.join(dict.fromkeys(errs[-3:] or lines[-3:]))[:800]


def _kill_tree(p):
    """a CLI behind a .cmd shim (npm's gemini / qwen) is cmd.exe → node: killing the child alone leaves the grandchild alive and holding
    the pipes (review M3) — the whole tree goes"""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True, timeout=20)
        else:
            os.killpg(p.pid, signal.SIGKILL)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def ask_cli(m, prompt, folder, timeout):
    sandbox = tempfile.mkdtemp(prefix='foreman_panel_')    # (an empty folder OUTSIDE the project: no project file, no other answer — M1)
    out = os.path.join(sandbox, 'answer.out')
    try:
        cmd = m['cmd']
        if isinstance(cmd, str):                            # (a command written as one string in config.json — review S8)
            cmd = [x.strip('"') for x in shlex.split(cmd, posix=os.name != 'nt')]   # (Windows keeps the quotes inside a token)
        cmd = [str(x).replace('{out}', out).replace('{dir}', sandbox) for x in cmd]
        extra = [str(x) for x in m.get('args') or []]      # (the member's own flags: a model, an effort — «each at its strongest», S5)
        cmd = cmd[:-1] + extra + cmd[-1:] if extra and cmd[-1] == '-' else cmd + extra
        exe = _resolve_exe(cmd[0])
        strip = set(m.get('strip_env') or [])
        env = {k: v for k, v in os.environ.items() if k not in strip}
        env['PYTHONIOENCODING'] = 'utf-8'
        p = subprocess.Popen([exe] + cmd[1:], stdin=subprocess.PIPE if m.get('stdin') else subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=sandbox, env=env, **({} if os.name == 'nt' else {'start_new_session': True}))
        try:
            so, se = p.communicate(input=prompt.encode('utf-8') if m.get('stdin') else None, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(p)
            try:
                p.communicate(timeout=10)
            except Exception:
                pass
            raise RuntimeError(tx('timeout'))
        so, se = so.decode('utf-8', 'replace'), se.decode('utf-8', 'replace')
        text = io.open(out, encoding='utf-8', errors='replace').read() if os.path.exists(out) else so
        if p.returncode != 0 and not text.strip():
            raise RuntimeError(f'exit {p.returncode}: {_why(se or so)}')
        return text.strip(), m.get('model') or m.get('label') or m['name']
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def ask_ollama(m, prompt, timeout):
    """Ollama's own /api/chat with options.num_ctx: through its OpenAI-compatible address the context size cannot be set, and a long
    brief is cut without a word (review S6). num_ctx: the member's own, else 32768"""
    base = m['base_url'].rstrip('/')
    base = base[:-3] if base.endswith('/v1') else base
    body = {'model': m['model'], 'messages': [{'role': 'user', 'content': prompt}], 'stream': False,
            'options': {'num_ctx': int(m.get('num_ctx') or 32768), **(m.get('params') or {})}}
    req = urllib.request.Request(base + '/api/chat', data=json.dumps(body).encode('utf-8'), method='POST',
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'HTTP {e.code}: {e.read().decode("utf-8", "replace")[:400]}')
    return str((d.get('message') or {}).get('content') or '').strip(), d.get('model') or m['model']


def ask_api(m, prompt, timeout):
    if m.get('name') == 'ollama' or m.get('native') == 'ollama':
        return ask_ollama(m, prompt, timeout)
    key = os.environ.get(m.get('key_env') or '', '') if m.get('key_env') else ''
    if m.get('key_env') and not key:
        raise RuntimeError(f"no variable {m['key_env']}")
    body = {'model': m['model'], 'messages': [{'role': 'user', 'content': prompt}], **(m.get('params') or {})}
    req = urllib.request.Request(m['base_url'].rstrip('/') + '/chat/completions', data=json.dumps(body).encode('utf-8'), method='POST',
                                 headers={'Content-Type': 'application/json', **({'Authorization': f'Bearer {key}'} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'HTTP {e.code}: {e.read().decode("utf-8", "replace")[:400]}')
    return str(((d.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip(), d.get('model') or m['model']


def _ask_all(members, make_prompt, folder, prefix):
    timeout = int((FM.CFG.get('panel') or {}).get('timeout_s', 600))
    results = {}

    def write_err(m, msg):
        io.open(os.path.join(folder, f"{prefix}_{m['name']}.err.md"), 'w', encoding='utf-8', newline='\n').write(
            f"# {m['name']} — {tx('failed')}\n\n{msg}\n")

    def one(m):
        t0 = time.time()
        try:
            prompt = make_prompt(m)
            text, model = ask_cli(m, prompt, folder, timeout) if m['kind'] == 'cli' else ask_api(m, prompt, timeout)
            if not text:
                raise RuntimeError(tx('empty'))
            settings = '; '.join([f'{k}={v}' for k, v in (m.get('params') or {}).items()] + [' '.join(map(str, m.get('args') or []))]).strip('; ')
            head = (f"<!-- panel: member={m['name']}; kind={m['kind']}; model={model}; settings={settings or '-'}; "
                    f"seconds={time.time() - t0:.0f}; ts={dt.datetime.now().isoformat(timespec='seconds')} -->\n# {m['name']} ({model})\n\n")
            dst = os.path.join(folder, f"{prefix}_{m['name']}.md")      # (whole or nothing: a temp file, then a replace — N5)
            io.open(dst + '.tmp', 'w', encoding='utf-8', newline='\n').write(head + text + '\n')
            os.replace(dst + '.tmp', dst)
            results[m['name']] = ('ok', f'{time.time() - t0:.0f} s')
        except Exception as e:                              # (one member down never stops the others)
            write_err(m, str(e))
            results[m['name']] = ('error', str(e)[:200])
    threads = [threading.Thread(target=one, args=(m,), daemon=True) for m in members]
    for t in threads:
        t.start()
    deadline = time.time() + timeout + 60
    for t in threads:
        t.join(max(0.0, deadline - time.time()))
    for m in members:                                       # (a member still hanging after the wait: its error file is written — M3)
        if m['name'] not in results:
            write_err(m, tx('timeout'))
            results[m['name']] = ('error', tx('timeout'))
    return results


def _prepare(a):
    folder = os.path.abspath(positional(a) or '.')
    brief = _gate(a, folder)
    if brief is None:
        return None
    members, problems = members_for(a)
    for p in problems:
        print('  ' + p)
    if not members:
        print(tx('none')); return None
    ok, why = owner_ok(a)
    if not ok:
        print(tx('owner_ok', why=why)); return None
    for m in members:
        print('  ' + tx('sending', n=m['name'], to=m['base_url'] if m['kind'] == 'api' else os.path.basename(str(m['cmd'][0]))))
    return folder, brief, members


def _log(kind, folder, members, a):
    try:
        FM.append_event({'kind': kind, 'id': os.path.basename(folder), 'to': ','.join(m['name'] for m in members),
                         'text': (flag(a, '--owner-ok') or '')[:200]})
    except Exception:
        pass


def run_cmd(a):
    ready = _prepare(a)
    if not ready:
        return 1
    folder, brief, members = ready
    stances = {}
    for i, x in enumerate(a):
        if x == '--stance' and i + 1 < len(a) and '=' in a[i + 1]:
            k, _, v = a[i + 1].partition('=')
            stances[k.strip()] = v.strip().lower()
    res = _ask_all(members, lambda m: T[lang()]['head_prompt'] + STANCE.get(stances.get(m['name'], ''), '') + brief, folder, 'answer')
    _log('panel_run', folder, members, a)
    for name, (st, info) in res.items():
        print(f'  {name:12s} {st:7s} {info}')
    print(folder)
    return 0 if any(st == 'ok' for st, _ in res.values()) else 1


def review_cmd(a):
    """the second round (llm-council): every answer WITHOUT its author's name, in a fixed shuffled order; each member finds the factual
    errors and ranks them. The key (letter → member) is written only AFTER the round (a member with file access must not read it — M1)"""
    ready = _prepare(a)
    if not ready:
        return 1
    folder, brief, members = ready
    answers = [p for p in sorted(glob.glob(os.path.join(folder, 'answer_*.md'))) if not p.endswith('.err.md')]
    if len(answers) < 2:
        print(tx('review_need')); return 1
    order = sorted(answers, key=lambda p: hashlib.sha1((os.path.basename(p) + os.path.basename(folder)).encode()).hexdigest())
    key, parts = {}, []
    for n, p in enumerate(order):
        letter = chr(ord('A') + n)
        key[letter] = os.path.basename(p)[len('answer_'):-3]
        text = re.sub(r'<!--.*?-->\s*', '', io.open(p, encoding='utf-8').read(), flags=re.S)
        text = re.sub(r'^# .*\n', '', text, count=1)
        parts.append(f"## {T[lang()]['answer']} {letter}\n\n{text.strip()}\n")
    ask = f"{T[lang()]['review_ask']}\n\n# {T[lang()]['brief_h']}\n\n{brief}\n\n# {T[lang()]['answers_h']}\n\n" + '\n'.join(parts)
    if len(ask) > LIMIT * 2:
        print(tx('review_long')); return 1
    res = _ask_all(members, lambda m: ask, folder, 'review')
    io.open(os.path.join(folder, 'review_key.json'), 'w', encoding='utf-8').write(json.dumps(key, ensure_ascii=False, indent=1))
    _log('panel_review', folder, members, a)
    for name, (st, info) in res.items():
        print(f'  {name:12s} {st:7s} {info}')
    print(folder)
    return 0 if any(st == 'ok' for st, _ in res.values()) else 1


def main(fm, a):
    global FM
    FM = fm
    sub = a[0] if a else 'detect'
    return {'detect': detect_cmd, 'new': new_cmd, 'run': run_cmd, 'review': review_cmd}.get(sub, lambda x: (print(__doc__), 1)[1])(a[1:])
