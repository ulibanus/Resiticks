#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="$SCRIPT_DIR/app.py"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"

echo "============================================================"
echo " 🎮 Instalador de Sistema Linux — Resiticks"
echo "============================================================"

# 1. Instalar lanzadores locales para el usuario
mkdir -p "$BIN_DIR" "$APP_DIR"
cat > "$BIN_DIR/resiticks" <<EOF
#!/bin/bash
exec python3 "$APP_PATH" "\$@"
EOF
chmod +x "$BIN_DIR/resiticks"

cat > "$APP_DIR/resiticks.desktop" <<EOF
[Desktop Entry]
Name=Resiticks
Comment=Hub Universal de Joysticks & Puente XInput
Exec=$BIN_DIR/resiticks
Icon=input-gaming
Terminal=false
Type=Application
Categories=Game;Utility;
EOF

echo "✅ Lanzadores instalados en $BIN_DIR/resiticks y menú de aplicaciones."

# 1b. Servicio systemd --user en segundo plano (opcional con --enable-service)
if [ -f "$SCRIPT_DIR/resiticks.service" ] && command -v systemctl >/dev/null 2>&1; then
  SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
  mkdir -p "$SYSTEMD_USER_DIR"
  cp "$SCRIPT_DIR/resiticks.service" "$SYSTEMD_USER_DIR/resiticks.service"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  if [ "$1" = "--enable-service" ]; then
    systemctl --user enable --now resiticks.service
    echo "✅ Servicio systemd --user habilitado e iniciado en segundo plano (--daemon)."
  else
    echo "ℹ️  Plantilla systemd instalada en $SYSTEMD_USER_DIR/resiticks.service."
    echo "   Para iniciar Resiticks automáticamente al iniciar sesión ejecutá:"
    echo "   systemctl --user enable --now resiticks.service"
  fi
fi

# 2. Verificar permisos de /dev/uinput y grupo input
if [ ! -w /dev/uinput ] || ! id -nG "$USER" | grep -qw input; then
  echo ""
  echo "⚙️  Se requieren permisos para crear mandos virtuales (/dev/uinput) y leer evdev (grupo 'input')."
  echo "   Se solicitará contraseña sudo para instalar la regla udev oficial:"
  sudo bash -c '
    modprobe uinput || true
    echo "uinput" > /etc/modules-load.d/resiticks-uinput.conf
    echo '\''KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"'\'' > /etc/udev/rules.d/99-resiticks-uinput.rules
    udevadm control --reload-rules
    udevadm trigger /dev/uinput || true
  '
  sudo usermod -aG input "$USER"
  echo "✅ Regla udev y módulo uinput configurados."
  echo "ℹ️  Si recién fuiste agregado al grupo 'input', cerrá sesión y volvé a entrar para aplicar los cambios."
else
  echo "✅ Permisos de /dev/uinput y grupo 'input' ya configurados correctamente."
fi
