"""test_lessons.py — Foreman 2.0 «Lessons» checks (the council's decision of 2026-11-04 as cases): the empty start costs nothing, a rule
is born «proposed» and only the owner's «yes» makes it hot or a guard, recall finds a rule across RU/EN, the prompt hook stays within
its budget, the Stop gate wants a REAL record (the words «записано: …» alone are not one), guards block once, the whole ask is kept,
one writer at a time, the module can be switched off. Standard library only; a throw-away project in the temp folder.
  python tests/test_lessons.py            exit 0 = all passed"""
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
fails = 0


def check(name, ok, info=''):
    global fails
    fails += not ok
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {str(info)[:300]}' if info and not ok else ''))


def fm(proj, *args, stdin=None):
    r = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=proj, input=stdin,
                       capture_output=True, encoding='utf-8')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def hook(proj, mode, payload):
    code, out = fm(proj, 'hook', mode, stdin=json.dumps(payload, ensure_ascii=False))
    try:
        o = json.loads(out) if out.strip() else {}
    except ValueError:
        o = {'raw': out}
    return o


def ctx(o):
    return (o.get('hookSpecificOutput') or {}).get('additionalContext', '')


def transcript(path, owner, assistant_blocks, ts_shift=60):
    ts = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=ts_shift)).isoformat().replace('+00:00', 'Z')
    rows = [{'type': 'user', 'timestamp': ts, 'message': {'role': 'user', 'content': owner}},
            {'type': 'assistant', 'message': {'role': 'assistant', 'content': assistant_blocks}}]
    io.open(path, 'w', encoding='utf-8').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    return path


def install(proj, *extra):
    return subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes', *extra], capture_output=True, encoding='utf-8')


base = tempfile.mkdtemp(prefix='foreman_lessons_')
try:
    proj = os.path.join(base, 'proj')
    os.makedirs(proj)
    r = install(proj)
    f = lambda n: os.path.join(proj, '.foreman', n)
    check('install 2.0', r.returncode == 0 and all(os.path.exists(f(n)) for n in ('recall.py', 'lexicon.json', 'rules.jsonl', 'ledger.md')), r.stdout[-400:])
    settings = json.load(io.open(os.path.join(proj, '.claude', 'settings.local.json'), encoding='utf-8'))
    check('the prompt hook is «hook prompt»', 'hook prompt' in json.dumps(settings))
    cfg = json.load(io.open(f('config.json'), encoding='utf-8'))
    check('modules: promises + lessons on, board off', cfg['modules'] == {'promises': True, 'lessons': True, 'board': False}, cfg.get('modules'))

    # the empty start — an ordinary message costs 0 characters; an ask gets only the inbox note
    o = hook(proj, 'prompt', {'prompt': 'интересно, как вообще устроены такие системы памяти у агентов'})
    check('an ordinary message → no output at all', o == {}, o)
    o = hook(proj, 'prompt', {'prompt': 'сделай экспорт отчёта в CSV и добавь кнопку на страницу'})
    check('an ask → the inbox note only (no rules yet)', 'I-0001' in ctx(o) and 'память' not in ctx(o), ctx(o))
    long_ask = 'сделай отчёт ' + 'очень длинная просьба владельца ' * 200
    hook(proj, 'prompt', {'prompt': long_ask})
    inbox = [json.loads(l) for l in io.open(f('inbox.jsonl'), encoding='utf-8') if l.strip()]
    check('the WHOLE ask is kept (1.1 cut it at 800)', len(inbox[-1]['text']) == len(long_ask.strip()), len(inbox[-1]['text']))
    hook(proj, 'inbox', {'prompt': 'добавь, пожалуйста, тёмную тему в настройки приложения'})
    check('«hook inbox» (the 1.1 name) still files an ask', len([l for l in io.open(f('inbox.jsonl'), encoding='utf-8') if l.strip()]) == 3)

    # rules: refused without a quote; born «proposed», level ≤ 1; hot / guard only after «accept»
    code, out = fm(proj, 'rule', 'add', json.dumps({'when': 'sending a comparison', 'do': 'one picture per variant'}))
    check('a rule without the owner\'s quote is refused', code == 1, out)
    rule = {'when': 'before sending a comparison sheet of several variants', 'do': 'one big picture per variant on a viewer page',
            'quote': 'таблица не читается, всё мелко', 'keys': 'лист таблица сравнение картинки варианты sheet grid compare', 'level': 3}
    code, out = fm(proj, 'rule', 'add', json.dumps(rule, ensure_ascii=False), '--situation', 'пришли мне таблицу сравнения вариантов',
                  '--not', 'как настроить базу данных для отчётов')
    rows = [json.loads(l) for l in io.open(f('rules.jsonl'), encoding='utf-8') if l.strip()]
    check('rule added as R-001, «proposed», level forced to 1', code == 0 and rows[0]['id'] == 'R-001' and rows[0]['status'] == 'proposed'
          and rows[0]['level'] == 1, out)
    check('the ledger got a «kept» line', 'kept -> R-001' in io.open(f('ledger.md'), encoding='utf-8').read())
    code, out = fm(proj, 'rule', 'set', 'R-001', 'level=2')
    check('a proposed rule cannot be hot', code == 1, out)
    code, out = fm(proj, 'recall', 'покажи сравнение вариантов картинками')
    check('recall: a RU situation finds the rule (EN when, RU keys)', 'R-001' in out, out)
    code, out = fm(proj, 'recall', 'migrate the postgres schema')
    check('recall: an unrelated situation finds nothing', 'R-001' not in out, out)
    code, out = fm(proj, 'recall', '--eval')
    check('eval: recall@3 1.0 and no false positive', 'recall@3 1.0' in out and ('ложных срабатываний 0' in out or 'false positives 0' in out), out)
    fm(proj, 'rule', 'accept', 'R-001')
    code, out = fm(proj, 'rule', 'set', 'R-001', 'hot=true')
    o = hook(proj, 'session', {'source': 'startup'})
    check('an accepted hot rule is in the session brief', code == 0 and 'R-001' in ctx(o), ctx(o)[-300:])

    # the prompt hook on a correction: the protocol + the pack, within the budget even for a 5 KB message
    o = hook(proj, 'prompt', {'prompt': 'опять ты прислал огромную таблицу сравнения вариантов, всё мелко, ничего не видно'})
    c = ctx(o)
    check('a correction → the lesson protocol + the rule from recall', 'ПОПРАВКУ' in c and 'R-001' in c, c)
    o = hook(proj, 'prompt', {'prompt': 'опять сравнение вариантов ' + 'слово ' * 900})
    check('the prompt hook output ≤ 1200 characters', len(ctx(o)) <= 1200, len(ctx(o)))
    o = hook(proj, 'prompt', {'prompt': '<agent-message from="x">[Subagent hand-back] опять правило сравнения</agent-message>'})
    check('a subagent hand-back is not the owner → no output', o == {}, o)

    # the Stop gate: a REAL record, not the words
    tp = os.path.join(base, 't.jsonl')
    corr = 'опять ты забыл подписать картинки, это неприемлемо'
    say = lambda t: [{'type': 'text', 'text': t}]
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('Исправил подписи.'))})
    check('a correction without a record → block', o.get('decision') == 'block' and 'ПОПРАВКУ' in o.get('reason', ''), o)
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('Исправил. записано: R-001'))})
    check('the words «записано: R-…» alone are NOT a record → block', o.get('decision') == 'block', o)
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('Готово. уже записано: R-001'))})
    check('«уже записано: R-001» with an existing rule → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('Готово. уже записано: R-777'))})
    check('«уже записано» with a rule that does not exist → block', o.get('decision') == 'block', o)
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('не поправка: владелец уточнил вкус, не правило'))})
    check('«не поправка: …» → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('ok') + [{'type': 'tool_use', 'name': 'Bash',
                            'input': {'command': 'python .foreman/foreman.py rule add \'{...}\''}}])})
    check('a tool call that writes a rule → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('Исправил.'), ts_shift=-3600)})
    check('rules.jsonl changed after the correction (file time) → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, 'спасибо, отличный отчёт получился', say('Рад помочь'))})
    check('an ordinary message → the Stop is free', o == {}, o)
    o = hook(proj, 'stop', {'stop_hook_active': True, 'transcript_path': transcript(tp, corr, say('x'))})
    check('stop_hook_active → never twice', o == {}, o)

    # guards: green → red blocks ONCE; red from the start never blocks
    io.open(os.path.join(proj, 'README.md'), 'w', encoding='utf-8').write('# app\n')
    fm(proj, 'rule', 'add', json.dumps({'when': 'editing the README', 'do': 'no TODO left in it', 'quote': 'никаких TODO в README',
                                         'keys': 'readme todo'}, ensure_ascii=False))
    fm(proj, 'rule', 'accept', 'R-002')
    code, out = fm(proj, 'rule', 'set', 'R-002', 'guard=get:http://x', 'level=3')
    check('a guard must be a file probe', code == 1, out)
    fm(proj, 'rule', 'set', 'R-002', 'guard=nogrep:README.md:TODO', 'level=3')
    quiet = transcript(tp, 'спасибо, хорошо', say('ok'))
    o1 = hook(proj, 'stop', {'transcript_path': quiet})
    io.open(os.path.join(proj, 'README.md'), 'a', encoding='utf-8').write('TODO: later\n')
    o2 = hook(proj, 'stop', {'transcript_path': quiet})
    o3 = hook(proj, 'stop', {'transcript_path': quiet})
    check('guard: green → no block; turns red → block once; stays red → no second block',
          o1 == {} and o2.get('decision') == 'block' and 'R-002' in o2.get('reason', '') and o3 == {}, [o1, o2, o3])
    o = hook(proj, 'session', {'source': 'compact'})
    check('the red guard shows in the session brief', 'R-002' in ctx(o) and len(ctx(o)) <= 2000, ctx(o)[-300:])

    # one writer at a time: two parallel processes add 10 items each
    procs = [subprocess.Popen([PY, '-c', f'''
import subprocess, sys, json
for i in range(10):
    subprocess.run([sys.executable, r"{f('foreman.py')}", "add", json.dumps({{"title": "w{w}-" + str(i), "quote": "q"}})], capture_output=True)
'''], cwd=proj) for w in range(2)]
    for p in procs:
        p.wait()
    titles = [json.loads(l)['title'] for l in io.open(f('promises.jsonl'), encoding='utf-8') if l.strip()]
    check('two writers in parallel: all 20 items kept', len([t for t in titles if t.startswith('w')]) == 20, len(titles))

    # the module switched off adds nothing
    p2 = os.path.join(base, 'proj2')
    os.makedirs(p2)
    install(p2, '--modules', 'promises')
    o = hook(p2, 'prompt', {'prompt': 'опять ты забыл подписать картинки, это неприемлемо'})
    check('--modules promises: a correction gets no lesson note', 'ПОПРАВКУ' not in ctx(o), ctx(o))
    code, out = fm(p2, 'recall', 'картинки')
    check('--modules promises: recall says the module is off', code == 1 and 'off' in out, out)
    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), p2, '--uninstall', '--yes'], capture_output=True, encoding='utf-8')
    s2 = json.load(io.open(os.path.join(p2, '.claude', 'settings.local.json'), encoding='utf-8'))
    check('uninstall leaves no Foreman hook', 'foreman.py' not in json.dumps(s2), s2)
finally:
    shutil.rmtree(base, ignore_errors=True)
print('LESSONS TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
