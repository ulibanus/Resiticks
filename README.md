# 🎮 Resiticks — Hub Universal de Joysticks (Linux & Windows)

Solución multiplataforma para gestionar hasta **8 joysticks USB y Bluetooth** (genéricos DragonRise/Microntek, Gasia, BDA, Shanwan, Switch Pro, PS4, Xbox) sin doble entrada, sin botones cruzados y con orden fijo de jugadores para **PES 6**, **Steam** y emuladores.

---

## 📁 Estructura Unificada

```text
Resiticks/
├── 1_Linux/
│   ├── app.py                     # Motor principal + Servidor Web UI (127.0.0.1:8765)
│   ├── web_ui.py                  # Panel interactivo, tester en vivo y calibrador web PES
│   ├── virtual_xbox.py            # Emulador nativo /dev/uinput (Xbox 360 + Force Feedback)
│   ├── evdev_utils.py             # Detección física, perfiles, configuración y diagnóstico USB
│   ├── calibration_core.py        # Lógica compartida PES Settings (8/10/16-bit + alerta ANALOG)
│   ├── calibrate.py               # Calibrador alternativo por consola
│   ├── sniffer.py                 # Depurador en vivo de eventos evdev
│   ├── iniciar_resiticks.sh       # Lanzador Linux
│   ├── calibrar_nuevo_mando.sh    # Calibrador rápido consola
│   └── instalar_sistema_linux.sh  # Instalador regla udev /dev/uinput + ícono de escritorio
├── 2_Windows/
│   ├── resiticks_windows.py       # Motor Windows ViGEmBus multi-perfil + panel web
│   ├── instalar_requisitos_windows.bat
│   └── GUIA_WINDOWS.txt
├── profiles/                      # 15 perfiles listos para enchufar y jugar
├── tests/                         # Suite automatizada de pruebas Linux uinput/HTTP/UI
├── actualizar.sh                  # Actualizador 1-clic Linux desde GitHub
├── actualizar.bat                 # Actualizador 1-clic Windows desde GitHub
└── LEEME_INSTRUCCIONES.txt
```

---

## 🚀 Inicio Rápido (Linux)

```bash
cd Resiticks/1_Linux
./iniciar_resiticks.sh
```

Si es tu primera vez en una distro nueva sin acceso a `/dev/uinput`, ejecutá una sola vez:
```bash
cd Resiticks/1_Linux
./instalar_sistema_linux.sh
```

Para correr los tests automatizados:
```bash
python3 Resiticks/tests/test_resiticks.py
```
