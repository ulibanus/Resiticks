#!/usr/bin/env python3
import os
import sys
import re
import json
import struct
import select
import time
import fcntl

# Linux input_event 64-bit
EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03

ABS_HAT0X = 16
ABS_HAT0Y = 17

def get_abs_info(fd):
    info = {}
    for axis in range(64):
        try:
            buf = bytearray(24)
            fcntl.ioctl(fd, 0x80184540 + axis, buf)
            val, minimum, maximum, fuzz, flat, res = struct.unpack("iiiiii", buf)
            info[axis] = {"val": val, "min": minimum, "max": maximum}
        except OSError:
            pass
    return info

def get_connected_gamepads():
    gamepads = []
    try:
        with open("/proc/bus/input/devices", "r") as f:
            content = f.read()
    except Exception as e:
        print(f"Error leyendo /proc/bus/input/devices: {e}")
        return []

    entries = content.strip().split("\n\n")
    for entry in entries:
        lines = entry.split("\n")
        info = {}
        for line in lines:
            if line.startswith("I:"):
                m = re.search(r"Vendor=([0-9a-fA-F]+)\s+Product=([0-9a-fA-F]+)", line)
                if m:
                    info["vendor"] = m.group(1).lower()
                    info["product"] = m.group(2).lower()
            elif line.startswith("N:"):
                m = re.search(r'Name="([^"]+)"', line)
                if m:
                    info["name"] = m.group(1)
            elif line.startswith("S:"):
                m = re.search(r"Sysfs=(.*)", line)
                if m:
                    info["sysfs"] = m.group(1)
            elif line.startswith("H:"):
                m = re.search(r"Handlers=(.*)", line)
                if m:
                    handlers = m.group(1).split()
                    for h in handlers:
                        if h.startswith("event"):
                            info["event"] = h
                        if h.startswith("js"):
                            info["js"] = h

        name = info.get("name", "")
        if "Motion Sensors" in name or "Resiticks" in name or "(IMU)" in name or "Touchpad" in name or "Mouse" in name:
            continue
        if "virtual" in info.get("sysfs", ""):
            continue

        if "event" in info and ("js" in info or "Gamepad" in name or "Joystick" in name or "Controller" in name or "pad" in name):
            info["dev_path"] = f"/dev/input/{info['event']}"
            gamepads.append(info)

    return gamepads

def wait_for_release(fd, abs_info):
    """Espera a que el usuario suelte botones y vuelva los ejes al centro"""
    time.sleep(0.12)
    while True:
        r, _, _ = select.select([fd], [], [], 0.05)
        if not r:
            break
        try:
            os.read(fd, EVENT_SIZE * 64)
        except:
            break

def wait_for_input(fd, prompt, abs_info, allow_skip=True):
    print(f"\n👉 {prompt}")
    if allow_skip:
        print("   (Presioná [ENTER] en el teclado para saltear)")

    wait_for_release(fd, abs_info)

    while True:
        r, _, _ = select.select([sys.stdin, fd], [], [])
        if sys.stdin in r:
            sys.stdin.readline()
            if allow_skip:
                print("   ⏩ Salteado.")
                return None

        if fd in r:
            try:
                data = os.read(fd, EVENT_SIZE)
            except OSError:
                continue

            if len(data) < EVENT_SIZE:
                continue

            tv_sec, tv_usec, ev_type, code, value = struct.unpack(EVENT_FORMAT, data)

            # Botón normal
            if ev_type == EV_KEY and value == 1:
                print(f"   ✅ Detectado Botón: Código {code} (0x{code:03x})")
                wait_for_release(fd, abs_info)
                return {"type": "btn", "code": code}

            # Eje D-Pad tipo HAT (flechas)
            elif ev_type == EV_ABS and code in (ABS_HAT0X, ABS_HAT0Y):
                if value != 0:
                    axis_name = "HAT Y (Vertical)" if code == ABS_HAT0Y else "HAT X (Horizontal)"
                    dir_name = "-1 (Arriba/Izq)" if value < 0 else "+1 (Abajo/Der)"
                    print(f"   ✅ Detectado D-Pad: {axis_name}, Dirección {dir_name}")
                    wait_for_release(fd, abs_info)
                    return {"type": "hat", "code": code, "value": value}

            # Ejes analógicos estándar (sticks o gatillos analógicos)
            elif ev_type == EV_ABS and code not in (ABS_HAT0X, ABS_HAT0Y):
                info = abs_info.get(code, {"min": 0, "max": 255, "val": 0})
                val_min = info.get("min", 0)
                val_max = info.get("max", 255)
                rest_val = info.get("val", 0)

                # Caso 1: Gatillos analógicos (L2/R2 tipo Xbox/PS3, rango 0..255 descansando en 0)
                if val_min == 0 and val_max <= 255 and rest_val < 35:
                    if value > 120:
                        print(f"   ✅ Detectado Gatillo Analógico: Código {code} (Valor: {value})")
                        wait_for_release(fd, abs_info)
                        return {"type": "axis", "code": code, "direction": 1, "value": value, "is_trigger": True}

                # Caso 2: Sticks Xbox con rango de 16 bits (-32768 a 32767, centrados en 0)
                elif val_min < -1000:
                    if abs(value) > 16000:
                        direction = 1 if value > 0 else -1
                        print(f"   ✅ Detectado Stick Analógico (Xbox): Código {code}, Dirección: {direction} (Valor: {value})")
                        wait_for_release(fd, abs_info)
                        return {"type": "axis", "code": code, "direction": direction, "value": value}

                # Caso 3: Sticks genéricos con rango de 8 bits (0 a 255, centrados en ~128)
                else:
                    mid = (val_min + val_max) / 2.0
                    span = (val_max - val_min) / 2.0
                    if span > 0:
                        deviation = (value - mid) / span
                        if abs(deviation) > 0.45:
                            direction = 1 if deviation > 0 else -1
                            print(f"   ✅ Detectado Stick Analógico (Genérico): Código {code}, Dirección: {direction} (Valor: {value})")
                            wait_for_release(fd, abs_info)
                            return {"type": "axis", "code": code, "direction": direction, "value": value}

def main():
    # Asegurar que ningún puente en segundo plano retenga el bloqueo exclusivo EVIOCGRAB
    try:
        import subprocess
        subprocess.run(["pkill", "-f", "joybridge/app.py"], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-f", "joybridge/bridge.py"], stderr=subprocess.DEVNULL)
        time.sleep(0.3)
    except Exception:
        pass

    print("=" * 65)
    print(" 🎮 JoyBridge - Calibrador con Orden Oficial PES (Settings)")
    print("=" * 65)

    gamepads = get_connected_gamepads()
    if not gamepads:
        print("❌ No se encontró ningún joystick conectado en /proc/bus/input/devices.")
        sys.exit(1)

    print("\nJoysticks detectados:")
    for i, gp in enumerate(gamepads):
        print(f" [{i+1}] {gp.get('name')} (VID: {gp.get('vendor')}, PID: {gp.get('product')}) en {gp.get('dev_path')}")

    if len(gamepads) == 1:
        choice = 0
        print(f"\nSeleccionado automáticamente el joystick 1: {gamepads[0]['name']}")
    else:
        ans = input(f"\nElegí el número de joystick a calibrar (1-{len(gamepads)}): ")
        choice = int(ans.strip()) - 1

    selected = gamepads[choice]
    dev_path = selected["dev_path"]

    try:
        fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        print(f"❌ Error de permisos al abrir {dev_path}.")
        sys.exit(1)

    abs_info = get_abs_info(fd)

    print("\n" + "=" * 65)
    print("📋 CALIBRACIÓN SIGUIENDO EL ORDEN EXACTO DE PES SETTINGS:")
    print("   Primero la columna izquierda completa, luego la columna derecha.")
    print("=" * 65)

    mapping = {}

    steps = [
        # --- COLUMNA IZQUIERDA (PES SETTINGS) ---
        ("lt", "1. [Lado Izq] Presioná Gatillo L2", True),
        ("lb", "2. [Lado Izq] Presioná Botón L1", False),
        
        ("dpup", "3. [Lado Izq] D-Pad: Flecha ARRIBA (Hat Switch N)", False),
        ("dpleft", "4. [Lado Izq] D-Pad: Flecha IZQUIERDA (Hat Switch W)", False),
        ("dpdown", "5. [Lado Izq] D-Pad: Flecha ABAJO (Hat Switch S)", False),
        ("dpright", "6. [Lado Izq] D-Pad: Flecha DERECHA (Hat Switch E)", False),

        ("left_up", "7. [Lado Izq] Stick Izquierdo: Mové hacia ARRIBA (Y Axis -)", True),
        ("left_left", "8. [Lado Izq] Stick Izquierdo: Mové hacia IZQUIERDA (X Axis -)", True),
        ("left_down", "9. [Lado Izq] Stick Izquierdo: Mové hacia ABAJO (Y Axis +)", True),
        ("left_right", "10. [Lado Izq] Stick Izquierdo: Mové hacia DERECHA (X Axis +)", True),

        ("thumbl", "11. [Lado Izq] Click Stick Izquierdo (L3)", True),
        ("back", "12. [Lado Izq] Botón SELECT", False),

        # --- COLUMNA DERECHA (PES SETTINGS) ---
        ("rt", "13. [Lado Der] Presioná Gatillo R2", True),
        ("rb", "14. [Lado Der] Presioná Botón R1", False),

        ("y", "15. [Lado Der] Botón TRIÁNGULO / Y (Superior)", False),
        ("x", "16. [Lado Der] Botón CUADRADO / X (Izquierdo)", False),
        ("a", "17. [Lado Der] Botón CRUZ / A (Inferior)", False),
        ("b", "18. [Lado Der] Botón CÍRCULO / B (Derecho)", False),

        ("right_up", "19. [Lado Der] Stick Derecho: Mové hacia ARRIBA", True),
        ("right_left", "20. [Lado Der] Stick Derecho: Mové hacia IZQUIERDA", True),
        ("right_down", "21. [Lado Der] Stick Derecho: Mové hacia ABAJO", True),
        ("right_right", "22. [Lado Der] Stick Derecho: Mové hacia DERECHA", True),

        ("thumbr", "23. [Lado Der] Click Stick Derecho (R3)", True),
        ("start", "24. [Lado Der] Botón START", False),
    ]

    for key, prompt, allow_skip in steps:
        res = wait_for_input(fd, prompt, abs_info, allow_skip)
        if res is not None:
            mapping[key] = res

    os.close(fd)

    # Derivar configuraciones canónicas de ejes X/Y para los sticks si se calibraron las 4 direcciones
    # Stick Izquierdo
    if "left_right" in mapping:
        mapping["leftx"] = {"type": "axis", "code": mapping["left_right"]["code"], "direction": 1}
    if "left_down" in mapping:
        mapping["lefty"] = {"type": "axis", "code": mapping["left_down"]["code"], "direction": 1}

    # Stick Derecho
    if "right_right" in mapping:
        mapping["rightx"] = {"type": "axis", "code": mapping["right_right"]["code"], "direction": 1}
    if "right_down" in mapping:
        mapping["righty"] = {"type": "axis", "code": mapping["right_down"]["code"], "direction": 1}

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
        "mapping": mapping
    }

    out_file = f"/home/ulises/joybridge/profiles/{vendor}_{product}.json"
    with open(out_file, "w") as f:
        json.dump(profile_data, f, indent=2)

    print("\n" + "=" * 65)
    print(" 🎉 ¡Calibración completada con éxito al estilo PES Settings!")
    print(f" 💾 Perfil actualizado en: {out_file}")
    print("=" * 65)

if __name__ == "__main__":
    main()
