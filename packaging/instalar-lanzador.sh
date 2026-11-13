#!/usr/bin/env bash
set -e
RUTA="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DESTINO"
sed "s|@RUTA@|$RUTA|g" "$RUTA/packaging/escriba.desktop" > "$DESTINO/escriba.desktop"
chmod +x "$DESTINO/escriba.desktop"
echo "Listo: busca Escriba en el menú de aplicaciones."
