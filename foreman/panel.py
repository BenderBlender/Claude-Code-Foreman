"""panel.py — Foreman's MODEL PANEL (2.2): one self-contained brief to several AI models the owner HAS, independent answers in one
folder, then Claude checks the claims and writes the decision. Offered at install; the owner decides whether to use it at all.

Members, all optional:
  subagent — Claude's own subagents of other models (always there; Claude starts them itself — nothing leaves the machine);
  cli      — a program that takes the question and prints an answer: Codex CLI, Gemini CLI, Qwen Code, `llm`… (found in PATH,
             in npm's folder, in the Codex app's folder) or any command the owner writes into config.json;
  api      — any OpenAI-compatible address: OpenAI, Gemini, OpenRouter, DeepSeek, xAI, Mistral, a local Ollama / LM Studio; the key
             is read from an environment variable by its NAME and never printed or written;
  manual   — a web chat of the owner's (ChatGPT, AI Studio…): Foreman writes the brief, the answer goes into answer_<name>.md by hand.

  python .foreman/foreman.py panel detect                       who is available
  python .foreman/foreman.py panel new "<topic>"                .foreman/panel/<date>_<topic>/ with BRIEF.md and DECISION.md
  python .foreman/foreman.py panel run <folder> [--members a,b] [--stance a=против] [--allow-sensitive]
  python .foreman/foreman.py panel review <folder> [--members a,b]   a second round: every answer without names, find errors, rank
Standard library only. The procedure for Claude: .claude/skills/foreman-panel/SKILL.md."""
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

FM = None
LIMIT = 60000

# ---------------------------------------------------------------- what can be found
CLIS = [   # (name, executable, the call; {prompt_file} {prompt_name} {out} {dir} are filled in; stdin = the prompt goes to stdin)
    {'name': 'codex', 'exe': 'codex', 'label': 'OpenAI Codex CLI',
     'cmd': ['{exe}', 'exec', '--skip-git-repo-check', '-C', '{dir}', '-s', 'read-only', '-o', '{out}', '--',
             'Read the file {prompt_name} in the current folder completely and answer it as it asks. Change no files.'], 'stdin': False},
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
SECRETS = [('ключ API', r'\bsk-[A-Za-z0-9_\-]{20,}'), ('ключ Google', r'\bAIza[0-9A-Za-z_\-]{30,}'), ('токен GitHub', r'\b(?:ghp|gho|ghs)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}'),
           ('токен Slack', r'\bxox[abpr]-[A-Za-z0-9\-]{10,}'), ('ключ AWS', r'\bAKIA[0-9A-Z]{16}\b'), ('приватный ключ', r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
           ('пароль', r'(?i)\b(?:password|passwd|пароль)\s*[:=]\s*\S+'), ('адрес e-mail', r'[\w.+\-]+@[\w\-]+\.[\w.\-]+')]


def _which(exe):
    """PATH, npm's folder on Windows, the Codex app's own folder (%LOCALAPPDATA%\\OpenAI\\Codex\\bin\\<build>\\codex.exe — the newest)"""
    p = shutil.which(exe)
    if p:
        return p
    if os.name == 'nt':
        for c in (os.path.join(os.environ.get('APPDATA', ''), 'npm', exe + '.cmd'),):
            if os.path.isfile(c):
                return c
        if exe == 'codex':
            builds = glob.glob(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'OpenAI', 'Codex', 'bin', '**', 'codex.exe'), recursive=True)
            if builds:
                return max(builds, key=os.path.getmtime)
    return None


def _get_json(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def detect(probe_local=True):
    """→ the members that can be used here: what the config already has (kept as the owner set it) + what is found now"""
    have = {m['name']: m for m in (FM.CFG.get('panel') or {}).get('members') or []}
    found = [{'name': 'subagents', 'kind': 'subagent', 'label': 'субагенты Claude других моделей (Opus / Sonnet / Haiku…)',
              'how': 'Claude Code', 'ready': True}]
    for c in CLIS:
        p = _which(c['exe'])
        if p:
            found.append({'name': c['name'], 'kind': 'cli', 'label': c['label'], 'how': p, 'ready': True,
                          'cmd': [p if x == '{exe}' else x for x in c['cmd']], 'stdin': c['stdin']})
    for name, keys, base in APIS:
        key = next((k for k in keys if os.environ.get(k)), None)
        if key:
            found.append({'name': name, 'kind': 'api', 'label': f'{name} (ключ в {key})', 'how': f'переменная {key}', 'base_url': base,
                          'key_env': key, 'model': '', 'ready': False, 'note': 'впишите model в config.json → panel.members'})
    if probe_local:
        for name, base in LOCAL:
            d = _get_json(base.replace('/v1', '/api/tags') if name == 'ollama' else base + '/models')
            models = [m.get('name') or m.get('id') for m in ((d or {}).get('models') or (d or {}).get('data') or [])]
            if models:
                found.append({'name': name, 'kind': 'api', 'label': f'{name} на этом компьютере', 'how': base, 'base_url': base,
                              'key_env': '', 'model': models[0], 'models': models[:12], 'ready': True})
    out = []
    for f in found:
        m = dict(f, **have[f['name']]) if f['name'] in have else dict(f, enabled=f.get('ready', False) and f['kind'] != 'api')
        m['ready'] = bool(m.get('model')) if m['kind'] == 'api' and m.get('key_env') else m.get('ready', True)
        out.append(m)
    out += [dict(m, how=m.get('how', 'config'), ready=m.get('kind') in ('manual', 'subagent') or bool(m.get('cmd') or m.get('model')))
            for n, m in have.items() if n not in {f['name'] for f in found}]
    return out


def detect_cmd(a):
    rows = detect(probe_local='--no-local' not in a)
    if '--json' in a:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print(FM.L.get('panel_head', 'Консилиум моделей — кто доступен:'))
    for m in rows:
        state = ('включён' if m.get('enabled') else 'выключен') if m.get('ready') else 'не готов'
        print(f"  {m['name']:12s} {m['kind']:8s} {state:9s} {m.get('label', '')} — {m.get('how', '')}" + (f" ({m['note']})" if m.get('note') else ''))
    on = (FM.CFG.get('modules') or {}).get('panel')
    print(FM.L.get('panel_on' if on else 'panel_off', 'модуль включён' if on else 'модуль выключен (решает владелец: config.json → modules.panel)'))
    return 0


# ---------------------------------------------------------------- a new panel folder
BRIEF_RU = """# Бриф консилиума: {topic}

Один и тот же бриф получает каждый участник; ответы независимы — чужих ответов не читайте.

## Контекст (самодостаточно: участник не видит наш проект)
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
"""
DECISION_RU = """# Решение консилиума: {topic}

Участники и настройки: …

## Проверено нами (факты, которыми сверены утверждения участников)
- …

## В чём согласны все
- …

## Где разошлись — что выбрали и почему
| вопрос | участник → мнение | выбор | почему (проверка) |
|---|---|---|---|

## Порядок, цена, риски
…

## Оценка участников (что дал каждый, где ошибся)
…
"""


def slug(t):
    s = re.sub(r'[^\w\-]+', '_', t.strip().lower(), flags=re.U).strip('_')
    return s[:48] or 'topic'


def new_cmd(a):
    topic = ' '.join(x for x in a if not x.startswith('--')).strip()
    if not topic:
        print('тема: panel new "<тема>"'); return 1
    d = os.path.join(FM.HERE, 'panel', f"{dt.date.today().isoformat()}_{slug(topic)}")
    os.makedirs(d, exist_ok=True)
    for n, tpl in (('BRIEF.md', BRIEF_RU), ('DECISION.md', DECISION_RU)):
        p = os.path.join(d, n)
        if not os.path.exists(p):
            io.open(p, 'w', encoding='utf-8', newline='\n').write(tpl.format(topic=topic))
    print(d)
    return 0


# ---------------------------------------------------------------- run
HEAD = {'ru': ('Ты — независимый эксперт консилиума. Ниже бриф. Ответь самостоятельно (другие участники отвечают отдельно, их ответов ты '
               'не видишь). Отделяй проверенное от предположений, у каждого предложения назови цену и риск. Отвечай на языке брифа.\n\n'),
        'en': ('You are an independent expert on a panel. The brief follows. Answer on your own (the others answer separately; you do not '
               'see them). Separate what is known from guesses; give each proposal its cost and risk. Answer in the brief\'s language.\n\n')}
STANCE = {'против': 'Твоя роль в этом консилиуме — КРИТИК: ищи слабые места, риски и доводы против; не соглашайся из вежливости.\n\n',
          'за': 'Твоя роль в этом консилиуме — ЗАЩИТНИК: найди самые сильные доводы за предложенное направление и как его довести.\n\n',
          'against': 'Your role on this panel is the CRITIC: look for weak points, risks and arguments against; do not agree to be polite.\n\n',
          'for': 'Your role on this panel is the ADVOCATE: find the strongest arguments for the proposed direction and how to make it work.\n\n'}


def sensitive(text):
    """→ the kinds of secrets / private data found in the brief (never the values themselves)"""
    kinds = [name for name, rx in SECRETS if re.search(rx, text)]
    for k, v in os.environ.items():
        if len(v) >= 16 and re.search(r'(?i)key|token|secret|pass', k) and v in text:
            kinds.append(f'значение переменной {k}')
    return kinds


def members_for(a):
    want = None
    if '--members' in a and a.index('--members') + 1 < len(a):
        want = {x.strip() for x in a[a.index('--members') + 1].split(',') if x.strip()}
    rows = [m for m in detect(probe_local=False) if m['kind'] in ('cli', 'api') and m.get('ready')]
    return [m for m in rows if (m['name'] in want if want is not None else m.get('enabled'))]


def ask_cli(m, prompt, folder, timeout):
    pf = os.path.join(folder, f"prompt_{m['name']}.md")
    io.open(pf, 'w', encoding='utf-8', newline='\n').write(prompt)
    out = os.path.join(folder, f".out_{m['name']}.md")
    if os.path.exists(out):
        os.remove(out)
    fill = {'{prompt_file}': pf, '{prompt_name}': os.path.basename(pf), '{out}': out, '{dir}': folder}

    def put(x):
        for k, v in fill.items():
            x = x.replace(k, v)
        return x
    cmd = [put(str(x)) for x in m['cmd']]
    r = subprocess.run(cmd, input=prompt if m.get('stdin') else None, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=timeout, cwd=folder, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    text = io.open(out, encoding='utf-8', errors='replace').read() if os.path.exists(out) else r.stdout
    if os.path.exists(out):
        os.remove(out)
    if r.returncode != 0 and not text.strip():
        raise RuntimeError(f'код {r.returncode}: {_why(r.stderr or r.stdout)}')
    return text.strip(), m.get('model') or m.get('label') or m['name']


def _why(log):
    """the reason a CLI gave, without its plumbing noise: a usage limit / a sign-in first, else its last «ERROR» lines"""
    lines = [l.strip() for l in str(log).splitlines() if l.strip()]
    for key, say in (('usage limit', 'лимит исчерпан'), ('not logged in', 'нужен вход'), ('login', 'нужен вход'), ('quota', 'лимит исчерпан')):
        hit = next((l for l in lines if key in l.lower()), None)
        if hit:
            return f'{say}: {hit[:300]}'
    errs = [l for l in lines if 'error' in l.lower() and 'transport' not in l.lower()]
    return ' | '.join(dict.fromkeys(errs[-3:] or lines[-3:]))[:800]


def ask_api(m, prompt, timeout):
    key = os.environ.get(m.get('key_env') or '', '') if m.get('key_env') else ''
    if m.get('key_env') and not key:
        raise RuntimeError(f"нет переменной {m['key_env']}")
    body = json.dumps({'model': m['model'], 'messages': [{'role': 'user', 'content': prompt}]}).encode('utf-8')
    req = urllib.request.Request(m['base_url'].rstrip('/') + '/chat/completions', data=body, method='POST',
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

    def one(m):
        t0 = time.time()
        try:
            prompt = make_prompt(m)
            text, model = ask_cli(m, prompt, folder, timeout) if m['kind'] == 'cli' else ask_api(m, prompt, timeout)
            if not text:
                raise RuntimeError('пустой ответ')
            head = (f"<!-- panel: member={m['name']}; kind={m['kind']}; model={model}; seconds={time.time() - t0:.0f}; "
                    f"ts={dt.datetime.now().isoformat(timespec='seconds')} -->\n# {m['name']} ({model})\n\n")
            io.open(os.path.join(folder, f"{prefix}_{m['name']}.md"), 'w', encoding='utf-8', newline='\n').write(head + text + '\n')
            results[m['name']] = ('ok', f'{time.time() - t0:.0f} с')
        except Exception as e:                              # (one member down never stops the others)
            msg = 'таймаут' if isinstance(e, subprocess.TimeoutExpired) else str(e)
            io.open(os.path.join(folder, f"{prefix}_{m['name']}.err.md"), 'w', encoding='utf-8', newline='\n').write(
                f"# {m['name']} — не ответил\n\n{msg}\n")
            results[m['name']] = ('ошибка', msg[:160])
    threads = [threading.Thread(target=one, args=(m,), daemon=True) for m in members]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout + 30)
    return results


def _gate(a, folder):
    if not (FM.CFG.get('modules') or {}).get('panel'):
        print(FM.L.get('panel_off_run', 'Консилиум моделей выключен. Включает только владелец: install.py … --modules …,panel или '
                                        'config.json → modules.panel = true. Сначала: foreman.py panel detect — кто доступен.'))
        return None
    if not os.path.isdir(folder) or not os.path.exists(os.path.join(folder, 'BRIEF.md')):
        print(f'нет брифа: {folder}/BRIEF.md (panel new "<тема>")'); return None
    brief = io.open(os.path.join(folder, 'BRIEF.md'), encoding='utf-8').read()
    if len(brief) > LIMIT:
        print(f'бриф длиннее {LIMIT} символов — сократите'); return None
    kinds = sensitive(brief)
    if kinds and '--allow-sensitive' not in a:
        print('В брифе похоже на личное или секретное: ' + ', '.join(dict.fromkeys(kinds)) + '. Наружу не отправлено. Уберите это '
              'из брифа — или, если владелец разрешил, --allow-sensitive.')
        return None
    return brief


def positional(a):
    """the first argument that is neither a flag nor a flag's value"""
    skip = False
    for x in a:
        if skip:
            skip = False
            continue
        if x in ('--members', '--stance'):
            skip = True
            continue
        if not x.startswith('--'):
            return x
    return ''


def run_cmd(a):
    folder = os.path.abspath(positional(a) or '.')
    brief = _gate(a, folder)
    if brief is None:
        return 1
    members = members_for(a)
    if not members:
        print('Внешних участников нет (или все выключены): foreman.py panel detect. Субагентов Claude запускает сам.'); return 1
    stances = {}
    for i, x in enumerate(a):
        if x == '--stance' and i + 1 < len(a) and '=' in a[i + 1]:
            k, _, v = a[i + 1].partition('=')
            stances[k.strip()] = v.strip().lower()
    lang = 'en' if FM.CFG.get('lang') == 'en' else 'ru'
    res = _ask_all(members, lambda m: HEAD[lang] + STANCE.get(stances.get(m['name'], ''), '') + brief, folder, 'answer')
    for name, (st, info) in res.items():
        print(f'  {name:12s} {st:7s} {info}')
    print(folder)
    return 0 if any(st == 'ok' for st, _ in res.values()) else 1


def review_cmd(a):
    """the second round (llm-council): every answer WITHOUT its author's name, in a fixed shuffled order; each member finds the factual
    errors and ranks them. The key (letter → member) stays in review_key.json for Claude, never in a prompt"""
    folder = os.path.abspath(positional(a) or '.')
    brief = _gate(a, folder)
    if brief is None:
        return 1
    answers = sorted(glob.glob(os.path.join(folder, 'answer_*.md')))
    answers = [p for p in answers if not p.endswith('.err.md')]
    if len(answers) < 2:
        print('для второго круга нужно ≥ 2 ответов'); return 1
    order = sorted(answers, key=lambda p: hashlib.sha1((os.path.basename(p) + os.path.basename(folder)).encode()).hexdigest())
    key, parts = {}, []
    for n, p in enumerate(order):
        letter = chr(ord('A') + n)
        key[letter] = os.path.basename(p)[len('answer_'):-3]
        text = re.sub(r'<!--.*?-->\s*', '', io.open(p, encoding='utf-8').read(), flags=re.S)
        text = re.sub(r'^# .*\n', '', text, count=1)
        parts.append(f'## Ответ {letter}\n\n{text.strip()}\n')
    io.open(os.path.join(folder, 'review_key.json'), 'w', encoding='utf-8').write(json.dumps(key, ensure_ascii=False, indent=1))
    ask = ('Второй круг консилиума. Ниже бриф и ответы участников БЕЗ имён (A, B, C…). Для каждого ответа: фактические ошибки и '
           'непроверенные утверждения; что в нём самое ценное; затем общий рейтинг от лучшего к худшему с причиной. Свой прежний ответ '
           'не защищай — оценивай по существу.\n\n# Бриф\n\n' + brief + '\n\n# Ответы\n\n' + '\n'.join(parts))
    if len(ask) > LIMIT * 2:
        print('ответы слишком длинные для второго круга'); return 1
    res = _ask_all(members_for(a), lambda m: ask, folder, 'review')
    for name, (st, info) in res.items():
        print(f'  {name:12s} {st:7s} {info}')
    print(folder)
    return 0 if any(st == 'ok' for st, _ in res.values()) else 1


def main(fm, a):
    global FM
    FM = fm
    sub = a[0] if a else 'detect'
    return {'detect': detect_cmd, 'new': new_cmd, 'run': run_cmd, 'review': review_cmd}.get(sub, lambda x: (print(__doc__), 1)[1])(a[1:])
