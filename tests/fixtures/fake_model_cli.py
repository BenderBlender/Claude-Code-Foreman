"""fake_model_cli.py — a stand-in for a model CLI in the panel tests: answers «FAKE ANSWER» + the first 3000 characters of what it was
asked (stdin, or the file named after --file); --sleep N waits first (a member that does not answer in time)."""
import io
import sys
import time

a = sys.argv[1:]
if '--pidfile' in a:                                        # (so a test can see the process is gone after a timeout)
    import os
    io.open(a[a.index('--pidfile') + 1], 'w').write(str(os.getpid()))
if '--sleep' in a:
    time.sleep(float(a[a.index('--sleep') + 1]))
text = io.open(a[a.index('--file') + 1], encoding='utf-8').read() if '--file' in a else sys.stdin.read()
sys.stdout.reconfigure(encoding='utf-8')
extra = ''
if '--ls' in a:                                             # (what the member can see where it runs)
    import os
    extra += ' | CWD FILES: ' + ','.join(sorted(os.listdir('.')))
if '--env' in a:
    import os
    v = a[a.index('--env') + 1]
    extra += f' | ENV {v}: ' + ('present' if os.environ.get(v) else 'absent')
print('FAKE ANSWER: ' + text[:3000].replace('\n', ' ') + extra)
