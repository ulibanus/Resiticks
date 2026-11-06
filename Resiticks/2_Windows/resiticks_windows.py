#!/usr/bin/env python3
"""
Resiticks - Versión Windows (vgamepad + pygame)
Carga los mismos perfiles JSON y crea mandos virtuales de Xbox 360 mediante ViGEmBus.
"""
import os
import sys
import glob
import json
import time

try:
    import pygame
    import vgamepad as vg
except ImportError:
    print("❌ Faltan dependencias. Ejecutá: pip install vgamepad pygame")
    sys.exit(1)

PROFILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles")

def load_profiles():
    profiles = {}
    for p in glob.glob(os.path.join(PROFILES_DIR, "*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
                key = f"{d['vendor']}:{d['product']}".lower()
                profiles[key] = d
        except Exception:
            pass
    return profiles

def main():
    print("=" * 65)
    print(" 🎮 Resiticks para Windows (XInput ViGEmBus)")
    print("=" * 65)
    pygame.init()
    pygame.joystick.init()

    num_joysticks = pygame.joystick.get_count()
    print(f"Joysticks físicos detectados en Windows: {num_joysticks}")

    profiles = load_profiles()
    print(f"Perfiles cargados en biblioteca: {len(profiles)}")

    if num_joysticks == 0:
        print("⚠️ No hay joysticks enchufados. Conectá tus mandos.")
        return

    virtual_gamepads = []
    for i in range(min(num_joysticks, 4)):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        vpad = vg.VX360Gamepad()
        virtual_gamepads.append((joy, vpad))
        print(f" ✅ [Jugador {i+1}] {joy.get_name()} -> Xbox 360 Pad {i+1} Activo")

    print("\nPuente corriendo. Presioná Ctrl+C para salir.")
    try:
        while True:
            pygame.event.pump()
            for joy, vpad in virtual_gamepads:
                # Eje izquierdo
                lx = joy.get_axis(0) if joy.get_numaxes() > 0 else 0
                ly = joy.get_axis(1) if joy.get_numaxes() > 1 else 0
                vpad.left_joystick_float(x_value_float=lx, y_value_float=-ly)

                # Eje derecho
                rx = joy.get_axis(2) if joy.get_numaxes() > 2 else 0
                ry = joy.get_axis(3) if joy.get_numaxes() > 3 else 0
                vpad.right_joystick_float(x_value_float=rx, y_value_float=-ry)

                # Botones principales
                if joy.get_numbuttons() > 0:
                    if joy.get_button(0): vpad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    else: vpad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                if joy.get_numbuttons() > 1:
                    if joy.get_button(1): vpad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                    else: vpad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                if joy.get_numbuttons() > 2:
                    if joy.get_button(2): vpad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
                    else: vpad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
                if joy.get_numbuttons() > 3:
                    if joy.get_button(3): vpad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
                    else: vpad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)

                vpad.update()
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nDeteniendo mandos virtuales...")

if __name__ == "__main__":
    main()
