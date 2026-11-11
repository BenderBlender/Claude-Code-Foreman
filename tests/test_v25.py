"""test_v25.py — Foreman 2.5 «knowledge at the moment of action» (act.py), on fixtures modelled on the case of 09.11 (the owner's
messages and the kinds of actions of that day; her real tool calls could not be replayed — copying them was stopped by Claude Code's
own protection). The plan was reviewed by Fable before any code (FABLE_2.5_review.md):
  A  materials — «first study …» with links / paths / a web topic → M-…; the first working action refused once; studied = notes that
     name every source and say what was taken / not read (+ opened in the transcript);
  B  recall by the action — a switch, off by default (the council of 11.11); hot rules only, ≥ 2 trigger words from the situation
     and the Keys (borrowed from a card), a score bar, once per 30 min; silent when the rule has its own guard or the action runs
     the tool it names; ordinary commands stay silent;
  ♥  heartbeat — a switch, off by default; after a compaction or when the owner is silent ≥ 30 min, working calls only, rotated,
     a day's cap;
  C  attempts — variants of the script a command RUNS (after the interpreter, through gpu_guard -Run; the registry never counts):
     a warning on the 3rd; a refusal on the 5th only with attempts_deny;
  D  engines — the doc's section before the first RUN of its script in a session (not a path in an argument, not a reading);
     deny_first refuses once; ack with the modes;
  the quietness — `replay --tools` over a modelled day; the time per call.
Standard library only; throw-away projects.   python tests/test_v25.py   exit 0 = all passed"""
import datetime as dt
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

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
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {str(info)[:500]}' if info and not ok else ''))


ENV = dict(os.environ)


def fm(proj, *args, stdin=None):
    r = subprocess.run([PY, os.path.join(proj, '.foreman', 'foreman.py'), *args], cwd=proj, input=stdin, capture_output=True,
                       encoding='utf-8', env=ENV)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def hook(proj, mode, payload):
    code, out = fm(proj, 'hook', mode, stdin=json.dumps(payload, ensure_ascii=False))
    try:
        return json.loads(out) if out.strip() else {}
    except ValueError:
        return {'raw': out}


def ctx(o):
    return (o.get('hookSpecificOutput') or {}).get('additionalContext', '')


def denied(o):
    hs = o.get('hookSpecificOutput') or {}
    return hs.get('permissionDecisionReason', '') if hs.get('permissionDecision') == 'deny' else ''


def write(proj, rel, text):
    p = os.path.join(proj, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(text)
    return p


def tool(proj, sid, name, cwd=None, transcript=None, **ti):
    return hook(proj, 'tool', {'session_id': sid, 'tool_name': name, 'tool_input': ti, 'cwd': cwd or proj,
                               **({'transcript_path': transcript} if transcript else {})})


def bash(proj, sid, command, description='', **kw):
    return tool(proj, sid, 'Bash', command=command, description=description, **kw)


def act_rows(proj):
    p = os.path.join(proj, '.foreman', 'act.jsonl')
    return [json.loads(l) for l in io.open(p, encoding='utf-8') if l.strip()] if os.path.exists(p) else []


def set_act_rows(proj, rows):
    io.open(os.path.join(proj, '.foreman', 'act.jsonl'), 'w', encoding='utf-8', newline='\n').write(
        ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))


def materials(proj):
    p = os.path.join(proj, '.foreman', 'materials.jsonl')
    return {json.loads(l)['id']: json.loads(l) for l in io.open(p, encoding='utf-8') if l.strip()} if os.path.exists(p) else {}


def utc(minutes_ago=0):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)).isoformat().replace('+00:00', 'Z')


def transcript(path, rows):
    """rows: ('user', text, minutes_ago) | ('tool', name, input, minutes_ago) | ('compact',)"""
    out = []
    for r in rows:
        if r[0] == 'user':
            out.append({'type': 'user', 'timestamp': utc(r[2]), 'message': {'role': 'user', 'content': r[1]}})
        elif r[0] == 'tool':
            out.append({'type': 'assistant', 'timestamp': utc(r[3]), 'message': {'content': [{'type': 'tool_use', 'id': 't', 'name': r[1],
                                                                                                'input': r[2]}]}})
        elif r[0] == 'compact':
            out.append({'type': 'user', 'isCompactSummary': True, 'timestamp': utc(0), 'message': {'content': 'summary'}})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, 'w', encoding='utf-8').write(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in out))
    return path


# (a hot rule book modelled on the project's PLAYBOOK rows that 09.11 broke — the 2nd cell is what to DO)
PLAYBOOK = """# PLAYBOOK

| When | Do | Where |
|---|---|---|
| [P2] ANY build / measure / check work — judging a render, a wire, a model view, a selection | Never one view: front AND side (+ ¾), each full size, every defect named per view before any verdict — look through `look_views.py`. | `cards/views.md` |
| [P10·P13] A SUB-GOAL fails TWICE (a selection, a tool chain, colour bands, a method) | Stop: what exactly is wrong? 2–3 different approaches in OPTIONS.md, pick one, then go on. | `cards/work.md` |
| [P8] Using an ENGINE we ALREADY HAVE (P3-SAM, SAM, TRELLIS, X-Part) for a new purpose | Read its study first: modes, the click +/− selection, companions. | `cards/engines.md` |
| [P12] Something WORKED (a recipe, a tool chain) · a milestone | Save it NOW: exact commands into the skill, a ledger line. | `cards/work.md` |
| [P1] A GPU job (generation, training, a big render) while another may run | One GPU job at a time: check the lock first. | `cards/resources.md` |
| [P13] The 3D STUDIO after a COMPACTION — CORRECTION 07.11 from the producer, a repeat of his correction messages: «Почему я вижу старый интерфейс?» | Read the registry, not the summary. | `cards/studio.md` |
| [P4] Taking a SCREENSHOT of a web page to study it — failed twice | Full-size shots; the hook `pane_shot_hook.mjs` denies the small pane shot. | `cards/work.md` |
"""
# (a card: the same GPU row with its Keys — the hot copy above has none; B borrows them)
CARD = """# Card «resources»

| When | Do | With | Keys |
|---|---|---|---|
| [P1] A GPU job (generation, training, a big render) while another may run | One GPU job at a time. | `gpu_guard` | Keys: видеокарта, nvidia, vram, cuda, out of memory |
"""
STUDY = """# P3-SAM — study

## Как устроено
Сегментация меша по точкам.

## Режимы
- авто: сетка точек, части склеиваются по рамкам;
- щелчки «+» / «−» — для тонких частей (пальцы, уши), режим точек;
- X-Part — достраивает скрытые поверхности.

## Ловушки
Авто режет тонкое.
"""
M_1228 = ('Делай. Но сначала изучи в интернете эффективные системы ретопологии (особенно те что использует Zbrush). '
          'И посмотри если есть готовые решения на гитхабе — чтобы не изобретать велосипед.')
M_1416 = ('Вот ещё ссылки, потом разбери: https://github.com/someone/BlenderRetopology-Skill и '
          'https://github.com/Tencent-Hunyuan/Hunyuan3D-Omni/tree/main/P3-SAM')

base = tempfile.mkdtemp(prefix='foreman_v25_')
ENV['FOREMAN_TRANSCRIPTS'] = os.path.join(base, 'transcripts')
try:
    proj = os.path.join(base, 'proj')
    os.makedirs(proj)
    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes'], capture_output=True, encoding='utf-8')
    check('install', r.returncode == 0, r.stdout[-400:])
    settings = json.load(io.open(os.path.join(proj, '.claude', 'settings.local.json'), encoding='utf-8'))
    pre = settings['hooks'].get('PreToolUse') or []
    check('install: ONE PreToolUse hook «tool» on Bash|PowerShell|Edit|Write|…|Agent|Task, the 2.4 «edit» hook replaced',
          len(pre) == 1 and 'hook tool' in pre[0]['hooks'][0]['command'] and 'Bash' in pre[0]['matcher'] and 'Agent' in pre[0]['matcher']
          and 'Edit' in pre[0]['matcher'] and 'hook edit' not in json.dumps(settings), pre)
    check('install: act.py copied, config has «act» and «engines»', os.path.exists(os.path.join(proj, '.foreman', 'act.py')))
    cm = io.open(os.path.join(proj, 'CLAUDE.md'), encoding='utf-8').read()
    check('install: the CLAUDE.md section has the rule «Знание в момент действия» numbered after the contract rule (11.)',
          '11. **Знание в момент действия (2.5).**' in cm and 'material read' in cm, cm[-700:])
    cfgp = os.path.join(proj, '.foreman', 'config.json')
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    md = cfg.get('modules') or {}
    check('install: recall by the action, the heartbeat and the advisor are switches, OFF by default (the council of 11.11); A, C, D on; '
          'the «advisor» section is written', md.get('act_recall') is False and md.get('heartbeat') is False and md.get('advisor') is False
          and md.get('materials') and md.get('attempts') and md.get('engines') and (cfg.get('advisor') or {}).get('day_max') == 3, [md, cfg.get('advisor')])
    cfg['act'] = {**cfg.get('act', {}), 'hot_books': ['rules/PLAYBOOK.md'], 'keys_books': ['rules/cards/*.md'],
                  # (the project's own bookkeeping and its GPU wrapper — as this project's config names them)
                  'bookkeeping': [r'foreman\.py', r'promises_check\.py'], 'wrappers': [r'gpu_guard\.ps1']}
    cfg['engines'] = [{'name': 'P3-SAM', 'match': r'p3.?sam', 'doc': 'docs/P3SAM_STUDY.md', 'section': 'Режимы'}]
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    write(proj, 'rules/PLAYBOOK.md', PLAYBOOK)
    write(proj, 'rules/cards/resources.md', CARD)
    write(proj, 'docs/P3SAM_STUDY.md', STUDY)
    write(proj, 'tools/gpu_guard.ps1', 'param($Run, $Name, $NeedGB)\n')

    # ---------------------------------------------------------------- A: the owner's materials
    o = hook(proj, 'prompt', {'prompt': M_1228, 'session_id': 'sA'})
    m = materials(proj).get('M-0001') or {}
    check('A1 12:28 «сначала изучи в интернете … на гитхабе» → M-0001: a web topic, FIRST; the note says the work will be stopped once',
          m.get('topic') and m.get('first') and 'M-0001' in ctx(o) and 'СНАЧАЛА' in ctx(o) and 'остановлено один раз' in ctx(o), [m, ctx(o)])
    o = hook(proj, 'prompt', {'prompt': M_1416, 'session_id': 'sA'})
    m = materials(proj).get('M-0002') or {}
    check('A2 14:16 two links + «потом разбери» → M-0002 with both sources, no gate (no «first»)',
          len(m.get('sources') or []) == 2 and not m.get('first') and 'M-0002' in ctx(o), [m, ctx(o)])
    o = hook(proj, 'prompt', {'prompt': 'Поправь F:\\work\\retopo\\bands_to_groups.py — там порог не тот', 'session_id': 'sA'})
    check('A3 a path that is only the object of an edit («поправь F:\\…\\x.py») → no material', 'M-0003' not in materials(proj), ctx(o))
    o = hook(proj, 'prompt', {'prompt': 'Посмотри почему падает F:\\work\\retopo\\run.py', 'session_id': 'sA'})
    m = materials(proj).get('M-0003') or {}
    check('A4 «посмотри почему падает <path>» → a material without a gate', m and not m.get('first') and 'остановлено' not in ctx(o), [m, ctx(o)])
    for t in ('Read', 'Grep', 'WebFetch'):
        o = tool(proj, 'sA', t, file_path='x.md', url='https://github.com/x')
        check(f'A5 {t} before the study → passes, silent', not denied(o) and not ctx(o), o)
    o = bash(proj, 'sA', 'ls -la F:/work/retopo', 'List the retopo folder')
    check('A6 a pure read in the shell (ls) → passes', not denied(o), o)
    o = tool(proj, 'sA', 'Write', file_path=os.path.join(proj, 'research', 'RESEARCH.md'), content='# notes')
    check('A7 writing the study notes (.md) → passes', not denied(o), o)
    o = bash(proj, 'sA', 'python F:/work/retopo/qremesh_guides.py --mesh granny.glb', 'Build QRemesh guides on the granny head')
    check('A8 the first WORKING action before the study → refused once, naming M-0001 and the exit',
          'M-0001' in denied(o) and 'material read' in denied(o) and 'materials-later' in denied(o), o)
    o = bash(proj, 'sA', 'python F:/work/retopo/qremesh_guides.py --mesh granny.glb', 'Build QRemesh guides on the granny head')
    check('A9 the same action again → passes (one refusal per material — advice, not a wall)', not denied(o), o)
    o = hook(proj, 'stop', {'session_id': 'sA'})
    check('A10 Stop → «материалы не изучены: M-0001 …»', 'материалы не изучены' in str(o.get('reason')) and 'M-0001' in str(o.get('reason')), o)
    o = hook(proj, 'stop', {'session_id': 'sA'})
    check('A11 Stop again at once → no repeat (once per 20 min)', 'материалы не изучены' not in str(o.get('reason', '')), o)
    o = hook(proj, 'session', {'source': 'startup', 'session_id': 'sA2'})
    check('A12 the session brief lists the materials not studied', 'Материалы владельца не изучены' in ctx(o) and 'M-0001' in ctx(o), ctx(o))
    # studied = the notes name every source + say what was taken / not read
    write(proj, 'research/half.md', 'Взято из https://github.com/someone/BlenderRetopology-Skill: петли. Не прочитано: остальное.\n')
    code, out = fm(proj, 'material', 'read', 'M-0002', '--study', 'research/half.md')
    check('A13 notes without one of the sources → refused, naming it', code == 1 and 'Hunyuan3D-Omni' in out, out)
    write(proj, 'research/nomarks.md', 'someone/BlenderRetopology-Skill — петли.\nTencent-Hunyuan/Hunyuan3D-Omni/tree/main/P3-SAM — точки.\n')
    code, out = fm(proj, 'material', 'read', 'M-0002', '--study', 'research/nomarks.md')
    check('A14 notes naming both but not saying what was taken / not read → refused', code == 1 and 'не прочитано' in out, out)
    write(proj, 'research/full.md', 'Взято: someone/BlenderRetopology-Skill — петли вокруг глаз.\n'
                                    'Взято: github.com/Tencent-Hunyuan/Hunyuan3D-Omni/tree/main/P3-SAM — щелчки +/−.\nНе прочитано: X-Part.\n')
    code, out = fm(proj, 'material', 'read', 'M-0002', '--study', 'research/full.md')
    check('A15 full notes, no transcript of the session → studied, «проверен только разбор»',
          code == 0 and materials(proj)['M-0002']['state'] == 'read' and 'только разбор' in out, out)
    write(proj, 'research/topic1.md', 'Взято: одна ссылка https://example.com/a. Не прочитано: остальное.\n')
    code, out = fm(proj, 'material', 'read', 'M-0001', '--study', 'research/topic1.md')
    check('A16 a web topic with < 2 links in the notes → refused', code == 1 and '≥ 2' in out, out)
    write(proj, 'research/topic2.md', 'Взято: https://www.maxon.net/zremesher и https://github.com/a/quadwild. Не прочитано: Exoside.\n')
    code, out = fm(proj, 'material', 'read', 'M-0001', '--study', 'research/topic2.md')
    check('A17 a web topic with 2 links, taken / not read → studied', code == 0 and materials(proj)['M-0001']['state'] == 'read', out)
    code, out = fm(proj, 'material', 'skip', 'M-0003', '--why', 'нет')
    check('A18 skip without a real reason → refused', code == 1, out)
    code, out = fm(proj, 'material', 'skip', 'M-0003', '--why', 'владелец сам починил, разбор не нужен')
    check('A19 skip with a reason → deferred + a ledger line', code == 0 and materials(proj)['M-0003']['state'] == 'skipped'
          and 'M-0003' in io.open(os.path.join(proj, '.foreman', 'ledger.md'), encoding='utf-8').read(), out)
    # the «opened» check: a transcript of the session (where Claude Code keeps it) must show the sources opened
    hook(proj, 'prompt', {'prompt': 'Сначала изучи https://github.com/a/OpenRepo и https://github.com/b/ClosedRepo', 'session_id': 'sO'})
    slug = re.sub(r'[^A-Za-z0-9]', '-', proj)
    tp = transcript(os.path.join(ENV['FOREMAN_TRANSCRIPTS'], slug, 'sO.jsonl'),
                    [('user', 'Сначала изучи …', 1), ('tool', 'WebFetch', {'url': 'https://github.com/a/OpenRepo'}, 0)])
    o = hook(proj, 'stop', {'session_id': 'sO', 'transcript_path': tp})
    check('A20 Stop counts what was opened in the transcript: «открыто 1/2»', 'открыто 1/2' in str(o.get('reason')), o)
    write(proj, 'research/two.md', 'Взято: a/OpenRepo — X. Взято: b/ClosedRepo — Y. Не прочитано: ничего.\n')
    code, out = fm(proj, 'material', 'read', 'M-0004', '--study', 'research/two.md')
    check('A21 notes name a source that was never OPENED → refused, naming it', code == 1 and 'ClosedRepo' in out and 'OpenRepo' not in out.split(':', 2)[-1], out)
    transcript(tp, [('user', 'Сначала изучи …', 2), ('tool', 'WebFetch', {'url': 'https://github.com/a/OpenRepo'}, 0),
                    ('tool', 'Bash', {'command': 'git clone https://github.com/b/ClosedRepo M:/repos/ClosedRepo'}, 0)])
    code, out = fm(proj, 'material', 'read', 'M-0004', '--study', 'research/two.md')
    check('A22 both opened (a fetch, a git clone) → studied «открыто 2/2»', code == 0 and 'открыто 2/2' in out, out)
    hook(proj, 'prompt', {'prompt': 'Прежде чем продолжать, изучи https://github.com/c/AgentRepo', 'session_id': 'sG'})
    o = tool(proj, 'sG', 'Agent', description='Study the repo', subagent_type='general-purpose',
             prompt='Read https://github.com/c/AgentRepo and write notes. Файл результата: `research/agent.md`')
    check('A23 an agent whose brief names the material\'s source IS the study → passes', not denied(o), o)
    o = tool(proj, 'sG', 'Agent', description='Build the retopo', subagent_type='general-purpose', prompt='Make the retopology now.')
    check('A24 an agent sent to WORK before the study → refused once', 'M-0005' in denied(o), o)
    o = bash(proj, 'sOther', 'python x.py', 'run')
    check('A25 another session is not gated by this session\'s material', not denied(o), o)
    hook(proj, 'prompt', {'prompt': 'Сначала изучи https://github.com/k/KRepo', 'session_id': 'sK'})
    o = bash(proj, 'sK', 'python -X utf8 tools/promises_check.py --set P-001 next="python tools/run.py"', 'Park the item in the registry')
    o2 = bash(proj, 'sK', 'Get-Content tools/run.ps1 -TotalCount 20', 'Read the runner')
    o3 = bash(proj, 'sK', 'python tools/run.py', 'Run it')
    check('A26 the registry (act.bookkeeping) and reading a .ps1 are no work → pass; the first real run is refused (10.11: a false refusal)',
          not denied(o) and not denied(o2) and 'M-0006' in denied(o3), [o, o2, o3])

    # ---------------------------------------------------------------- B: recall by the action (hot rules only) — a switch, off by default
    o = bash(proj, 'sB0', 'python F:/work/retopo/render_wire.py --view front', 'Render the face wire from the front view')
    check('B0 recall by the action is OFF by default → silent', 'Never one view' not in ctx(o), ctx(o))
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['modules'].update({'act_recall': True, 'heartbeat': True})
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    o = bash(proj, 'sB', 'python F:/work/retopo/render_wire.py --view front', 'Render the face wire from the front view')
    check('B1 «Render the face wire from the front view» → the hot rule\'s DO: «Never one view …»',
          'Never one view' in ctx(o) and 'горячее правило' in ctx(o), ctx(o))
    o = bash(proj, 'sB', 'python F:/work/retopo/render_wire.py --view side', 'Render the face wire from the side view')
    check('B2 the same rule again within 30 min → not repeated', 'Never one view' not in ctx(o), ctx(o))
    quiet = [('ls -la', 'List files in directory'), ('git status', 'Show working tree status'),
             ('pip install -r requirements.txt', 'Install package dependencies'), ('cat README.md', 'Read the readme'),
             ('python -m http.server 8000', 'Start the dev server'), ('node tools/uishot.mjs --js=a.js', 'Take a screenshot of the page'),
             ('npm test', 'Run the test suite'), ('python tools/export.py --out x.glb', 'Export the scene to GLB')]
    loud = [(c, d, ctx(bash(proj, 'sB', c, d))) for c, d in quiet]
    check('B3 ordinary commands → silent (ls, git status, pip install, cat, a server, a screenshot, npm test, an export)',
          not any(x for _, _, x in loud), [(d, x) for _, d, x in loud if x])
    o = tool(proj, 'sB2', 'Write', file_path=os.path.join(proj, 'tools', 'views_sheet.py'),
             content='# one camera: render the front view of the model for the check\ncam = front()\nrender(cam)\n')
    check('B4 writing a CHECKING tool (views_sheet.py, one camera) → the one-view rule', 'Never one view' in ctx(o), ctx(o))
    o = tool(proj, 'sB2', 'Edit', file_path=os.path.join(proj, 'server', 'server.py'), old_string='a', new_string='render front view model')
    check('B5 an edit of an ordinary file (server.py) → silent, whatever its text', not ctx(o), ctx(o))
    o = tool(proj, 'sB3', 'Agent', description='Judge the model views', subagent_type='critic',
             prompt='Check the render of the model from the front view and judge it.')
    check('B6 an agent\'s brief about judging a render → the rule for the parent (who writes the brief)', 'Never one view' in ctx(o), ctx(o))
    o = bash(proj, 'sB4', 'python tools/count_cues.py --since 2026-10-26', 'Count producer messages and flagged corrections since cutover')
    check('B7 a rule\'s HISTORY words (CORRECTION, the producer, messages) never call it — measured noise of a real day', not ctx(o), ctx(o))
    o = bash(proj, 'sB5', 'python tools/studio.py --after compaction', 'Reopen the studio after the compaction')
    check('B8 its SITUATION words do (the studio, after a compaction)', 'Read the registry' in ctx(o), ctx(o))
    o = bash(proj, 'sB9', 'node tools/capture.mjs --url http://localhost:8000', 'Take a screenshot of the web page to study it')
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['act']['guard_marks'] = r'(?!)'
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    o2 = bash(proj, 'sB9b', 'node tools/capture.mjs --url http://localhost:8000', 'Take a screenshot of the web page to study it')
    del cfg['act']['guard_marks']
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    check('B9 a rule with a guard of its own (a hook that denies) → silent; the same rule without the guard mark → shown',
          'pane shot' not in ctx(o) and 'pane shot' in ctx(o2), [ctx(o), ctx(o2)])
    o = bash(proj, 'sB10', 'python tools/look_views.py --mesh granny.glb', 'Render the model views for the check')
    check('B10 the action already runs the tool the rule names (look_views.py) → silent (Fable 11.11: 17 of 60 notes)',
          'Never one view' not in ctx(o), ctx(o))
    o = bash(proj, 'sB11', 'python tools/free_mem.py --all', 'Free the nvidia vram, cuda out of memory')
    check('B11 a hot row without Keys borrows the Keys of the same row in a card (видеокарта, nvidia, vram …) → the GPU rule',
          'One GPU job at a time' in ctx(o), ctx(o))
    cfg['act']['recall_min_score'] = 1000
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    o = bash(proj, 'sB12', 'python F:/work/retopo/render_wire.py --view front', 'Render the face wire from the front view')
    check('B12 below recall_min_score → silent (the bar of the council: 10.11 had none, 5.3 notes per 100 calls)',
          'Never one view' not in ctx(o), ctx(o))
    del cfg['act']['recall_min_score']
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))

    # ---------------------------------------------------------------- ♥: the heartbeat — a switch, off by default
    def age(kind, sid, minutes):
        rows = act_rows(proj)
        for r in rows:
            if r.get('session') == sid and r.get('kind') == kind:
                r['ts'] = (dt.datetime.now() - dt.timedelta(minutes=minutes)).isoformat(timespec='seconds')
        set_act_rows(proj, rows)

    def beat(o):
        return 'горячие правила' in ctx(o)

    work = lambda sid, n=0: bash(proj, sid, f'python tools/batch.py --n {n}', 'Process the next batch', transcript=tr)   # noqa: E731
    tr = transcript(os.path.join(base, 'tr_beat.jsonl'), [('tool', 'Bash', {'command': f'python render_{i}.py', 'description':
                                                                             'Render the model view for the check'}, 30 - i) for i in range(10)])
    o = work('sH')
    check('H1 the first call of a session → the heartbeat clock starts silently', not beat(o)
          and any(r.get('kind') == 'beat' and r.get('session') == 'sH' for r in act_rows(proj)), ctx(o))
    o = work('sH', 1)
    check('H2 a call 0 minutes later → no beat', not beat(o), ctx(o))
    age('beat', 'sH', 50)
    o = bash(proj, 'sH', 'ls -la', 'List files', transcript=tr)
    check('H3 a beat is due, but the call only READS (ls) → no beat (10.11: 14 of 42 beats on reading / the plan)', not beat(o), ctx(o))
    hook(proj, 'prompt', {'prompt': 'Продолжай работу над рендерами, пожалуйста', 'session_id': 'sH'})
    o = work('sH', 2)
    check('H4 50 minutes of work, but the owner spoke a minute ago → no beat (only when he is silent ≥ 30 min)', not beat(o), ctx(o))
    op = os.path.join(proj, '.foreman', 'owner.jsonl')
    own = [json.loads(l) for l in io.open(op, encoding='utf-8') if l.strip()]
    for r in own:
        if r.get('session_id') == 'sH':
            r['ts'] = (dt.datetime.now() - dt.timedelta(minutes=35)).isoformat(timespec='seconds')
    io.open(op, 'w', encoding='utf-8', newline='\n').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in own))
    o = work('sH', 3)
    check('H5 the owner silent 35 min, 50 min since the last beat, a working call → the hot rules nearest to the last actions',
          beat(o) and 'Never one view' in ctx(o) and len(ctx(o)) <= 1100, ctx(o))
    o = work('sH', 4)
    check('H6 the next call → no beat again', not beat(o), ctx(o))
    hook(proj, 'session', {'source': 'compact', 'session_id': 'sH'})
    o = bash(proj, 'sH', 'cat notes.md', 'Read the notes', transcript=tr)
    o2 = work('sH', 5)
    check('H7 right after a compaction → the first WORKING call beats at once (a reading one does not)', not beat(o) and beat(o2), [ctx(o), ctx(o2)])
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['act']['beat_rules'] = 1
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    tr = transcript(os.path.join(base, 'tr_beat2.jsonl'),
                    [('tool', 'Bash', {'command': f'python job_{i}.py', 'description': d}, 30 - i)
                     for i, d in enumerate(['Render the model view for the check', 'A big GPU render, generation while another job may run'] * 4)])
    work('sH2')
    shown = []
    for k in range(3):
        age('beat', 'sH2', 50)
        o = work('sH2', k + 1)
        shown.append(re.findall(r'\[([^\]]+)\]\s*$', ctx(o), re.M))
    check('H8 rotation: one rule per beat, the least shown first — three beats show more than one rule (10.11: 72 % were 3 rows)',
          all(shown) and len({tuple(s) for s in shown}) >= 2, shown)
    today = dt.date.today().isoformat()
    cfg['act']['beat_day_max'] = sum(1 for r in act_rows(proj) if r.get('kind') == 'beat' and r.get('rules') and r.get('ts', '')[:10] == today)
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    work('sH3')
    age('beat', 'sH3', 50)
    o = work('sH3', 1)
    check('H9 the day\'s cap reached (beat_day_max) → no beat in any session', not beat(o), ctx(o))
    del cfg['act']['beat_rules'], cfg['act']['beat_day_max']
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))

    # ---------------------------------------------------------------- C: variants of the same script
    write(proj, 'work/bands_to_groups.py', 'print(1)\n')
    outs = [bash(proj, 'sC', f'python work/bands_to_groups.py --mesh granny.glb --thr 0.{i}', f'Colour bands to polygroups, try {i}')
            for i in range(1, 8)]
    warn = [n + 1 for n, o in enumerate(outs) if 'вариант' in ctx(o)]
    check('C1 seven variants of bands_to_groups.py (other thresholds) in minutes → a warning on the 3rd only, no refusal by default',
          warn == [3] and not any(denied(o) for o in outs), [warn, [ctx(o)[:80] for o in outs]])
    outs = [bash(proj, 'sC2', 'python work/bands_to_groups.py --thr 0.5', 'Colour bands') for _ in range(4)]
    check('C2 the SAME command four times → one attempt, no warning', not any('вариант' in ctx(o) for o in outs), [ctx(o) for o in outs])
    outs = [bash(proj, 'sC3', 'pytest -q tests/test_bands.py', f'Run tests {i}') for i in range(7)] + \
           [bash(proj, 'sC3', f'python tests/test_bands.py --case {i}', 'Run a test') for i in range(5)]
    check('C3 test runs (pytest ×7, tests/… ×5) → never counted', not any('вариант' in ctx(o) or denied(o) for o in outs))
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['act']['attempts_deny'] = True
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    outs = [bash(proj, 'sC4', f'python work/bands_to_groups.py --thr 0.{i}', 'Colour bands') for i in range(1, 7)]
    den = [n + 1 for n, o in enumerate(outs) if denied(o)]
    check('C4 with attempts_deny: the 5th variant refused ONCE (the 6th passes), the reason names the exits',
          den == [5] and 'OPTIONS.md' in denied(outs[4]) and 'attempts think' in denied(outs[4]), [den, denied(outs[4])])
    write(proj, 'work/OPTIONS.md', '# options\n1. clicks +/−\n2. hide parts\n3. guides from the reference\n')
    outs = [bash(proj, 'sC5', f'python work/bands_to_groups.py --thr 0.{i}', 'Colour bands') for i in range(1, 7)]
    check('C5 an OPTIONS.md next to the work, newer than the first variant → no refusal', not any(denied(o) for o in outs), [denied(o) for o in outs])
    os.remove(os.path.join(proj, 'work', 'OPTIONS.md'))
    outs = [bash(proj, 'sC6', f'python work/bands_to_groups.py --thr 0.{i}', 'Colour bands') for i in range(1, 3)]
    o = bash(proj, 'sC6', 'python work/bands_to_groups.py --thr 0.9  # options: hide the other parts first, then clicks', 'Colour bands')
    outs = [bash(proj, 'sC6', f'python work/bands_to_groups.py --thr 0.{i}{i}', 'Colour bands') for i in range(1, 5)]
    check('C6 «# options: …» in the command → the count starts again (no warning at the 3rd run in all)',
          not ctx(o) and [n for n, x in enumerate(outs) if 'вариант' in ctx(x)] == [1], [ctx(x)[:60] for x in outs])
    code, out = fm(proj, 'attempts', 'think', 'bands_to_groups.py', '--options', 'коротко')
    check('C7 attempts think without real options → refused', code == 1, out)
    code, out = fm(proj, 'attempts', 'think', 'bands_to_groups.py', '--options', 'клики +/−; скрыть части; направляющие по референсу')
    o = bash(proj, 'sC6', 'python work/bands_to_groups.py --thr 0.77', 'Colour bands')
    check('C8 attempts think with options → recorded, the count starts again', code == 0 and not denied(o) and 'вариант' not in ctx(o), [out, o])
    cfg['act']['attempts_deny'] = False
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    outs = [bash(proj, 'sC7', f'powershell -ExecutionPolicy Bypass -File tools/gpu_guard.ps1 -Run "python work/bands_to_groups.py --thr 0.{i}" '
                               f'-Name b{i}', 'Colour bands under the GPU guard') for i in range(1, 4)]
    check('C9 three variants run through the wrapper (gpu_guard.ps1 -Run "python …") → the warning names the REAL script',
          'bands_to_groups.py' in ctx(outs[2]) and 'gpu_guard' not in ctx(outs[2]) and not any('вариант' in ctx(o) for o in outs[:2]),
          [ctx(o)[:90] for o in outs])
    outs = [bash(proj, 'sC8', f'powershell -File tools/gpu_guard.ps1 -NeedGB {i}', 'Check the GPU') for i in range(10, 15)]
    check('C10 the wrapper\'s own checks (no job inside) → never an attempt', not any('вариант' in ctx(o) for o in outs), [ctx(o) for o in outs])
    outs = [bash(proj, 'sC9', f'python -X utf8 tools/promises_check.py --set P-00{i} next="python work/bands_to_groups.py --thr 0.{i}"',
                 'Update the registry') for i in range(1, 6)]
    check('C11 the registry (act.bookkeeping) five times with other arguments → never an attempt, whatever its text names',
          not any('вариант' in ctx(o) for o in outs) and not any(r.get('session') == 'sC9' and r.get('kind') == 'run' for r in act_rows(proj)),
          [ctx(o) for o in outs])
    bash(proj, 'sC10', 'Get-Content work/notes.py | python work/bands_to_groups.py --thr 0.1', 'Feed the notes')
    runs_ = [r for r in act_rows(proj) if r.get('session') == 'sC10' and r.get('kind') == 'run']
    check('C12 the script AFTER the interpreter, not the first file named («Get-Content a.py | python b.py» → b.py)',
          [r.get('sig') for r in runs_] == ['bands_to_groups.py'], runs_)
    # (rc1's replay of 09.11: 13 warnings, 5 real loops — a «variant» on ANOTHER input, a looking tool, a dry run, a script named in a
    #  variable were counted)
    outs = [bash(proj, 'sC11', f'python work/bands_to_groups.py --mesh head_v{i}.glb --out res/v{i} --thr 0.5', 'Colour bands on the next mesh')
            for i in range(1, 6)]
    check('C13 the same script on five DIFFERENT inputs (the output folders differ too) → other jobs, no warning',
          not any('вариант' in ctx(o) for o in outs), [ctx(o)[:80] for o in outs])
    outs = [bash(proj, 'sC12', f'python work/bands_to_groups.py --out res/v{i} --mesh head.glb --thr 0.{i}', 'Colour bands') for i in range(1, 4)]
    check('C14 the SAME input with other parameters (an output option before it is skipped) → the warning on the 3rd',
          'вариант 3' in ctx(outs[2]) and not any('вариант' in ctx(o) for o in outs[:2]), [ctx(o)[:80] for o in outs])
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['act']['look_tools'] = [r'^measure_', r'^compare_page\.py$']
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    outs = [bash(proj, 'sC13', f'python tools/measure_round3.py --mesh head.glb --cut {i}', 'Measure the result') for i in range(1, 6)]
    check('C15 a looking tool of the project (act.look_tools: measure_*) five times on one input → never an attempt',
          not any('вариант' in ctx(o) for o in outs), [ctx(o)[:80] for o in outs])
    outs = [bash(proj, 'sC14', c, 'Delete the old engine') for c in
            ('powershell -File work/delete_old.ps1 -Target M:/old -DryRun', 'powershell -File work/delete_old.ps1 -Target M:/old',
             'powershell -File work/delete_old.ps1 -Target M:/old -Keep logs -DryRun', 'powershell -File work/delete_old.ps1 -Target M:/old -Keep logs')]
    check('C16 a dry run and the same run for real are one variant (four runs = two variants → no warning)',
          not any('вариант' in ctx(o) for o in outs), [ctx(o)[:80] for o in outs])
    write(proj, 'tools/lab_env_run.cmd', '@echo off\r\nset UV_CACHE_DIR=M:\\uv\r\n%*\r\n')
    outs = [bash(proj, 'sC16', c, 'Through the lab environment') for c in
            ('tools\\lab_env_run.cmd .venv\\Scripts\\python.exe -m uv pip install pytest',
             'tools\\lab_env_run.cmd .venv\\Scripts\\python.exe -m pytest -q', 'tools\\lab_env_run.cmd .venv\\Scripts\\python.exe work/bootstrap.py',
             'tools\\lab_env_run.cmd .venv\\Scripts\\python.exe work/bootstrap.py --force')]
    sigs = [r.get('sig') for r in act_rows(proj) if r.get('session') == 'sC16' and r.get('kind') == 'run']
    check('C18 an environment launcher («lab_env_run.cmd .venv\\Scripts\\python.exe …», 11.11) → unwrapped: three different commands are '
          'no variants of the .cmd; the script run is the signature', not any('вариант' in ctx(o) for o in outs)
          and sigs and set(sigs) == {'bootstrap.py'}, [sigs, [ctx(o)[:60] for o in outs]])
    write(proj, 'work/run_authors.cmd', '@echo off\r\necho %*\r\n')
    outs = [bash(proj, 'sC17', f'work\\run_authors.cmd {objs}', 'The authors\' demo') for objs in ('fox gnome', 'warrior', 'ram hummingbird shoe_house')]
    write(proj, 'work/bench.py', 'print(1)\n')
    outs += [bash(proj, 'sC18', 'python work/bench.py smoke --seed 1', 'Smoke'), bash(proj, 'sC18', 'python work/bench.py smoke --seed 1 --fix', 'Smoke again'),
             bash(proj, 'sC18', 'python work/bench.py matrix audrey', 'The matrix')]
    outs2 = [bash(proj, 'sC19', f'python work/bench.py smoke --seed {i}', 'Smoke') for i in range(1, 4)]
    check('C19 inputs named by bare words (objects, modes: «run_authors.cmd fox gnome» / «warrior» / «ram …»; «bench.py smoke» → «matrix '
          'audrey») are other jobs → no warning; the same positional input with other options → the warning on the 3rd (11.11)',
          not any('вариант' in ctx(o) for o in outs) and 'вариант 3' in ctx(outs2[2]), [[ctx(o)[:50] for o in outs], ctx(outs2[2])[:60]])
    write(proj, 'work/parts_to_obj.py', 'print(1)\n')
    write(proj, 'work/p3click.py', 'print(1)\n')
    outs = [bash(proj, 'sC20', f'python work/parts_to_obj.py --ids 1,2 --target parts/{t} --out o/{t} --clean 1 2>&1 | tail -5', 'Parts to OBJ')
            for t in ('a', 'b', 'c')]
    outs2 = [bash(proj, 'sC21', f'python work/p3click.py {sub} glasses p3click/glasses_clicks.json {opt}', 'Clicks')
             for sub, opt in (('prep', ''), ('eval', '--probes 3'), ('vote', '--min-piece 2'))]
    check('C20 a redirection «2>&1» is no input (three --target runs = three jobs); sub-commands before a PATH (prep / eval / vote … '
          'clicks.json) are one loop → its 3rd run warned (the 09.11 replay of 2.6.1 rc)',
          not any('вариант' in ctx(o) for o in outs) and 'вариант 3' in ctx(outs2[2]), [[ctx(o)[:40] for o in outs], ctx(outs2[2])[:60]])
    outs = [bash(proj, 'sC15', f'F=work/bands_to_groups.py; sed -n {i},40p $F', 'Read the script') for i in range(1, 5)]
    check('C17 a script named in a variable and read («F=x.py; sed -n … $F») → no run, no attempt',
          not any(r.get('session') == 'sC15' and r.get('kind') == 'run' for r in act_rows(proj)), [ctx(o)[:80] for o in outs])

    # ---------------------------------------------------------------- D: an engine's notes before its first use
    tr0 = transcript(os.path.join(base, 'tr_empty.jsonl'), [('user', 'Делай', 5)])
    o = bash(proj, 'sD', 'python F:/engines/p3sam_run.py --mesh granny.glb --auto', 'Segment the granny with P3-SAM', transcript=tr0)
    check('D1 the first P3-SAM run of a session, its study not read → the «Режимы» section in front of Claude (no refusal by default)',
          not denied(o) and 'P3-SAM' in ctx(o) and 'щелчки' in ctx(o) and 'X-Part' in ctx(o), ctx(o))
    o = bash(proj, 'sD', 'python F:/engines/p3sam_run.py --mesh granny.glb --auto', 'Segment again', transcript=tr0)
    check('D2 the second run → silent', 'щелчки' not in ctx(o), ctx(o))
    trR = transcript(os.path.join(base, 'tr_read.jsonl'), [('tool', 'Read', {'file_path': os.path.join(proj, 'docs', 'P3SAM_STUDY.md')}, 3)])
    o = bash(proj, 'sD2', 'python p3sam_run.py --mesh a.glb', 'Segment with P3-SAM', transcript=trR)
    check('D3 the study read in this session → silent', 'щелчки' not in ctx(o), ctx(o))
    trC = transcript(os.path.join(base, 'tr_compact.jsonl'), [('tool', 'Read', {'file_path': os.path.join(proj, 'docs', 'P3SAM_STUDY.md')}, 9),
                                                             ('compact',)])
    o = bash(proj, 'sD3', 'python p3sam_run.py --mesh a.glb', 'Segment with P3-SAM', transcript=trC)
    check('D4 read BEFORE a compaction → counts as not read (the section is shown)', 'щелчки' in ctx(o), ctx(o))
    cfg['engines'][0]['deny_first'] = True
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    o = bash(proj, 'sD4', 'python p3sam_run.py --mesh a.glb', 'Segment with P3-SAM', transcript=tr0)
    o2 = bash(proj, 'sD4', 'python p3sam_run.py --mesh a.glb', 'Segment with P3-SAM', transcript=tr0)
    check('D5 deny_first → refused once with the section and the exits, then passes',
          'щелчки' in denied(o) and 'engine ack' in denied(o) and not denied(o2), [o, o2])
    code, out = fm(proj, 'engine', 'ack', 'P3-SAM')
    check('D6 engine ack without --modes → refused', code == 1, out)
    code, out = fm(proj, 'engine', 'ack', 'P3-SAM', '--modes', 'авто; щелчки +/−; X-Part для скрытого')
    o = bash(proj, 'sD5', 'python p3sam_run.py --mesh a.glb', 'Segment with P3-SAM', transcript=tr0)
    check('D7 engine ack with the modes → a new session passes silently', code == 0 and not denied(o) and 'щелчки' not in ctx(o), [out, o])
    o = bash(proj, 'sD6', 'python p3sam_run.py --mesh a.glb  # engine-read: читал разбор утром, режим щелчков', 'Segment', transcript=tr0)
    check('D8 «# engine-read: …» in the command → passes', not denied(o), o)
    o = bash(proj, 'sD7', 'python -c "open(\'LEDGER.md\', \'a\').write(\'урок: P3-SAM резал очки авто-режимом\')"', 'Record the case lesson',
             transcript=tr0)
    check('D9 a command that only MENTIONS the engine in its text (a ledger line) → no engine gate (measured on a real day)',
          not denied(o) and 'щелчки' not in ctx(o), o)
    write(proj, 'docs/MESHCLOSE_AUTHORS.md', '# MeshClose — authors\' run\n\n## Ключи\n--quad / --tris / --tier\n')
    write(proj, 'docs/OPTIMIZERS.md', '# Optimizers\n\n| Node | Mode |\n|---|---|\n| Quad Reconstruct | ON, 8 M input |\n')
    write(proj, 'docs/ENGINES_CARD.md', '# Engines\n\n| When | Do |\n|---|---|\n| [P7] Image → 3D | Pixal3D = 2.5D relief on a room; TRELLIS.2 for characters |\n')
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    cfg['engines'] += [{'name': 'MeshClose', 'match': r'meshclose', 'doc': ['docs/MESHCLOSE_AUTHORS.md', 'docs/OPTIMIZERS.md'],
                        'section': 'Quad Reconstruct'},
                       {'name': 'Pixal3D', 'match': r'pixal3d|run_geometry', 'doc': 'docs/ENGINES_CARD.md', 'section': 'Image → 3D'}]
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    trM = transcript(os.path.join(base, 'tr_mc.jsonl'), [('tool', 'Read', {'file_path': os.path.join(proj, 'docs', 'MESHCLOSE_AUTHORS.md')}, 2)])
    o = bash(proj, 'sD8', 'python engines/MeshClose/meshclose.py --quad --tier 2 in.glb', 'Close the mesh', transcript=trM)
    check('D10 an engine with TWO docs, one read → the note names the unread one and shows the section from the doc that HAS it',
          'OPTIMIZERS.md' in ctx(o) and 'MESHCLOSE_AUTHORS.md' not in ctx(o) and '8 M input' in ctx(o), ctx(o))
    trM2 = transcript(os.path.join(base, 'tr_mc2.jsonl'), [('tool', 'Read', {'file_path': os.path.join(proj, 'docs', d)}, 2)
                                                          for d in ('MESHCLOSE_AUTHORS.md', 'OPTIMIZERS.md')])
    o = bash(proj, 'sD9', 'python engines/MeshClose/meshclose.py --quad in.glb', 'Close the mesh', transcript=trM2)
    check('D11 both docs read → silent', 'MeshClose' not in ctx(o), ctx(o))
    o = bash(proj, 'sD10', 'python engines/Pixal3D/run_geometry.py --image room.png', 'Room relief', transcript=tr0)
    check('D12 a «section» that is a card\'s table row → that row in front of Claude', 'Pixal3D = 2.5D relief' in ctx(o), ctx(o))
    # (P3-SAM was acked above for 12 hours — the run-only checks get an engine of their own, never acked, with deny_first: under
    #  2.5's matching each of D13–D15 was a refusal)
    cfg['engines'][0]['deny_first'] = False
    cfg['engines'].append({'name': 'SegEng', 'match': r'seg.?eng', 'doc': 'docs/P3SAM_STUDY.md', 'section': 'Режимы', 'deny_first': True})
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    o = bash(proj, 'sD11', 'python tools/measure.py --path F:/engines/SegEng/segeng_run.py', 'Measure the size of the SegEng folder',
             transcript=tr0)
    check('D13 the engine only in an ARGUMENT and in the description → no engine gate (10.11: «Measure … Hunyuan folder», a false refusal)',
          'щелчки' not in ctx(o) + denied(o), o)
    o = bash(proj, 'sD12', 'Get-Content F:/engines/SegEng/segeng_run.py -TotalCount 40', 'Read the SegEng runner', transcript=tr0)
    check('D14 READING the engine\'s script → no engine gate', 'щелчки' not in ctx(o) + denied(o), o)
    o = bash(proj, 'sD13', 'python -X utf8 tools/promises_check.py --set P-181 probes="file:F:/engines/SegEng/segeng_run.py"',
             'Fix P-181 probes', transcript=tr0)
    check('D15 the registry naming the engine\'s script in a probe → no engine gate (10.11: a false refusal)', 'щелчки' not in ctx(o) + denied(o), o)
    o = bash(proj, 'sD16', "mkdir -p work/r && cat > work/r/run.sh <<'EOF'\ncd /work/SegEng\npython demo/auto_mask.py --x\nEOF",
             'Write the SegEng run script', transcript=tr0)
    o2 = bash(proj, 'sD17', 'python - <<EOF\nimport json\njson.dump({"run": "F:/engines/SegEng/segeng_run.py"}, open("q.json", "w"))\nEOF',
              'Write the request files for the queue', transcript=tr0)
    check('D18 a heredoc that WRITES a script / a JSON naming the engine → no engine gate (rc1\'s replay: 3 of 4 engine notes)',
          'щелчки' not in ctx(o) + denied(o) + ctx(o2) + denied(o2), [o, o2])
    o = bash(proj, 'sD14', 'powershell -File tools/gpu_guard.ps1 -Run "python F:/engines/SegEng/segeng_run.py --auto" -Name s',
             'Segment under the guard', transcript=tr0)
    check('D16 the engine RUN through gpu_guard -Run → the gate (deny_first here)', 'щелчки' in denied(o), o)
    o = bash(proj, 'sD15', 'wsl -d U -- bash -lc "cd /work/SegEng && /venvs/seg/bin/python demo/auto_mask.py --x"', 'Segment in WSL',
             transcript=tr0)
    check('D17 «bash -lc "cd <engine folder> && python demo/x.py"» → the gate (the folder of a relative script counts)', 'щелчки' in denied(o), o)
    cfg['engines'].pop()
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))

    # ---------------------------------------------------------------- E: the advisor's events (2.6, the council of 11.11)
    reg = os.path.join(proj, 'reg', 'PROMISES.jsonl')
    regrows = lambda rows: write(proj, 'reg/PROMISES.jsonl', ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))   # noqa: E731
    regrows([{'id': 'P-1', 'title': 'Формат хранения версий', 'status': 'в работе', 'costly': 'формат данных — дорого переделывать'},
             {'id': 'P-2', 'title': 'Кнопка экспорта', 'status': 'в работе'},
             {'id': 'P-3', 'title': 'Новый движок', 'status': 'не начато', 'costly': 'архитектура'}])
    write(proj, 'rules/HISTORY.md', '# History\n\n| When | Do | Where |\n|---|---|---|\n'
          '| [P2] Оценка модели по одному виду (judging a model from ONE view) — failed AGAIN 05.11 and AGAIN 09.11 | Смотреть со всех '
          'сторон. | `cards/views.md` |\n| [P4] Цвет подбирать пипеткой (picking colours) | Пипетка, не на глаз. | `cards/refs.md` |\n')
    cfg = json.load(io.open(cfgp, encoding='utf-8'))
    o = bash(proj, 'sE0', 'ls -la', 'List files')
    o0 = hook(proj, 'prompt', {'prompt': 'Опять оценила модель по одному виду. Сколько можно!', 'session_id': 'sE0'})
    check('E0 the advisor is OFF by default → no event notes', 'повод' not in ctx(o) + ctx(o0), [ctx(o), ctx(o0)])
    cfg['modules']['advisor'] = True
    cfg['advisor'] = {**cfg.get('advisor', {}), 'registries': ['reg/PROMISES.jsonl']}
    cfg['lessons']['rules_extra'] = ['rules/HISTORY.md']
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))
    o = bash(proj, 'sE', 'ls -la', 'List files')
    check('E1 a registry item marked «costly» and IN WORK → one note (event 3); not the unmarked one, not the marked one not started',
          'повод 3' in ctx(o) and 'P-1' in ctx(o) and 'P-2' not in ctx(o) and 'P-3' not in ctx(o) and 'Вызовов сегодня 0/3' in ctx(o), ctx(o))
    o = bash(proj, 'sE', 'git status', 'Show status')
    check('E2 … once per item and session', 'повод 3' not in ctx(o), ctx(o))
    regrows([{'id': 'P-1', 'title': 'Формат хранения версий', 'status': 'в работе', 'costly': 'формат данных'},
             {'id': 'P-3', 'title': 'Новый движок', 'status': 'в работе', 'costly': 'архитектура'}])
    os.utime(reg, (time.time() + 5, time.time() + 5))
    o = bash(proj, 'sE', 'git status', 'Show status')
    check('E3 the registry changed: the newly started marked item → its note; the old one not again', 'P-3' in ctx(o) and 'P-1' not in ctx(o), ctx(o))
    write(proj, 'work/sweep.py', 'print(1)\n')
    outs = [bash(proj, 'sE2', f'python work/sweep.py --mesh a.glb --thr 0.{i}', 'Sweep') for i in range(1, 4)]
    check('E4 event 2 rides on the attempt warning (the 3rd variant): the advisor\'s line with the brief\'s frame',
          'вариант 3' in ctx(outs[2]) and 'повод 2' in ctx(outs[2]) and '700 слов' in ctx(outs[2]), ctx(outs[2]))
    brief = 'Цель: выбрать формат. Файл результата: `out/adv.md`'
    calls = [tool(proj, 'sE3', 'Agent', description=f'Advisor {i}', subagent_type='general-purpose', model='fable', prompt=brief)
             for i in range(4)]
    check('E5 the advisor\'s calls are counted: calls 1–3 silent, the 4th → «потолок» (a note, never a refusal)',
          not any('потолк' in ctx(c) for c in calls[:3]) and 'потолк' in ctx(calls[3]) and not any(denied(c) for c in calls), [ctx(c) for c in calls])
    o = tool(proj, 'sE4', 'Agent', description='Advisor long', subagent_type='general-purpose', model='fable', prompt='слово ' * 800)
    o2 = tool(proj, 'sE4', 'Agent', description='A reader', subagent_type='Explore', model='haiku', prompt='слово ' * 800)
    check('E6 a brief over 700 words to the advisor → «сократите»; another model\'s agent → not counted, silent',
          'сократите' in ctx(o) and 'сократите' not in ctx(o2), [ctx(o), ctx(o2)])
    o = hook(proj, 'tool', {'session_id': 'sE5', 'agent_id': 'ag7', 'agent_type': 'general-purpose', 'tool_name': 'Agent',
                            'tool_input': {'model': 'fable', 'prompt': 'слово ' * 800, 'description': 'nested'}, 'cwd': proj})
    check('E7 inside a subagent → no advisor notes (no advisor calling an advisor)', 'сократите' not in ctx(o) and 'повод' not in ctx(o), ctx(o))
    o = hook(proj, 'prompt', {'prompt': 'Опять оценила модель по одному виду. Сколько можно!', 'session_id': 'sE6'})
    check('E8 a correction matching a rule that failed AGAIN … AGAIN (≥ 2 times) → event 5: the advisor on why the guard did not hold',
          'повод 5' in ctx(o) and 'одному виду' in ctx(o), ctx(o))
    o = hook(proj, 'prompt', {'prompt': 'Опять оценила модель по одному виду, ну сколько можно!', 'session_id': 'sE6'})
    o2 = hook(proj, 'prompt', {'prompt': 'Опять цвет подобрала на глаз, а не пипеткой!', 'session_id': 'sE6'})
    check('E9 … once per rule a day; a correction matching a rule with no history of repeats → no event 5',
          'повод 5' not in ctx(o) and 'повод 5' not in ctx(o2), [ctx(o), ctx(o2)])
    code, out = fm(proj, 'advisor')
    check('E10 `foreman.py advisor` — the journal: the events by kind and the calls', code == 0 and 'вызовов' in out and '3:' in out and '5:' in out, out)
    cfg['modules']['advisor'] = False
    cfg['lessons']['rules_extra'] = []
    io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))

    # ---------------------------------------------------------------- K: the subagent contract per session (2.5.1)
    # (11.11: an Explore agent of ANOTHER session stopped without its output file; this session's Stop was told and marked it seen,
    #  so the real parent never heard it)
    evp = os.path.join(proj, '.foreman', 'events.jsonl')
    trA = transcript(os.path.join(base, 'agent_A.jsonl'), [('user', 'Найди камеры.\n\nФайл результата: `out/cams_A.md`', 1)])
    o = hook(proj, 'subagent', {'session_id': 'sessA', 'agent_type': 'Explore', 'agent_id': 'agA', 'agent_transcript_path': trA, 'cwd': proj})
    o2 = hook(proj, 'stop', {'session_id': 'sessB', 'transcript_path': '', 'last_assistant_message': 'готово'})
    o3 = hook(proj, 'agent-done', {'session_id': 'sessB', 'tool_name': 'Agent', 'tool_input': {}})
    check('K1 a read-only agent of session A stops without its file → session B is NOT told (Stop, PostToolUse)',
          not o and 'cams_A' not in str(o2.get('reason', '')) and 'cams_A' not in ctx(o3), [o, o2, o3])
    o = hook(proj, 'agent-done', {'session_id': 'sessA', 'tool_name': 'Agent', 'tool_input': {}})
    check('K2 … its own session A is told, with the read-only text (the result is in its answer, not «resume the agent»)',
          'cams_A' in ctx(o) and 'только читает' in ctx(o) and 'Продолжите того же агента' not in ctx(o), ctx(o))
    o = hook(proj, 'stop', {'session_id': 'sessA', 'transcript_path': '', 'last_assistant_message': 'готово'})
    check('K3 … once only', 'cams_A' not in str(o.get('reason', '')), o)
    ev = [json.loads(l) for l in io.open(evp, encoding='utf-8') if l.strip()]
    check('K4 the contract events carry the parent\'s session', any(e.get('kind') == 'agent_artifact_missing' and e.get('session') == 'sessA'
                                                                  for e in ev), ev[-3:])
    o = tool(proj, 'sessC', 'Agent', description='Map the cameras', subagent_type='Explore',
             prompt='Найди, где задаются камеры.\n\nФайл результата: `out/cams_C.md`')
    o2 = tool(proj, 'sessC', 'Agent', description='Map the cameras', subagent_type='general-purpose',
              prompt='Найди, где задаются камеры.\n\nФайл результата: `out/cams_C.md`')
    check('K5 a brief with an output file to an agent that only reads → said BEFORE the run; to one that writes → silent',
          'только читает' in ctx(o) and 'cams_C' in ctx(o) and not denied(o) and 'только читает' not in ctx(o2), [ctx(o), ctx(o2)])
    # (2.6.2: readers on the expensive model — the council of 11.11; on 10.11 two readers ran on Opus by default)
    read_brief = 'Прочитай репозиторий M:/repos/lab и составь список его систем. Файл результата: `out/lab.md`'
    o = tool(proj, 'sR1', 'Agent', description='Read the lab repo', subagent_type='general-purpose', prompt=read_brief)
    check('K6 a READING brief to general-purpose with no model (inherit = the main session) → the note «sonnet / haiku», no refusal',
          'читатель' in ctx(o) and 'inherit' in ctx(o) and not denied(o), ctx(o))
    o = tool(proj, 'sR2', 'Agent', description='Read the lab repo', subagent_type='general-purpose', model='sonnet', prompt=read_brief)
    o2 = tool(proj, 'sR3', 'Agent', description='Map the code', subagent_type='Explore', prompt='Изучи, где задаются камеры.')
    o3 = tool(proj, 'sR4', 'Agent', description='Advisor', subagent_type='general-purpose', model='fable', prompt=read_brief)
    check('K7 the same on sonnet; Explore (a built-in on haiku); the advisor\'s model → silent', 'читатель' not in ctx(o) + ctx(o2) + ctx(o3),
          [ctx(o), ctx(o2), ctx(o3)])
    write(proj, '.claude/agents/critic.md', '---\nname: critic\nmodel: opus\n---\nThe critic.\n')
    o = tool(proj, 'sR5', 'Agent', description='Review the frame', subagent_type='critic', prompt='Изучи кадр и найди ошибки.')
    o2 = tool(proj, 'sR6', 'Agent', description='Build it', subagent_type='general-purpose', prompt='Сделай модуль экспорта и тесты.')
    check('K8 a crew agent on Opus by its definition (not a generic reader type); a working brief → silent',
          'читатель' not in ctx(o) + ctx(o2), [ctx(o), ctx(o2)])
    o = tool(proj, 'sR7', 'Agent', description='Read the logs', subagent_type='general-purpose', model='opus', prompt='Read the logs and summarize.')
    check('K9 an explicit model «opus» on a reading brief → the note names it', 'читатель' in ctx(o) and 'opus' in ctx(o), ctx(o))

    # ---------------------------------------------------------------- 2.4 still: the path rule through the new hook
    code, out = fm(proj, 'rule', 'add', json.dumps({'when': 'editing the far config', 'do': 'keep the comments', 'quote': 'не трогай комментарии',
                                                    'paths': [os.path.join(base, 'far', '*.ini').replace('\\', '/')]}, ensure_ascii=False))
    rid = re.search(r'R-\d+', out).group(0)
    hook(proj, 'prompt', {'prompt': f'{rid} принимаю — да', 'session_id': 'sR'})
    fm(proj, 'rule', 'accept', rid, '--quote', f'{rid} принимаю — да')
    o = tool(proj, 'sR', 'Edit', file_path=os.path.join(base, 'far', 'app.ini'), old_string='a', new_string='b')
    check('R1 a 2.4 rule with a path outside the project still shows through «hook tool»', 'keep the comments' in ctx(o), [out, ctx(o)])

    # ---------------------------------------------------------------- the quietness and the case, replayed
    calls = []
    for i in range(120):
        c, d = quiet[i % len(quiet)]
        calls.append(('tool', 'Bash', {'command': c, 'description': d}, 300 - i * 2))
        calls.append(('tool', 'Read', {'file_path': f'src/f{i}.py'}, 300 - i * 2))
    trQ = transcript(os.path.join(base, 'tr_quiet.jsonl'), [('user', 'Продолжай работу над экспортом', 301)] + calls)
    before = (len(act_rows(proj)), len(materials(proj)))
    code, out = fm(proj, 'replay', '--tools', trQ, '--json')
    js = json.loads(out.strip().splitlines()[-1])
    per100 = 100.0 * sum(js.get(k, 0) for k in ('recall', 'attempts', 'engine', 'materials')) / js['calls']
    check('Q1 a quiet modelled day (240 ordinary calls, no correction) → ≤ 1 note per 100 calls, 0 refusals',
          per100 <= 1 and not js.get('deny'), out)
    case = [('user', M_1228, 300)]
    case += [('tool', 'Bash', {'command': 'python retopo/qremesh_guides.py --mesh granny.glb', 'description': 'Build QRemesh guides'}, 290)]
    case += [('tool', 'Bash', {'command': 'python retopo/render_wire.py --view front', 'description': 'Render the face wire from the front view'}, 250)]
    case += [('tool', 'Bash', {'command': f'python retopo/p3sam_run.py --auto --thr 0.{i}', 'description': 'Segment the head with P3-SAM'}, 200 - i)
             for i in range(2)]
    case += [('tool', 'Bash', {'command': f'python retopo/bands_to_groups.py --thr 0.{i}', 'description': 'Colour bands to polygroups'}, 160 - i)
             for i in range(7)]
    trK = transcript(os.path.join(base, 'tr_case.jsonl'), case + calls[:40])
    code, out = fm(proj, 'replay', '--tools', trK, '--json')
    js = json.loads(out.strip().splitlines()[-1])
    caught = [k for k in ('materials', 'recall', 'attempts', 'engine') if js.get(k)]
    check('Q2 the case of 09.11, modelled → ≥ 3 of its 4 rows caught (materials, the one-view rule, the attempts, the engine)',
          len(caught) >= 3, out)
    print('     caught:', ', '.join(caught))
    check('Q3 the replays wrote nothing (act.jsonl and materials.jsonl unchanged)', (len(act_rows(proj)), len(materials(proj))) == before,
          [before, len(act_rows(proj)), len(materials(proj))])
    trZ = transcript(os.path.join(base, 'tr_compact_replay.jsonl'),
                     [('user', 'Продолжай рендеры', 60)] + [('tool', 'Bash', {'command': f'python render_{i}.py', 'description':
                                                                              'Render the model view for the check'}, 50 - i) for i in range(5)]
                     + [('compact',), ('tool', 'Bash', {'command': 'python render_9.py', 'description': 'Render the model view'}, 0)])
    code, out = fm(proj, 'replay', '--tools', trZ, '--json')
    js = json.loads(out.strip().splitlines()[-1])
    check('Q4 the replay sees a compaction → the heartbeat after it is counted; the totals line and the modules are printed',
          js.get('heartbeat', 0) >= 1 and 'ALL notes' in out and 'act_recall=on' in out, out)

    # ---------------------------------------------------------------- the time per call
    times = []
    for i in range(60):
        t0 = time.perf_counter()
        bash(proj, 'sT', 'ls -la', 'List files in directory')
        times.append(time.perf_counter() - t0)
    med = statistics.median(times)
    check(f'T1 the time per ordinary call: median {med:.3f} s ≤ 0.3 s', med <= 0.3, times[:5])
    times = []
    for i in range(20):
        t0 = time.perf_counter()
        bash(proj, f'sT{i}', 'python tools/x.py --view front', 'Render the face wire from the front view')
        times.append(time.perf_counter() - t0)
    med = statistics.median(times)
    check(f'T2 the time per call that searches the hot rules: median {med:.3f} s ≤ 0.4 s', med <= 0.4, times[:5])
finally:
    shutil.rmtree(base, ignore_errors=True)
print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
