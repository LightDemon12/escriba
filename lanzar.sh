#!/usr/bin/env bash
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && .venv/bin/pip install -e . || { echo "Falló la instalación"; read -r -p "Pulsa Enter para cerrar"; exit 1; }
fi
exec .venv/bin/python -m escriba "$@"
