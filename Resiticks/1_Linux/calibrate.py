#!/usr/bin/env python3
"""
Resiticks CLI calibrator following Konami PES Settings 2-column order.
Coordinates gracefully with a running app.py server without killing it.
"""
import os
import sys
import select
import struct
import time
import urllib.request
import json

from evdev_utils import (
    get_abs_info,
    get_connected_gamepads,
    resolve_profiles_dir,
    save_profile,
)
from calibration_core import (
    CALIBRATION_STEPS,
    EVENT_FORMAT,
    EVENT_SIZE,
    derive_canonical_axes,
    detect_digital_mode_warning,
    detect_input_event,
    drain_and_wait_neutral,
    validate_calibration_consistency,
)


def _notify_server_pause(dev_path, action="pause"):
    """Politely ask running Resiticks web server to release/reclaim one device without killing app.py."""
    url = f"http://127.0.0.1:8765/api/calibrate/{action}"
    payload = json.dumps({"dev_path": dev_path}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def choose_gamepad(gamepads):
    """Prompt user with strict input validation until a valid gamepad index is selected."""
    if len(gamepads) == 1:
        print(f"\nSeleccionado automáticamente el joystick 1: {gamepads[0]['name']}")
        return gamepads[0]

    while True:
        try:
            ans = input(f"\nElegí el número de joystick a calibrar (1-{len(gamepads)}): ").strip()
            idx = int(ans) - 1
            if 0 <= idx < len(gamepads):
                return gamepads[idx]
        except ValueError:
            pass
        print(f"⚠️  Ingresá un número válido entre 1 y {len(gamepads)}.")


def wait_for_step_input(fd, step, abs_info):
    """Wait for a single input matching a calibration step, warning on Digital Mode."""
    prompt = step["prompt"]
    allow_skip = step["allow_skip"]
    step_key = step["key"]

    while True:
        print(f"\n👉 {prompt}")
        if allow_skip:
            print("   (Presioná [ENTER] en el teclado para saltear)")

        drain_and_wait_neutral(fd, abs_info)
        detected = None

        while detected is None:
            r, _, _ = select.select([sys.stdin, fd], [], [])
            if sys.stdin in r:
                sys.stdin.readline()
                if allow_skip:
                    print("   ⏩ Salteado.")
                    return None
                print("   ⚠️  Este botón es obligatorio en PES. Presionalo en el joystick.")
                continue

            if fd in r:
                try:
                    data = os.read(fd, EVENT_SIZE)
                except OSError:
                    continue
                if len(data) < EVENT_SIZE:
                    continue
                _, _, ev_type, code, value = struct.unpack(EVENT_FORMAT, data)
                detected = detect_input_event(ev_type, code, value, abs_info)

        warn = detect_digital_mode_warning(step_key, detected)
        if warn:
            print(f"\n⚠️  {warn}")
            retry = input("   Presioná [ENTER] para repetir este paso (o 's' + ENTER para conservarlo igual): ").strip().lower()
            if retry != "s":
                continue

        t = detected.get("type")
        if t == "btn":
            print(f"   ✅ Detectado Botón: Código {detected['code']} (0x{detected['code']:03x})")
        elif t == "hat":
            print(f"   ✅ Detectado D-Pad HAT: Eje {detected['code']}, Valor {detected['value']}")
        else:
            print(f"   ✅ Detectado Eje Analógico: Código {detected['code']}, Dir {detected.get('direction', 1)} (Valor {detected.get('value')})")

        drain_and_wait_neutral(fd, abs_info)
        return detected


def main():
    """Run interactive CLI calibration wizard in Konami PES Settings order."""
    print("=" * 65)
    print(" 🎮 Resiticks - Calibrador Oficial por Consola (Orden PES)")
    print("=" * 65)

    gamepads = get_connected_gamepads()
    if not gamepads:
        print("❌ No se encontró ningún joystick conectado en /proc/bus/input/devices.")
        sys.exit(1)

    print("\nJoysticks detectados:")
    for i, gp in enumerate(gamepads):
        print(f" [{i+1}] {gp.get('name')} (VID: {gp.get('vendor')}, PID: {gp.get('product')}) en {gp.get('dev_path')}")

    selected = choose_gamepad(gamepads)
    dev_path = selected["dev_path"]
    paused_server = _notify_server_pause(dev_path, "pause")
    if paused_server:
        print(f"ℹ️  Servidor Resiticks activo detectado: liberando temporalmente {dev_path}...")
        time.sleep(0.25)

    fd = None
    try:
        try:
            fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
        except PermissionError:
            print(f"❌ Error de permisos al abrir {dev_path}. Verificá pertenecer al grupo 'input'.")
            sys.exit(1)

        abs_info = get_abs_info(fd)
        print("\n" + "=" * 65)
        print("📋 CALIBRACIÓN SIGUIENDO EL ORDEN EXACTO DE PES SETTINGS:")
        print("   Primero la columna izquierda completa, luego la columna derecha.")
        print("   Tip: en joysticks con botón ANALOG, verificá que el LED rojo esté encendido.")
        print("=" * 65)

        mapping = {}
        for step in CALIBRATION_STEPS:
            res = wait_for_step_input(fd, step, abs_info)
            if res is not None:
                mapping[step["key"]] = res

        mapping = derive_canonical_axes(mapping)
        warnings = validate_calibration_consistency(mapping)
        if warnings:
            print("\n⚠️  Advertencias detectadas en la calibración:")
            for w in warnings:
                print(f"   • {w}")

        hw_name = selected.get("name", "Unknown Gamepad")
        print("\n" + "-" * 65)
        custom_name = input(f"¿Qué nombre querés ponerle a este joystick? [{hw_name}]: ").strip()
        if not custom_name:
            custom_name = hw_name

        vendor = selected.get("vendor", "0000")
        product = selected.get("product", "0000")
        profile_data = {
            "name": custom_name,
            "hardware_name": hw_name,
            "vendor": vendor,
            "product": product,
            "mapping": mapping,
        }

        out_file = save_profile(profile_data, profiles_dir=resolve_profiles_dir())
        print("\n" + "=" * 65)
        print(" 🎉 ¡Calibración completada con éxito al estilo PES Settings!")
        print(f" 💾 Perfil guardado en: {out_file}")
        print("=" * 65)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if paused_server:
            _notify_server_pause(dev_path, "resume")


if __name__ == "__main__":
    main()
