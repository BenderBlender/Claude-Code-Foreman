"""test_v24.py — Foreman 2.4 checks (ideas from Claude-Code-Game-Studios, read 07.11; the plan reviewed by Fable before any code):
  A  evidence stamps — an acceptance hashes what its proof stands on (grep → the matched lines ± 2, doc → its heading section, file /
     evidence → the whole file, text normalised); a later edit of THAT is a yellow «re-check» line; `stamp P-…` after a re-check;
  B  the subagent contract — a brief's «Файл результата: `…`» must exist when the subagent stops: one block, then the parent is told;
  C  rules with paths — inside the project → .claude/rules/foreman-R-….md (generated, following the rule's life), outside → the edit
     hook, once per session;
  E  «a temporary absence is not a durable fact» — a warning, and «re-check» in recall;  F  weak probes;  install / uninstall.
Standard library only; throw-away projects.   python tests/test_v24.py   exit 0 = all passed"""
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
fails = 0


def check(name, ok, info=''):
    global fails
    fails += not ok
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {str(info)[:400]}' if info and not ok else ''))


def fm(proj, *args, stdin=None):
    r = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=proj, input=stdin, capture_output=True,
                       encoding='utf-8')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def hook(proj, mode, payload):
    code, out = fm(proj, 'hook', mode, stdin=json.dumps(payload, ensure_ascii=False))
    try:
        return json.loads(out) if out.strip() else {}
    except ValueError:
        return {'raw': out}


def ctx(o):
    return (o.get('hookSpecificOutput') or {}).get('additionalContext', '')


def write(proj, rel, text, mode='w', nl='\n'):
    p = os.path.join(proj, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, mode, encoding='utf-8', newline=nl).write(text)


def reg(proj):
    return {json.loads(l)['id']: json.loads(l) for l in io.open(os.path.join(proj, '.foreman', 'promises.jsonl'), encoding='utf-8') if l.strip()}


def events(proj):
    p = os.path.join(proj, '.foreman', 'events.jsonl')
    return [json.loads(l) for l in io.open(p, encoding='utf-8') if l.strip()] if os.path.exists(p) else []


def add(proj, title, probes, **more):
    code, out = fm(proj, 'add', json.dumps({'title': title, 'quote': title, 'probes': probes, **more}, ensure_ascii=False))
    return out.strip().splitlines()[-1]


def accept(proj, pid, *more):
    words = f'{pid} принимаю, всё проверил сам'
    hook(proj, 'prompt', {'prompt': words})
    return fm(proj, 'set', pid, 'status=accepted', *more, '--quote', words)


def brief(proj):
    return fm(proj, 'brief')[1]


def transcript(base, name, brief_text, ts=None):
    p = os.path.join(base, name + '.jsonl')
    ts = ts or dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
    rows = [{'type': 'system', 'content': 'init'}, {'type': 'user', 'timestamp': ts, 'message': {'role': 'user', 'content': brief_text}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Файл результата: `fake/should_not_count.md`'}]}}]
    io.open(p, 'w', encoding='utf-8').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    return p


APP = ''.join(f'line {n}\n' for n in range(40)) + 'def export(fmt):\n    return render(fmt)\n' + ''.join(f'tail {n}\n' for n in range(40))
GUIDE = '# Guide\n\n## Импорт\nКак загрузить файл.\n\n## Экспорт\nКнопка «Экспорт» сохраняет PDF.\n\n## Прочее\nРазное.\n'

base = tempfile.mkdtemp(prefix='foreman_v24_')
try:
    proj = os.path.join(base, 'proj')
    os.makedirs(proj)
    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes'], capture_output=True, encoding='utf-8')
    check('install', r.returncode == 0, r.stdout[-400:])
    write(proj, 'src/app.py', APP)
    write(proj, 'src/util.py', 'def helper():\n    return 1\n')
    write(proj, 'docs/guide.md', GUIDE)
    os.makedirs(os.path.join(proj, 'shots'))
    io.open(os.path.join(proj, 'shots', 'export.png'), 'wb').write(b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 4)

    # ---------------------------------------------------------------- A: stamps
    p1 = add(proj, 'PDF export', ['grep:src/app.py:def export', 'doc:docs/guide.md:Экспорт', 'file:src/util.py'],
             evidence=['shots/export.png'])
    code, out = accept(proj, p1)
    st = (reg(proj)[p1].get('accepted') or {}).get('stamp') or {}
    kinds = sorted((f['path'], f['kind']) for f in st.get('files', []))
    check('A1 acceptance stamps the probes\' files and the evidence (grep region, doc section, file, evidence)', code == 0 and kinds == [
        ('docs/guide.md', 'doc'), ('shots/export.png', 'file'), ('src/app.py', 'grep'), ('src/util.py', 'file')], [out, kinds])
    check('A2 right after the acceptance: no yellow line, `check` says the stamp matches',
          'менялись после приёмки' not in brief(proj) and 'совпадает' in fm(proj, 'check', p1)[1], brief(proj)[-300:])
    write(proj, 'src/app.py', 'new tail line\n', mode='a')
    check('A3 an edit far from the grep region → quiet', 'менялись после приёмки' not in brief(proj), brief(proj)[-300:])
    write(proj, 'src/app.py', ''.join(f'inserted {n}\n' for n in range(10)) + io.open(os.path.join(proj, 'src/app.py'), encoding='utf-8').read())
    check('A4 lines inserted above the region (it moved) → quiet', 'менялись после приёмки' not in brief(proj), brief(proj)[-300:])
    write(proj, 'src/util.py', 'def helper():   \n    return 1\n', nl='\r\n')
    check('A5 the same text saved with CRLF and trailing spaces → quiet', 'менялись после приёмки' not in brief(proj), brief(proj)[-300:])
    write(proj, 'docs/guide.md', GUIDE.replace('Разное.', 'Совсем другое.'))
    check('A6 another section of the doc edited → quiet', 'менялись после приёмки' not in brief(proj), brief(proj)[-300:])
    write(proj, 'docs/guide.md', GUIDE.replace('сохраняет PDF', 'сохраняет PNG'))
    b = brief(proj)
    check('A7 the doc probe\'s own section edited → yellow «раздел»', 'менялись после приёмки' in b and p1 in b and 'раздел' in b, b[-400:])
    write(proj, 'docs/guide.md', GUIDE)
    t = io.open(os.path.join(proj, 'src/app.py'), encoding='utf-8').read().replace('    return render(fmt)', '    return render(fmt, dpi=72)')
    write(proj, 'src/app.py', t)
    b = brief(proj)
    check('A8 the grep region edited (the line after `def export`) → yellow «область»', p1 in b and 'app.py: область' in b, b[-400:])
    os.remove(os.path.join(proj, 'shots', 'export.png'))
    out = fm(proj, 'check', p1)[1]
    check('A9 the stamped evidence deleted → «НЕТ ФАЙЛА» (gone ≠ optional)', 'shots/export.png (НЕТ ФАЙЛА)' in out, out[-400:])
    code, out = fm(proj, 'stamp', p1, '--note', 'перепроверил')
    check('A10 `stamp` with the evidence missing → refused', code == 1 and 'не нашлось' in out, out)
    io.open(os.path.join(proj, 'shots', 'export.png'), 'wb').write(b'\x89PNG new render')
    code, out = fm(proj, 'stamp', p1, '--note', 'перепроверил экспорт руками')
    it = reg(proj)[p1]
    check('A11 `stamp` after a re-check → a new stamp, the note kept, an event; the brief is clean; still accepted',
          code == 0 and it['status'] == 'accepted' and (it['accepted'].get('restamp') or [{}])[-1].get('note') == 'перепроверил экспорт руками'
          and any(e.get('kind') == 'restamp' and e.get('id') == p1 for e in events(proj)) and 'менялись после приёмки' not in brief(proj),
          [out, it.get('accepted', {}).get('restamp')])
    p2 = add(proj, 'red one', ['file:src/missing.py'])
    accept(proj, p2)
    code, out = fm(proj, 'stamp', p2, '--note', 'x')
    check('A12 `stamp` on red probes → refused', code == 1 and 'зелёные' in out, out)
    p3 = add(proj, 'with evidence', ['file:src/util.py'], evidence=['shots/none_*.png'])
    code, out = accept(proj, p3)
    check('A13 acceptance whose evidence finds no file → refused, not accepted', code == 1 and reg(proj)[p3]['status'] != 'accepted'
          and 'не нашлось' in out, out)
    fm(proj, 'set', p1, 'probes=["file:src/util.py"]')
    check('A14 `set probes=` after the acceptance still voids it (2.1 rule kept)', reg(proj)[p1]['status'] == 'doing', reg(proj)[p1])
    p4 = add(proj, 'late evidence', ['grep:src/util.py:def helper'])
    accept(proj, p4)
    fm(proj, 'set', p4, 'evidence=["shots/export.png"]')
    out = fm(proj, 'check', p4)[1]
    check('A15 evidence named after the acceptance → «не в печати»', reg(proj)[p4]['status'] == 'accepted' and 'не в печати' in out, out[-300:])
    code, out = fm(proj, 'selftest')
    check('A16 the control still fails (selftest ok)', code == 0 and 'ok' in out, out[-200:])

    # ---------------------------------------------------------------- F: weak probes
    p5 = add(proj, 'only a file', ['file:src/util.py'])
    accept(proj, p5)
    p6 = add(proj, 'no probes at all', [])
    accept(proj, p6)
    b = brief(proj)
    line = next((l for l in b.splitlines() if 'пробы слабые' in l), '')
    check('F1 accepted on existence-only probes and on NO probes → the weak line; a grep-probed item is not there',
          p5 in line and p6 in line and p4 not in line, b[-500:])

    # ---------------------------------------------------------------- B: the subagent contract
    out_rel = 'out/report.md'
    tp = transcript(base, 'a1', f'Изучи код.\n\nФайл результата: `{out_rel}`')
    o = hook(proj, 'subagent', {'agent_type': 'general-purpose', 'agent_id': 'ag-1', 'agent_transcript_path': tp, 'stop_hook_active': False, 'cwd': proj})
    check('B1 missing output file → ONE block naming the path (the subagent goes on)', o.get('decision') == 'block' and out_rel in o.get('reason', ''), o)
    o = hook(proj, 'subagent', {'agent_type': 'general-purpose', 'agent_id': 'ag-1', 'agent_transcript_path': tp, 'stop_hook_active': False, 'cwd': proj})
    check('B2 the same agent stops again without the file → no second block (even if stop_hook_active is not set), an event',
          not o and any(e.get('kind') == 'agent_artifact_missing' and e.get('agent_id') == 'ag-1' for e in events(proj)), o)
    o = hook(proj, 'agent-done', {'tool_name': 'Agent', 'tool_input': {}})
    check('B3 PostToolUse(Agent) tells the parent once', 'report.md' in ctx(o) and 'НЕ сделан' in ctx(o), o)
    o = hook(proj, 'agent-done', {'tool_name': 'Agent', 'tool_input': {}})
    check('B4 … and only once', not ctx(o), o)
    write(proj, out_rel, '# report\n')
    tp2 = transcript(base, 'a2', f'Сделай отчёт. Файл результата: `{out_rel}`')
    n0 = len(events(proj))
    o = hook(proj, 'subagent', {'agent_type': 'general-purpose', 'agent_id': 'ag-2', 'agent_transcript_path': tp2, 'cwd': proj})
    check('B5 the file exists → silence, no missing event', not o and not any(e.get('kind') == 'agent_artifact_missing' and e.get('agent_id') == 'ag-2'
                                                                       for e in events(proj)[n0:]), o)
    for name, text in (('placeholder', 'Файл результата: `<path>`'), ('example', 'Формат брифа, например Файл результата: `x/y.md`'),
                       ('word', 'Output file: `path`'), ('none', 'Просто посмотри код')):
        tpx = transcript(base, 'a_' + name, text)
        o = hook(proj, 'subagent', {'agent_type': 'general-purpose', 'agent_id': 'ag-' + name, 'agent_transcript_path': tpx, 'cwd': proj})
        check(f'B6 no contract ({name}) → silence', not o, o)
    tp3 = transcript(base, 'a3', 'Output file: `out/en_report.md`')
    o = hook(proj, 'subagent', {'agent_type': 'general-purpose', 'agent_id': 'ag-3', 'agent_transcript_path': tp3, 'cwd': proj})
    check('B7 the English marker works too', o.get('decision') == 'block' and 'en_report.md' in o.get('reason', ''), o)
    o = hook(proj, 'subagent', {'agent_type': '', 'agent_id': 'ag-int', 'agent_transcript_path': tp3, 'cwd': proj})
    check('B8 Claude Code\'s internal agent (empty agent_type) → silence', not o, o)
    o = hook(proj, 'subagent', {'agent_type': 'Explore', 'agent_id': 'ag-ro', 'agent_transcript_path': tp3, 'cwd': proj})
    check('B9 a read-only agent type → never blocked, only an event', not o and any(e.get('kind') == 'agent_artifact_missing'
                                                                                    and e.get('agent_id') == 'ag-ro' for e in events(proj)), o)
    o = hook(proj, 'stop', {'transcript_path': '', 'last_assistant_message': 'готово'})
    check('B10 the main Stop hook tells what the parent has not heard yet (a background agent)', o.get('decision') == 'block'
          and 'Explore' in o.get('reason', ''), o)
    fm(proj, 'hook', 'subagent-start', stdin=json.dumps({'agent_type': 'general-purpose', 'agent_id': 'ag-9'}))
    check('B11 SubagentStart → an audit line', any(e.get('kind') == 'agent_start' and e.get('agent_id') == 'ag-9' for e in events(proj)))

    # ---------------------------------------------------------------- C: rules with paths
    far = os.path.join(base, 'other_drive', 'studio3d')
    os.makedirs(far)
    rule = {'when': 'editing the app code', 'do': 'bump the cache keys of every importer', 'quote': 'ключи кэша меняй везде',
            'paths': ['src/**', far.replace('\\', '/') + '/**']}
    code, out = fm(proj, 'rule', 'add', json.dumps(rule, ensure_ascii=False))
    rid = out.strip().split()[-1] if 'R-' in out else 'R-001'
    rid = next((w.strip('.,:;') for w in out.split() if w.startswith('R-')), 'R-001')
    words = f'{rid} принимаю, хорошее правило'
    hook(proj, 'prompt', {'prompt': words})
    code, out = fm(proj, 'rule', 'accept', rid, '--quote', words)
    gen = os.path.join(proj, '.claude', 'rules', f'foreman-{rid}.md')
    body = io.open(gen, encoding='utf-8').read() if os.path.exists(gen) else ''
    check('C1 an accepted rule with paths inside → .claude/rules/foreman-R-….md (paths: src/**; marked generated; the far path not in it)',
          code == 0 and '"src/**"' in body and 'generated by Foreman' in body and 'other_drive' not in body, [out, body[:300]])
    o = hook(proj, 'edit', {'session_id': 's1', 'tool_name': 'Edit', 'tool_input': {'file_path': os.path.join(far, 'app.js')}})
    check('C2 an edit of a file OUTSIDE the project under the rule\'s path → the rule shown', rid in ctx(o) and 'cache keys' in ctx(o), o)
    o = hook(proj, 'edit', {'session_id': 's1', 'tool_name': 'Edit', 'tool_input': {'file_path': os.path.join(far, 'logic.js')}})
    check('C3 the second edit in the same session → silent', not ctx(o), o)
    o = hook(proj, 'edit', {'session_id': 's2', 'tool_name': 'Write', 'tool_input': {'file_path': os.path.join(far, 'logic.js')}})
    check('C4 a new session → shown again', rid in ctx(o), o)
    o = hook(proj, 'edit', {'session_id': 's3', 'tool_name': 'Edit', 'tool_input': {'file_path': os.path.join(proj, 'src', 'app.py')}})
    check('C5 an in-project path → not by the hook (Claude Code loads .claude/rules itself)', not ctx(o), o)
    for payload in ({'session_id': 's4', 'tool_name': 'Edit', 'tool_input': {}}, {'nonsense': True}):
        o = hook(proj, 'edit', payload)
        check('C6 no file / odd input → silent', not ctx(o), o)
    code, out = fm(proj, 'rule', 'drop', rid)
    check('C7 the rule dropped → its generated file removed', not os.path.exists(gen), out)

    # ---------------------------------------------------------------- E: «a temporary absence is not a durable fact»
    code, out = fm(proj, 'rule', 'add', json.dumps({'when': 'texturing a model', 'do': 'UltraTex не установлен — используй UniForge',
                                                       'quote': 'пока так'}, ensure_ascii=False))
    check('E1 a rule about something absent, no as_of → a warning', 'НЕТ' in out and 'as_of' in out, out)
    code, out = fm(proj, 'rule', 'add', json.dumps({'when': 'rigging', 'do': 'SkinTokens не установлен — проверить перед работой',
                                                       'quote': 'проверяй', 'as_of': '2026-01-01'}, ensure_ascii=False))
    check('E2 … with as_of → no warning', 'as_of' not in out, out)
    code, out = fm(proj, 'recall', 'rigging SkinTokens')
    check('E3 recall marks an old absence rule «проверить»', 'проверить' in out, out[-300:])
    sys.path.insert(0, os.path.join(proj, '.foreman'))
    import recall as RC
    yes = ['модель не установлена', 'веса отсутствуют', 'not installed here', "it doesn't exist", 'нет весов для этого', 'no wheel yet',
           'пока нет поддержки', 'ещё нет', 'папка отсутствует', "isn't installed"]
    no = ['нет, так не делай', 'нет смысла', 'я не установил приоритет', 'exists and works', 'there is no problem', 'нетривиально',
          'установлен и работает', 'отличный результат', 'not yet decided by the owner', 'да, нет — решай сам']
    bad = [s for s in yes if not RC.ABSENCE.search(s)] + [s for s in no if RC.ABSENCE.search(s)]
    check('E4 the absence pattern: 10 true, 10 false', not bad, bad)

    # ---------------------------------------------------------------- install / uninstall
    sp = os.path.join(proj, '.claude', 'settings.local.json')
    s = json.load(io.open(sp, encoding='utf-8'))
    hk = s.get('hooks', {})
    check('I1 install wired SubagentStop, SubagentStart, PostToolUse(Agent|Task), PreToolUse(Edit|Write|…)',
          all(e in hk for e in ('SubagentStop', 'SubagentStart', 'PostToolUse', 'PreToolUse'))
          and hk['PostToolUse'][0].get('matcher') == 'Agent|Task' and 'Edit' in hk['PreToolUse'][0].get('matcher', ''), list(hk))
    s['hooks'].setdefault('PreToolUse', []).append({'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'node my_guard.js'}]})
    io.open(sp, 'w', encoding='utf-8').write(json.dumps(s))
    subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes'], capture_output=True, encoding='utf-8')
    hk = json.load(io.open(sp, encoding='utf-8'))['hooks']
    ours = lambda ev: sum('.foreman' in h.get('command', '') for g in hk.get(ev, []) for h in g.get('hooks', []))
    check('I2 re-install → no duplicates, the foreign hook kept', ours('SubagentStop') == 1 and ours('PreToolUse') == 1
          and any('my_guard' in h.get('command', '') for g in hk['PreToolUse'] for h in g['hooks']), hk.get('PreToolUse'))
    subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes', '--modules', 'promises,lessons'], capture_output=True, encoding='utf-8')
    hk = json.load(io.open(sp, encoding='utf-8'))['hooks']
    check('I3 --modules without contract / rules_paths → their hooks gone', 'SubagentStop' not in hk and ours('PreToolUse') == 0, list(hk))
    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes'], capture_output=True, encoding='utf-8')
    cfgm = json.load(io.open(os.path.join(proj, '.foreman', 'config.json'), encoding='utf-8'))['modules']
    check('I3b a plain re-install keeps the modules the owner chose (contract stays off)', cfgm.get('contract') is False, cfgm)
    subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes', '--modules', 'promises,lessons,contract,rules_paths'],
                   capture_output=True, encoding='utf-8')
    code, out = fm(proj, 'rule', 'add', json.dumps({'when': 'docs', 'do': 'keep headings', 'quote': 'держи заголовки', 'paths': ['docs/**']},
                                                     ensure_ascii=False))
    rid2 = next((w.strip('.,:;') for w in out.split() if w.startswith('R-')), '')
    words = f'{rid2} принимаю, хорошее правило'
    hook(proj, 'prompt', {'prompt': words})
    fm(proj, 'rule', 'accept', rid2, '--quote', words)
    gen2 = os.path.join(proj, '.claude', 'rules', f'foreman-{rid2}.md')
    own_rule = os.path.join(proj, '.claude', 'rules', 'mine.md')
    io.open(own_rule, 'w', encoding='utf-8').write('---\npaths:\n  - "x/**"\n---\nmy rule\n')
    had = os.path.exists(gen2)
    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--uninstall', '--yes'], capture_output=True, encoding='utf-8')
    hk = json.load(io.open(sp, encoding='utf-8')).get('hooks', {})
    check('I4 uninstall → our hooks and the generated rule gone; the owner\'s own rule file and foreign hook kept',
          had and not os.path.exists(gen2) and os.path.exists(own_rule) and 'SubagentStop' not in hk
          and any('my_guard' in h.get('command', '') for g in hk.get('PreToolUse', []) for h in g['hooks']), [had, list(hk)])
finally:
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{"ALL PASSED" if not fails else f"{fails} FAILED"}')
sys.exit(1 if fails else 0)
