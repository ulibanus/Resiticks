#!/usr/bin/env python3
import os
import sys
import json
import time
import glob
import re
import fcntl
import struct
import threading
import select
import zipfile
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import subprocess

from virtual_xbox import (
    VirtualXboxPad,
    BTN_A, BTN_B, BTN_X, BTN_Y,
    BTN_TL, BTN_TR, BTN_SELECT, BTN_START, BTN_MODE, BTN_THUMBL, BTN_THUMBR,
    ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ, ABS_HAT0X, ABS_HAT0Y,
    EV_KEY, EV_ABS
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EVIOCGRAB = 0x40044590

MAX_SLOTS = 8 # Soporte extendido para hasta 8 jugadores (PES 6, torneos)

class ResiticksState:
    def __init__(self):
        self.bridge_enabled = True
        self.active_slots = {i: None for i in range(1, MAX_SLOTS + 1)}
        self.connected_devices = []
        self.workers = {}
        self.live_inputs = {i: {} for i in range(1, MAX_SLOTS + 1)}
        self.lock = threading.Lock()

state = ResiticksState()

def load_profiles():
    profiles = {}
    for p in glob.glob(os.path.join(PROFILES_DIR, "*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = f"{data['vendor']}:{data['product']}".lower()
                profiles[key] = data
        except Exception:
            pass
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
    except Exception:
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

        if "virtual" in info.get("sysfs", ""):
            continue
        name = info.get("name", "")
        if "Motion Sensors" in name or "(IMU)" in name or "Touchpad" in name or "Mouse" in name:
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
        for target, data in mapping.items():
            t_type = data.get("type")
            code = data.get("code")
            if t_type == "btn":
                self.btn_map[code] = target
            elif t_type == "hat":
                self.hat_map[(code, data.get("value"))] = target

        canonical_axes = ["leftx", "lefty", "rightx", "righty", "lt", "rt"]
        for target in canonical_axes:
            if target in mapping:
                data = mapping[target]
                if data.get("type") == "axis":
                    self.axis_map[data.get("code")] = (target, data.get("direction", 1))

        if "leftx" not in mapping and "left_right" in mapping:
            self.axis_map[mapping["left_right"]["code"]] = ("leftx", 1)
        if "lefty" not in mapping and "left_down" in mapping:
            self.axis_map[mapping["left_down"]["code"]] = ("lefty", 1)
        if "rightx" not in mapping and "right_right" in mapping:
            self.axis_map[mapping["right_right"]["code"]] = ("rightx", 1)
        if "righty" not in mapping and "right_down" in mapping:
            self.axis_map[mapping["right_down"]["code"]] = ("righty", 1)

        self.dpad_state = {"x": 0, "y": 0}
        self.live_state = {
            "lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0,
            "lt": 0, "rt": 0,
            "buttons": {
                "a": False, "b": False, "x": False, "y": False,
                "lb": False, "rb": False, "lt": False, "rt": False,
                "back": False, "start": False, "guide": False,
                "thumbl": False, "thumbr": False,
                "dpup": False, "dpdown": False, "dpleft": False, "dpright": False
            }
        }

    def run(self):
        dev_path = self.dev_info["dev_path"]
        try:
            self.dev_fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
            fcntl.ioctl(self.dev_fd, EVIOCGRAB, 1)
        except Exception:
            return

        abs_info = get_abs_info(self.dev_fd)
        if state.bridge_enabled:
            self.vpad = VirtualXboxPad(self.player_num, custom_name=self.profile.get("name"))

        with state.lock:
            state.active_slots[self.player_num] = {
                "name": self.profile.get("name"),
                "vendor": self.profile.get("vendor"),
                "product": self.profile.get("product"),
                "dev_path": dev_path,
                "player_num": self.player_num
            }

        while self.running:
            r, _, _ = select.select([self.dev_fd], [], [], 0.05)
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

                if ev_type == EV_KEY:
                    target = self.btn_map.get(code)
                    if target:
                        is_pressed = (value == 1)
                        self.live_state["buttons"][target] = is_pressed
                        if self.vpad:
                            if target == "a": self.vpad.emit_key(BTN_A, is_pressed)
                            elif target == "b": self.vpad.emit_key(BTN_B, is_pressed)
                            elif target == "x": self.vpad.emit_key(BTN_X, is_pressed)
                            elif target == "y": self.vpad.emit_key(BTN_Y, is_pressed)
                            elif target == "lb": self.vpad.emit_key(BTN_TL, is_pressed)
                            elif target == "rb": self.vpad.emit_key(BTN_TR, is_pressed)
                            elif target == "lt":
                                self.live_state["lt"] = 100 if is_pressed else 0
                                self.vpad.emit_abs(ABS_Z, 255 if is_pressed else 0)
                            elif target == "rt":
                                self.live_state["rt"] = 100 if is_pressed else 0
                                self.vpad.emit_abs(ABS_RZ, 255 if is_pressed else 0)
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

                elif ev_type == EV_ABS:
                    if (code, value) in self.hat_map:
                        target = self.hat_map[(code, value)]
                        is_active = (value != 0)
                        self.live_state["buttons"][target] = is_active
                        if self.vpad:
                            if target in ("dpup", "dpdown"): self.vpad.emit_abs(ABS_HAT0Y, value)
                            elif target in ("dpleft", "dpright"): self.vpad.emit_abs(ABS_HAT0X, value)
                    elif code in (16, 17) and value == 0:
                        if code == 16:
                            self.live_state["buttons"]["dpleft"] = False
                            self.live_state["buttons"]["dpright"] = False
                            if self.vpad: self.vpad.emit_abs(ABS_HAT0X, 0)
                        elif code == 17:
                            self.live_state["buttons"]["dpup"] = False
                            self.live_state["buttons"]["dpdown"] = False
                            if self.vpad: self.vpad.emit_abs(ABS_HAT0Y, 0)

                    elif code in self.axis_map:
                        target, direction = self.axis_map[code]
                        info = abs_info.get(code, {"min": 0, "max": 255, "val": 0})
                        val_min, val_max = info["min"], info["max"]

                        if target in ("lt", "rt"):
                            span = max(1, val_max - val_min)
                            trig_norm = max(0.0, min(1.0, (value - val_min) / span))
                            trig_val = int(trig_norm * 255)
                            pct = int(trig_norm * 100)
                            self.live_state[target] = pct
                            self.live_state["buttons"][target] = (pct > 15)
                            if self.vpad:
                                if target == "lt": self.vpad.emit_abs(ABS_Z, trig_val)
                                elif target == "rt": self.vpad.emit_abs(ABS_RZ, trig_val)

                        elif target in ("leftx", "lefty", "rightx", "righty"):
                            mid = (val_min + val_max) / 2.0
                            span = (val_max - val_min) / 2.0
                            if span > 0:
                                norm = (value - mid) / span * direction
                                raw_norm = norm
                                if abs(norm) < 0.05:
                                    norm = 0.0
                                xbox_val = int(max(-1.0, min(1.0, norm)) * 32767)

                                if target == "leftx":
                                    self.live_state["lx"] = round(raw_norm, 2)
                                    if self.vpad: self.vpad.emit_abs(ABS_X, xbox_val)
                                elif target == "lefty":
                                    self.live_state["ly"] = round(raw_norm, 2)
                                    if self.vpad: self.vpad.emit_abs(ABS_Y, xbox_val)
                                elif target == "rightx":
                                    self.live_state["rx"] = round(raw_norm, 2)
                                    if self.vpad: self.vpad.emit_abs(ABS_RX, xbox_val)
                                elif target == "righty":
                                    self.live_state["ry"] = round(raw_norm, 2)
                                    if self.vpad: self.vpad.emit_abs(ABS_RY, xbox_val)

            if self.vpad:
                self.vpad.sync()

            with state.lock:
                state.live_inputs[self.player_num] = self.live_state

        self.cleanup()

    def cleanup(self):
        with state.lock:
            state.active_slots[self.player_num] = None
            state.live_inputs[self.player_num] = {}
        if self.dev_fd:
            try:
                fcntl.ioctl(self.dev_fd, EVIOCGRAB, 0)
                os.close(self.dev_fd)
            except Exception:
                pass
        if self.vpad:
            self.vpad.close()

    def stop(self):
        self.running = False

def device_supervisor():
    while True:
        try:
            profiles = load_profiles()
            connected = get_connected_gamepads()
            current_paths = set()

            with state.lock:
                state.connected_devices = connected

            for gp in connected:
                key = f"{gp['vendor']}:{gp['product']}".lower()
                dev_path = gp["dev_path"]
                identifier = gp.get("phys") or dev_path
                current_paths.add(identifier)

                if identifier not in state.workers and key in profiles:
                    for slot in range(1, MAX_SLOTS + 1):
                        if state.active_slots[slot] is None:
                            worker = GamepadWorker(gp, profiles[key], slot)
                            worker.start()
                            state.workers[identifier] = worker
                            break

            dead_identifiers = [ident for ident in list(state.workers.keys()) if ident not in current_paths]
            for ident in dead_identifiers:
                w = state.workers.pop(ident)
                w.stop()

        except Exception:
            pass

        time.sleep(0.8)

HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resiticks — Hub Universal de Joysticks</title>
<style>
  :root {
    --bg: #0b1120;
    --card-bg: #151e32;
    --card-border: #24324f;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --success: #10b981;
    --warning: #f59e0b;
    --text: #f8fafc;
    --text-muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); padding: 18px; font-size: 13px; }
  
  header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--card-border); padding-bottom: 14px; margin-bottom: 16px; }
  .logo-title h1 { font-size: 22px; font-weight: 800; color: #60a5fa; letter-spacing: -0.5px; display: flex; align-items: center; gap: 8px; }
  .logo-title p { font-size: 12px; color: var(--text-muted); }
  
  .header-actions { display: flex; align-items: center; gap: 10px; }
  .tabs { display: flex; gap: 8px; }
  .tab-btn { background: var(--card-bg); color: var(--text-muted); border: 1px solid var(--card-border); padding: 7px 14px; border-radius: 6px; font-weight: 600; font-size: 12px; cursor: pointer; transition: 0.15s; }
  .tab-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
  
  .btn-calibrate-top { background: #10b981; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; font-weight: 700; font-size: 12px; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: 0.15s; }
  .btn-calibrate-top:hover { background: #059669; }
  
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  
  /* Grid de Tarjetas de Jugadores (Hasta 8 slots) */
  .slots-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 14px; }
  @media (max-width: 900px) { .slots-grid { grid-template-columns: 1fr; } }

  .slot-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px; padding: 14px; border-top: 4px solid var(--card-border); transition: 0.2s; }
  .slot-card.connected { border-top-color: var(--success); }
  
  .slot-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  .slot-tag { font-size: 11px; font-weight: 800; background: #1e293b; padding: 3px 8px; border-radius: 4px; color: #cbd5e1; }
  .slot-card.connected .slot-tag { background: #064e3b; color: #6ee7b7; }
  .slot-title { font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 2px; }
  .slot-sub { font-size: 11.5px; color: var(--text-muted); margin-bottom: 10px; }
  
  .card-inner-tester {
    background: #090e1a;
    border: 1px solid #1c2742;
    border-radius: 8px;
    padding: 10px;
    display: grid;
    grid-template-columns: 150px 1fr;
    gap: 12px;
    align-items: center;
  }
  
  .sticks-box { display: flex; justify-content: space-between; align-items: center; }
  .stick-unit { text-align: center; }
  .stick-circle { width: 62px; height: 62px; border-radius: 50%; border: 1px solid #334155; position: relative; background: #121929; margin: 3px 0; }
  .deadzone-guide { width: 10px; height: 10px; border-radius: 50%; border: 1px dashed rgba(239, 68, 68, 0.6); position: absolute; top: 25px; left: 25px; }
  .stick-dot { width: 14px; height: 14px; border-radius: 50%; background: #3b82f6; position: absolute; top: 24px; left: 24px; box-shadow: 0 0 6px #3b82f6; transition: 0.04s; }
  .stick-label { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }
  .drift-badge { font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 3px; display: inline-block; background: #064e3b; color: #6ee7b7; }
  .drift-badge.drift { background: #78350f; color: #fcd34d; }

  .buttons-cluster { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .dpad-layout { display: grid; grid-template-columns: 20px 20px 20px; grid-template-rows: 20px 20px 20px; gap: 2px; justify-content: center; align-content: center; }
  .face-layout { display: grid; grid-template-columns: 20px 20px 20px; grid-template-rows: 20px 20px 20px; gap: 2px; justify-content: center; align-content: center; }
  
  .btn-chip {
    width: 20px; height: 20px; border-radius: 4px;
    background: #172136; border: 1px solid #293856;
    color: #64748b; font-size: 9px; font-weight: 800;
    display: flex; align-items: center; justify-content: center;
    transition: 0.05s;
  }
  .btn-chip.circle { border-radius: 50%; font-size: 10px; }
  .btn-chip.pressed { background: #3b82f6; color: #ffffff; border-color: #60a5fa; box-shadow: 0 0 8px rgba(59, 130, 246, 0.8); transform: scale(1.1); }
  
  .triggers-row { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .trig-badge { font-size: 10px; font-weight: 700; background: #172136; border: 1px solid #293856; padding: 2px 6px; border-radius: 4px; color: #94a3b8; }
  .trig-badge.pressed { background: #10b981; color: #fff; border-color: #34d399; }
  
  .card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 11px; }
  .btn-small { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: 4px 10px; border-radius: 4px; font-size: 11px; cursor: pointer; text-decoration: none; font-weight: 600; }
  .btn-small:hover { background: #334155; color: #fff; }

  .btn { background: var(--primary); color: #fff; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }
  table { width: 100%; border-collapse: collapse; margin-top: 15px; }
  th { text-align: left; padding: 9px; background: #151e32; color: var(--text-muted); border-bottom: 1px solid var(--card-border); font-size: 12px; }
  td { padding: 9px; border-bottom: 1px solid var(--card-border); font-size: 12px; }
</style>
</head>
<body>

<header>
  <div class="logo-title">
    <h1>🎮 Resiticks</h1>
    <p>Hub Universal de Joysticks & Puente Multi-Jugador (Hasta 8 Jugadores)</p>
  </div>
  <div class="header-actions">
    <button class="btn-calibrate-top" onclick="launchCalibration()">➕ Calibrar Nuevo Mando</button>
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('tab-dashboard')">🏟️ Partida en Vivo (8 Slots)</button>
      <button class="tab-btn" onclick="switchTab('tab-profiles')">📁 Biblioteca de Amigos</button>
    </div>
  </div>
</header>

<div id="tab-dashboard" class="tab-content active">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
    <div>
      <span style="font-size: 12.5px; color: var(--text-muted);">Estado del Motor:</span>
      <span style="color: #34d399; font-weight: 700; margin-left: 5px;">🟢 ACTIVO (8 Slots Disponibles para PES 6 / Torneos)</span>
    </div>
    <div style="font-size: 11.5px; color: var(--text-muted);">
      💡 Presioná botones o palancas en cualquier mando para ver el diagnóstico en vivo
    </div>
  </div>

  <div class="slots-grid" id="slots-container"></div>
</div>

<div id="tab-profiles" class="tab-content">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
    <div>
      <h2 style="font-size: 18px; color: #fff;">Biblioteca de Mandos Guardados</h2>
      <p style="color: var(--text-muted); font-size: 12px;">Mandos calibrados y listos para conectar y jugar sin configurar nada.</p>
    </div>
    <div style="display: flex; gap: 10px;">
      <button class="btn" style="background: #3b82f6;" onclick="launchCalibration()">➕ Calibrar Nuevo</button>
      <a href="/api/export_pack" class="btn" style="background: #10b981;">📦 Descargar Pack ZIP para Amigos</a>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Nombre del Joystick</th>
        <th>Hardware VID:PID</th>
        <th>Estado</th>
      </tr>
    </thead>
    <tbody id="profiles-body"></tbody>
  </table>
</div>

<script>
  function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    event.target.classList.add('active');
  }

  async function launchCalibration() {
    try {
      await fetch('/api/calibrate/launch', { method: 'POST' });
    } catch(e) {
      alert('Error abriendo el asistente de calibración.');
    }
  }

  function renderSlot(slot, item, inp) {
    if (!item) {
      return `
        <div class="slot-card">
          <div class="slot-header">
            <span class="slot-tag">JUGADOR ${slot} [P${slot}]</span>
            <span style="font-size: 11px; color: #64748b;">DISPONIBLE</span>
          </div>
          <div class="slot-title" style="color: #64748b;">(Slot Libre)</div>
          <div class="slot-sub">Enchufá cualquier joystick para tomar el Jugador ${slot}.</div>
          <div class="card-inner-tester" style="opacity: 0.3; text-align: center; display: block; padding: 25px 10px; color: #64748b;">
            Esperando mando de amigo...
          </div>
        </div>
      `;
    }

    const btns = inp.buttons || {};
    const lx = inp.lx !== undefined ? inp.lx : 0;
    const ly = inp.ly !== undefined ? inp.ly : 0;
    const rx = inp.rx !== undefined ? inp.rx : 0;
    const ry = inp.ry !== undefined ? inp.ry : 0;
    const lt = inp.lt || 0;
    const rt = inp.rt || 0;

    const driftL = (Math.abs(lx) > 0.08 || Math.abs(ly) > 0.08);
    const driftR = (Math.abs(rx) > 0.08 || Math.abs(ry) > 0.08);

    return `
      <div class="slot-card connected">
        <div class="slot-header">
          <span class="slot-tag">JUGADOR ${slot} [P${slot}]</span>
          <span style="font-size: 11px; color: #34d399; font-weight: 700;">🟢 CONECTADO</span>
        </div>
        <div class="slot-title">🎮 ${item.name}</div>
        <div class="slot-sub">Hardware: <code>${item.vendor}:${item.product}</code> • Asignado a Xbox 360 (Player ${slot})</div>
        
        <div class="card-inner-tester">
          <div class="sticks-box">
            <div class="stick-unit">
              <div class="stick-label">Stick Izq</div>
              <div class="stick-circle">
                <div class="deadzone-guide"></div>
                <div class="stick-dot" style="transform: translate(${lx * 23}px, ${ly * 23}px);"></div>
              </div>
              <span class="drift-badge ${driftL ? 'drift' : ''}">${driftL ? '⚠️ Moviendo' : 'Drift: OK'}</span>
            </div>
            
            <div class="stick-unit">
              <div class="stick-label">Stick Der</div>
              <div class="stick-circle">
                <div class="deadzone-guide"></div>
                <div class="stick-dot" style="transform: translate(${rx * 23}px, ${ry * 23}px);"></div>
              </div>
              <span class="drift-badge ${driftR ? 'drift' : ''}">${driftR ? '⚠️ Moviendo' : 'Drift: OK'}</span>
            </div>
          </div>

          <div>
            <div class="triggers-row">
              <span class="trig-badge ${btns.lb ? 'pressed' : ''}">LB</span>
              <span class="trig-badge ${lt > 15 ? 'pressed' : ''}">LT ${lt}%</span>
              <span class="trig-badge ${rt > 15 ? 'pressed' : ''}">RT ${rt}%</span>
              <span class="trig-badge ${btns.rb ? 'pressed' : ''}">RB</span>
            </div>

            <div class="buttons-cluster">
              <div class="dpad-layout">
                <div></div>
                <div class="btn-chip ${btns.dpup ? 'pressed' : ''}">▲</div>
                <div></div>
                <div class="btn-chip ${btns.dpleft ? 'pressed' : ''}">◀</div>
                <div class="btn-chip" style="font-size: 7px; color: #475569;">+</div>
                <div class="btn-chip ${btns.dpright ? 'pressed' : ''}">▶</div>
                <div></div>
                <div class="btn-chip ${btns.dpdown ? 'pressed' : ''}">▼</div>
                <div></div>
              </div>

              <div class="face-layout">
                <div></div>
                <div class="btn-chip circle ${btns.y ? 'pressed' : ''}">Y</div>
                <div></div>
                <div class="btn-chip circle ${btns.x ? 'pressed' : ''}">X</div>
                <div class="btn-chip circle" style="font-size: 8px; color: #475569;">Xbox</div>
                <div class="btn-chip circle ${btns.b ? 'pressed' : ''}">B</div>
                <div></div>
                <div class="btn-chip circle ${btns.a ? 'pressed' : ''}">A</div>
                <div></div>
              </div>
            </div>

            <div style="display: flex; justify-content: space-around; margin-top: 6px; font-size: 10px;">
              <span class="trig-badge ${btns.back ? 'pressed' : ''}">SELECT</span>
              <span class="trig-badge ${btns.thumbl ? 'pressed' : ''}">L3</span>
              <span class="trig-badge ${btns.thumbr ? 'pressed' : ''}">R3</span>
              <span class="trig-badge ${btns.start ? 'pressed' : ''}">START</span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <span style="color: #6ee7b7; font-weight: 600;">✓ Mando Calibrado</span>
          <button class="btn-small" onclick="launchCalibration()">⚙️ Recalibrar</button>
        </div>
      </div>
    `;
  }

  async function updateDashboard() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      
      const container = document.getElementById('slots-container');
      let html = '';
      for (let slot = 1; slot <= 8; slot++) {
        const item = data.active_slots[slot];
        const inp = data.live_inputs[slot] || {};
        html += renderSlot(slot, item, inp);
      }
      container.innerHTML = html;
    } catch (e) {}
  }

  async function loadProfilesList() {
    try {
      const res = await fetch('/api/profiles');
      const profiles = await res.json();
      const body = document.getElementById('profiles-body');
      let html = '';
      for (const p of profiles) {
        html += `
          <tr>
            <td><strong>🎮 ${p.name}</strong></td>
            <td><code>${p.vendor}:${p.product}</code></td>
            <td><span class="slot-tag" style="background: #064e3b; color: #6ee7b7;">Listo para Usar</span></td>
          </tr>
        `;
      }
      body.innerHTML = html;
    } catch(e) {}
  }

  setInterval(updateDashboard, 70);
  loadProfilesList();
</script>

</body>
</html>
"""

class ResiticksHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/calibrate/launch":
            term = "alacritty" if os.path.exists("/usr/bin/alacritty") else "kitty"
            subprocess.Popen([term, "-e", "python3", os.path.join(BASE_DIR, "calibrate.py")])
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "launched"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/" or url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))

        elif url.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with state.lock:
                data = {
                    "bridge_enabled": state.bridge_enabled,
                    "active_slots": state.active_slots,
                    "live_inputs": state.live_inputs
                }
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif url.path == "/api/profiles":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            profiles = load_profiles()
            plist = [{"name": p.get("name"), "vendor": p.get("vendor"), "product": p.get("product")} for p in profiles.values()]
            self.wfile.write(json.dumps(plist).encode("utf-8"))

        elif url.path == "/api/export_pack":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in glob.glob(os.path.join(PROFILES_DIR, "*.json")):
                    zf.write(p, arcname=os.path.join("profiles", os.path.basename(p)))
                zf.write(os.path.join(BASE_DIR, "bridge.py"), arcname="bridge.py")
                zf.write(os.path.join(BASE_DIR, "virtual_xbox.py"), arcname="virtual_xbox.py")
                zf.write(os.path.join(BASE_DIR, "calibrate.py"), arcname="calibrate.py")
            buf.seek(0)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="resiticks_amigos_pack.zip"')
            self.end_headers()
            self.wfile.write(buf.read())

        else:
            self.send_response(404)
            self.end_headers()

def main():
    print("=" * 65)
    print(" 🎮 Resiticks — Hub de Joysticks (8 Jugadores)")
    print("=" * 65)

    sup_thread = threading.Thread(target=device_supervisor, daemon=True)
    sup_thread.start()

    server = HTTPServer(("127.0.0.1", 8765), ResiticksHTTPHandler)
    print(" 🚀 Servidor Resiticks corriendo en: http://127.0.0.1:8765")

    try:
        subprocess.Popen(["chromium", "--app=http://127.0.0.1:8765", "--window-size=1040,780"])
    except Exception as e:
        print(f"Abrí http://127.0.0.1:8765: {e}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Cerrando Resiticks...")
        for w in state.workers.values():
            w.stop()
        print("✅ Mandos liberados.")

if __name__ == "__main__":
    main()
