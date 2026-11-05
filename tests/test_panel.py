"""test_panel.py — Foreman 2.2's model panel: offered, never forced (a silent install switches nothing on, a run is refused while the
module is off, a member the owner did not switch on never gets the brief, a brief leaves only on the owner's own logged words), members
found (a CLI in PATH, a key's NAME in the environment), one brief to every switched-on member in parallel with each answer in its own
file, a CLI member in an empty folder outside the project with the keys it must not use taken out of its environment, a hung member
behind a .cmd shim killed with its children, an API key sent but never written, a critic's stance, a brief with secrets never leaves,
the second round without names. Standard library only; fake members.
  python tests/test_panel.py            exit 0 = all passed"""
import glob
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')            # (a cp1251 console: the checks' names carry «…» and «→» — review S3)
except Exception:
    pass
KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
FAKE = os.path.join(KIT, 'tests', 'fixtures', 'fake_model_cli.py')
fails = 0


def check(name, ok, info=''):
    global fails
    fails += not ok
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {str(info)[:300]}' if info and not ok else ''))


def fm(proj, *args, env=None, stdin=None):
    r = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=proj, capture_output=True, encoding='utf-8',
                       input=stdin, env={**os.environ, 'PYTHONIOENCODING': 'utf-8', **(env or {})})
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def install(proj, *extra, env=None):
    return subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes', *extra], capture_output=True, encoding='utf-8',
                          env={**os.environ, **(env or {})})


def owner(proj, text):
    fm(proj, 'hook', 'prompt', stdin=json.dumps({'prompt': text}, ensure_ascii=False))


def shim(bindir, name, *args):
    """a .cmd shim on Windows (as npm installs gemini / qwen), a shell script elsewhere"""
    if os.name == 'nt':
        p = os.path.join(bindir, name + '.cmd')
        io.open(p, 'w').write(f'@"{PY}" "{FAKE}" {" ".join(args)} %*\n')
    else:
        p = os.path.join(bindir, name)
        io.open(p, 'w').write(f'#!/bin/sh\nexec "{PY}" "{FAKE}" {" ".join(args)} "$@"\n')
        os.chmod(p, 0o755)
    return p


def alive(pid):
    if os.name == 'nt':
        # (bytes: on a Russian Windows tasklist prints in the console's OEM code page — text=True decoded it with the ANSI one,
        #  the reader thread failed and stdout came back None; 2.3)
        r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True)
        return str(pid) in (r.stdout or b'').decode('cp866', 'replace')
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class FakeAPI(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode('utf-8'))
        FakeAPI.seen.append({'auth': self.headers.get('Authorization'), 'path': self.path, 'body': body})
        if self.path.endswith('/api/chat'):                 # (Ollama's own address)
            out = json.dumps({'model': body.get('model'), 'message': {'role': 'assistant', 'content': 'OLLAMA ANSWER: ок'}}).encode()
        else:
            out = json.dumps({'model': body.get('model'), 'choices': [{'message': {'role': 'assistant', 'content': 'API ANSWER: ок'}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)


base = tempfile.mkdtemp(prefix='foreman_panel_')
srv = None
try:
    bindir = os.path.join(base, 'bin')
    os.makedirs(bindir)
    shim(bindir, 'gemini')
    penv = {'PATH': bindir + os.pathsep + os.environ.get('PATH', '')}

    # offered, never forced
    p0 = os.path.join(base, 'silent')
    os.makedirs(p0)
    install(p0, env=penv)
    c0 = json.load(io.open(os.path.join(p0, '.foreman', 'config.json'), encoding='utf-8'))
    g0 = next((m for m in c0['panel']['members'] if m['name'] == 'gemini'), {})
    check('a silent install leaves the panel OFF and every found member switched off', c0['modules'].get('panel') is False
          and g0 and g0.get('enabled') is False, [c0['modules'], g0])
    check('…and installs no panel skill', not os.path.exists(os.path.join(p0, '.claude', 'skills', 'foreman-panel')))
    code, out = fm(p0, 'panel', 'new', 'тема')
    code, out = fm(p0, 'panel', 'run', out.strip().splitlines()[-1])
    check('panel run while the module is off → refused, says who switches it on', code == 1 and 'владел' in out, out)

    proj = os.path.join(base, 'proj')
    os.makedirs(proj)
    r = install(proj, '--modules', 'promises,lessons,panel', env=penv)
    cfgp = os.path.join(proj, '.foreman', 'config.json')
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    check('--modules …,panel (the owner named it) → on, the found members on, the skill and the CLAUDE.md rule 10', r.returncode == 0
          and cfg['modules'].get('panel') and next((m for m in cfg['panel']['members'] if m['name'] == 'gemini'), {}).get('enabled')
          and os.path.exists(os.path.join(proj, '.claude', 'skills', 'foreman-panel', 'SKILL.md'))
          and 'консилиум моделей' in io.open(os.path.join(proj, 'CLAUDE.md'), encoding='utf-8').read(), r.stdout[-300:])

    # detection: a CLI in PATH, a key's NAME, a CLI that appears later is NOT switched on
    shim(bindir, 'qwen')
    code, out = fm(proj, 'panel', 'detect', '--json', '--no-local', env={**penv, 'OPENROUTER_API_KEY': 'or-test-key-0123456789'})
    rows = {m['name']: m for m in json.loads(out[out.index('['):])}
    check('detect: a CLI in PATH → a cli member, ready', rows.get('gemini', {}).get('kind') == 'cli' and rows['gemini'].get('ready'), list(rows))
    check('detect: a CLI that appeared AFTER the install is listed switched OFF', rows.get('qwen') and rows['qwen'].get('enabled') is False, rows.get('qwen'))
    check('detect: a key → an api member named by the variable, not ready without a model; the key not printed',
          rows.get('openrouter', {}).get('key_env') == 'OPENROUTER_API_KEY' and not rows['openrouter'].get('ready') and 'or-test-key' not in out,
          rows.get('openrouter'))

    # the members the test drives
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeAPI)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    slow = shim(bindir, 'slowmodel', '--sleep', '60', '--pidfile', os.path.join(base, 'slow.pid'))
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['panel']['timeout_s'] = 4
    cfg['panel']['members'] += [
        {'name': 'fake', 'kind': 'cli', 'cmd': [PY, FAKE, '--ls', '--env', 'FAKE_KEEP_ME'], 'stdin': True, 'enabled': True},
        {'name': 'strip', 'kind': 'cli', 'cmd': [PY, FAKE, '--env', 'FAKE_STRIP_ME'], 'stdin': True, 'enabled': True, 'strip_env': ['FAKE_STRIP_ME']},
        {'name': 'slow', 'kind': 'cli', 'cmd': [slow], 'stdin': True, 'enabled': True},
        {'name': 'off', 'kind': 'cli', 'cmd': [PY, FAKE], 'stdin': True, 'enabled': False},
        {'name': 'withargs', 'kind': 'cli', 'cmd': [PY, FAKE], 'stdin': True, 'enabled': True, 'args': ['--env', 'FAKE_KEEP_ME']},
        {'name': 'ollama', 'kind': 'api', 'base_url': f'http://127.0.0.1:{srv.server_address[1]}/v1', 'key_env': '', 'model': 'llama-test',
         'enabled': True},
        {'name': 'fakeapi', 'kind': 'api', 'base_url': f'http://127.0.0.1:{srv.server_address[1]}/v1', 'key_env': 'FAKE_PANEL_KEY',
         'model': 'fake-1', 'enabled': True, 'params': {'temperature': 0.2}}]
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False))
    code, out = fm(proj, 'panel', 'new', 'Выбор формата хранения')
    d = out.strip().splitlines()[-1]
    io.open(os.path.join(d, 'BRIEF.md'), 'w', encoding='utf-8').write('# Бриф\n\nКакой формат хранения выбрать: JSONL или SQLite? Цена и риск.\n')
    renv = {**penv, 'FAKE_PANEL_KEY': 'k-secret-0123456789abcdef', 'FAKE_STRIP_ME': 'x', 'FAKE_KEEP_ME': 'y'}
    words = 'да, отправь консилиуму этот бриф'
    members = 'fake,strip,fakeapi'

    code, out = fm(proj, 'panel', 'run', d, '--members', members, '--owner-ok', words, env=renv)
    check('a member the engine did not find (written into config.json) runs only with allow_cmd', code == 1 and 'allow_cmd' in out, out)
    cfg['allow_cmd'] = True
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False))
    code, out = fm(proj, 'panel', 'run', d, '--members', members, env=renv)
    check('without --owner-ok (ask_each_time) → refused, nothing sent', code == 1 and '--owner-ok' in out and not FakeAPI.seen, out)
    code, out = fm(proj, 'panel', 'run', d, '--members', members, '--owner-ok', words, env=renv)
    check('--owner-ok with words the owner never said → refused', code == 1 and not FakeAPI.seen, out)
    code, out = fm(proj, 'panel', 'run', d, '--members', 'off', '--owner-ok', words, env=renv)
    check('--members naming a member the owner switched off → refused', 'выключен' in out and not os.path.exists(os.path.join(d, 'answer_off.md')), out)

    owner(proj, 'Да, отправь консилиуму этот бриф — посмотрим, что скажут')
    t0 = time.time()
    code, out = fm(proj, 'panel', 'run', d, '--members', members + ',slow', '--stance', 'fake=против', '--owner-ok', words, env=renv)
    took = time.time() - t0
    read = lambda n: io.open(os.path.join(d, n), encoding='utf-8').read() if os.path.exists(os.path.join(d, n)) else ''
    a_fake, a_strip, a_api = read('answer_fake.md'), read('answer_strip.md'), read('answer_fakeapi.md')
    check('run: each answer in its own file with a header (member, model, settings, seconds)', 'FAKE ANSWER' in a_fake and 'member=fake' in a_fake
          and 'API ANSWER' in a_api and 'model=fake-1' in a_api and 'temperature=0.2' in a_api, [out, a_fake[:200]])
    check('run: the brief went in full with the panel\'s instruction and the critic\'s role', 'JSONL или SQLite' in a_fake
          and 'независим' in a_fake and 'КРИТИК' in a_fake, a_fake[:300])
    check('a CLI member runs in an EMPTY folder outside the project (no BRIEF, no answers, no review key)',
          'CWD FILES: |' in a_fake.replace('CWD FILES:  |', 'CWD FILES: |') or 'CWD FILES: ' + '|' in a_fake or
          ('CWD FILES:' in a_fake and 'answer_' not in a_fake.split('CWD FILES:')[1] and 'BRIEF' not in a_fake.split('CWD FILES:')[1]), a_fake[-200:])
    check('strip_env: the member does not get the variables it must not use; the others keep theirs',
          'ENV FAKE_STRIP_ME: absent' in a_strip and 'ENV FAKE_KEEP_ME: present' in a_fake, [a_strip[-80:], a_fake[-80:]])
    check('the API got the key as «Bearer …» from the variable, with the member\'s params', FakeAPI.seen
          and FakeAPI.seen[-1]['auth'] == 'Bearer k-secret-0123456789abcdef' and FakeAPI.seen[-1]['body'].get('temperature') == 0.2, FakeAPI.seen[-1:])
    written = ''.join(io.open(p, encoding='utf-8', errors='replace').read() for p in glob.glob(os.path.join(proj, '.foreman', '**', '*'), recursive=True)
                      if os.path.isfile(p))
    check('the key is never written anywhere in .foreman', 'k-secret-0123456789abcdef' not in written)
    pid = int(io.open(os.path.join(base, 'slow.pid')).read()) if os.path.exists(os.path.join(base, 'slow.pid')) else 0
    check('a hung member behind a shim → answer_slow.err.md, killed with its children, the run did not wait for it',
          'таймаут' in read('answer_slow.err.md') and pid and not alive(pid) and took < 40, [took, pid, read('answer_slow.err.md')])
    code, out = fm(proj, 'panel', 'run', d, '--members', 'withargs,ollama', '--owner-ok', words, env=renv)
    a_args, a_oll = read('answer_withargs.md'), read('answer_ollama.md')
    check('a member\'s own flags (args) reach the program and the header', 'ENV FAKE_KEEP_ME: present' in a_args
          and 'settings=--env FAKE_KEEP_ME' in a_args, [out, a_args[-200:]])
    oll = [x for x in FakeAPI.seen if x['path'].endswith('/api/chat')]
    check('Ollama through its own /api/chat with the context size (a long brief is not cut silently)', 'OLLAMA ANSWER' in a_oll
          and oll and oll[-1]['body'].get('options', {}).get('num_ctx') == 32768, [out, oll[-1:]])
    ev = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'events.jsonl'), encoding='utf-8') if l.strip()]
    check('the sending is logged (to whom, the owner\'s words)', any(e.get('kind') == 'panel_run' and 'fakeapi' in e.get('to', '') for e in ev), ev[-2:])

    # a brief with secrets never leaves; package versions are not e-mails
    n0 = len(FakeAPI.seen)
    for leak in ('ключ sk-abcdefghijklmnopqrstuvwxyz0123', 'пишите на owner@example.com', 'password = hunter22', 'hf_abcdefghijklmnopqrstuvwx',
                 'путь C:\\Users\\Someone\\proj'):
        io.open(os.path.join(d, 'BRIEF.md'), 'w', encoding='utf-8').write('# Бриф\n\n' + leak + '\n')
        code, out = fm(proj, 'panel', 'run', d, '--members', 'fakeapi', '--owner-ok', words, env=renv)
        check(f'a brief with «{leak[:18]}…» → refused, nothing sent', code == 1 and len(FakeAPI.seen) == n0 and 'Наружу не отправлено' in out, out)
    io.open(os.path.join(d, 'BRIEF.md'), 'w', encoding='utf-8').write('# Бриф\n\nreact@18.3.1 и python@3.10 — какой брать?\n')
    code, out = fm(proj, 'panel', 'run', d, '--members', 'fakeapi', '--owner-ok', words, env=renv)
    check('package versions (react@18.3.1) are not e-mails → sent', code == 0 and len(FakeAPI.seen) == n0 + 1, out)

    # the second round: every answer without its author's name; the key written after the round
    io.open(os.path.join(d, 'BRIEF.md'), 'w', encoding='utf-8').write('# Бриф\n\nКакой формат хранения выбрать?\n')
    code, out = fm(proj, 'panel', 'review', d, '--members', 'fakeapi', '--owner-ok', words, env=renv)
    asked = FakeAPI.seen[-1]['body']['messages'][-1]['content'] if FakeAPI.seen else ''
    key = json.load(io.open(os.path.join(d, 'review_key.json'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'review_key.json')) else {}
    check('review: the answers go as A, B… without names or headers; the key in review_key.json', code == 0 and 'Ответ A' in asked
          and 'Ответ B' in asked and 'member=' not in asked and '# fake' not in asked and set(key.values()) >= {'fake', 'fakeapi'}, [out, asked[:300]])

    pa = os.path.join(base, 'asked')
    os.makedirs(pa)
    q = 'Включить консилиум моделей'
    r1 = subprocess.run([PY, os.path.join(KIT, 'install.py'), pa], input='д\nн\n', capture_output=True, encoding='utf-8',
                        env={**os.environ, **penv, 'PYTHONIOENCODING': 'utf-8'})
    r2 = subprocess.run([PY, os.path.join(KIT, 'install.py'), pa], input='д\n', capture_output=True, encoding='utf-8',
                        env={**os.environ, **penv, 'PYTHONIOENCODING': 'utf-8'})
    ca = json.load(io.open(os.path.join(pa, '.foreman', 'config.json'), encoding='utf-8'))
    check('the installer asks about the panel ONCE; a «no» is remembered (an update does not ask again)', q in r1.stdout and q not in r2.stdout
          and ca['modules'].get('panel') is False and ca['panel'].get('offered'), [r1.stdout[-200:], r2.stdout[-200:]])

    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--uninstall', '--yes'], capture_output=True, encoding='utf-8')
    check('uninstall removes the kit\'s unchanged panel skill', not os.path.exists(os.path.join(proj, '.claude', 'skills', 'foreman-panel')), r.stdout[-200:])
finally:
    if srv:
        srv.shutdown()
    shutil.rmtree(base, ignore_errors=True)
print('PANEL TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
