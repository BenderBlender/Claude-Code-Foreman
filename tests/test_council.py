"""test_council.py — the council's checks (the review of 1.1, 2026-11-04): each finding of the review is a case here, so it can't
come back. Standard library only; installs Foreman into a throw-away project in the system temp folder and removes it.
  python tests/test_council.py            exit 0 = all passed"""
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
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {info}' if info and not ok else ''))


def fm(proj, *args, cwd=None, stdin=None):
    r = subprocess.run([PY, '-X', 'utf8', os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=cwd or proj, input=stdin,
                       capture_output=True, text=True, encoding='utf-8')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def registry(proj):
    return [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), encoding='utf-8') if l.strip()]


base = tempfile.mkdtemp(prefix='foreman_test_')
try:
    proj, cand_a, empty = (os.path.join(base, n) for n in ('proj', 'cand-a', 'cand-empty'))
    for d in (os.path.join(proj, 'src'), os.path.join(cand_a, 'src'), empty):
        os.makedirs(d)
    io.open(os.path.join(cand_a, 'src', 'app.py'), 'w').write('def export_csv(): pass\n')
    r = subprocess.run([PY, '-X', 'utf8', os.path.join(KIT, 'install.py'), proj, '--yes', '--lang', 'en'], capture_output=True,
                       text=True, encoding='utf-8')
    check('install', r.returncode == 0 and os.path.exists(os.path.join(proj, '.foreman', 'foreman.py')), r.stdout[-300:])
    fm(proj, 'add', json.dumps({'title': 'csv', 'quote': 'q', 'priority': 'high', 'probes': ['file:src/app.py', 'grep:src/app.py:def export_csv']}))
    abs_probe = 'file:' + os.path.join(proj, 'src').replace('\\', '/')
    fm(proj, 'add', json.dumps({'title': 'abs', 'quote': 'q', 'probes': [abs_probe, 'get:http://127.0.0.1:9/never']}))

    # 1 — candidate paths are relative to the PROJECT, not to the folder the command is typed in
    code, out = fm(proj, 'compare', 'P-001', 'L=.', 'A=../cand-a', cwd=os.path.join(proj, 'src'))
    check('compare from a subfolder resolves against the project', code == 0 and 'A (../cand-a): done 2/2' in out and 'L (.): not' in out, out)
    code, out = fm(proj, 'compare', 'P-001', 'L=.', 'B=../no-such')
    check('a missing candidate folder → exit 1', code == 1 and 'no such folder' in out, out)
    # 2 — probes that don't depend on the folder are «not comparable» on a candidate
    code, out = fm(proj, 'compare', 'P-002', 'L=.', 'E=../cand-empty')
    check('an empty folder does not pass by absolute / server probes', 'E (../cand-empty): unchecked 0/2' in out and 'not comparable' in out, out)
    # 8, 9 — arguments without «=», no green at all
    code, out = fm(proj, 'compare', 'P-001', '../cand-a')
    check('compare refuses arguments without «=»', code == 1 and 'LABEL=FOLDER' in out, out)
    code, out = fm(proj, 'compare', 'P-001', 'L=.', 'E=../cand-empty')
    check('no «most green» when nothing passes', 'No candidate passes any probe' in out, out)
    code, out = fm(proj, 'check', 'P-001', '--root', '../cand-a')
    check('check on a candidate: done → exit 0', code == 0 and 'done (2/2)' in out, out)
    code, out = fm(proj, 'check', 'P-001')
    check('check on the project: not done → exit 1', code == 1, out)

    # 4 — round validation, stop, no override of n / date
    for bad in ('{}', '{"tried": "L"}', '{"tried": ["L"], "accepted": "false"}', '{"tried": ["L","A"], "accepted": true}', 'not json'):
        code, out = fm(proj, 'round', 'P-001', bad)
        check(f'round refuses {bad}', code == 1, out)
    code, out = fm(proj, 'round', 'P-001', '{"tried": ["L","A"], "winner": "A", "accepted": true, "n": 99, "date": "x", "why": "A green"}')
    rec = registry(proj)[0]['rounds'][-1]
    check('round 1 logged; n and date are the engine\'s', code == 0 and rec['n'] == 1 and rec['date'] != 'x', out)
    rf = os.path.join(base, 'round.json')
    io.open(rf, 'w', encoding='utf-8').write('{"tried": ["L","B"], "accepted": false, "why": "B no better"}')
    code, out = fm(proj, 'round', 'P-001', '@' + rf)
    check('round from @file (PowerShell-safe)', code == 0 and 'round 2/3' in out, out)
    code, out = fm(proj, 'round', 'P-001', '{"tried": ["L","C"], "accepted": false}')
    check('2 rounds without a gain → STOP, leader kept', 'COUNCIL STOP' in out and 'BEST (A)' in out, out)
    check('the item is marked stopped', registry(proj)[0].get('council') == 'stopped')
    code, out = fm(proj, 'round', 'P-001', '{"tried": ["L","D"], "accepted": false}')
    check('a round after STOP is refused', code == 1 and 'has stopped' in out, out)
    code, out = fm(proj, 'brief')
    check('a stopped council is not listed as running', 'Council:' not in out, out)

    # 3 — the frozen criteria and the guarded fields; the brief and the hook survive bad data
    code, out = fm(proj, 'set', 'P-001', 'probes=["file:x"]')
    check('probes frozen after a round', code == 1 and 'frozen' in out, out)
    code, out = fm(proj, 'set', 'P-001', 'rounds=')
    check('set rounds without --force refused', code == 1 and 'keeps the field' in out, out)
    code, out = fm(proj, 'set', 'P-001', 'rounds="[]"', '--force')
    check('set rounds to a non-list refused even with --force', code == 1, out)
    lines = io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), encoding='utf-8').read().splitlines()
    it = json.loads(lines[0]); it['rounds'] = '[]'; lines[0] = json.dumps(it)
    io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    code, out = fm(proj, 'brief')
    check('brief survives a hand-broken «rounds»', code in (0, 2) and 'Traceback' not in out, out)
    code, out = fm(proj, 'hook', 'session', stdin='{"source": "compact"}')
    check('the session hook still answers', 'additionalContext' in out, out[:200])

    # 7, 11 — the installer never replaces an unreadable settings file nor guesses a half-marked CLAUDE.md section
    p2 = os.path.join(base, 'proj2')
    os.makedirs(os.path.join(p2, '.claude'))
    io.open(os.path.join(p2, '.claude', 'settings.local.json'), 'w').write('{"permissions": {"allow": []},}')
    r = subprocess.run([PY, '-X', 'utf8', os.path.join(KIT, 'install.py'), p2, '--yes'], capture_output=True, text=True, encoding='utf-8')
    kept = io.open(os.path.join(p2, '.claude', 'settings.local.json')).read() == '{"permissions": {"allow": []},}'
    check('an unreadable settings.local.json stops the install, untouched', r.returncode != 0 and kept, r.stdout[-200:])
    p3 = os.path.join(base, 'proj3')
    os.makedirs(p3)
    io.open(os.path.join(p3, 'CLAUDE.md'), 'w', encoding='utf-8').write('# mine\n<!-- foreman:start -->\nhalf\n')
    subprocess.run([PY, '-X', 'utf8', os.path.join(KIT, 'install.py'), p3, '--yes'], capture_output=True, text=True, encoding='utf-8')
    text = io.open(os.path.join(p3, 'CLAUDE.md'), encoding='utf-8').read()
    check('a half-marked CLAUDE.md is left alone', text.count('<!-- foreman:start -->') == 1, text)

    # update keeps the data; uninstall removes ours only
    r = subprocess.run([PY, '-X', 'utf8', os.path.join(KIT, 'install.py'), proj, '--yes', '--lang', 'en'], capture_output=True, text=True, encoding='utf-8')
    check('update keeps the registry', len(registry(proj)) == 2 and r.returncode == 0)
    r = subprocess.run([PY, '-X', 'utf8', os.path.join(KIT, 'install.py'), proj, '--uninstall', '--yes'], capture_output=True, text=True, encoding='utf-8')
    gone = not any(os.path.exists(os.path.join(proj, '.claude', *p)) for p in (('agents', 'foreman.md'), ('agents', 'foreman-judge.md'),
                                                                                 ('skills', 'foreman-council', 'SKILL.md')))
    check('uninstall removes the agents and the skill', r.returncode == 0 and gone, r.stdout[-200:])
finally:
    shutil.rmtree(base, ignore_errors=True)
print('COUNCIL TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
