"""test_v21.py — Foreman 2.1 checks: a probe that could not run is «unknown» with its reason (never a red or a green), the fresh:
probe (a result counts only if made after the last edit), rules keep the date they were last confirmed (stale list, confirm, replace —
never erased), a lesson may be DEFERRED with a reason, the TaskCompleted hook keeps a task naming P-… open while its probes are red.
The positive checks fail on 2.0 (17 of 23); the negative ones guard against over-blocking. Standard library only; throw-away projects in the temp folder.
  python tests/test_v21.py            exit 0 = all passed"""
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

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


def run(proj, *args, stdin=None):
    r = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=proj, input=stdin, capture_output=True,
                       encoding='utf-8')
    return r.returncode, (r.stdout or ''), (r.stderr or '')


def fm(proj, *args, stdin=None):
    code, out, err = run(proj, *args, stdin=stdin)
    return code, out + err


def hook(proj, mode, payload):
    code, out = fm(proj, 'hook', mode, stdin=json.dumps(payload, ensure_ascii=False))
    try:
        return json.loads(out) if out.strip() else {}
    except ValueError:
        return {'raw': out}


def ctx(o):
    return (o.get('hookSpecificOutput') or {}).get('additionalContext', '')


def add(proj, title, probes):
    code, out = fm(proj, 'add', json.dumps({'title': title, 'quote': title, 'probes': probes}, ensure_ascii=False))
    return out.strip().splitlines()[-1]


def state(proj, pid):
    code, out = fm(proj, 'check', pid)
    return out.strip().splitlines()[-1].split(': ', 1)[-1].split(' ')[0], out


def owner_accepts(proj, rid, *more):
    """the owner really says it (the prompt hook logs it), then Claude accepts with his words"""
    words = f'{rid} принимаю, хорошее правило'
    hook(proj, 'prompt', {'prompt': words})
    return fm(proj, 'rule' if rid.startswith('R-') else 'set', 'accept' if rid.startswith('R-') else rid, *([rid] if rid.startswith('R-') else
              ['status=accepted']), *more, '--quote', words)


def install(proj, *extra):
    return subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes', *extra], capture_output=True, encoding='utf-8')


def transcript(path, owner, reply):
    ts = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=60)).isoformat().replace('+00:00', 'Z')
    rows = [{'type': 'user', 'timestamp': ts, 'message': {'role': 'user', 'content': owner}},
            {'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': reply}]}}]
    io.open(path, 'w', encoding='utf-8').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    return path


base = tempfile.mkdtemp(prefix='foreman_v21_')
try:
    proj = os.path.join(base, 'proj')
    os.makedirs(os.path.join(proj, 'src'))
    r = install(proj)
    check('install', r.returncode == 0, r.stdout[-300:])
    io.open(os.path.join(proj, 'src', 'a.py'), 'w').write('x = 1\n')

    # slice 2 — «unknown» with its reason; a real «no» outranks an «unknown»; green + unknown is not «done»
    p1 = add(proj, 'server answers', ['get:http://127.0.0.1:9/never'])
    st, out = state(proj, p1)
    check('a server that does not answer → «unknown» with the reason, not «not»', st == 'unchecked' and 'не отвечает' in out, out)
    p2 = add(proj, 'file + server', ['file:src/a.py', 'get:http://127.0.0.1:9/never'])
    check('green + unknown → «unknown» (2.0 said «partly»)', state(proj, p2)[0] == 'unchecked', state(proj, p2)[1])
    p3 = add(proj, 'missing + server', ['file:src/missing.py', 'get:http://127.0.0.1:9/never'])
    check('a real «no» + unknown → «not» (2.0 hid the red behind «unknown»)', state(proj, p3)[0] == 'not', state(proj, p3)[1])
    p4 = add(proj, 'broken regex', ['grep:src/a.py:x = (1'])
    st, out = state(proj, p4)
    check('a broken regex → «unknown: a broken regex» (2.0: a red «not built»)', st == 'unchecked' and 'регулярка' in out, out)
    p5 = add(proj, 'odd kind', ['foo:bar'])
    check('an unknown probe kind → «unknown» (2.0: red)', state(proj, p5)[0] == 'unchecked', state(proj, p5)[1])

    # slice 2 — fresh:
    rep = os.path.join(proj, 'report.txt')
    time.sleep(0.05)
    io.open(rep, 'w').write('tests passed\n')
    p6 = add(proj, 'tests ran after the last edit', ['fresh:report.txt:src/**/*.py'])
    check('fresh: the report is newer than every source → done', state(proj, p6)[0] == 'done', state(proj, p6)[1])
    later = time.time() + 5
    os.utime(os.path.join(proj, 'src', 'a.py'), (later, later))
    check('fresh: a source edited after the report → not', state(proj, p6)[0] == 'not', state(proj, p6)[1])
    p7 = add(proj, 'fresh with an empty pattern', ['fresh:report.txt:nowhere/*.py'])
    st, out = state(proj, p7)
    check('fresh: a pattern that finds nothing → «unknown» (a typo never turns green)', st == 'unchecked', out)
    p8 = add(proj, 'fresh without a report', ['fresh:no_report.txt:src/*.py'])
    check('fresh: no result at all → not', state(proj, p8)[0] == 'not', state(proj, p8)[1])

    # slice 3 — rules: confirmed date, stale list, confirm, replace (never erased)
    rule = {'when': 'sending a comparison of variants', 'do': 'one big picture per variant', 'quote': 'всё мелко', 'keys': 'сравнение варианты compare'}
    fm(proj, 'rule', 'add', json.dumps(rule, ensure_ascii=False))
    owner_accepts(proj, 'R-001')
    rows = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'rules.jsonl'), encoding='utf-8') if l.strip()]
    check('accept stamps the confirmation date', rows[0].get('confirmed') == dt.date.today().isoformat(), rows[0])
    rows[0]['confirmed'] = '2026-01-01'
    io.open(os.path.join(proj, '.foreman', 'rules.jsonl'), 'w', encoding='utf-8').write(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
    o = hook(proj, 'session', {'source': 'startup'})
    check('a rule unconfirmed for > 60 days is listed in the session brief', 'давно не подтверждались' in ctx(o) and 'R-001' in ctx(o), ctx(o)[-300:])
    code, out = fm(proj, 'rule', 'confirm', 'R-001')
    o = hook(proj, 'session', {'source': 'startup'})
    check('rule confirm → off the stale list', code == 0 and 'давно не подтверждались' not in ctx(o), ctx(o)[-300:])
    rule2 = {'when': 'sending a comparison of variants', 'do': 'a viewer page with arrows', 'quote': 'листай стрелками', 'keys': 'сравнение варианты viewer'}
    fm(proj, 'rule', 'add', json.dumps(rule2, ensure_ascii=False))
    code, out = fm(proj, 'rule', 'replace', 'R-001', '--by', 'R-099')
    check('replace by a rule that does not exist → refused', code == 1, out)
    code, out = fm(proj, 'rule', 'replace', 'R-001', '--by', 'R-002')
    rows = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'rules.jsonl'), encoding='utf-8') if l.strip()]
    check('replace → status «replaced» + replaced_by, the rule is kept', code == 0 and rows[0].get('status') == 'replaced'
          and rows[0].get('replaced_by') == 'R-002' and len(rows) == 2, rows[0])
    code, out = fm(proj, 'recall', 'пришли сравнение вариантов')
    check('a replaced rule is no longer recalled (its successor is)', 'R-001' not in out and 'R-002' in out, out)

    # slice 3 — a deferred lesson (with a reason) passes the gate, is logged once, shows in the brief
    tp = os.path.join(base, 't.jsonl')
    corr = 'опять ты забыл подписать картинки, это неприемлемо'
    o = hook(proj, 'stop', {'transcript_path': transcript(tp, corr, 'Понял. отложено: уточню у владельца, какие подписи нужны')})
    hook(proj, 'stop', {'transcript_path': tp})
    ev = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'events.jsonl'), encoding='utf-8') if l.strip()]
    d = [e for e in ev if e.get('kind') == 'lesson_deferred']
    check('«отложено: <why>» → the Stop passes, the lesson is logged ONCE', o == {} and len(d) == 1 and 'уточню' in d[0].get('why', ''), [o, d])
    code, out = fm(proj, 'cues', '--deferred')
    o = hook(proj, 'session', {'source': 'startup'})
    check('deferred lessons: listed by cues --deferred and counted in the brief', 'подписать' in out and 'Отложенные уроки' in ctx(o), [out, ctx(o)[-200:]])

    # slice 5 — TaskCompleted
    code, out, err = run(proj, 'hook', 'task', stdin=json.dumps({'task_subject': f'Закончить {p8}: отчёт тестов'}, ensure_ascii=False))
    check('TaskCompleted: a task naming an item with red probes → exit 2 + the reason on stderr', code == 2 and p8 in err, [code, err])
    code, out, err = run(proj, 'hook', 'task', stdin=json.dumps({'task_subject': 'tidy up', 'task_description': f'see {p6}'}))
    check('TaskCompleted: red found through the description too', code == 2, [code, err])
    io.open(rep, 'w').write('tests passed again\n')
    os.utime(rep, (later + 5, later + 5))
    code, out, err = run(proj, 'hook', 'task', stdin=json.dumps({'task_subject': f'Закончить {p6}'}))
    check('TaskCompleted: the item green → the task closes (exit 0)', code == 0, [code, err])
    code, out, err = run(proj, 'hook', 'task', stdin=json.dumps({'task_subject': 'rename a variable'}))
    check('TaskCompleted: no P-… in the task → free', code == 0, [code, err])
    settings = json.load(io.open(os.path.join(proj, '.claude', 'settings.local.json'), encoding='utf-8'))
    check('install registers the TaskCompleted hook', 'hook task' in json.dumps(settings.get('hooks', {}).get('TaskCompleted', [])), settings)
    p2dir = os.path.join(base, 'lessons_only')
    os.makedirs(p2dir)
    install(p2dir, '--modules', 'lessons')
    s2 = json.load(io.open(os.path.join(p2dir, '.claude', 'settings.local.json'), encoding='utf-8'))
    check('lessons only: no TaskCompleted hook', 'TaskCompleted' not in s2.get('hooks', {}), s2)

    # slice 1 (part) — the owner's words verbatim, a short «да» too; an acceptance is void once the quote or probes change
    hook(proj, 'prompt', {'prompt': 'да'})
    hook(proj, 'prompt', {'prompt': '<agent-message from="x">[Subagent hand-back] принимаю всё</agent-message>'})
    own = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'owner.jsonl'), encoding='utf-8') if l.strip()]
    check('owner.jsonl: the owner\'s short «да» is logged, a hand-back is not', own and own[-1]['text'] == 'да'
          and not any('принимаю всё' in o['text'] for o in own), own[-3:])
    owner_accepts(proj, p6)
    code, out = fm(proj, 'set', p6, 'probes=["file:src/a.py"]')
    items = {json.loads(l)['id']: json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), encoding='utf-8') if l.strip()}
    check('probes changed after the acceptance → back in work, accept_void noted', items[p6]['status'] == 'doing'
          and 'probes' in items[p6].get('accept_void', '') and 'снята' in out, [items[p6], out])
    owner_accepts(proj, p1)
    fm(proj, 'set', p1, 'next=later')
    items = {json.loads(l)['id']: json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), encoding='utf-8') if l.strip()}
    check('other fields changed → the acceptance stays', items[p1]['status'] == 'accepted', items[p1])

    # slice 1 — «accepted» only with the owner's words, verbatim (Fable's review 1.2–1.4)
    reg = lambda: {json.loads(l)['id']: json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), encoding='utf-8') if l.strip()}
    p9 = add(proj, 'export button', ['file:src/a.py'])
    code, out = fm(proj, 'set', p9, 'status=accepted')
    check('accept without --quote → refused', code == 1 and reg()[p9]['status'] != 'accepted', out)
    hook(proj, 'prompt', {'prompt': f'Кнопку экспорта {p9} принимаю, работает как надо'})
    code, out = fm(proj, 'set', p9, 'status=accepted', '--quote', 'кнопка экспорта принята, всё работает')
    check('a paraphrase of the owner → refused', code == 1 and reg()[p9]['status'] != 'accepted', out)
    code, out = fm(proj, 'set', p9, 'status=accepted', '--quote', f'кнопку экспорта {p9} принимаю')
    acc = reg()[p9].get('accepted') or {}
    check('his words verbatim (case, «», ё normalised) → accepted + the record', code == 0 and reg()[p9]['status'] == 'accepted'
          and acc.get('by') == 'owner-quote' and acc.get('msg_ts'), [out, acc])
    p10 = add(proj, 'import button', ['file:src/a.py'])
    code, out = fm(proj, 'set', p10, 'status=accepted', 'probes=["file:nothing"]', '--quote', f'кнопку экспорта {p9} принимаю')
    check('accept together with new probes in one command → refused', code == 1, out)
    tq = os.path.join(base, 'q.jsonl')
    io.open(tq, 'w', encoding='utf-8').write(json.dumps({'type': 'assistant', 'message': {'role': 'assistant', 'content': [
        {'type': 'text', 'text': f'Готово: {p10} — импорт работает, пробы зелёные. Принять?'}]}}, ensure_ascii=False) + '\n')
    hook(proj, 'prompt', {'prompt': 'да', 'transcript_path': tq})
    code, out = fm(proj, 'set', p10, 'status=accepted', '--quote', 'да')
    check('a short «да» to a reply that named the id → accepted', code == 0 and reg()[p10]['status'] == 'accepted', out)
    p11 = add(proj, 'third button', ['file:src/a.py'])
    code, out = fm(proj, 'set', p11, 'status=accepted', '--quote', 'да')
    check('the same «да» for an id the reply did NOT name → refused', code == 1, out)
    own = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'owner.jsonl'), encoding='utf-8') if l.strip()]
    for o in own:
        o['ts'] = '2026-01-01T10:00:00'
    io.open(os.path.join(proj, '.foreman', 'owner.jsonl'), 'w', encoding='utf-8').write(''.join(json.dumps(o, ensure_ascii=False) + '\n' for o in own))
    code, out = fm(proj, 'set', p11, 'status=accepted', '--quote', f'кнопку экспорта {p9} принимаю')
    check('the owner\'s words older than 14 days → refused', code == 1, out)
    rr = os.path.join(proj, '.foreman', 'promises.jsonl')
    rows = [json.loads(l) for l in io.open(rr, encoding='utf-8') if l.strip()]
    for r in rows:
        if r['id'] == p11:
            r['status'] = 'accepted'
    io.open(rr, 'w', encoding='utf-8').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    code, out = fm(proj, 'brief')
    check('«accepted» written around the check → «Принято без слова владельца» in the brief', 'без слова владельца' in out and p11 in out, out[-300:])
    install(proj)
    code, out = fm(proj, 'brief')
    check('an update marks earlier acceptances legacy (once) → the line is gone', 'без слова владельца' not in out
          and reg()[p11].get('accepted') == {'legacy': True}, out[-300:])
    fm(proj, 'rule', 'add', json.dumps({'when': 'w3', 'do': 'd3', 'quote': 'q3', 'keys': 'k3'}))
    fm(proj, 'rule', 'add', json.dumps({'when': 'w4', 'do': 'd4', 'quote': 'q4', 'keys': 'k4'}))
    io.open(tq, 'w', encoding='utf-8').write(json.dumps({'type': 'assistant', 'message': {'role': 'assistant', 'content': [
        {'type': 'text', 'text': 'Принять правила R-003 и R-004?'}]}}, ensure_ascii=False) + '\n')
    hook(proj, 'prompt', {'prompt': 'принимаю', 'transcript_path': tq})
    code, out = fm(proj, 'rule', 'accept', 'R-003', 'R-004', '--quote', 'принимаю')
    rules = {json.loads(l)['id']: json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'rules.jsonl'), encoding='utf-8') if l.strip()}
    check('two rules at once with one «принимаю» to a reply naming both', code == 0 and rules['R-003']['status'] == 'active'
          and rules['R-004']['status'] == 'active', out)

    # slice 1 — the edit gate (who checks the checker); markers from last_assistant_message (Fable's review 1.5, 1.6)
    def turn(*blocks, reply='Готово.'):
        rows = [{'type': 'user', 'timestamp': dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
                 'message': {'role': 'user', 'content': 'сделай отчёт по тестам'}}]
        rows += [{'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'tool_use', 'name': n, 'input': i}]}} for n, i in blocks]
        rows.append({'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': reply}]}})
        p = os.path.join(base, f'e{len(blocks)}{abs(hash(str(blocks) + reply)) % 10 ** 6}.jsonl')
        io.open(p, 'w', encoding='utf-8').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
        return p
    rf = os.path.join(proj, '.foreman', 'rules.jsonl')
    t1 = turn(('Write', {'file_path': rf, 'content': '{}'}))
    o1 = hook(proj, 'stop', {'transcript_path': t1})
    o2 = hook(proj, 'stop', {'transcript_path': t1})
    check('a direct Write of .foreman/rules.jsonl → block once (the second Stop of the turn passes)',
          o1.get('decision') == 'block' and 'правка проверок' in o1.get('reason', '').lower() and o2 == {}, [o1, o2])
    o = hook(proj, 'stop', {'transcript_path': turn(('Edit', {'file_path': os.path.join(proj, '.claude', 'settings.local.json')}),
                                                    reply='правка проверок: владелец попросил добавить хук')})
    check('an edit of the hook settings + «правка проверок: <why>» → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': turn(('Bash', {'command': 'python .foreman/foreman.py rule add \'{"when": "x"}\''}),
                                                    ('Bash', {'command': 'cat .foreman/rules.jsonl'}))})
    check('the engine\'s own commands and a plain read → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': turn(('Bash', {'command': 'curl -X POST http://127.0.0.1:8765/fm/api/accept'}))})
    check('driving the board\'s API → block', o.get('decision') == 'block', o)
    o = hook(proj, 'stop', {'transcript_path': turn(('Bash', {'command': 'curl http://127.0.0.1:8001/api/presets'}))})
    check('another local server\'s /api/ → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': turn(('Bash', {'command': 'git add -A && git commit -q -m "board: foreman.py board --token-file F"'}))})
    check('a commit message that only NAMES the board → pass', o == {}, o)
    other = os.path.join(base, 'other_project')
    o = hook(proj, 'stop', {'transcript_path': turn(('Write', {'file_path': os.path.join(other, '.foreman', 'rules.jsonl'), 'content': '{}'}),
                                                    ('Bash', {'command': f'S="{other}"; cp a.json "$S/.foreman/promises.jsonl"'}),
                                                    ('Bash', {'command': f'python install.py "{other}" --yes --modules lessons'}))})
    check('edits of ANOTHER project\'s .foreman (a test copy) are not this project\'s checks → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': turn(('Bash', {'command': f'S="{proj}"; cp a.json "$S/.foreman/promises.jsonl"'}))})
    check('…but the same command aimed at THIS project → block', o.get('decision') == 'block', o)
    o = hook(proj, 'stop', {'transcript_path': turn(('Bash', {'command': f'S="{base}"; P="$S/other_project"; cd "$P" && F="python .foreman/foreman.py" && echo x > .foreman/promises.jsonl'}))})
    check('a relative .foreman path after `cd` to another project → pass', o == {}, o)
    o = hook(proj, 'stop', {'transcript_path': turn(('Bash', {'command': "python -c \"open('.foreman/promises.jsonl','w').write('')\""}))})
    check('a python one-liner writing promises.jsonl → block', o.get('decision') == 'block', o)
    tl = os.path.join(base, 'last.jsonl')
    io.open(tl, 'w', encoding='utf-8').write(json.dumps({'type': 'user', 'timestamp': dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
        'message': {'role': 'user', 'content': 'опять ты забыл подписать картинки, это неприемлемо'}}, ensure_ascii=False) + '\n')
    o = hook(proj, 'stop', {'transcript_path': tl, 'last_assistant_message': 'не поправка: владелец уточнил вкус, не правило'})
    check('the marker only in last_assistant_message (the transcript lacks the reply) → pass', o == {}, o)

    # slice 2 — an «unknown» guard changes nothing (Fable's review 2.2)
    hook(proj, 'prompt', {'prompt': 'R-004 стражем делаем, принимаю'})
    fm(proj, 'rule', 'set', 'R-004', 'guard=fresh:report.txt:nowhere/*.x', 'level=3')
    quiet = turn(reply='ок')
    o = hook(proj, 'stop', {'transcript_path': quiet})
    ev = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'events.jsonl'), encoding='utf-8') if l.strip()]
    check('a guard whose probe is «unknown» → no block, no state logged', o == {} and not any(e.get('kind') == 'guard' and e.get('id') == 'R-004' for e in ev), o)
finally:
    shutil.rmtree(base, ignore_errors=True)
print('V2.1 TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
