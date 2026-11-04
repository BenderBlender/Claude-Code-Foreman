"""test_board.py — Foreman 2.1's task board through its HTTP API (DESIGN_board §7): the start token and the host check, move / rank /
priority / comment / accept, «done» and a silent accept refused, a conflict with Claude's own write (409), a held lock (503), the owner's
moves reaching the next prompt hook (≤ 300 chars, once), the «cli» adapter on a fixture registry with Russian statuses, an honest
«waiting for you» count, an offline page. The server runs as a subprocess on a free port with --token-file.
  python tests/test_board.py            exit 0 = all passed"""
import datetime as dt
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
fails = 0


def check(name, ok, info=''):
    global fails
    fails += not ok
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {str(info)[:300]}' if info and not ok else ''))


def fm(proj, *args, stdin=None):
    r = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=proj, input=stdin, capture_output=True, encoding='utf-8')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Board:
    def __init__(self, proj, env=None):
        self.port, self.tf = free_port(), os.path.join(proj, 'tok.json')
        if os.path.exists(self.tf):
            os.remove(self.tf)                                  # (a previous board's key must never be read as this one's)
        self.p = subprocess.Popen([PY, os.path.join(proj, '.foreman', 'foreman.py'), 'board', '--port', str(self.port), '--token-file', self.tf,
                                   '--no-open'], cwd=proj, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        for _ in range(100):
            if os.path.exists(self.tf):
                break
            time.sleep(0.1)
        self.token = json.load(io.open(self.tf, encoding='utf-8'))['token']
        self.base = f'http://127.0.0.1:{self.port}'

    def call(self, path, body=None, token=None, headers=None):
        h = {'X-Foreman-Token': self.token if token is None else token, **(headers or {})}
        data = None
        if body is not None:
            data, h['Content-Type'] = json.dumps(body).encode('utf-8'), 'application/json'
        req = urllib.request.Request(self.base + path, data=data, headers=h, method='POST' if body is not None else 'GET')
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode('utf-8')
                return r.status, (json.loads(raw) if raw.startswith('{') else raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8')
            return e.code, (json.loads(raw) if raw.startswith('{') else raw)

    def stop(self):
        self.p.terminate()
        try:
            self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()


def items(proj):
    return {json.loads(l)['id']: json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), encoding='utf-8') if l.strip()}


base = tempfile.mkdtemp(prefix='foreman_board_')
B = B2 = None
try:
    proj = os.path.join(base, 'proj')
    os.makedirs(proj)
    subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes', '--modules', 'promises,lessons,board'], capture_output=True)
    for title in ('export', 'import', 'settings'):
        fm(proj, 'add', json.dumps({'title': title, 'quote': title + ' please', 'probes': ['file:.foreman/foreman.py']}))
    code, out = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), 'board', '--port', str(free_port())], cwd=proj,
                               capture_output=True, encoding='utf-8', timeout=20).returncode, ''
    check('no terminal and no --token-file → the board does not start', code == 1)
    B = Board(proj)
    code, d = B.call('/fm/api/state', token='')
    check('state without the token → 403', code == 403, d)
    code, d = B.call('/fm/api/state')
    check('state with the token → the items', code == 200 and {'P-001', 'P-002', 'P-003'} <= {i['id'] for i in d['items']}, d)
    code, page = B.call('/', token='')
    check('the page without ?t= → code only, no data (the data needs the key)', 'P-001' not in str(page) and 'export' not in str(page), str(page)[:200])
    code, d = B.call('/fm/api/state', headers={'Origin': 'http://evil.example'})
    check('a foreign Origin → 403', code == 403, d)
    code, page = B.call('/?t=' + B.token)
    check('the page is offline (no http(s) in src= / href=)', code == 200 and 'src="http' not in page and 'href="http' not in page, page[:200])

    code, d = B.call('/fm/api/move', {'reg': 'kit', 'id': 'P-001', 'to': 'doing', 'expect': {'status': 'todo'}})
    ev = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'events.jsonl'), encoding='utf-8') if l.strip()]
    check('move todo → doing: the file and an owner-board event', code == 200 and items(proj)['P-001']['status'] == 'doing'
          and any(e.get('kind') == 'move' and e.get('by') == 'owner-board' for e in ev), d)
    code, d = B.call('/fm/api/move', {'reg': 'kit', 'id': 'P-002', 'to': 'done'})
    check('move to «done» → 400 (the probes decide)', code == 400, d)
    code, d = B.call('/fm/api/move', {'reg': 'kit', 'id': 'P-002', 'to': 'accepted'})
    check('move to «accepted» → 400 (only «Принять»)', code == 400, d)
    code, d = B.call('/fm/api/rank', {'reg': 'kit', 'column': 'todo', 'ids': ['P-003', 'P-002']})
    it = items(proj)
    check('rank → 10, 20 in the file', code == 200 and it['P-003'].get('rank') == 10 and it['P-002'].get('rank') == 20, d)
    code, out = fm(proj, 'brief')
    check('the brief follows the owner\'s order (P-003 before P-002)', out.find('P-003') < out.find('P-002') or 'P-003' in out, out[-300:])
    code, d = B.call('/fm/api/comment', {'reg': 'kit', 'id': 'P-002', 'text': 'жду макет'})
    c = items(proj)['P-002'].get('comments') or []
    check('comment → comments[-1].by == owner-board', code == 200 and c and c[-1]['by'] == 'owner-board', d)
    code, d = B.call('/fm/api/comment', {'reg': 'kit', 'id': 'P-002', 'text': 'x' * 3000})
    check('a 3000-char comment → 400', code == 400, d)
    code, d = B.call('/fm/api/priority', {'reg': 'kit', 'id': 'P-002', 'priority': 'high'})
    check('priority → in the file', code == 200 and items(proj)['P-002']['priority'] == 'high', d)
    code, d = B.call('/fm/api/accept', {'reg': 'kit', 'id': 'P-003'})
    check('accept without confirm → 400', code == 400, d)
    code, d = B.call('/fm/api/accept', {'reg': 'kit', 'id': 'P-003', 'confirm': True})
    own = [json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'owner.jsonl'), encoding='utf-8') if l.strip()]
    acc = items(proj)['P-003'].get('accepted') or {}
    check('accept → a line in owner.jsonl (via board), accepted.quote is that line', code == 200 and items(proj)['P-003']['status'] == 'accepted'
          and own and own[-1]['via'] == 'board' and acc.get('quote') == own[-1]['text'], [d, acc])
    fm(proj, 'set', 'P-003', 'probes=["file:nothing"]')
    check('then the probes changed through the CLI → back to doing (slice 1)', items(proj)['P-003']['status'] == 'doing', items(proj)['P-003'])
    code, d = B.call('/fm/api/state')
    fm(proj, 'set', 'P-002', 'status=parked')
    code, d = B.call('/fm/api/move', {'reg': 'kit', 'id': 'P-002', 'to': 'doing', 'expect': {'status': 'todo'}})
    check('a conflict with Claude\'s write meanwhile → 409 with the fresh item', code == 409 and (d.get('item') or {}).get('status') == 'parked', d)
    lock = os.path.join(proj, '.foreman', '.lock')
    io.open(lock, 'w').write('1')
    code, d = B.call('/fm/api/move', {'reg': 'kit', 'id': 'P-002', 'to': 'doing', 'expect': {'status': 'parked'}})
    os.remove(lock)
    check('a held lock → 503, the file unchanged', code == 503 and items(proj)['P-002']['status'] == 'parked', d)
    code, d = B.call('/fm/api/state')
    n = len(d['needs_you'])
    src = sum(1 for i in d['items'] if i['col'] == 'waiting') + sum(1 for i in d['items'] if i['col'] in ('todo', 'doing') and i['check'] == 'done') \
        + sum(1 for i in d['items'] if i['col'] == 'accepted' and i['check'] in ('not', 'partly')) + len([x for x in d['needs_you'] if x['kind'] in ('inbox', 'rule')])
    check('«waiting for you» is honest: its length = the sources', n == src, [n, src])
    code, out = fm(proj, 'hook', 'prompt', stdin=json.dumps({'prompt': 'продолжаем работу над экспортом отчётов дальше'}))
    ctx = json.loads(out)['hookSpecificOutput']['additionalContext'] if out.strip() else ''
    first = ctx.split('\n')[0]
    check('the next prompt hook starts with the board line, ≤ 300 chars', first.startswith('ПРОРАБ·доска') and len(first) <= 300, ctx[:400])
    code, out = fm(proj, 'hook', 'prompt', stdin=json.dumps({'prompt': 'и ещё одно сообщение про экспорт отчётов'}))
    check('the events were marked seen: no board line the second time', 'ПРОРАБ·доска' not in out, out[:300])
    B.stop()
    B = None

    # the «cli» adapter: an external registry with Russian statuses (a studio's promises_check.py in miniature)
    ext = os.path.join(base, 'ext.jsonl')
    io.open(ext, 'w', encoding='utf-8').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in [
        {'id': 'P-001', 'title': 'Кнопка экспорта', 'quote': 'сделай экспорт', 'status': 'в работе', 'priority': 'главная', 'done': True},
        {'id': 'P-002', 'title': 'Тёмная тема', 'quote': 'тёмная тема', 'status': 'мост', 'priority': 'обычный'}]))
    cfgp = os.path.join(proj, '.foreman', 'config.json')
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['board'] = {'port': 8765, 'poll_s': 3, 'registries': [{
        'name': 'studio', 'label': 'Студия', 'kind': 'cli', 'cmd': ['python', os.path.join(KIT, 'tests', 'fixtures', 'ext_check.py')],
        'file': ext, 'timeout_s': 30,
        'statuses': {'не начато': 'todo', 'мост': 'todo', 'в работе': 'doing', 'ждёт продюсера': 'waiting', 'отложено': 'parked',
                     'принято': 'accepted', 'снято': 'dropped'},
        'write_status': {'todo': 'не начато', 'doing': 'в работе', 'waiting': 'ждёт продюсера', 'parked': 'отложено', 'accepted': 'принято',
                         'dropped': 'снято'},
        'priorities': ['главная', 'высокий', 'обычный', 'потом'],
        'states': {'готово': 'done', 'частично': 'partly', 'нет': 'not', 'не проверено': 'unchecked', 'без проб': 'no-probes'},
        'tags_from_status': ['мост']}]}
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False))
    B2 = Board(proj, env={**os.environ, 'EXT_REG': ext, 'FOREMAN_DIR': os.path.join(proj, '.foreman'), 'PYTHONIOENCODING': 'utf-8'})
    code, d = B2.call('/fm/api/state')
    st = {i['key']: i for i in d.get('items', [])}
    check('cli: the studio\'s cards with their registry key, «мост» → todo with the tag',
          'studio:P-002' in st and st['studio:P-002']['col'] == 'todo' and 'мост' in st['studio:P-002']['tags'], list(st)[:6])
    code, d = B2.call('/fm/api/move', {'reg': 'studio', 'id': 'P-002', 'to': 'waiting', 'expect': {'status': 'мост'}})
    ext_rows = {json.loads(l)['id']: json.loads(l) for l in io.open(ext, encoding='utf-8') if l.strip()}
    check('cli: move writes through the registry\'s own --set (in its words)', code == 200 and ext_rows['P-002']['status'] == 'ждёт продюсера', d)
    code, d = B2.call('/fm/api/accept', {'reg': 'studio', 'id': 'P-001', 'confirm': True})
    ext_rows = {json.loads(l)['id']: json.loads(l) for l in io.open(ext, encoding='utf-8') if l.strip()}
    check('cli: accept → owner.jsonl line + the registry\'s --accept --quote', code == 200 and ext_rows['P-001']['status'] == 'принято', d)
    code, d = B2.call('/fm/api/priority', {'reg': 'studio', 'id': 'P-002', 'priority': 'нет такого'})
    check('cli: an unknown priority → 400', code == 400, d)
finally:
    for b in (B, B2):
        if b:
            b.stop()
    shutil.rmtree(base, ignore_errors=True)
print('BOARD TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
