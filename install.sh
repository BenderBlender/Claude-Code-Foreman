#!/bin/sh
# Foreman (Прораб) installer for macOS / Linux:  ./install.sh /path/to/project [--lang en] [--uninstall [--purge]]
DIR="$(cd "$(dirname "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then exec python3 "$DIR/install.py" "$@"; fi
if command -v python >/dev/null 2>&1; then exec python "$DIR/install.py" "$@"; fi
echo "Python 3.8+ was not found / Python 3.8+ не найден: https://www.python.org/downloads/"; exit 1
