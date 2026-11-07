"""board.py — Foreman's task board (2.1): every item of the registry on one page — see, drag between columns (the status), order a
column (the priority), comment, accept; the owner's moves reach Claude through .foreman/events.jsonl at his next message.

The design: production/harness/foreman_v2/DESIGN_board.md of the project Foreman was born in (Fable 5.1, 04.11.2026) — a window over
the SAME files (no second database); several registries on one board: the kit's own (.foreman/promises.jsonl) and external ones
through an adapter «cli» (a command that speaks `--json --light / --set / --rank / --comment / --accept / --skip`, e.g. a studio's
promises_check.py), each written only through its own path so its guards apply. «Done» is never a column: the probes decide.

  python .foreman/foreman.py board [--port 8765] [--token-file F] [--no-open]
The link (with a start token) is printed to YOUR terminal only; without a terminal the board starts only with --token-file.
Standard library only. The page: board.html next to this file (inline CSS / JS, offline)."""
import datetime as dt
import http.server
import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

FM = None                                                   # the foreman module (foreman.py), set by serve()
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = ''
PORT = 8765
COLS = ('todo', 'doing', 'waiting', 'parked', 'accepted', 'dropped')
MOVABLE = ('todo', 'doing', 'waiting', 'parked', 'dropped')   # (accepted only through «Принять» — the owner's word, slice 1)
_mutex = threading.Lock()
_cache = {}


def now():
    return dt.datetime.now().isoformat(timespec='seconds')


def mtime(p):
    try:
        return os.stat(p).st_mtime_ns
    except OSError:
        return 0


def event(reg, kind, **kw):
    """an owner's move → the shared events log (the item's history; the next prompt hook tells Claude, then marks it seen)"""
    row = {'ts': now(), 'by': 'owner-board', 'reg': reg, 'kind': kind, **{k: v for k, v in kw.items() if v is not None}, 'seen': False}
    with io.open(FM.EVENTS, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def owner_line(text):
    """the board's click is the owner's word: one line in owner.jsonl (via: board) — the same invariant as a quoted acceptance"""
    rows = FM.jsonl(FM.OWNER)[-499:]
    rows.append({'ts': now(), 'session_id': '', 'text': text, 'prev': '', 'via': 'board'})
    FM.write_jsonl(FM.OWNER, rows)


class Refused(Exception):
    def __init__(self, code, msg, item=None):
        super().__init__(msg)
        self.code, self.msg, self.item = code, msg, item


# ---------------------------------------------------------------- the kit's own registry
class KitRegistry:
    name, kind = 'kit', 'kit'

    def __init__(self, label):
        self.label = label
        self.priorities = ['high', 'normal', 'later']

    def word(self, col):
        return col

    def col(self, status):
        return status if status in COLS else 'todo'

    def version(self):
        return f'{mtime(FM.REG)}-{mtime(FM.INBOX)}'

    def read(self):
        r = FM.run()
        items = []
        for it in r['registry']:
            items.append(card(self, it, it.get('status') or 'todo', it.get('_check'),
                              [[p, v, FM.WHY.get(p, '')] for p, v in it.get('_probes', [])]))
        return {'items': items, 'control_ok': r['control_ok'], 'inbox': [dict(i, reg=self.name) for i in r['inbox_new']], 'error': ''}

    def _write(self, pid, fn):
        with FM.locked() as held:
            if not held:
                raise Refused(503, FM.L.get('board_busy', 'Реестр занят — повторите через пару секунд.'))
            rows = FM.jsonl(FM.REG)
            it = next((i for i in rows if i.get('id') == pid), None)
            if not it:
                raise Refused(404, f'нет пункта {pid}')
            out = fn(it, rows)
            it['touched'] = FM.today()
            FM.write_jsonl(FM.REG, rows)
            return out

    def move(self, pid, to, expect):
        def fn(it, rows):
            if expect and it.get('status', 'todo') != expect:
                raise Refused(409, f"Claude только что перевёл {pid} в «{it.get('status')}»", it)
            was = it.get('status', 'todo')
            it['status'] = to
            if to != 'accepted':
                it.pop('accepted', None)
            if to == 'dropped':
                it['dropped_by'] = 'owner-board'
            return was
        return self._write(pid, fn)

    def rank(self, ids):
        with FM.locked() as held:
            if not held:
                raise Refused(503, 'Реестр занят — повторите через пару секунд.')
            rows = FM.jsonl(FM.REG)
            pos = {pid: (n + 1) * 10 for n, pid in enumerate(ids)}
            for it in rows:
                if it.get('id') in pos:
                    it['rank'] = pos[it['id']]
            FM.write_jsonl(FM.REG, rows)

    def priority(self, pid, p):
        def fn(it, rows):
            it['priority'] = p
        self._write(pid, fn)

    def comment(self, pid, text):
        def fn(it, rows):
            it.setdefault('comments', []).append({'ts': now(), 'by': 'owner-board', 'text': text})
        self._write(pid, fn)

    def accept(self, pid, quote):
        def fn(it, rows):
            it['status'] = 'accepted'
            st, _ = FM.stamp_of(it) if hasattr(FM, 'stamp_of') else (None, [])   # (2.4: the board's acceptance is stamped too — Fable 07.11)
            it['accepted'] = {'ts': now(), 'by': 'owner-board', 'quote': quote, **({'stamp': st} if st else {})}
            it.pop('accept_void', None)
        self._write(pid, fn)
        event(self.name, 'accept', id=pid, text=quote[:120])

    def skip(self, iid, why):
        with FM.locked() as held:
            if not held:
                raise Refused(503, 'Реестр занят — повторите через пару секунд.')
            rows = FM.jsonl(FM.INBOX)
            it = next((i for i in rows if i.get('id') == iid), None)
            if not it:
                raise Refused(404, f'нет входящей {iid}')
            it.update(state='skipped', why=why)
            FM.write_jsonl(FM.INBOX, rows)


# ---------------------------------------------------------------- an external registry through its own command («cli»)
class CliRegistry:
    kind = 'cli'

    def __init__(self, spec, root):
        self.spec, self.root = spec, root
        self.name = spec.get('name', 'ext')
        self.label = spec.get('label', self.name)
        self.cmd = [sys.executable if c == 'python' else c for c in spec.get('cmd', [])]
        self.statuses = spec.get('statuses', {})
        self.write_status = spec.get('write_status', {})
        self.priorities = spec.get('priorities', [])
        self.states = spec.get('states', {})
        self.tags = spec.get('tags_from_status', [])
        self.timeout = int(spec.get('timeout_s', 40))
        self.file = os.path.join(root, spec['file']) if spec.get('file') else ''
        self.last = None

    def word(self, col):
        return self.write_status.get(col, col)

    def col(self, status):
        return self.statuses.get(status, 'todo')

    def version(self):
        return str(mtime(self.file)) if self.file else str(int(time.time() // 10))

    def run(self, *args):
        try:
            r = subprocess.run(self.cmd + list(args), cwd=self.root, capture_output=True, text=True, encoding='utf-8', errors='replace',
                               timeout=self.timeout, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        except subprocess.TimeoutExpired:
            raise Refused(504, f'реестр «{self.label}» не ответил за {self.timeout} с')
        except OSError as e:
            raise Refused(500, f'реестр «{self.label}» не запустился: {e}')
        if r.returncode != 0:
            raise Refused(400, (r.stdout.strip() or r.stderr.strip() or f'код {r.returncode}')[-600:])
        return r.stdout

    def read(self):
        try:
            r = subprocess.run(self.cmd + ['--json', '--light'], cwd=self.root, capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=self.timeout, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            out = r.stdout
            d = json.loads(out[out.index('{'):])
        except (subprocess.TimeoutExpired, OSError, ValueError) as e:
            if self.last:                                    # (the last good answer, marked stale — never an empty board)
                return dict(self.last, error=f'реестр «{self.label}» не ответил ({type(e).__name__}) — показано последнее известное')
            return {'items': [], 'control_ok': True, 'inbox': [], 'error': f'реестр «{self.label}» не читается: {type(e).__name__}'}
        items = []
        for it in d.get('registry', []):
            st = it.get('status') or ''
            probes = [[p[0], p[1], p[2] if len(p) > 2 else ''] for p in it.get('_probes') or []]
            items.append(card(self, it, st, self.states.get(it.get('_check'), it.get('_check')), probes))
        res = {'items': items, 'control_ok': bool(d.get('control_ok', True)),
               'inbox': [dict(i, reg=self.name) for i in d.get('inbox_new') or []], 'error': '', 'server': d.get('server')}
        self.last = res
        return res

    def move(self, pid, to, expect):
        cur = next((c for c in (self.last or {}).get('items', []) if c['id'] == pid), None)
        if expect and cur and cur['status'] != expect:
            raise Refused(409, f"Claude только что перевёл {pid} в «{cur['status']}»", cur)
        self.run('--set', pid, f'status={self.word(to)}', '--by', 'owner-board')
        return cur['status'] if cur else None

    def rank(self, ids):
        self.run('--rank', *ids, '--by', 'owner-board')

    def priority(self, pid, p):
        self.run('--set', pid, f'priority={p}', '--by', 'owner-board')

    def comment(self, pid, text):
        self.run('--comment', pid, text, '--by', 'owner-board')

    def accept(self, pid, quote):
        self.run('--accept', pid, '--quote', quote, '--by', 'owner-board')   # (it logs the «accept» event itself)

    def skip(self, iid, why):
        self.run('--skip', iid, '--why', why)


def card(reg, it, status, check, probes):
    rounds = it.get('rounds') if isinstance(it.get('rounds'), list) else []
    try:
        days = (dt.date.today() - dt.date.fromisoformat(str(it.get('touched') or it.get('date') or '')[:10])).days
    except ValueError:
        days = None
    return {'key': f"{reg.name}:{it.get('id')}", 'reg': reg.name, 'id': it.get('id'), 'title': it.get('title', ''),
            'quote': it.get('quote', ''), 'next': it.get('next', ''), 'waits': it.get('waits', ''), 'source': it.get('source', ''),
            'priority': it.get('priority', ''), 'status': status, 'col': reg.col(status),
            'tags': [status] if status in getattr(reg, 'tags', []) else [], 'check': check or 'no-probes', 'probes': probes,
            'comments': it.get('comments') if isinstance(it.get('comments'), list) else [], 'rank': it.get('rank'),
            'days': days, 'accepted': it.get('accepted'), 'accept_void': it.get('accept_void', ''),
            'council': f"{len(rounds)}" if rounds and it.get('council') != 'stopped' else '', 'unreadable': it.get('id') == '?',
            'date': it.get('date', '')}


def registries():
    cfg = FM.CFG
    out = []
    if cfg['modules'].get('promises'):
        out.append(KitRegistry(FM.L.get('board_kit', 'Прораб')))
    for spec in (cfg.get('board') or {}).get('registries') or []:
        if spec.get('kind') == 'cli' and spec.get('cmd'):
            out.append(CliRegistry(spec, FM.PROJECT))
    return out


REGS = []


def reg_of(name):
    r = next((r for r in REGS if r.name == name), None)
    if not r:
        raise Refused(404, f'нет реестра {name}')
    return r


def prio_index(reg, p):
    return reg.priorities.index(p) if p in reg.priorities else len(reg.priorities)


def state(force=False):
    """the page's whole state; each registry cached for poll_s (an external one for 10 s); a write or «Проверить сейчас» drops it"""
    poll = float((FM.CFG.get('board') or {}).get('poll_s', 3))
    data = []
    for r in REGS:
        ttl = 10 if r.kind == 'cli' else poll
        c = _cache.get(r.name)
        if force or not c or time.time() - c[0] > ttl or c[1] != r.version():
            c = (time.time(), r.version(), r.read())
            _cache[r.name] = c
        data.append((r, c[2]))
    items, inbox, broken, needs = [], [], [], []
    control_ok = True
    stale_days = FM.CFG.get('stale_days', 3)
    for r, d in data:
        control_ok = control_ok and d['control_ok']
        if d.get('error'):
            broken.append({'kind': 'registry', 'reg': r.name, 'text': d['error']})
        for c in d['items']:
            c['prio'] = prio_index(r, c['priority'])
            items.append(c)
        inbox += d['inbox']
        if r.kind == 'cli' and d.get('server') is False:
            broken.append({'kind': 'server', 'reg': r.name, 'text': f'{r.label}: сервер не запущен — пробы get: «неизвестно»'})
    by = lambda col: [c for c in items if c['col'] == col]
    for c in by('waiting'):
        needs.append({'kind': 'waiting', 'reg': c['reg'], 'id': c['id'], 'title': c['title'], 'why': c['waits'] or c['next'],
                      'actions': ['comment', 'doing']})
    for c in [c for c in items if c['col'] in ('todo', 'doing') and c['check'] == 'done']:
        needs.append({'kind': 'built', 'reg': c['reg'], 'id': c['id'], 'title': c['title'], 'why': 'пробы зелёные — примите или верните',
                      'actions': ['accept', 'doing']})
    for c in [c for c in items if c['col'] == 'accepted' and c['check'] in ('not', 'partly')]:
        needs.append({'kind': 'red', 'reg': c['reg'], 'id': c['id'], 'title': c['title'], 'why': '«принято», а пробы красные',
                      'actions': ['doing']})
    for i in inbox:
        needs.append({'kind': 'inbox', 'reg': i['reg'], 'id': i.get('id'), 'title': str(i.get('text', ''))[:160],
                      'why': 'просьба не разобрана', 'actions': ['triage', 'skip']})
    R = FM.lessons() if FM.CFG['modules'].get('promises') or FM.CFG['modules'].get('lessons') else None
    if R:
        for rule in R.proposed():
            needs.append({'kind': 'rule', 'reg': 'rules', 'id': rule['id'], 'title': f"{rule.get('when')} → {rule.get('do')}",
                          'why': f"правило ждёт вашего «да» («{str(rule.get('quote', ''))[:80]}»)", 'actions': ['rule_accept', 'rule_drop']})
    if not control_ok:
        broken.append({'kind': 'control', 'text': 'контроль сломан — подставная проба прошла, пробам не верить'})
    unk = [c for c in items if c['check'] == 'unchecked' and c['col'] not in ('dropped',)]
    if unk:
        broken.append({'kind': 'unknown', 'text': f'пробы «неизвестно» у {len(unk)} пунктов: ' + ', '.join(c['id'] for c in unk[:8])})
    old = [c for c in items if c['col'] == 'doing' and (c['days'] or 0) > stale_days]
    if old:
        broken.append({'kind': 'stale', 'text': f'в работе без движения > {stale_days} дн.: ' + ', '.join(c['id'] for c in old[:10])})
    bad = [c for c in items if c['unreadable']]
    if bad:
        broken.append({'kind': 'unreadable', 'text': f'нечитаемые строки реестра: {len(bad)}'})
    return {'ok': True, 'lang': FM.CFG.get('lang', 'ru'), 'when': dt.datetime.now().strftime('%H:%M:%S'), 'control_ok': control_ok,
            'registries': [{'name': r.name, 'label': r.label, 'priorities': r.priorities} for r in REGS],
            'items': items, 'needs_you': needs, 'broken': broken, 'version': version()}


def version():
    R = FM.lessons()
    return '-'.join([r.version() for r in REGS] + [str(mtime(FM.EVENTS))] + ([str(mtime(R.RULES))] if R else []))


def item_detail(reg, pid):
    c = next((c for c in state()['items'] if c['reg'] == reg and c['id'] == pid), None)
    if not c:
        raise Refused(404, f'нет пункта {pid}')
    hist = [e for e in FM.jsonl(FM.EVENTS) if e.get('id') == pid and e.get('reg', 'kit') == reg][-40:]
    return dict(c, history=list(reversed(hist)))


# ---------------------------------------------------------------- the actions (each one a write through the registry's own path)
def act(path, body):
    reg_name, pid = body.get('reg', ''), str(body.get('id', ''))
    if path == 'recheck':
        _cache.clear()
        return {}
    if path == 'rule':
        R = FM.lessons()
        if not R:
            raise Refused(400, 'модуль уроков выключен')
        to = body.get('to')
        with FM.locked() as held:
            if not held:
                raise Refused(503, 'Реестр занят — повторите через пару секунд.')
            if to == 'active':
                words = f'[доска] принимаю правило {pid}'
                owner_line(words)
                code = R.rule_cmd(['accept', pid, '--quote', words], quote_check=FM.owner_says)
            else:
                code = R.rule_cmd(['drop', pid, '--why', 'владелец (доска)'])
        if code:
            raise Refused(400, f'правило {pid} не изменено')
        event('rules', 'rule', id=pid, to=to)
        return {}
    if path == 'triage':
        event(reg_name, 'triage', id=pid)
        return {}
    r = reg_of(reg_name)
    if path == 'skip':
        r.skip(pid, str(body.get('why') or 'владелец (доска): не задача')[:300])
        event(reg_name, 'skip', id=pid)
        return {}
    if path == 'move':
        to = body.get('to')
        if to not in MOVABLE:
            raise Refused(400, 'туда нельзя: «сделано» решают пробы, «принято» — только кнопкой «Принять»')
        was = r.move(pid, r.word(to), (body.get('expect') or {}).get('status'))
        event(reg_name, 'move', id=pid, **{'from': was, 'to': r.word(to)})
        if body.get('order'):
            r.rank([str(x) for x in body['order']][:400])
        return {}
    if path == 'rank':
        ids = [str(x) for x in body.get('ids') or []][:400]
        if not ids:
            raise Refused(400, 'пустой порядок')
        r.rank(ids)
        event(reg_name, 'rank', column=body.get('column'), n=len(ids))
        return {}
    if path == 'priority':
        p = str(body.get('priority', ''))
        if p not in r.priorities:
            raise Refused(400, f'нет такого приоритета: {p}')
        r.priority(pid, p)
        event(reg_name, 'priority', id=pid, to=p)
        return {}
    if path == 'comment':
        text = str(body.get('text', '')).strip()
        if not text or len(text) > 2000:
            raise Refused(400, 'комментарий: от 1 до 2000 символов')
        r.comment(pid, text)
        event(reg_name, 'comment', id=pid, text=text[:200])
        return {}
    if path == 'accept':
        if not body.get('confirm'):
            raise Refused(400, 'принять — только с подтверждением')
        c = next((c for c in state()['items'] if c['reg'] == reg_name and c['id'] == pid), None)
        if not c:
            raise Refused(404, f'нет пункта {pid}')
        if c['check'] in ('not', 'partly') and not body.get('red_ok'):
            raise Refused(409, 'пробы красные — всё равно принять?', dict(c, need='red_ok'))
        words = f"[доска] принято {pid} «{c['title'][:80]}»"
        with FM.locked() as held:
            if not held:
                raise Refused(503, 'Реестр занят — повторите через пару секунд.')
            owner_line(words)
        r.accept(pid, words)
        return {}
    raise Refused(404, 'нет такого действия')


# ---------------------------------------------------------------- HTTP
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'ForemanBoard/2.1'

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8', extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        allowed = (f'127.0.0.1:{PORT}', f'localhost:{PORT}')
        return host in allowed and (origin is None or origin in tuple('http://' + a for a in allowed))

    def _token_ok(self):
        return secrets.compare_digest(self.headers.get('X-Foreman-Token', ''), TOKEN)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if not self._host_ok():
            return self._send(403, {'ok': False, 'error': 'чужой адрес'})
        if u.path == '/':
            # (the page is code without data: every byte of data comes from /fm/api/ with the key; the page keeps its tab's key in
            #  sessionStorage, so F5 after the key left the address bar still works)
            nonce = secrets.token_hex(12)
            csp = (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; connect-src 'self'; img-src data:; "
                   "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            html = io.open(os.path.join(HERE, 'board.html'), encoding='utf-8').read()
            poll = float((FM.CFG.get('board') or {}).get('poll_s', 3))
            html = html.replace('{{NONCE}}', nonce).replace('{{LANG}}', FM.CFG.get('lang', 'ru')).replace('{{POLL_MS}}', str(int(poll * 1000)))
            return self._send(200, html.encode('utf-8'), 'text/html; charset=utf-8', {'Content-Security-Policy': csp})
        if not u.path.startswith('/fm/api/'):
            return self._send(404, {'ok': False, 'error': 'нет такого адреса'})
        if not self._token_ok():
            return self._send(403, {'ok': False, 'error': 'нет ключа доски'})
        q = urllib.parse.parse_qs(u.query)
        try:
            with _mutex:
                if u.path == '/fm/api/state':
                    if q.get('since', [''])[0] == version():
                        return self._send(200, {'ok': True, 'unchanged': True, 'version': version()})
                    return self._send(200, state())
                if u.path == '/fm/api/item':
                    return self._send(200, {'ok': True, 'item': item_detail(q.get('reg', [''])[0], q.get('id', [''])[0]), 'version': version()})
            return self._send(404, {'ok': False, 'error': 'нет такого адреса'})
        except Refused as e:
            return self._send(e.code, {'ok': False, 'error': e.msg, 'item': e.item})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if not self._host_ok() or not self._token_ok():
            return self._send(403, {'ok': False, 'error': 'нет ключа доски или чужой адрес'})
        if not u.path.startswith('/fm/api/'):
            return self._send(404, {'ok': False, 'error': 'нет такого адреса'})
        n = int(self.headers.get('Content-Length') or 0)
        if n > 64 * 1024:
            return self._send(413, {'ok': False, 'error': 'слишком большой запрос'})
        try:
            body = json.loads(self.rfile.read(n).decode('utf-8') or '{}')
        except ValueError:
            return self._send(400, {'ok': False, 'error': 'не JSON'})
        try:
            with _mutex:
                out = act(u.path[len('/fm/api/'):], body if isinstance(body, dict) else {})
                _cache.clear()
                return self._send(200, {'ok': True, **out, 'version': version()})
        except Refused as e:
            _cache.clear()
            return self._send(e.code, {'ok': False, 'error': e.msg, 'item': e.item})


class Server(http.server.ThreadingHTTPServer):
    """the port is taken EXCLUSIVELY: http.server's default SO_REUSEADDR lets a second server on Windows bind a port another one
    already listens on — the browser then reaches either (04.11: an idle `python -m http.server 8765` answered the owner's board
    link with a directory listing)"""
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve(fm, argv):
    global FM, TOKEN, PORT, REGS
    FM = fm
    bcfg = FM.CFG.get('board') or {}
    PORT = int(argv[argv.index('--port') + 1]) if '--port' in argv else int(bcfg.get('port', 8765))
    token_file = argv[argv.index('--token-file') + 1] if '--token-file' in argv else bcfg.get('token_file', '')
    if not sys.stdout.isatty() and not token_file:
        print(FM.L.get('board_tty', 'Доску запускает владелец из своего терминала (там печатается ссылка с ключом); для автоматики — '
                                    '--token-file <путь>.'))
        return 1
    REGS = registries()
    if not REGS:
        print('На доске нечего показывать: модуль promises выключен, а в config.json → board.registries пусто.')
        return 1
    TOKEN = secrets.token_hex(16)
    srv, wanted = None, PORT
    for p in [PORT] if '--port' in argv else range(PORT, PORT + 20):   # (the configured port busy → the next free one)
        try:
            srv = Server(('127.0.0.1', p), Handler)
            PORT = p
            break
        except OSError:
            continue
    if not srv:
        print(f'Порт {wanted} занят другой программой' + ('' if '--port' in argv else f' (и следующие 19 тоже)') + ' — укажите --port N.')
        return 1
    if PORT != wanted:
        print(f'Порт {wanted} занят другой программой — доска открыта на {PORT}.')
    url = f'http://127.0.0.1:{PORT}/?t={TOKEN}'
    if token_file:
        with io.open(token_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'token': TOKEN, 'port': PORT}))
    if sys.stdout.isatty():
        print(f'Прораб · доска: {url}\n(Ctrl+C — остановить)')
        if '--no-open' not in argv:
            try:
                webbrowser.open(url)
            except Exception:
                pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
