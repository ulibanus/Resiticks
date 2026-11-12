#!/usr/bin/env python3
"""
Interactive live evdev sniffer for debugging buttons, D-Pad hats, and 8/10/16-bit axes.
Accepts an optional device path CLI argument or lets the user select one cleanly.
"""
import os
import sys
import struct
import select
import urllib.request
import json

from evdev_utils import get_abs_info, get_connected_gamepads, EVENT_FORMAT, EVENT_SIZE


def _check_server_grab():
    """Warn user if Resiticks HTTP server is running and may hold EVIOCGRAB on gamepads."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=0.6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("bridge_enabled"):
                print("⚠️  Aviso: Resiticks está corriendo con el puente activo (EVIOCGRAB).")
                print("   Si no ves eventos en consola, pausá el puente desde la Web UI.\n")
    except Exception:
        pass


def pick_device():
    """Resolve target /dev/input/eventX from CLI arg or interactive gamepad selector."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    gamepads = get_connected_gamepads()
    if not gamepads:
        print("❌ No se detectó ningún joystick conectado y no pasaste ruta por argumento.")
        print("   Uso: python3 sniffer.py /dev/input/eventX")
        sys.exit(1)

    if len(gamepads) == 1:
        return gamepads[0]["dev_path"]

    print("Joysticks detectados:")
    for idx, gp in enumerate(gamepads, 1):
        print(f" [{idx}] {gp.get('name')} ({gp.get('vendor')}:{gp.get('product')}) -> {gp['dev_path']}")
    while True:
        try:
            choice = int(input(f"Elegí dispositivo (1-{len(gamepads)}): ").strip()) - 1
            if 0 <= choice < len(gamepads):
                return gamepads[choice]["dev_path"]
        except ValueError:
            pass
        print("⚠️  Selección inválida.")


def main():
    """Stream filtered real-time button and axis events from the selected evdev node."""
    dev_path = pick_device()
    if not os.path.exists(dev_path):
        print(f"❌ No existe {dev_path}")
        sys.exit(1)

    _check_server_grab()
    fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
    abs_info = get_abs_info(fd)

    print("=" * 60)
    print(" 🔍 RESITICKS — SNIFFER DE EVENTOS EN VIVO")
    print(f" Escuchando {dev_path}...")
    print(" Presioná botones o mové sticks. Ctrl+C para salir.")
    print("=" * 60)

    try:
        while True:
            select.select([fd], [], [])
            try:
                data = os.read(fd, EVENT_SIZE * 32)
            except BlockingIOError:
                continue
            if not data:
                break
            n = len(data) // EVENT_SIZE
            for i in range(n):
                _, _, ev_type, code, value = struct.unpack(EVENT_FORMAT, data[i * EVENT_SIZE : (i + 1) * EVENT_SIZE])
                if ev_type == 1:
                    st = "PRESIONADO (1)" if value == 1 else ("SOLTADO (0)" if value == 0 else f"REPETICIÓN ({value})")
                    print(f"👉 BOTÓN: Código {code} (0x{code:03x}) -> {st}")
                elif ev_type == 3:
                    if code in (16, 17):
                        print(f"✚ D-PAD HAT {code}: {value}")
                        continue
                    info = abs_info.get(code, {"min": 0, "max": 255, "val": 0})
                    span = max(1, info["max"] - info["min"])
                    rest = info.get("val", (info["min"] + info["max"]) / 2.0)
                    # Dynamic noise threshold (>12% away from resting point) handles 8/10/16-bit controllers
                    if abs(value - rest) / span > 0.12:
                        print(f"📊 EJE {code}: Valor {value} (rango {info['min']}..{info['max']})")
    except KeyboardInterrupt:
        print("\nSniffer finalizado.")
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
