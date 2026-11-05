"""test_v23.py — Foreman 2.3 checks (ideas from deepseek-harness, read 05.11): every line a hook shows Claude is logged («Model-visible
means logged», AGENTS.md) and `foreman.py hooklog` reads it back; an ordinary message logs nothing; `foreman.py replay` runs the owner's
recorded messages through the prompt hook's detectors WITHOUT side effects (no inbox row, no cue event) and reports what changed against
its saved snapshot («a recorded session serves as the expected result», docs/testing.md). Standard library only; throw-away projects.
  python tests/test_v23.py            exit 0 = all passed"""
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
    print(('ok   ' if ok else 'FAIL ') + name + (f' — {str(info)[:300]}' if info and not ok else ''))


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


def events(proj):
    p = os.path.join(proj, '.foreman', 'events.jsonl')
    return [json.loads(l) for l in io.open(p, encoding='utf-8') if l.strip()] if os.path.exists(p) else []


def lines(proj, name):
    p = os.path.join(proj, '.foreman', name)
    return [json.loads(l) for l in io.open(p, encoding='utf-8') if l.strip()] if os.path.exists(p) else []


base = tempfile.mkdtemp(prefix='foreman_v23_')
try:
    proj = os.path.join(base, 'proj')
    os.makedirs(proj)
    r = subprocess.run([PY, os.path.join(KIT, 'install.py'), proj, '--yes'], capture_output=True, encoding='utf-8')
    check('install', r.returncode == 0, r.stdout[-300:])

    # the hook journal
    before = len([e for e in events(proj) if e.get('kind') == 'hook_out'])
    o = hook(proj, 'prompt', {'prompt': 'посмотри, пожалуйста, как там дела с отчётом за неделю'})
    after = [e for e in events(proj) if e.get('kind') == 'hook_out']
    quiet = not (o.get('hookSpecificOutput') or {}).get('additionalContext')
    check('an ordinary message with no hook output logs nothing', quiet and len(after) == before, (o, len(after)))
    o = hook(proj, 'prompt', {'prompt': 'Добавь, пожалуйста, экспорт отчёта в PDF для бухгалтерии'})
    shown = (o.get('hookSpecificOutput') or {}).get('additionalContext', '')
    hk = [e for e in events(proj) if e.get('kind') == 'hook_out']
    check('an ask → the hook output is logged verbatim (hook «prompt», its chars, the message head)',
          shown and hk and hk[-1].get('hook') == 'prompt' and hk[-1].get('text') == shown and hk[-1].get('chars') == len(shown)
          and 'экспорт' in hk[-1].get('head', ''), (shown, hk[-1:] if hk else None))
    o = hook(proj, 'prompt', {'prompt': 'Опять ты забыл подписать картинки, я же просил'})
    hk = [e for e in events(proj) if e.get('kind') == 'hook_out']
    check('a correction → its lesson-protocol line is logged too', hk and 'забыл' in hk[-1].get('head', '') and hk[-1].get('text'), hk[-1:])
    o = hook(proj, 'stop', {'transcript_path': '', 'last_assistant_message': 'готово'})
    hk = [e for e in events(proj) if e.get('kind') == 'hook_out']
    check('a Stop block → logged as hook «stop» with the same reason', o.get('decision') == 'block' and hk[-1].get('hook') == 'stop'
          and hk[-1].get('text') == o.get('reason'), (o, hk[-1:]))
    code, out = fm(proj, 'hooklog', '--n', '2')
    check('`hooklog` prints the last outputs and the count', code == 0 and 'hook outputs logged' in out and 'stop' in out, out[-400:])
    code, out = fm(proj, 'hooklog', '--grep', 'экспорт')
    check('`hooklog --grep` finds an output by the message head', code == 0 and 'экспорт' in out, out[-300:])
    cfg_p = os.path.join(proj, '.foreman', 'config.json')
    cfg = json.load(io.open(cfg_p, encoding='utf-8'))
    cfg['hook_log'] = False
    json.dump(cfg, io.open(cfg_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n0 = len([e for e in events(proj) if e.get('kind') == 'hook_out'])
    hook(proj, 'prompt', {'prompt': 'Сделай, пожалуйста, ещё одну выгрузку для склада'})
    check('`"hook_log": false` → nothing logged', len([e for e in events(proj) if e.get('kind') == 'hook_out']) == n0)
    cfg['hook_log'] = True
    json.dump(cfg, io.open(cfg_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # replay
    inbox0, ev0 = len(lines(proj, 'inbox.jsonl')), len(events(proj))
    code, out = fm(proj, 'replay')
    check('`replay` without a snapshot → says so, exit 0', code == 0 and 'no snapshot' in out, out)
    check('`replay` has no side effects (no inbox row, no event)', len(lines(proj, 'inbox.jsonl')) == inbox0 and len(events(proj)) == ev0,
          (len(lines(proj, 'inbox.jsonl')), inbox0, len(events(proj)), ev0))
    code, out = fm(proj, 'replay', '--save')
    check('`replay --save` writes the snapshot', code == 0 and os.path.exists(os.path.join(proj, '.foreman', 'replay_baseline.json')), out)
    # (the four owner messages so far: an ordinary one, two asks — «Добавь…», «Сделай…» — and one correction)
    check('…counting the asks and the corrections it found', '4 owner messages' in out and 'asks 2' in out and 'corrections 1' in out, out)
    code, out = fm(proj, 'replay')
    check('`replay` against an unchanged snapshot → 0 changed, exit 0', code == 0 and '0 changed' in out, out)
    cfg['extra_ask_cues'] = ['как там дела']
    json.dump(cfg, io.open(cfg_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    code, out = fm(proj, 'replay')
    check('a cue edit that changes how a PAST message reads → CHANGED with the message, exit 1',
          code == 1 and 'CHANGED' in out and 'как там дела' in out and '1 changed' in out, out)
    hook(proj, 'prompt', {'prompt': 'Напиши, пожалуйста, новую страницу помощи для склада'})
    code, out = fm(proj, 'replay')
    check('a message newer than the snapshot is reported as new, not as a change', '1 new message' in out, out)
    code, out = fm(proj, 'replay', '--show')
    check('`replay --show` lists each message with its tags', '«' in out and 'ask:' in out, out[-400:])
finally:
    shutil.rmtree(base, ignore_errors=True)
print('V2.3 TEST:', 'OK' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
