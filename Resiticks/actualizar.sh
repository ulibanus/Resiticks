#!/bin/bash
set -e

RESITICKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$RESITICKS_DIR" rev-parse --show-toplevel 2>/dev/null || true)"

echo "============================================================"
echo " 🔄 Actualizador Resiticks — GitHub (ulibanus/Resiticks)"
echo "============================================================"

if [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT/.git" ]; then
  echo "📂 Repositorio Git detectado en $REPO_ROOT"
  git -C "$REPO_ROOT" pull --ff-only
  echo "✅ Resiticks y biblioteca de perfiles actualizados vía Git."
  exit 0
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "⬇️  Descargando última versión desde GitHub..."
curl -fsSL "https://github.com/ulibanus/Resiticks/archive/refs/heads/main.tar.gz" -o "$TMP_DIR/resiticks.tar.gz"
tar -xzf "$TMP_DIR/resiticks.tar.gz" -C "$TMP_DIR"

SRC_DIR="$TMP_DIR/Resiticks-main/Resiticks"
if [ ! -d "$SRC_DIR" ]; then
  echo "❌ No se encontró la carpeta Resiticks dentro del archivo descargado."
  exit 1
fi

mkdir -p "$RESITICKS_DIR/profiles"
cp -f "$SRC_DIR/profiles/"*.json "$RESITICKS_DIR/profiles/"
cp -rf "$SRC_DIR/1_Linux/"* "$RESITICKS_DIR/1_Linux/"
cp -rf "$SRC_DIR/2_Windows/"* "$RESITICKS_DIR/2_Windows/"
chmod +x "$RESITICKS_DIR/1_Linux/"*.sh "$RESITICKS_DIR/actualizar.sh" 2>/dev/null || true

echo "✅ Resiticks y todos los perfiles actualizados correctamente."
