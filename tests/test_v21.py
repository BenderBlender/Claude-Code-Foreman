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
    fm(proj, 'rule', 'accept', 'R-001')
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
finally:
    shutil.rmtree(base, ignore_errors=True)
print('V2.1 TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
