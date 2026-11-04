"""test_panel.py — Foreman 2.2's model panel: offered, never forced (a silent install leaves it off, a run is refused while it is off),
members found (a CLI in PATH, a key's NAME in the environment), one brief to every member in parallel with each answer in its own file,
an API key sent but never written, a critic's stance, one slow member never stops the others, a brief with secrets never leaves, the
second round without names, the skill and the CLAUDE.md rule only with the module. Standard library only; fake members.
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

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
FAKE = os.path.join(KIT, 'tests', 'fixtures', 'fake_model_cli.py')
fails = 0


def check(name, ok, info=''):
    global fails
    fails += not ok
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {str(info)[:300]}' if info and not ok else ''))


def fm(proj, *args, env=None):
    r = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=proj, capture_output=True, encoding='utf-8',
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8', **(env or {})})
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def install(proj, *extra):
    return subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes', *extra], capture_output=True, encoding='utf-8')


class FakeAPI(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode('utf-8'))
        FakeAPI.seen.append({'auth': self.headers.get('Authorization'), 'path': self.path, 'body': body})
        out = json.dumps({'model': body.get('model'), 'choices': [{'message': {'role': 'assistant', 'content': 'API ANSWER: ок'}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)


base = tempfile.mkdtemp(prefix='foreman_panel_')
srv = None
try:
    # offered, never forced
    p0 = os.path.join(base, 'silent')
    os.makedirs(p0)
    install(p0)
    c0 = json.load(io.open(os.path.join(p0, '.foreman', 'config.json'), encoding='utf-8'))
    check('a silent install (--yes) leaves the panel OFF', c0['modules'].get('panel') is False, c0['modules'])
    check('…and installs no panel skill', not os.path.exists(os.path.join(p0, '.claude', 'skills', 'foreman-panel')))
    code, out = fm(p0, 'panel', 'new', 'тема')
    d0 = out.strip().splitlines()[-1]
    code, out = fm(p0, 'panel', 'run', d0)
    check('panel run while the module is off → refused, says who switches it on', code == 1 and 'владел' in out, out)

    proj = os.path.join(base, 'proj')
    os.makedirs(proj)
    r = install(proj, '--modules', 'promises,lessons,panel')
    check('--modules …,panel → on, the skill and the CLAUDE.md rule 10', r.returncode == 0
          and os.path.exists(os.path.join(proj, '.claude', 'skills', 'foreman-panel', 'SKILL.md'))
          and 'консилиум моделей' in io.open(os.path.join(proj, 'CLAUDE.md'), encoding='utf-8').read(), r.stdout[-300:])

    # members found: a CLI in PATH, a key's name in the environment
    bindir = os.path.join(base, 'bin')
    os.makedirs(bindir)
    if os.name == 'nt':
        io.open(os.path.join(bindir, 'gemini.cmd'), 'w').write(f'@"{PY}" "{FAKE}" %*\n')
    else:
        g = os.path.join(bindir, 'gemini')
        io.open(g, 'w').write(f'#!/bin/sh\nexec "{PY}" "{FAKE}" "$@"\n')
        os.chmod(g, 0o755)
    env = {'PATH': bindir + os.pathsep + os.environ.get('PATH', ''), 'OPENROUTER_API_KEY': 'or-test-key-0123456789'}
    code, out = fm(proj, 'panel', 'detect', '--json', '--no-local', env=env)
    rows = {m['name']: m for m in json.loads(out[out.index('['):])}
    check('detect: a CLI in PATH → a cli member, ready', rows.get('gemini', {}).get('kind') == 'cli' and rows['gemini'].get('ready'), list(rows))
    check('detect: a key in the environment → an api member named by the variable, not ready without a model',
          rows.get('openrouter', {}).get('key_env') == 'OPENROUTER_API_KEY' and not rows['openrouter'].get('ready')
          and 'or-test-key' not in out, rows.get('openrouter'))
    check('detect: Claude\'s own subagents are always there', rows.get('subagents', {}).get('kind') == 'subagent', list(rows))

    # one brief to every member, in parallel; the key sent, never written
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeAPI)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfgp = os.path.join(proj, '.foreman', 'config.json')
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['panel']['timeout_s'] = 6
    cfg['panel']['members'] = [
        {'name': 'fake', 'kind': 'cli', 'cmd': [PY, FAKE], 'stdin': True, 'enabled': True},
        {'name': 'slow', 'kind': 'cli', 'cmd': [PY, FAKE, '--sleep', '30'], 'stdin': True, 'enabled': True},
        {'name': 'fakeapi', 'kind': 'api', 'base_url': f'http://127.0.0.1:{srv.server_address[1]}/v1', 'key_env': 'FAKE_PANEL_KEY',
         'model': 'fake-1', 'enabled': True}]
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False))
    code, out = fm(proj, 'panel', 'new', 'Выбор формата хранения')
    d = out.strip().splitlines()[-1]
    io.open(os.path.join(d, 'BRIEF.md'), 'w', encoding='utf-8').write('# Бриф\n\nКакой формат хранения выбрать: JSONL или SQLite? Цена и риск.\n')
    penv = {'FAKE_PANEL_KEY': 'k-secret-0123456789abcdef'}
    code, out = fm(proj, 'panel', 'run', d, '--members', 'fake,slow,fakeapi', '--stance', 'fake=против', env=penv)
    a_fake = io.open(os.path.join(d, 'answer_fake.md'), encoding='utf-8').read() if os.path.exists(os.path.join(d, 'answer_fake.md')) else ''
    a_api = io.open(os.path.join(d, 'answer_fakeapi.md'), encoding='utf-8').read() if os.path.exists(os.path.join(d, 'answer_fakeapi.md')) else ''
    check('run: each answer in its own file with a header (member, model, seconds)', 'FAKE ANSWER' in a_fake and 'member=fake' in a_fake
          and 'API ANSWER' in a_api and 'model=fake-1' in a_api, [out, a_fake[:200]])
    check('run: the brief went in full with the panel\'s instruction', 'JSONL или SQLite' in a_fake and 'независим' in a_fake, a_fake[:300])
    check('run: --stance fake=против → that member got the critic\'s role', 'КРИТИК' in a_fake, a_fake[:300])
    check('run: the API got the key as «Bearer …» from the variable', FakeAPI.seen and FakeAPI.seen[-1]['auth'] == 'Bearer k-secret-0123456789abcdef'
          and FakeAPI.seen[-1]['path'].endswith('/chat/completions'), FakeAPI.seen[-1:])
    written = ''.join(io.open(p, encoding='utf-8', errors='replace').read() for p in glob.glob(os.path.join(proj, '.foreman', '**', '*'), recursive=True)
                      if os.path.isfile(p))
    check('the key is never written anywhere in .foreman', 'k-secret-0123456789abcdef' not in written)
    err = os.path.join(d, 'answer_slow.err.md')
    check('a member that does not answer in time → answer_slow.err.md, the others still answered',
          os.path.exists(err) and 'таймаут' in io.open(err, encoding='utf-8').read() and a_fake and a_api, out)

    # a brief with secrets never leaves
    n0 = len(FakeAPI.seen)
    for leak in ('ключ sk-abcdefghijklmnopqrstuvwxyz0123', 'пишите на owner@example.com', 'password = hunter22'):
        io.open(os.path.join(d, 'BRIEF.md'), 'w', encoding='utf-8').write('# Бриф\n\n' + leak + '\n')
        code, out = fm(proj, 'panel', 'run', d, '--members', 'fakeapi', env=penv)
        check(f'a brief with «{leak[:18]}…» → refused, nothing sent', code == 1 and len(FakeAPI.seen) == n0 and 'Наружу не отправлено' in out, out)
    code, out = fm(proj, 'panel', 'run', d, '--members', 'fakeapi', '--allow-sensitive', env=penv)
    check('--allow-sensitive (the owner allowed) → sent', code == 0 and len(FakeAPI.seen) == n0 + 1, out)

    # the second round: every answer without its author's name
    io.open(os.path.join(d, 'BRIEF.md'), 'w', encoding='utf-8').write('# Бриф\n\nКакой формат хранения выбрать?\n')
    code, out = fm(proj, 'panel', 'review', d, '--members', 'fakeapi', env=penv)
    asked = FakeAPI.seen[-1]['body']['messages'][-1]['content'] if FakeAPI.seen else ''
    key = json.load(io.open(os.path.join(d, 'review_key.json'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'review_key.json')) else {}
    check('review: the answers go as A, B… without names or headers; the key stays in review_key.json', code == 0 and 'Ответ A' in asked
          and 'Ответ B' in asked and 'member=' not in asked and '# fake' not in asked and set(key.values()) >= {'fake', 'fakeapi'}, [out, asked[:300]])

    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--uninstall', '--yes'], capture_output=True, encoding='utf-8')
    check('uninstall removes the kit\'s unchanged panel skill', not os.path.exists(os.path.join(proj, '.claude', 'skills', 'foreman-panel')), r.stdout[-200:])
finally:
    if srv:
        srv.shutdown()
    shutil.rmtree(base, ignore_errors=True)
print('PANEL TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
