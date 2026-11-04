"""fake_model_cli.py — a stand-in for a model CLI in the panel tests: answers «FAKE ANSWER» + the first 3000 characters of what it was
asked (stdin, or the file named after --file); --sleep N waits first (a member that does not answer in time)."""
import io
import sys
import time

a = sys.argv[1:]
if '--sleep' in a:
    time.sleep(float(a[a.index('--sleep') + 1]))
text = io.open(a[a.index('--file') + 1], encoding='utf-8').read() if '--file' in a else sys.stdin.read()
sys.stdout.reconfigure(encoding='utf-8')
print('FAKE ANSWER: ' + text[:3000].replace('\n', ' '))
