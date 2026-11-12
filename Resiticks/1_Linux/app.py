#!/usr/bin/env python3
"""
Resiticks — Universal Multi-Player Gamepad Hub & Xbox 360 Bridge (Linux).
Manages up to 8 virtual Xbox 360 controllers via /dev/uinput with EVIOCGRAB,
anti-drift tuning, live web calibration, rumble passthrough, and slot management.
"""
import argparse
import copy
import errno
import fcntl
import glob
import io
import json
import os
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from calibration_core import (
    CALIBRATION_STEPS,
    derive_canonical_axes,
    detect_digital_mode_warning,
    detect_input_event,
    is_axis_at_rest,
    validate_calibration_consistency,
)
from evdev_utils import (
    EVIOCGRAB,
    EVENT_FORMAT,
    EVENT_SIZE,
    delete_profile,
    detect_terminal_cmd,
    diagnose_system,
    get_abs_info,
    get_connected_gamepads,
    get_ff_support,
    launch_browser_url,
    load_config,
    load_profiles,
    normalize_profile_data,
    resolve_app_root,
    resolve_profiles_dir,
    save_config,
    save_profile,
)
from virtual_xbox import (
    ABS_HAT0X,
    ABS_HAT0Y,
    ABS_RX,
    ABS_RY,
    ABS_X,
    ABS_Y,
    ABS_Z,
    ABS_RZ,
    BTN_A,
    BTN_B,
    BTN_MODE,
    BTN_SELECT,
    BTN_START,
    BTN_THUMBL,
    BTN_THUMBR,
    BTN_TL,
    BTN_TR,
    BTN_X,
    BTN_Y,
    EV_ABS,
    EV_KEY,
    EV_SYN,
    SYN_REPORT,
    VirtualXboxPad,
)
from web_ui import HTML_PAGE

MAX_SLOTS = 8
MAX_GITHUB_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_PROFILE_JSON_BYTES = 256 * 1024
PROFILE_FILENAME_RE = re.compile(r"^[0-9a-f]{4}_[0-9a-f]{4}\.json$")
ALLOWED_LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}
GITHUB_ARCHIVE_URL = "https://github.com/ulibanus/Resiticks/archive/refs/heads/main.tar.gz"


class ResiticksState:
    """Thread-safe central state shared between supervisor, workers, and HTTP handlers."""

    def __init__(self):
        cfg = load_config()
        self.lock = threading.Lock()
        self.supervisor_wakeup = threading.Event()
        self.shutdown_event = threading.Event()
        self.bridge_enabled = bool(cfg.get("bridge_enabled", True))
        self.slot_pins = dict(cfg.get("slot_pins", {}))
        self.slot_overrides = {}  # identifier -> forced slot 1..8
        self.active_slots = {i: None for i in range(1, MAX_SLOTS + 1)}
        self.live_inputs = {i: {} for i in range(1, MAX_SLOTS + 1)}
        self.connected_devices = []
        self.device_errors = {}
        self.paused_devices = set()  # dev_path or identifier paused for calibration
        self.workers = {}  # identifier -> GamepadWorker
        self.profile_revision = 0
        self.cal_launch_proc = None


state = ResiticksState()


class CalibrationSession:
    """Interactive non-blocking Web UI calibration session for a single physical gamepad."""

    def __init__(self):
        self.lock = threading.Lock()
        self.active = False
        self.dev_info = None
        self.fd = None
        self.abs_info = {}
        self.step_idx = 0
        self.mapping = {}
        self.waiting_neutral = False
        self.live_abs = {}
        self.held_keys = set()
        self.pending_warning = None
        self.pending_detected = None

    def start(self, dev_path):
        """Pause any active worker on dev_path and open raw evdev for calibration."""
        self.cancel()
        connected = get_connected_gamepads()
        dev_info = next((g for g in connected if g["dev_path"] == dev_path), None)
        if not dev_info:
            raise FileNotFoundError(f"Dispositivo no encontrado: {dev_path}")

        ident = dev_info["identifier"]
        with state.lock:
            state.paused_devices.add(dev_path)
            state.paused_devices.add(ident)
            existing = state.workers.pop(ident, None)
        state.supervisor_wakeup.set()

        if existing is not None:
            existing.stop(wait=True)
        time.sleep(0.12)

        try:
            fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
        except PermissionError as exc:
            with state.lock:
                state.paused_devices.discard(dev_path)
                state.paused_devices.discard(ident)
            state.supervisor_wakeup.set()
            raise PermissionError(
                f"Sin permiso para leer {dev_path}. Verificá pertenecer al grupo 'input'."
            ) from exc

        abs_info = get_abs_info(fd)
        with self.lock:
            self.active = True
            self.dev_info = dev_info
            self.fd = fd
            self.abs_info = abs_info
            self.step_idx = 0
            self.mapping = {}
            self.waiting_neutral = True
            self.live_abs = {c: v.get("val", 0) for c, v in abs_info.items()}
            self.held_keys = set()
            self.pending_warning = None
            self.pending_detected = None
            return self.snapshot_locked()

    def _drain_fd_locked(self):
        """Read pending raw events non-blockingly and return newly read event tuples."""
        events = []
        if self.fd is None:
            return events
        while True:
            try:
                raw = os.read(self.fd, EVENT_SIZE * 32)
                if not raw:
                    break
                n = len(raw) // EVENT_SIZE
                for i in range(n):
                    _, _, ev_t, code, val = struct.unpack(
                        EVENT_FORMAT, raw[i * EVENT_SIZE : (i + 1) * EVENT_SIZE]
                    )
                    if ev_t == EV_KEY:
                        if val == 0:
                            self.held_keys.discard(code)
                        else:
                            self.held_keys.add(code)
                    elif ev_t == EV_ABS:
                        self.live_abs[code] = val
                    events.append((ev_t, code, val))
            except BlockingIOError:
                break
            except OSError:
                break
        return events

    def poll(self):
        """Poll calibration hardware non-blockingly, gating step progression via neutral return."""
        with self.lock:
            if not self.active or self.fd is None:
                return {"active": False}
            if self.step_idx >= len(CALIBRATION_STEPS):
                return self.snapshot_locked()

            events = self._drain_fd_locked()
            if self.pending_warning is not None:
                return self.snapshot_locked()

            if self.waiting_neutral:
                all_rest = all(
                    is_axis_at_rest(c, v, self.abs_info) for c, v in self.live_abs.items()
                )
                if not self.held_keys and all_rest:
                    self.waiting_neutral = False
                return self.snapshot_locked()

            step = CALIBRATION_STEPS[self.step_idx]
            for ev_t, code, val in events:
                detected = detect_input_event(ev_t, code, val, self.abs_info)
                if not detected:
                    continue
                warn = detect_digital_mode_warning(step["key"], detected)
                if warn:
                    self.pending_warning = warn
                    self.pending_detected = detected
                    return self.snapshot_locked()

                self.mapping[step["key"]] = detected
                self.step_idx += 1
                self.waiting_neutral = True
                break

            return self.snapshot_locked()

    def skip_step(self):
        """Skip the current optional calibration step."""
        with self.lock:
            if not self.active or self.step_idx >= len(CALIBRATION_STEPS):
                return self.snapshot_locked()
            step = CALIBRATION_STEPS[self.step_idx]
            if step["allow_skip"]:
                self.mapping.pop(step["key"], None)
                self.pending_warning = None
                self.pending_detected = None
                self.step_idx += 1
                self.waiting_neutral = True
            return self.snapshot_locked()

    def prev_step(self):
        """Step backward cleanly to recalibrate the previous control."""
        with self.lock:
            if not self.active:
                return {"active": False}
            self.pending_warning = None
            self.pending_detected = None
            if self.step_idx > 0:
                self.step_idx -= 1
                self.mapping.pop(CALIBRATION_STEPS[self.step_idx]["key"], None)
                self.waiting_neutral = True
            return self.snapshot_locked()

    def accept_warning(self):
        """Accept a detected input even though a Digital Mode warning was raised."""
        with self.lock:
            if not self.active or not self.pending_detected or self.step_idx >= len(CALIBRATION_STEPS):
                return self.snapshot_locked()
            step = CALIBRATION_STEPS[self.step_idx]
            self.mapping[step["key"]] = self.pending_detected
            self.pending_warning = None
            self.pending_detected = None
            self.step_idx += 1
            self.waiting_neutral = True
            return self.snapshot_locked()

    def save(self, custom_name):
        """Finalize canonical axes, persist JSON profile, bump revision, and resume device."""
        with self.lock:
            if not self.active or not self.dev_info:
                raise RuntimeError("No hay calibración activa")
            hw_name = self.dev_info.get("name", "Mando Genérico")
            final_name = (custom_name or "").strip() or hw_name
            final_mapping = derive_canonical_axes(self.mapping)
            profile = {
                "name": final_name,
                "hardware_name": hw_name,
                "vendor": self.dev_info.get("vendor", "0000"),
                "product": self.dev_info.get("product", "0000"),
                "mapping": final_mapping,
            }
            out_path = save_profile(profile)
        with state.lock:
            state.profile_revision += 1
        self.cancel()
        return {"saved": True, "path": out_path, "name": final_name}

    def cancel(self):
        """Close raw calibration fd and release paused state so device returns to live slots."""
        with self.lock:
            fd = self.fd
            dev_info = self.dev_info
            self.active = False
            self.fd = None
            self.dev_info = None
            self.pending_warning = None
            self.pending_detected = None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if dev_info is not None:
            with state.lock:
                state.paused_devices.discard(dev_info.get("dev_path"))
                state.paused_devices.discard(dev_info.get("identifier"))
            state.supervisor_wakeup.set()

    def snapshot_locked(self):
        """Return UI-friendly representation of the current calibration state."""
        completed = self.step_idx >= len(CALIBRATION_STEPS)
        final_map = derive_canonical_axes(self.mapping) if completed else self.mapping
        return {
            "active": self.active,
            "completed": completed,
            "step_idx": self.step_idx,
            "total_steps": len(CALIBRATION_STEPS),
            "current_step": CALIBRATION_STEPS[self.step_idx] if not completed else None,
            "steps": CALIBRATION_STEPS,
            "mapped_keys": list(self.mapping.keys()),
            "warning": self.pending_warning,
            "default_name": (self.dev_info or {}).get("name", "Mando"),
            "warnings": validate_calibration_consistency(final_map) if completed else [],
        }


cal_session = CalibrationSession()


class GamepadWorker(threading.Thread):
    """Per-controller worker thread reading evdev events and driving VirtualXboxPad."""

    def __init__(self, dev_info, profile, player_num, bridge_mode=True):
        super().__init__(daemon=True)
        self.dev_info = dev_info
        self.identifier = dev_info["identifier"]
        self.player_num = player_num
        self.bridge_mode = bool(bridge_mode)
        self._stop_event = threading.Event()
        self._cfg_lock = threading.Lock()
        self._cleaned_up = False

        self.dev_fd = None
        self.vpad = None
        self.phys_rw = False
        self.phys_ff = False
        self.abs_info = {}

        self.btn_map = {}
        self.hat_map = {}
        self.axis_map = {}
        self.axis_dpad_map = {}
        self.dpad_state = {"x": 0, "y": 0}
        self.deadzone_left = 0.05
        self.deadzone_right = 0.05
        self.center_offset = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}
        self.rumble_enabled = True
        self.profile = copy.deepcopy(profile)
        self._compile_profile(self.profile)

        self.live_state = {
            "lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0,
            "raw_lx": 0.0, "raw_ly": 0.0, "raw_rx": 0.0, "raw_ry": 0.0,
            "lt": 0, "rt": 0,
            "polling_hz": 0,
            "buttons": {
                "a": False, "b": False, "x": False, "y": False,
                "lb": False, "rb": False, "lt": False, "rt": False,
                "back": False, "start": False, "guide": False,
                "thumbl": False, "thumbr": False,
                "dpup": False, "dpdown": False, "dpleft": False, "dpright": False,
            },
        }
        self._syn_count = 0
        self._hz_window_start = time.monotonic()

    def _compile_profile(self, profile):
        """Parse profile mapping, deadzone, center offsets, and rumble flag under _cfg_lock."""
        btn_map = {}
        hat_map = {}
        axis_map = {}
        axis_dpad_map = {}
        mapping = profile.get("mapping", {})

        for target, data in mapping.items():
            if not isinstance(data, dict):
                continue
            t_type = data.get("type")
            code = data.get("code")
            if code is None:
                continue
            if t_type == "btn":
                btn_map[code] = target
            elif t_type == "hat":
                hat_map[(code, data.get("value"))] = target
            elif t_type == "axis" and target in ("dpup", "dpdown", "dpleft", "dpright"):
                axis_dpad_map.setdefault(code, []).append((target, data.get("direction", 1)))

        canonical_axes = ("leftx", "lefty", "rightx", "righty", "lt", "rt")
        for target in canonical_axes:
            data = mapping.get(target)
            if isinstance(data, dict) and data.get("type") == "axis":
                axis_map[data.get("code")] = (target, data.get("direction", 1))

        # Safe fallback for legacy profiles lacking canonical keys
        legacy = [
            ("leftx", "left_right", 1),
            ("lefty", "left_down", 1),
            ("rightx", "right_right", 1),
            ("righty", "right_down", 1),
        ]
        for canon, dir_key, default_dir in legacy:
            if canon not in mapping and isinstance(mapping.get(dir_key), dict):
                d = mapping[dir_key]
                if d.get("type") == "axis" and d.get("code") is not None:
                    axis_map[d["code"]] = (canon, d.get("direction", default_dir))

        with self._cfg_lock:
            self.profile = copy.deepcopy(profile)
            self.btn_map = btn_map
            self.hat_map = hat_map
            self.axis_map = axis_map
            self.axis_dpad_map = axis_dpad_map
            self.deadzone_left = float(profile.get("deadzone_left", 0.05))
            self.deadzone_right = float(profile.get("deadzone_right", 0.05))
            co = profile.get("center_offset") or {}
            self.center_offset = {
                "lx": float(co.get("lx", 0.0)),
                "ly": float(co.get("ly", 0.0)),
                "rx": float(co.get("rx", 0.0)),
                "ry": float(co.get("ry", 0.0)),
            }
            self.rumble_enabled = bool(profile.get("rumble_enabled", True))

    def hot_reload_profile(self, profile):
        """Apply updated deadzones, center offsets, or mappings in-place if device active."""
        self._compile_profile(profile)
        with state.lock:
            slot_info = state.active_slots.get(self.player_num)
            if slot_info and slot_info.get("identifier") == self.identifier:
                slot_info["name"] = self.profile.get("name")
                slot_info["deadzone_left"] = self.deadzone_left
                slot_info["deadzone_right"] = self.deadzone_right
                slot_info["rumble_enabled"] = self.rumble_enabled

    def _open_physical_device(self, dev_path):
        """Open evdev device (preferring RW for rumble) and apply EVIOCGRAB if bridge_mode."""
        last_err = None
        for _ in range(5):
            if self._stop_event.is_set():
                return False
            fd = None
            try:
                try:
                    fd = os.open(dev_path, os.O_RDWR | os.O_NONBLOCK)
                    self.phys_rw = True
                except PermissionError:
                    fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
                    self.phys_rw = False

                if self.bridge_mode:
                    fcntl.ioctl(fd, EVIOCGRAB, 1)

                self.dev_fd = fd
                self.abs_info = get_abs_info(fd)
                self.phys_ff = self.phys_rw and get_ff_support(fd)
                return True
            except Exception as exc:
                last_err = exc
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                time.sleep(0.15)

        msg = f"{self.dev_info.get('name', dev_path)} ({dev_path}): {last_err}"
        print(f"[Worker P{self.player_num}] Error abriendo dispositivo: {msg}", file=sys.stderr)
        with state.lock:
            state.device_errors[self.identifier] = msg
        return False

    def _handle_key_event(self, code, value):
        """Translate physical EV_KEY presses (including autorepeat value=2) to Xbox outputs."""
        with self._cfg_lock:
            target = self.btn_map.get(code)
        if not target:
            return

        is_pressed = (value != 0)
        self.live_state["buttons"][target] = is_pressed

        if target == "lt":
            self.live_state["lt"] = 100 if is_pressed else 0
            if self.vpad:
                self.vpad.emit_abs(ABS_Z, 255 if is_pressed else 0)
            return
        if target == "rt":
            self.live_state["rt"] = 100 if is_pressed else 0
            if self.vpad:
                self.vpad.emit_abs(ABS_RZ, 255 if is_pressed else 0)
            return

        if target == "dpup":
            self.dpad_state["y"] = -1 if is_pressed else (0 if self.dpad_state["y"] == -1 else self.dpad_state["y"])
            if self.vpad:
                self.vpad.emit_abs(ABS_HAT0Y, self.dpad_state["y"])
            return
        if target == "dpdown":
            self.dpad_state["y"] = 1 if is_pressed else (0 if self.dpad_state["y"] == 1 else self.dpad_state["y"])
            if self.vpad:
                self.vpad.emit_abs(ABS_HAT0Y, self.dpad_state["y"])
            return
        if target == "dpleft":
            self.dpad_state["x"] = -1 if is_pressed else (0 if self.dpad_state["x"] == -1 else self.dpad_state["x"])
            if self.vpad:
                self.vpad.emit_abs(ABS_HAT0X, self.dpad_state["x"])
            return
        if target == "dpright":
            self.dpad_state["x"] = 1 if is_pressed else (0 if self.dpad_state["x"] == 1 else self.dpad_state["x"])
            if self.vpad:
                self.vpad.emit_abs(ABS_HAT0X, self.dpad_state["x"])
            return

        if not self.vpad:
            return

        btn_lookup = {
            "a": BTN_A, "b": BTN_B, "x": BTN_X, "y": BTN_Y,
            "lb": BTN_TL, "rb": BTN_TR, "back": BTN_SELECT, "start": BTN_START,
            "guide": BTN_MODE, "thumbl": BTN_THUMBL, "thumbr": BTN_THUMBR,
        }
        xbox_btn = btn_lookup.get(target)
        if xbox_btn is not None:
            self.vpad.emit_key(xbox_btn, is_pressed)

    def _handle_abs_event(self, code, value):
        """Translate D-Pad hats, axis D-Pads, triggers, and deadzone-compensated sticks."""
        with self._cfg_lock:
            hat_target = self.hat_map.get((code, value))
            hat_alt_pos = self.hat_map.get((code, 1)) or self.hat_map.get((code, -1))
            axis_dpad = self.axis_dpad_map.get(code)
            axis_spec = self.axis_map.get(code)
            dz_l = self.deadzone_left
            dz_r = self.deadzone_right
            offsets = self.center_offset

        if hat_target or (hat_alt_pos and value == 0) or code in (ABS_HAT0X, ABS_HAT0Y):
            if code == ABS_HAT0X or hat_target in ("dpleft", "dpright"):
                self.live_state["buttons"]["dpleft"] = (value < 0)
                self.live_state["buttons"]["dpright"] = (value > 0)
                if self.vpad:
                    self.vpad.emit_abs(ABS_HAT0X, -1 if value < 0 else (1 if value > 0 else 0))
                return
            if code == ABS_HAT0Y or hat_target in ("dpup", "dpdown"):
                self.live_state["buttons"]["dpup"] = (value < 0)
                self.live_state["buttons"]["dpdown"] = (value > 0)
                if self.vpad:
                    self.vpad.emit_abs(ABS_HAT0Y, -1 if value < 0 else (1 if value > 0 else 0))
                return

        if axis_dpad:
            info = self.abs_info.get(code, {"min": 0, "max": 255})
            mid = (info["min"] + info["max"]) / 2.0
            span = max(1.0, (info["max"] - info["min"]) / 2.0)
            norm = (value - mid) / span
            for target, direction in axis_dpad:
                pressed = (norm * direction) > 0.5
                self.live_state["buttons"][target] = pressed
                if target == "dpup" and pressed:
                    self.dpad_state["y"] = -1
                elif target == "dpdown" and pressed:
                    self.dpad_state["y"] = 1
                elif target in ("dpup", "dpdown") and not self.live_state["buttons"]["dpup"] and not self.live_state["buttons"]["dpdown"]:
                    self.dpad_state["y"] = 0
                elif target == "dpleft" and pressed:
                    self.dpad_state["x"] = -1
                elif target == "dpright" and pressed:
                    self.dpad_state["x"] = 1
                elif target in ("dpleft", "dpright") and not self.live_state["buttons"]["dpleft"] and not self.live_state["buttons"]["dpright"]:
                    self.dpad_state["x"] = 0
            if self.vpad:
                self.vpad.emit_abs(ABS_HAT0X, self.dpad_state["x"])
                self.vpad.emit_abs(ABS_HAT0Y, self.dpad_state["y"])
            return

        if not axis_spec:
            return

        target, direction = axis_spec
        info = self.abs_info.get(code, {"min": 0, "max": 255})
        val_min, val_max = info["min"], info["max"]

        if target in ("lt", "rt"):
            span = max(1, val_max - val_min)
            trig_norm = max(0.0, min(1.0, (value - val_min) / span))
            trig_val = int(trig_norm * 255)
            pct = int(trig_norm * 100)
            self.live_state[target] = pct
            self.live_state["buttons"][target] = (pct > 15)
            if self.vpad:
                self.vpad.emit_abs(ABS_Z if target == "lt" else ABS_RZ, trig_val)
            return

        mid = (val_min + val_max) / 2.0
        span = (val_max - val_min) / 2.0
        if span <= 0:
            return

        axis_key_map = {
            "leftx": ("lx", ABS_X, dz_l),
            "lefty": ("ly", ABS_Y, dz_l),
            "rightx": ("rx", ABS_RX, dz_r),
            "righty": ("ry", ABS_RY, dz_r),
        }
        spec = axis_key_map.get(target)
        if not spec:
            return
        live_key, xbox_code, dz = spec

        raw_norm = ((value - mid) / span) * direction
        adj = max(-1.0, min(1.0, raw_norm - offsets.get(live_key, 0.0)))
        self.live_state["raw_" + live_key] = round(raw_norm, 3)
        self.live_state[live_key] = round(adj, 2)

        if abs(adj) < dz:
            scaled = 0.0
        else:
            # Smoothly rescale remaining travel so 100% reach is preserved for larger deadzones
            scaled = ((abs(adj) - dz) / max(0.01, 1.0 - dz)) * (1.0 if adj > 0 else -1.0)
        xbox_val = int(max(-1.0, min(1.0, scaled)) * 32767)
        if self.vpad:
            self.vpad.emit_abs(xbox_code, xbox_val)

    def run(self):
        """Main worker loop: open device, register virtual pad, and relay input/rumble events."""
        dev_path = self.dev_info["dev_path"]
        try:
            if not self._open_physical_device(dev_path):
                return

            if self.bridge_mode:
                try:
                    self.vpad = VirtualXboxPad(
                        self.player_num,
                        custom_name=self.profile.get("name"),
                        enable_rumble=True,
                    )
                except Exception as exc:
                    msg = f"No se pudo crear mando virtual /dev/uinput: {exc}"
                    print(f"[Worker P{self.player_num}] {msg}", file=sys.stderr)
                    with state.lock:
                        state.device_errors[self.identifier] = msg
                    return

            with state.lock:
                state.device_errors.pop(self.identifier, None)
                state.active_slots[self.player_num] = {
                    "name": self.profile.get("name"),
                    "vendor": self.profile.get("vendor"),
                    "product": self.profile.get("product"),
                    "dev_path": dev_path,
                    "identifier": self.identifier,
                    "pin_key": self.dev_info.get("pin_key", ""),
                    "player_num": self.player_num,
                    "deadzone_left": self.deadzone_left,
                    "deadzone_right": self.deadzone_right,
                    "rumble_enabled": self.rumble_enabled,
                }
                state.live_inputs[self.player_num] = copy.deepcopy(self.live_state)

            while not self._stop_event.is_set():
                fd = self.dev_fd
                if fd is None:
                    break
                watch_fds = [fd]
                if self.vpad is not None and self.vpad.fd is not None and self.vpad.enable_rumble:
                    watch_fds.append(self.vpad.fd)

                try:
                    readable, _, _ = select.select(watch_fds, [], [], 0.05)
                except (ValueError, OSError):
                    break
                if not readable:
                    continue

                if self.vpad is not None and self.vpad.fd in readable:
                    with self._cfg_lock:
                        fwd_rumble = self.rumble_enabled and self.phys_ff
                    self.vpad.handle_ff_events(phys_fd=fd, forward_rumble=fwd_rumble)

                if fd not in readable:
                    continue

                try:
                    data = os.read(fd, EVENT_SIZE * 32)
                except BlockingIOError:
                    continue
                except (OSError, TypeError):
                    break

                if not data:
                    break

                num_events = len(data) // EVENT_SIZE
                saw_syn = False
                for i in range(num_events):
                    ev = data[i * EVENT_SIZE : (i + 1) * EVENT_SIZE]
                    _, _, ev_type, code, value = struct.unpack(EVENT_FORMAT, ev)
                    if ev_type == EV_KEY:
                        self._handle_key_event(code, value)
                    elif ev_type == EV_ABS:
                        self._handle_abs_event(code, value)
                    elif ev_type == EV_SYN and code == SYN_REPORT:
                        saw_syn = True
                        self._syn_count += 1
                        if self.vpad is not None:
                            self.vpad.sync()

                if not saw_syn:
                    self._syn_count += 1
                now_hz = time.monotonic()
                elapsed_hz = now_hz - self._hz_window_start
                if elapsed_hz >= 0.5:
                    self.live_state["polling_hz"] = int(round(self._syn_count / elapsed_hz))
                    self._syn_count = 0
                    self._hz_window_start = now_hz

                if self.vpad is not None:
                    self.vpad.sync()

                with state.lock:
                    if state.active_slots.get(self.player_num, {}) and state.active_slots[self.player_num].get("identifier") == self.identifier:
                        state.live_inputs[self.player_num] = copy.deepcopy(self.live_state)
        finally:
            self._cleanup_once()

    def _cleanup_once(self):
        """Release grab, descriptors, and slot references strictly once on worker exit."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        self._stop_event.set()

        with state.lock:
            cur = state.active_slots.get(self.player_num)
            if cur and cur.get("identifier") == self.identifier:
                state.active_slots[self.player_num] = None
                state.live_inputs[self.player_num] = {}

        fd = self.dev_fd
        self.dev_fd = None
        if fd is not None:
            if self.bridge_mode:
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, 0)
                except OSError:
                    pass
            try:
                os.close(fd)
            except OSError:
                pass

        vpad = self.vpad
        self.vpad = None
        if vpad is not None:
            vpad.close()

    def stop(self, wait=True):
        """Signal loop termination and optionally join worker thread so resources close cleanly."""
        self._stop_event.set()
        if wait and threading.current_thread() is not self and self.is_alive():
            self.join(timeout=1.0)


def _pick_slot_for_device(gp, assigned_slots, slot_overrides, slot_pins):
    """Select preferred override/pinned slot if free, otherwise first free slot 1..MAX_SLOTS."""
    ident = gp["identifier"]
    pin_key = gp.get("pin_key", "")
    preferred = slot_overrides.get(ident) or slot_pins.get(pin_key)
    if preferred and 1 <= preferred <= MAX_SLOTS and preferred not in assigned_slots:
        return preferred
    for slot in range(1, MAX_SLOTS + 1):
        if slot not in assigned_slots:
            return slot
    return None


def device_supervisor():
    """Poll hardware devices, stop disconnected workers, hot-reload profiles, and launch workers."""
    retry_backoff = {}  # identifier -> (fail_count, next_retry_ts)
    last_profile_snapshot = {}

    while not state.shutdown_event.is_set():
        state.supervisor_wakeup.clear()
        try:
            profiles = load_profiles()
            connected = get_connected_gamepads()
            current_by_ident = {gp["identifier"]: gp for gp in connected}

            to_stop = []
            with state.lock:
                state.connected_devices = connected
                bridge_mode = state.bridge_enabled
                paused = set(state.paused_devices)
                slot_overrides = dict(state.slot_overrides)
                slot_pins = dict(state.slot_pins)

                for ident in list(state.workers.keys()):
                    worker = state.workers[ident]
                    gp = current_by_ident.get(ident)
                    must_stop = (
                        not worker.is_alive()
                        or gp is None
                        or ident in paused
                        or gp["dev_path"] in paused
                        or worker.bridge_mode != bridge_mode
                    )
                    if must_stop:
                        to_stop.append(state.workers.pop(ident))
                    else:
                        key = f"{gp['vendor']}:{gp['product']}"
                        if key in profiles:
                            prof_sig = json.dumps({k: v for k, v in profiles[key].items() if not k.startswith("_")}, sort_keys=True)
                            if last_profile_snapshot.get(ident) != prof_sig:
                                worker.hot_reload_profile(profiles[key])
                                last_profile_snapshot[ident] = prof_sig

                for ident in list(state.device_errors.keys()):
                    if ident not in current_by_ident:
                        state.device_errors.pop(ident, None)
                        retry_backoff.pop(ident, None)

            for w in to_stop:
                w.stop(wait=True)

            # Determine slots after clean stops so reassigned/swapped slots reuse cleanly
            now = time.monotonic()
            with state.lock:
                assigned_slots = {w.player_num for w in state.workers.values() if w.is_alive()}
                new_workers = []
                # Process slot overrides and pinned controllers first so manual swaps always win their target slot
                ordered_devices = sorted(
                    connected,
                    key=lambda g: 0 if g["identifier"] in slot_overrides else (1 if g.get("pin_key") in slot_pins else 2),
                )
                for gp in ordered_devices:
                    ident = gp["identifier"]
                    key = f"{gp['vendor']}:{gp['product']}"
                    if ident in state.workers or key not in profiles:
                        continue
                    if ident in state.paused_devices or gp["dev_path"] in state.paused_devices:
                        continue
                    fails, next_ts = retry_backoff.get(ident, (0, 0.0))
                    if now < next_ts:
                        continue

                    slot = _pick_slot_for_device(gp, assigned_slots, slot_overrides, slot_pins)
                    if slot is None:
                        continue
                    assigned_slots.add(slot)
                    worker = GamepadWorker(gp, profiles[key], slot, bridge_mode=bridge_mode)
                    state.workers[ident] = worker
                    last_profile_snapshot[ident] = json.dumps(
                        {k: v for k, v in profiles[key].items() if not k.startswith("_")}, sort_keys=True
                    )
                    new_workers.append((ident, worker))

            for _, worker in new_workers:
                worker.start()

            # Track transient failures for exponential backoff without flooding stderr
            time.sleep(0.05)
            with state.lock:
                for ident, _ in new_workers:
                    if ident in state.device_errors:
                        fails, _ = retry_backoff.get(ident, (0, 0.0))
                        fails = min(fails + 1, 4)
                        retry_backoff[ident] = (fails, time.monotonic() + (1.0 * (2 ** (fails - 1))))
                    elif ident in state.workers and state.workers[ident].is_alive():
                        retry_backoff.pop(ident, None)

        except Exception as exc:
            import traceback
            print(f"[Supervisor] Error en ciclo de detección: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

        state.supervisor_wakeup.wait(timeout=0.75)


def _update_from_github():
    """Update profiles and scripts from ulibanus/Resiticks via git pull or archive download."""
    app_root = resolve_app_root()
    profiles_dir = resolve_profiles_dir()
    repo_root = os.path.dirname(app_root) if os.path.isdir(os.path.join(os.path.dirname(app_root), ".git")) else app_root

    if os.path.isdir(os.path.join(repo_root, ".git")) and shutil.which("git"):
        try:
            subprocess.check_output(["git", "-C", repo_root, "pull", "--ff-only"], stderr=subprocess.STDOUT, timeout=15)
            with state.lock:
                state.profile_revision += 1
            return {"ok": True, "method": "git", "message": "Repositorio actualizado correctamente desde GitHub (git pull)."}
        except subprocess.CalledProcessError as exc:
            # Fallback to profile sync below if local git tree has custom edits
            git_err = exc.output.decode("utf-8", errors="replace").strip()
        except Exception as exc:
            git_err = str(exc)
    else:
        git_err = None

    # Archive download fallback works on ZIP installs and dirty git clones without losing local custom profiles
    req = urllib.request.Request(GITHUB_ARCHIVE_URL, headers={"User-Agent": "Resiticks-Updater"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        tar_bytes = resp.read(MAX_GITHUB_ARCHIVE_BYTES + 1)
    if len(tar_bytes) > MAX_GITHUB_ARCHIVE_BYTES:
        raise ValueError("El archivo descargado de GitHub excede el límite seguro de 20 MB.")

    added = 0
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile() or member.size <= 0 or member.size > MAX_PROFILE_JSON_BYTES:
                continue
            parts = member.name.split("/")
            fname = parts[-1]
            # Expect Resiticks-main/Resiticks/profiles/<4hex>_<4hex>.json
            if "profiles" in parts and PROFILE_FILENAME_RE.fullmatch(fname):
                idx = parts.index("profiles")
                if idx == len(parts) - 2:
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    raw = extracted.read(MAX_PROFILE_JSON_BYTES + 1)
                    if len(raw) > MAX_PROFILE_JSON_BYTES:
                        continue
                    try:
                        parsed = normalize_profile_data(json.loads(raw.decode("utf-8")))
                    except Exception:
                        continue
                    dest = os.path.join(profiles_dir, f"{parsed['vendor']}_{parsed['product']}.json")
                    if not os.path.exists(dest):
                        save_profile(parsed, profiles_dir=profiles_dir)
                        added += 1

    with state.lock:
        state.profile_revision += 1
    extra = f" (nota git: {git_err})" if git_err else ""
    return {
        "ok": True,
        "method": "archive",
        "added": added,
        "message": f"Sincronizado desde GitHub: {added} perfil(es) nuevo(s) descargado(s){extra}.",
    }


def _build_full_export_zip():
    """Bundle complete Resiticks package (Linux, Windows, profiles, updaters, docs) into memory ZIP."""
    app_root = resolve_app_root()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(app_root):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "tests")]
            for fname in sorted(files):
                if fname.endswith((".pyc", ".pyo")) or fname == "resiticks_config.json":
                    continue
                full_path = os.path.join(root, fname)
                if not os.path.isfile(full_path):
                    continue
                rel_path = os.path.relpath(full_path, app_root)
                arc_path = os.path.join("Resiticks", rel_path)
                zinfo = zipfile.ZipInfo.from_file(full_path, arc_path)
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                if fname.endswith(".sh"):
                    zinfo.external_attr = (0o100755 & 0xFFFF) << 16
                with open(full_path, "rb") as src:
                    zf.writestr(zinfo, src.read())
    buf.seek(0)
    return buf.read()


class ResiticksHTTPHandler(BaseHTTPRequestHandler):
    """HTTP API & dashboard request handler for Resiticks."""

    def log_message(self, format, *args):
        pass

    def _is_valid_local_origin(self, require_same_origin=False):
        """Reject DNS rebinding (Host) and cross-origin browser CSRF (Origin/Referer)."""
        host_hdr = self.headers.get("Host", "")
        if host_hdr:
            parsed_host = urllib.parse.urlsplit("//" + host_hdr).hostname or ""
            if parsed_host.lower() not in ALLOWED_LOCAL_HOSTNAMES:
                return False

        if require_same_origin:
            origin = self.headers.get("Origin")
            if origin:
                orig_host = (urllib.parse.urlsplit(origin).hostname or "").lower()
                if orig_host not in ALLOWED_LOCAL_HOSTNAMES:
                    return False
            else:
                referer = self.headers.get("Referer")
                if referer:
                    ref_host = (urllib.parse.urlsplit(referer).hostname or "").lower()
                    if ref_host not in ALLOWED_LOCAL_HOSTNAMES:
                        return False
        return True

    def _send_bytes(self, status, content_type, data_bytes, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data_bytes)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        if data_bytes:
            self.wfile.write(data_bytes)

    def _send_json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, "application/json", body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        if length > 1024 * 1024:
            raise ValueError("Payload demasiado grande")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        if not self._is_valid_local_origin(require_same_origin=True):
            self._send_json(403, {"error": "Origen no permitido"})
            return
        self._send_bytes(204, "text/plain", b"")

    def do_GET(self):
        if not self._is_valid_local_origin(require_same_origin=False):
            self._send_json(403, {"error": "Host local inválido"})
            return
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self._send_bytes(200, "text/html; charset=utf-8", HTML_PAGE.encode("utf-8"))
            return

        if url.path == "/api/status":
            profiles = load_profiles()
            with state.lock:
                connected = copy.deepcopy(state.connected_devices)
                uncalibrated = [
                    gp for gp in connected
                    if f"{gp.get('vendor')}:{gp.get('product')}" not in profiles
                ]
                payload = {
                    "bridge_enabled": state.bridge_enabled,
                    "active_slots": copy.deepcopy(state.active_slots),
                    "live_inputs": copy.deepcopy(state.live_inputs),
                    "connected_devices": connected,
                    "uncalibrated_devices": uncalibrated,
                    "device_errors": copy.deepcopy(state.device_errors),
                    "profile_revision": state.profile_revision,
                }
            self._send_json(200, payload)
            return

        if url.path == "/api/profiles":
            profiles = load_profiles()
            plist = [
                {
                    "name": p.get("name"),
                    "vendor": p.get("vendor"),
                    "product": p.get("product"),
                    "deadzone_left": p.get("deadzone_left", 0.05),
                    "deadzone_right": p.get("deadzone_right", 0.05),
                    "rumble_enabled": p.get("rumble_enabled", True),
                    "center_offset": p.get("center_offset", {}),
                }
                for p in profiles.values()
            ]
            self._send_json(200, plist)
            return

        if url.path == "/api/system/diagnose":
            self._send_json(200, diagnose_system())
            return

        if url.path == "/api/export_pack":
            try:
                zip_bytes = _build_full_export_zip()
                self._send_bytes(
                    200,
                    "application/zip",
                    zip_bytes,
                    {"Content-Disposition": 'attachment; filename="resiticks_amigos_pack.zip"'},
                )
            except Exception as exc:
                self._send_json(500, {"error": f"No se pudo generar ZIP: {exc}"})
            return

        if url.path == "/api/calibrate/web/poll":
            self._send_json(200, cal_session.poll())
            return

        self._send_json(404, {"error": "Endpoint no encontrado"})

    def do_POST(self):
        if not self._is_valid_local_origin(require_same_origin=True):
            self._send_json(403, {"error": "Petición cross-origin bloqueada por seguridad"})
            return
        url = urllib.parse.urlparse(self.path)
        try:
            body = self._read_json_body()
        except Exception as exc:
            self._send_json(400, {"error": f"JSON inválido: {exc}"})
            return

        if url.path == "/api/bridge/toggle":
            with state.lock:
                state.bridge_enabled = not state.bridge_enabled
                enabled = state.bridge_enabled
                pins = dict(state.slot_pins)
            save_config({"bridge_enabled": enabled, "slot_pins": pins})
            state.supervisor_wakeup.set()
            self._send_json(200, {"bridge_enabled": enabled})
            return

        if url.path == "/api/slots/swap":
            from_slot = int(body.get("from_slot", 0))
            to_slot = int(body.get("to_slot", 0))
            if not (1 <= from_slot <= MAX_SLOTS and 1 <= to_slot <= MAX_SLOTS):
                self._send_json(400, {"error": "Número de slot inválido"})
                return
            to_restart = []
            with state.lock:
                src_w = next((w for w in state.workers.values() if w.player_num == from_slot), None)
                dst_w = next((w for w in state.workers.values() if w.player_num == to_slot), None)
                if src_w:
                    state.slot_overrides[src_w.identifier] = to_slot
                    to_restart.append(state.workers.pop(src_w.identifier))
                if dst_w:
                    state.slot_overrides[dst_w.identifier] = from_slot
                    to_restart.append(state.workers.pop(dst_w.identifier))
            for w in to_restart:
                w.stop(wait=True)
            state.supervisor_wakeup.set()
            self._send_json(200, {"swapped": [from_slot, to_slot]})
            return

        if url.path == "/api/slots/pin":
            slot = int(body.get("slot", 0))
            pin_key = str(body.get("pin_key", "")).strip()
            if not (1 <= slot <= MAX_SLOTS) or not pin_key:
                self._send_json(400, {"error": "Slot o pin_key inválido"})
                return
            with state.lock:
                state.slot_pins[pin_key] = slot
                cfg = {"bridge_enabled": state.bridge_enabled, "slot_pins": dict(state.slot_pins)}
            save_config(cfg)
            self._send_json(200, {"pinned": pin_key, "slot": slot})
            return

        if url.path == "/api/profile/tune":
            vendor = str(body.get("vendor", "")).lower().zfill(4)
            product = str(body.get("product", "")).lower().zfill(4)
            profiles = load_profiles()
            prof = profiles.get(f"{vendor}:{product}")
            if not prof:
                self._send_json(404, {"error": "Perfil no encontrado"})
                return
            if "deadzone_left" in body:
                prof["deadzone_left"] = max(0.01, min(0.45, float(body["deadzone_left"])))
            if "deadzone_right" in body:
                prof["deadzone_right"] = max(0.01, min(0.45, float(body["deadzone_right"])))
            if "rumble_enabled" in body:
                prof["rumble_enabled"] = bool(body["rumble_enabled"])
            if "center_offset" in body and isinstance(body["center_offset"], dict):
                prof["center_offset"] = body["center_offset"]
            save_profile(prof)
            with state.lock:
                state.profile_revision += 1
            state.supervisor_wakeup.set()
            self._send_json(200, {"ok": True})
            return

        if url.path == "/api/profile/center_zero":
            slot = int(body.get("slot", 0))
            with state.lock:
                slot_item = state.active_slots.get(slot)
                inp = copy.deepcopy(state.live_inputs.get(slot, {}))
            if not slot_item:
                self._send_json(404, {"error": "Slot vacío"})
                return
            profiles = load_profiles()
            key = f"{slot_item['vendor']}:{slot_item['product']}"
            prof = profiles.get(key)
            if not prof:
                self._send_json(404, {"error": "Perfil no encontrado"})
                return
            prof["center_offset"] = {
                "lx": round(float(inp.get("raw_lx", 0.0)), 3),
                "ly": round(float(inp.get("raw_ly", 0.0)), 3),
                "rx": round(float(inp.get("raw_rx", 0.0)), 3),
                "ry": round(float(inp.get("raw_ry", 0.0)), 3),
            }
            save_profile(prof)
            with state.lock:
                state.profile_revision += 1
            state.supervisor_wakeup.set()
            self._send_json(200, {"ok": True, "center_offset": prof["center_offset"]})
            return

        if url.path == "/api/profiles/rename":
            vendor = str(body.get("vendor", "")).lower().zfill(4)
            product = str(body.get("product", "")).lower().zfill(4)
            new_name = str(body.get("name", "")).strip()
            if not new_name:
                self._send_json(400, {"error": "Nombre vacío"})
                return
            profiles = load_profiles()
            prof = profiles.get(f"{vendor}:{product}")
            if not prof:
                self._send_json(404, {"error": "Perfil no encontrado"})
                return
            prof["name"] = new_name
            save_profile(prof)
            with state.lock:
                state.profile_revision += 1
            state.supervisor_wakeup.set()
            self._send_json(200, {"ok": True})
            return

        if url.path == "/api/profiles/delete":
            vendor = str(body.get("vendor", ""))
            product = str(body.get("product", ""))
            try:
                deleted = delete_profile(vendor, product)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            with state.lock:
                state.profile_revision += 1
            state.supervisor_wakeup.set()
            self._send_json(200 if deleted else 404, {"deleted": deleted})
            return

        if url.path == "/api/profiles/import":
            try:
                norm = normalize_profile_data(body)
                save_profile(norm)
                with state.lock:
                    state.profile_revision += 1
                state.supervisor_wakeup.set()
                self._send_json(200, {"ok": True, "name": norm["name"]})
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if url.path == "/api/update/github":
            try:
                res = _update_from_github()
                state.supervisor_wakeup.set()
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(500, {"error": f"Fallo al actualizar desde GitHub: {exc}"})
            return

        if url.path == "/api/calibrate/launch":
            with state.lock:
                if state.cal_launch_proc and state.cal_launch_proc.poll() is None:
                    self._send_json(200, {"status": "already_running"})
                    return
            term = detect_terminal_cmd()
            if not term:
                self._send_json(400, {"error": "No se detectó terminal gráfica compatible; usá el Calibrador Web."})
                return
            term_bin, flag = term
            cal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibrate.py")
            proc = subprocess.Popen([term_bin, flag, "python3", cal_path])
            with state.lock:
                state.cal_launch_proc = proc
            self._send_json(200, {"status": "launched", "terminal": os.path.basename(term_bin)})
            return

        if url.path == "/api/calibrate/pause":
            dev_path = str(body.get("dev_path", "")).strip()
            if dev_path:
                with state.lock:
                    state.paused_devices.add(dev_path)
                state.supervisor_wakeup.set()
                time.sleep(0.2)
            self._send_json(200, {"paused": dev_path})
            return

        if url.path == "/api/calibrate/resume":
            dev_path = str(body.get("dev_path", "")).strip()
            with state.lock:
                state.paused_devices.discard(dev_path)
            state.supervisor_wakeup.set()
            self._send_json(200, {"resumed": dev_path})
            return

        if url.path == "/api/calibrate/web/start":
            try:
                snap = cal_session.start(str(body.get("dev_path", "")))
                self._send_json(200, snap)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if url.path == "/api/calibrate/web/skip":
            self._send_json(200, cal_session.skip_step())
            return

        if url.path == "/api/calibrate/web/prev":
            self._send_json(200, cal_session.prev_step())
            return

        if url.path == "/api/calibrate/web/accept_warning":
            self._send_json(200, cal_session.accept_warning())
            return

        if url.path == "/api/calibrate/web/save":
            try:
                res = cal_session.save(body.get("name"))
                state.supervisor_wakeup.set()
                self._send_json(200, res)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if url.path == "/api/calibrate/web/cancel":
            cal_session.cancel()
            self._send_json(200, {"cancelled": True})
            return

        self._send_json(404, {"error": "Endpoint no encontrado"})


def main():
    """Boot device supervisor, start ThreadingHTTPServer cleanly, and open browser."""
    parser = argparse.ArgumentParser(description="Resiticks — Hub Universal de Joysticks")
    parser.add_argument("--port", type=int, default=8765, help="Puerto HTTP local (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="No abrir ventana de navegador al iniciar")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    print("=" * 65)
    print(" 🎮 Resiticks — Hub de Joysticks (8 Jugadores)")
    print(f" 📂 Perfiles: {resolve_profiles_dir()}")
    print("=" * 65)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), ResiticksHTTPHandler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(f"ℹ️  Resiticks ya está corriendo en {url}. Abriendo panel...")
            if not args.no_browser:
                launch_browser_url(url)
            sys.exit(0)
        raise

    sup_thread = threading.Thread(target=device_supervisor, daemon=True)
    sup_thread.start()

    print(f" 🚀 Servidor Resiticks corriendo en: {url}")
    if not args.no_browser:
        browser = launch_browser_url(url)
        if not browser:
            print(f"Abrí {url} en tu navegador.")

    def _handle_sig(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, _handle_sig)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Cerrando Resiticks...")
    finally:
        cal_session.cancel()
        state.shutdown_event.set()
        state.supervisor_wakeup.set()
        with state.lock:
            workers = list(state.workers.values())
            state.workers.clear()
        for w in workers:
            w.stop(wait=True)
        server.server_close()
        print("✅ Mandos liberados correctamente.")


if __name__ == "__main__":
    main()
