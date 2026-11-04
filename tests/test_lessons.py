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

try:
    sys.stdout.reconfigure(encoding='utf-8')            # (a cp1251 console: the checks' names carry «…» and «→»)
except Exception:
    pass
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


def rows_file(path, rows):
    """a transcript of real-format rows: ('owner', text) · ('say', text) · ('tool', name, input) · ('meta', text) · ('summary', text)"""
    ts = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=60)).isoformat().replace('+00:00', 'Z')
    out = []
    for r in rows:
        if r[0] in ('owner', 'meta', 'summary'):
            out.append({'type': 'user', 'timestamp': ts, 'message': {'role': 'user', 'content': r[1]},
                        **({'isMeta': True} if r[0] == 'meta' else {'isCompactSummary': True} if r[0] == 'summary' else {})})
        elif r[0] == 'say':
            out.append({'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': r[1]}]}})
        else:
            out.append({'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'tool_use', 'name': r[1], 'input': r[2]}]}})
    io.open(path, 'w', encoding='utf-8').write(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in out))
    return path


def owner_accepts(proj, rid, *more):
    """the owner really says it (the prompt hook logs it), then Claude accepts with his words"""
    words = f'{rid} принимаю, хорошее правило'
    hook(proj, 'prompt', {'prompt': words})
    return fm(proj, 'rule' if rid.startswith('R-') else 'set', 'accept' if rid.startswith('R-') else rid, *([rid] if rid.startswith('R-') else
              ['status=accepted']), *more, '--quote', words)


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
    check('modules: promises + lessons on, board and panel off', cfg['modules'] == {'promises': True, 'lessons': True, 'board': False,
                                                                                     'panel': False}, cfg.get('modules'))

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
    owner_accepts(proj, 'R-001')
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

    # the app's own rows are not the owner (Fable's final review 04.11: every compaction / background notice blocked)
    o = hook(proj, 'stop', {'transcript_path': rows_file(tp, [('owner', 'сделай отчёт по тестам'), ('say', 'делаю'),
             ('summary', 'This session is being continued… the owner said «опять забыл подписать», the rule …'), ('say', 'Готово.')])})
    check('the compaction summary is not the owner → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': rows_file(tp, [('owner', corr), ('say', 'не поправка: вкус, не правило'),
             ('owner', '<task-notification><task-id>a1</task-id><status>completed</status></task-notification>'),
             ('say', 'Фоновый агент закончил: отчёт в report.md.')])})
    check('a background notice after an answered correction → pass (no re-judging)', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': rows_file(tp, [('owner', 'спасибо, всё понятно и отлично'), ('say', 'ок'),
             ('meta', 'Stop hook feedback: ПРОРАБ·урок … похоже на ПОПРАВКУ «опять ты забыл» … ОДНО правило'), ('say', 'ок')])})
    check('the hook\'s own feedback row is not the owner → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': rows_file(tp, [('owner', corr), ('tool', 'Bash', {'command': 'cat .foreman/rules.jsonl'}),
             ('say', 'Исправил.')])})
    check('a command that only READS the rules is not a record → block', o.get('decision') == 'block', o)
    io.open(os.path.join(proj, '.foreman', 'inbox.jsonl'), 'a', encoding='utf-8').write('{"id": "I-9", "text": "обре\n')
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, say('Исправил подписи.'))})
    check('a corrupted inbox line does not silence the Stop hook → block', o.get('decision') == 'block' and 'ПОПРАВКУ' in o.get('reason', ''), o)
    code, out = fm(proj, 'rule', 'set', 'R-001', 'level=abc')
    check('rule set level=abc → a message, not a traceback', code == 1 and 'Traceback' not in out, out)

    # guards: green → red blocks ONCE; red from the start never blocks
    io.open(os.path.join(proj, 'README.md'), 'w', encoding='utf-8').write('# app\n')
    fm(proj, 'rule', 'add', json.dumps({'when': 'editing the README', 'do': 'no TODO left in it', 'quote': 'никаких TODO в README',
                                         'keys': 'readme todo'}, ensure_ascii=False))
    owner_accepts(proj, 'R-002')
    code, out = fm(proj, 'rule', 'set', 'R-002', 'guard=get:http://x', 'level=3')
    check('a guard must be a file probe', code == 1, out)
    fm(proj, 'rule', 'set', 'R-002', 'guard=nogrep:README.md:TODO', 'level=3')
    quiet = transcript(tp, 'спасибо, хорошо', say('ok'))
    o1 = hook(proj, 'stop', {'transcript_path': quiet})
    io.open(os.path.join(proj, 'README.md'), 'a', encoding='utf-8').write('TODO: later\n')
    fm(proj, 'status')                                      # (a status / a brief in between must not spend the block — review 04.11)
    hook(proj, 'session', {'source': 'compact'})
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

    # lessons only, in a project with its own rule book, judge and council skill (our own install, 04.11)
    p3 = os.path.join(base, 'proj3')
    own = {os.path.join(p3, '.claude', 'agents', 'foreman-judge.md'): 'our judge\n',
           os.path.join(p3, '.claude', 'skills', 'foreman-council', 'SKILL.md'): 'our council\n'}
    for path, text in own.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        io.open(path, 'w', encoding='utf-8').write(text)
    r = install(p3, '--modules', 'lessons')
    check('--modules lessons: the self-test passes (a quiet session is right)', r.returncode == 0, r.stdout[-400:])
    check('--modules lessons: the own judge and council skill untouched, no foreman agent',
          all(io.open(p, encoding='utf-8').read() == t for p, t in own.items())
          and not os.path.exists(os.path.join(p3, '.claude', 'agents', 'foreman.md')))
    c3 = json.load(io.open(os.path.join(p3, '.foreman', 'config.json'), encoding='utf-8'))
    c3['lessons']['record_hint'] = 'a row in docs/rules.md'
    io.open(os.path.join(p3, '.foreman', 'config.json'), 'w', encoding='utf-8').write(json.dumps(c3))
    o = hook(p3, 'prompt', {'prompt': 'опять ты забыл подписать картинки, это неприемлемо'})
    check('record_hint: the lesson note points at the own book, not rule add', 'docs/rules.md' in ctx(o) and 'rule add' not in ctx(o), ctx(o))
    install(p3)
    md = io.open(os.path.join(p3, 'CLAUDE.md'), encoding='utf-8').read()
    check('record_hint: the CLAUDE.md section points at the own book (an update keeps the hint and lessons only)',
          'docs/rules.md' in md and 'rule add' not in md and 'rules.jsonl' not in md, md[-400:])
    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), p3, '--uninstall', '--yes'], capture_output=True, encoding='utf-8')
    check('uninstall keeps the owner\'s own judge and council skill', all(os.path.exists(p) for p in own), r.stdout[-300:])
finally:
    shutil.rmtree(base, ignore_errors=True)
print('LESSONS TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
