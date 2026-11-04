"""ext_check.py — a tiny external registry for the board's «cli» adapter test (Russian statuses, like a studio's promises_check.py):
--json --light · --set ID k=v [--by X] · --rank ID… · --comment ID text [--by X] · --accept ID --quote Q [--by X] · --skip ID --why W.
«принято» only through --accept (whose quote must be in <FOREMAN_DIR>/owner.jsonl); the registry is ext.jsonl next to this script
(EXT_REG overrides)."""
import json
import os
import sys

REG = os.environ.get('EXT_REG', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ext.jsonl'))
FDIR = os.environ.get('FOREMAN_DIR', '')


def rows():
    return [json.loads(l) for l in open(REG, encoding='utf-8') if l.strip()] if os.path.exists(REG) else []


def save(rs):
    tmp = REG + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rs))
    os.replace(tmp, REG)


def item(rs, pid):
    it = next((r for r in rs if r['id'] == pid), None)
    if not it:
        print('нет пункта', pid)
        sys.exit(1)
    return it


a = sys.argv[1:]
rs = rows()
if '--json' in a:
    for r in rs:
        r['_check'] = 'готово' if r.get('done') else 'нет'
        r['_probes'] = [['file:x', bool(r.get('done'))]]
    print(json.dumps({'when': 'now', 'control_ok': True, 'registry': rs, 'inbox_new': [], 'server': True}, ensure_ascii=False))
elif '--set' in a:
    it = item(rs, a[a.index('--set') + 1])
    for kv in a[a.index('--set') + 2:]:
        if kv.startswith('--') or '=' not in kv:
            continue
        k, _, v = kv.partition('=')
        if k == 'status' and v == 'принято':
            print('«принято» — только --accept с цитатой')
            sys.exit(1)
        it[k] = v
    save(rs)
    print(json.dumps(it, ensure_ascii=False))
elif '--rank' in a:
    ids = [x for x in a[a.index('--rank') + 1:] if not x.startswith('--') and x != 'owner-board']
    for n, pid in enumerate(ids):
        item(rs, pid)['rank'] = (n + 1) * 10
    save(rs)
    print('{}')
elif '--comment' in a:
    i = a.index('--comment')
    it = item(rs, a[i + 1])
    it.setdefault('comments', []).append({'ts': 'now', 'by': a[a.index('--by') + 1] if '--by' in a else 'agent', 'text': a[i + 2]})
    save(rs)
    print(json.dumps(it, ensure_ascii=False))
elif '--accept' in a:
    it = item(rs, a[a.index('--accept') + 1])
    q = a[a.index('--quote') + 1] if '--quote' in a else ''
    said = [json.loads(l).get('text', '') for l in open(os.path.join(FDIR, 'owner.jsonl'), encoding='utf-8') if l.strip()] if FDIR else []
    if not q or not any(q in s for s in said):
        print('таких слов владельца нет в журнале')
        sys.exit(1)
    it.update(status='принято', accepted={'by': a[a.index('--by') + 1] if '--by' in a else 'owner-quote', 'quote': q})
    save(rs)
    print(json.dumps(it, ensure_ascii=False))
elif '--skip' in a:
    print('{}')
else:
    print('ext_check: nothing to do')
