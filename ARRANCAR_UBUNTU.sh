#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo 'Instala Python 3.11 o superior.'; exit 1; }
if [ ! -d .venv ]; then
  python3 -m venv .venv || { echo 'Falta python3-venv. Instala con sudo apt install python3-venv'; exit 1; }
fi
. .venv/bin/activate
if [ ! -f .venv/.savia_deps_installed ]; then
  python -m pip install --disable-pip-version-check -r requirements.txt
  touch .venv/.savia_deps_installed
fi
python iniciar.py
