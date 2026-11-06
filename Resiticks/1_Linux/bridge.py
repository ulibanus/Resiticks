#!/usr/bin/env python3
import os
import sys
import glob
import json
import re
import time
import fcntl
import struct
import threading
import select
from virtual_xbox import (
    VirtualXboxPad,
    BTN_A, BTN_B, BTN_X, BTN_Y,
    BTN_TL, BTN_TR, BTN_SELECT, BTN_START, BTN_MODE, BTN_THUMBL, BTN_THUMBR,
    ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ, ABS_HAT0X, ABS_HAT0Y,
    EV_KEY, EV_ABS
)

EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EVIOCGRAB = 0x40044590

PROFILES_DIR = os.path.expanduser("~/joybridge/profiles")

def load_profiles():
    profiles = {}
    for p in glob.glob(os.path.join(PROFILES_DIR, "*.json")):
        try:
            with open(p, "r") as f:
                data = json.load(f)
                key = f"{data['vendor']}:{data['product']}".lower()
                profiles[key] = data
        except Exception as e:
            print(f"Error cargando perfil {p}: {e}")
    return profiles

def get_abs_info(fd):
    info = {}
    for axis in range(64):
        try:
            buf = bytearray(24)
            fcntl.ioctl(fd, 0x80184540 + axis, buf)
            val, minimum, maximum, fuzz, flat, res = struct.unpack("iiiiii", buf)
            info[axis] = {"min": minimum, "max": maximum, "val": val}
        except OSError:
            pass
    return info

def get_connected_gamepads():
    gamepads = []
    try:
        with open("/proc/bus/input/devices", "r") as f:
            content = f.read()
    except Exception as e:
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
            elif line.startswith("P:"):
                m = re.search(r"Phys=(.*)", line)
                if m:
                    info["phys"] = m.group(1)
            elif line.startswith("S:"):
                m = re.search(r"Sysfs=(.*)", line)
                if m:
                    info["sysfs"] = m.group(1)
            elif line.startswith("H:"):
                m = re.search(r"Handlers=(.*)", line)
                if m:
                    for h in m.group(1).split():
                        if h.startswith("event"):
                            info["event"] = h
                        if h.startswith("js"):
                            info["js"] = h

        # IMPORTANTE: Ignorar dispositivos virtuales creados por uinput para evitar bucles
        if "virtual" in info.get("sysfs", ""):
            continue

        name = info.get("name", "")
        if "Motion Sensors" in name:
            continue

        if "event" in info and ("js" in info or "Gamepad" in name or "Joystick" in name or "pad" in name or "Controller" in name):
            info["dev_path"] = f"/dev/input/{info['event']}"
            gamepads.append(info)

    return gamepads

class GamepadWorker(threading.Thread):
    def __init__(self, dev_info, profile, player_num):
        super().__init__(daemon=True)
        self.dev_info = dev_info
        self.profile = profile
        self.player_num = player_num
        self.running = True
        self.dev_fd = None
        self.vpad = None

        self.btn_map = {}
        self.hat_map = {}
        self.axis_map = {}

        mapping = profile.get("mapping", {})

        # Registrar primero botones y hats
        for target, data in mapping.items():
            t_type = data.get("type")
            code = data.get("code")
            if t_type == "btn":
                self.btn_map[code] = target
            elif t_type == "hat":
                val = data.get("value")
                self.hat_map[(code, val)] = target

        # Registrar ejes canónicos prioritarios
        canonical_axes = ["leftx", "lefty", "rightx", "righty", "lt", "rt"]
        for target in canonical_axes:
            if target in mapping:
                data = mapping[target]
                if data.get("type") == "axis":
                    self.axis_map[data.get("code")] = (target, data.get("direction", 1))

        # Fallback si el perfil usaba nombres direccionales de sticks
        if "leftx" not in mapping and "left_right" in mapping:
            self.axis_map[mapping["left_right"]["code"]] = ("leftx", 1)
        if "lefty" not in mapping and "left_down" in mapping:
            self.axis_map[mapping["left_down"]["code"]] = ("lefty", 1)
        if "rightx" not in mapping and "right_right" in mapping:
            self.axis_map[mapping["right_right"]["code"]] = ("rightx", 1)
        if "righty" not in mapping and "right_down" in mapping:
            self.axis_map[mapping["right_down"]["code"]] = ("righty", 1)

        self.dpad_state = {"x": 0, "y": 0}

    def run(self):
        dev_path = self.dev_info["dev_path"]
        try:
            self.dev_fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
            # Bloqueo exclusivo EVIOCGRAB (oculta el mando físico de juegos y Steam)
            fcntl.ioctl(self.dev_fd, EVIOCGRAB, 1)
        except Exception as e:
            print(f"[{self.dev_info['name']}] Error abriendo {dev_path}: {e}")
            return

        abs_info = get_abs_info(self.dev_fd)
        self.vpad = VirtualXboxPad(self.player_num, custom_name=self.profile.get("name"))
        print(f" 🟢 [Jugador {self.player_num}] Conectado: {self.profile.get('name')} -> Xbox 360 Pad {self.player_num}")

        while self.running:
            r, _, _ = select.select([self.dev_fd], [], [], 0.1)
            if not r:
                continue

            try:
                data = os.read(self.dev_fd, EVENT_SIZE * 32)
            except OSError:
                break

            if not data:
                break

            num_events = len(data) // EVENT_SIZE
            for i in range(num_events):
                ev = data[i * EVENT_SIZE : (i + 1) * EVENT_SIZE]
                tv_sec, tv_usec, ev_type, code, value = struct.unpack(EVENT_FORMAT, ev)

                # BOTONES FÍSICOS
                if ev_type == EV_KEY:
                    target = self.btn_map.get(code)
                    if target:
                        is_pressed = (value == 1)
                        if target == "a": self.vpad.emit_key(BTN_A, is_pressed)
                        elif target == "b": self.vpad.emit_key(BTN_B, is_pressed)
                        elif target == "x": self.vpad.emit_key(BTN_X, is_pressed)
                        elif target == "y": self.vpad.emit_key(BTN_Y, is_pressed)
                        elif target == "lb": self.vpad.emit_key(BTN_TL, is_pressed)
                        elif target == "rb": self.vpad.emit_key(BTN_TR, is_pressed)
                        elif target == "lt": self.vpad.emit_abs(ABS_Z, 255 if is_pressed else 0)
                        elif target == "rt": self.vpad.emit_abs(ABS_RZ, 255 if is_pressed else 0)
                        elif target == "back": self.vpad.emit_key(BTN_SELECT, is_pressed)
                        elif target == "start": self.vpad.emit_key(BTN_START, is_pressed)
                        elif target == "guide": self.vpad.emit_key(BTN_MODE, is_pressed)
                        elif target == "thumbl": self.vpad.emit_key(BTN_THUMBL, is_pressed)
                        elif target == "thumbr": self.vpad.emit_key(BTN_THUMBR, is_pressed)
                        elif target == "dpup":
                            self.dpad_state["y"] = -1 if is_pressed else (0 if self.dpad_state["y"] == -1 else self.dpad_state["y"])
                            self.vpad.emit_abs(ABS_HAT0Y, self.dpad_state["y"])
                        elif target == "dpdown":
                            self.dpad_state["y"] = 1 if is_pressed else (0 if self.dpad_state["y"] == 1 else self.dpad_state["y"])
                            self.vpad.emit_abs(ABS_HAT0Y, self.dpad_state["y"])
                        elif target == "dpleft":
                            self.dpad_state["x"] = -1 if is_pressed else (0 if self.dpad_state["x"] == -1 else self.dpad_state["x"])
                            self.vpad.emit_abs(ABS_HAT0X, self.dpad_state["x"])
                        elif target == "dpright":
                            self.dpad_state["x"] = 1 if is_pressed else (0 if self.dpad_state["x"] == 1 else self.dpad_state["x"])
                            self.vpad.emit_abs(ABS_HAT0X, self.dpad_state["x"])

                # EJES ANALÓGICOS Y HAT
                elif ev_type == EV_ABS:
                    if (code, value) in self.hat_map:
                        target = self.hat_map[(code, value)]
                        if target in ("dpup", "dpdown"): self.vpad.emit_abs(ABS_HAT0Y, value)
                        elif target in ("dpleft", "dpright"): self.vpad.emit_abs(ABS_HAT0X, value)
                    elif code in (16, 17) and value == 0:
                        if code == 16: self.vpad.emit_abs(ABS_HAT0X, 0)
                        elif code == 17: self.vpad.emit_abs(ABS_HAT0Y, 0)

                    elif code in self.axis_map:
                        target, direction = self.axis_map[code]
                        info = abs_info.get(code, {"min": 0, "max": 255, "val": 0})
                        val_min, val_max = info["min"], info["max"]

                        if target in ("lt", "rt"):
                            # Gatillo analógico 0..255
                            span = max(1, val_max - val_min)
                            trig_norm = max(0.0, min(1.0, (value - val_min) / span))
                            trig_val = int(trig_norm * 255)
                            if target == "lt": self.vpad.emit_abs(ABS_Z, trig_val)
                            elif target == "rt": self.vpad.emit_abs(ABS_RZ, trig_val)

                        elif target in ("leftx", "lefty", "rightx", "righty"):
                            # Stick analógico normalizado a -32768..32767
                            mid = (val_min + val_max) / 2.0
                            span = (val_max - val_min) / 2.0
                            if span > 0:
                                norm = (value - mid) / span * direction
                                # Zona muerta suave del 5%
                                if abs(norm) < 0.05:
                                    norm = 0.0
                                xbox_val = int(max(-1.0, min(1.0, norm)) * 32767)

                                if target == "leftx": self.vpad.emit_abs(ABS_X, xbox_val)
                                elif target == "lefty": self.vpad.emit_abs(ABS_Y, xbox_val)
                                elif target == "rightx": self.vpad.emit_abs(ABS_RX, xbox_val)
                                elif target == "righty": self.vpad.emit_abs(ABS_RY, xbox_val)

            self.vpad.sync()

        self.cleanup()

    def cleanup(self):
        print(f"\n 🔴 [Jugador {self.player_num}] Desconectado: {self.profile.get('name')}")
        if self.dev_fd:
            try:
                fcntl.ioctl(self.dev_fd, EVIOCGRAB, 0)
                os.close(self.dev_fd)
            except:
                pass
        if self.vpad:
            self.vpad.close()

    def stop(self):
        self.running = False

def print_status_banner(profiles):
    print("=" * 68)
    print(" 🎮 JoyBridge - Hub Universal Multi-Mando (XInput Bridge)")
    print("=" * 68)
    print(f"📂 Base de perfiles ({len(profiles)} modelos soportados):")
    for k, p in sorted(profiles.items()):
        print(f"  • [{k}] {p.get('name')}")
    print("-" * 68)
    print(" 🚀 Listo para 4 jugadores (Slots P1 a P4 con EVIOCGRAB anti-conflicto)")
    print(" 🕹️  Compatible con: Steam, PES (Linux/Proton), Emuladores y Juegos de PC")
    print(" Presioná [Ctrl + C] para salir.\n" + "-" * 68)

def main():
    profiles = load_profiles()
    print_status_banner(profiles)

    active_workers = {}
    slot_assignments = {}

    try:
        while True:
            connected = get_connected_gamepads()
            current_paths = set()

            for gp in connected:
                key = f"{gp['vendor']}:{gp['product']}".lower()
                dev_path = gp["dev_path"]
                identifier = gp.get("phys") or dev_path
                current_paths.add(identifier)

                if identifier not in active_workers and key in profiles:
                    for slot in range(1, 5):
                        if slot not in slot_assignments:
                            worker = GamepadWorker(gp, profiles[key], slot)
                            worker.start()
                            active_workers[identifier] = worker
                            slot_assignments[slot] = worker
                            break

            dead_identifiers = [ident for ident in active_workers if ident not in current_paths]
            for ident in dead_identifiers:
                w = active_workers.pop(ident)
                slot_assignments.pop(w.player_num, None)
                w.stop()

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\n🛑 Deteniendo JoyBridge...")
        for w in active_workers.values():
            w.stop()
        time.sleep(0.5)
        print("✅ Mandos virtuales liberados correctamente.")

if __name__ == "__main__":
    main()
