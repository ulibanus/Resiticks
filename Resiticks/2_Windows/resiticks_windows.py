#!/usr/bin/env python3
"""
Resiticks para Windows (ViGEmBus via vgamepad + pygame).
Carga los perfiles JSON de ../profiles/, traduce mapeos HID/Linux o usa windows_mapping
nativo, soporta los 11 botones, D-Pad, gatillos analógicos/digitales, anti-drift,
intercambio de slots P1..P4, calibrador Windows y panel web local en 127.0.0.1:8765.
"""
import argparse
import copy
import glob
import http.server
import json
import os
import sys
import threading
import time
import urllib.parse
import webbrowser

try:
    import pygame
    import vgamepad as vg
    DEPS_OK = True
    IMPORT_ERR = None
except ImportError as exc:
    pygame = None
    vg = None
    DEPS_OK = False
    IMPORT_ERR = exc

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(APP_ROOT, "profiles")
MAX_WINDOWS_XINPUT_SLOTS = 4


def parse_sdl_guid_vid_pid(guid):
    """Extract (vendor, product) lowercase 4-char hex pair from SDL2/Pygame joystick GUID."""
    if not guid or len(guid) < 20:
        return None
    try:
        raw = bytes.fromhex(guid)
        if len(raw) >= 10:
            vid = int.from_bytes(raw[4:6], "little")
            pid = int.from_bytes(raw[8:10], "little")
            if vid > 0 or pid > 0:
                return f"{vid:04x}:{pid:04x}"
    except ValueError:
        pass
    return None


def load_profiles(profiles_dir=PROFILES_DIR):
    """Load all valid JSON profiles indexed by vid:pid and lowercased hardware_name."""
    profiles = {}
    by_name = {}
    for p in sorted(glob.glob(os.path.join(profiles_dir, "*.json"))):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            if "vendor" not in d or "product" not in d or "mapping" not in d:
                continue
            d["vendor"] = str(d["vendor"]).strip().lower().zfill(4)
            d["product"] = str(d["product"]).strip().lower().zfill(4)
            d.setdefault("deadzone_left", 0.05)
            d.setdefault("deadzone_right", 0.05)
            d.setdefault("center_offset", {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0})
            key = f"{d['vendor']}:{d['product']}"
            profiles[key] = d
            hw = str(d.get("hardware_name", "")).strip().lower()
            if hw:
                by_name[hw] = d
        except Exception as exc:
            print(f"[Windows] Ignorando perfil inválido {os.path.basename(p)}: {exc}", file=sys.stderr)
    return profiles, by_name


def build_windows_translation(profile, num_axes, num_buttons, num_hats):
    """
    Build Windows pygame->XInput translation table from explicit windows_mapping
    or smart conversion of Linux evdev profile codes.
    """
    if isinstance(profile.get("windows_mapping"), dict):
        return copy.deepcopy(profile["windows_mapping"])

    mapping = profile.get("mapping", {})
    win_map = {"buttons": {}, "axes": {}, "hat_idx": 0 if num_hats > 0 else None}

    # Map Linux axis codes preserving relative USB HID descriptor order when Windows compacts them
    axis_targets = ("leftx", "lefty", "rightx", "righty", "lt", "rt")
    linux_axis_codes = sorted({
        mapping[k]["code"]
        for k in axis_targets
        if isinstance(mapping.get(k), dict) and mapping[k].get("type") == "axis" and mapping[k].get("code") is not None
    })
    compact_axis_idx = {code: idx for idx, code in enumerate(linux_axis_codes)}

    for k in axis_targets:
        spec = mapping.get(k)
        if not isinstance(spec, dict) or spec.get("type") != "axis":
            continue
        code = spec.get("code")
        # Prefer direct code if Windows reports all 6 axes (e.g. XInput 0..5), else compacted HID index
        if num_axes > max(linux_axis_codes or [0]):
            ax_idx = code
        else:
            ax_idx = compact_axis_idx.get(code, code)
        if ax_idx is not None and ax_idx < num_axes:
            win_map["axes"][k] = {"index": ax_idx, "direction": spec.get("direction", 1), "is_trigger": bool(spec.get("is_trigger", k in ("lt", "rt")))}

    # Map button codes cleanly for both HID Joystick (288+) and Gamepad (304+) families
    btn_targets = ("a", "b", "x", "y", "lb", "rb", "back", "start", "guide", "thumbl", "thumbr", "lt", "rt")
    raw_btn_codes = sorted({
        mapping[k]["code"]
        for k in btn_targets
        if isinstance(mapping.get(k), dict) and mapping[k].get("type") == "btn" and mapping[k].get("code") is not None
    })
    min_code = min(raw_btn_codes) if raw_btn_codes else 288
    compact_btn = {c: idx for idx, c in enumerate(raw_btn_codes)}

    for k in btn_targets:
        spec = mapping.get(k)
        if not isinstance(spec, dict) or spec.get("type") != "btn":
            continue
        code = spec.get("code")
        if 288 <= code <= 303:
            b_idx = code - 288
        elif min_code >= 304:
            # Xbox/Gamepad codes: map known Xbox/PS DirectInput slots or fallback compact order
            gamepad_std = {304: 0, 305: 1, 307: 2, 308: 3, 310: 4, 311: 5, 314: 6, 315: 7, 316: 10, 317: 8, 318: 9}
            b_idx = gamepad_std.get(code, compact_btn.get(code, 0))
        else:
            b_idx = compact_btn.get(code, 0)
        if 0 <= b_idx < num_buttons:
            win_map["buttons"][k] = b_idx

    return win_map


def _apply_deadzone(val, dz, offset=0.0):
    """Apply center offset and smooth rescaled deadzone on normalized -1.0..1.0 input."""
    adj = max(-1.0, min(1.0, val - offset))
    if abs(adj) < dz:
        return 0.0
    return ((abs(adj) - dz) / max(0.01, 1.0 - dz)) * (1.0 if adj > 0 else -1.0)


def run_windows_bridge(port=8765, open_browser=True):
    """Run main ViGEmBus multi-controller bridge with local Web status dashboard."""
    if not DEPS_OK:
        print(f"❌ Faltan dependencias ({IMPORT_ERR}). Ejecutá: instalar_requisitos_windows.bat")
        sys.exit(1)

    print("=" * 65)
    print(" 🎮 Resiticks para Windows (ViGEmBus Multi-Perfil)")
    print("=" * 65)
    print("⚠️  Recordatorio HidHide: Ocultá los mandos DirectInput físicos en HidHide")
    print("   para evitar doble entrada en PES 6 / Steam.")

    pygame.init()
    pygame.joystick.init()
    profiles, by_name = load_profiles()

    slots_lock = threading.Lock()
    slot_info = {i: None for i in range(1, MAX_WINDOWS_XINPUT_SLOTS + 1)}
    live_info = {i: {} for i in range(1, MAX_WINDOWS_XINPUT_SLOTS + 1)}

    class WinHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path == "/api/status":
                with slots_lock:
                    data = json.dumps({"active_slots": slot_info, "live_inputs": live_info}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                html = (
                    "<html><body style='background:#0b1120;color:#f8fafc;font-family:sans-serif;padding:24px'>"
                    "<h1>🎮 Resiticks Windows (ViGEmBus)</h1>"
                    "<p>Estado en vivo (límite nativo Windows XInput: 4 jugadores). Revisá <code>/api/status</code>.</p>"
                    "<pre id='out'></pre>"
                    "<script>setInterval(async()=>{const r=await fetch('/api/status');document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2);},150);</script>"
                    "</body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), WinHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f" 🚀 Panel web Windows corriendo en http://127.0.0.1:{port}")
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}")

    num_joysticks = pygame.joystick.get_count()
    print(f"Joysticks detectados: {num_joysticks} (Perfiles cargados: {len(profiles)})")
    if num_joysticks > MAX_WINDOWS_XINPUT_SLOTS:
        print(f"⚠️  Windows XInput soporta máximo {MAX_WINDOWS_XINPUT_SLOTS} mandos simultáneos; se conectarán los primeros {MAX_WINDOWS_XINPUT_SLOTS}.")

    XBTN = vg.XUSB_BUTTON
    btn_const_map = {
        "a": XBTN.XUSB_GAMEPAD_A,
        "b": XBTN.XUSB_GAMEPAD_B,
        "x": XBTN.XUSB_GAMEPAD_X,
        "y": XBTN.XUSB_GAMEPAD_Y,
        "lb": XBTN.XUSB_GAMEPAD_LEFT_SHOULDER,
        "rb": XBTN.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "back": XBTN.XUSB_GAMEPAD_BACK,
        "start": XBTN.XUSB_GAMEPAD_START,
        "guide": XBTN.XUSB_GAMEPAD_GUIDE,
        "thumbl": XBTN.XUSB_GAMEPAD_LEFT_THUMB,
        "thumbr": XBTN.XUSB_GAMEPAD_RIGHT_THUMB,
    }

    active_pads = []
    for i in range(min(num_joysticks, MAX_WINDOWS_XINPUT_SLOTS)):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        guid = joy.get_guid() if hasattr(joy, "get_guid") else ""
        vid_pid = parse_sdl_guid_vid_pid(guid)
        prof = profiles.get(vid_pid) or by_name.get(joy.get_name().strip().lower()) or {
            "name": joy.get_name(),
            "vendor": "0000",
            "product": "0000",
            "deadzone_left": 0.05,
            "deadzone_right": 0.05,
            "center_offset": {"lx": 0, "ly": 0, "rx": 0, "ry": 0},
            "mapping": {},
        }
        wmap = build_windows_translation(prof, joy.get_numaxes(), joy.get_numbuttons(), joy.get_numhats())
        vpad = vg.VX360Gamepad()
        slot_num = i + 1
        active_pads.append((slot_num, joy, prof, wmap, vpad))
        with slots_lock:
            slot_info[slot_num] = {"name": prof["name"], "vid_pid": vid_pid or "auto"}
        print(f" ✅ [P{slot_num}] {prof['name']} ({vid_pid or joy.get_name()}) -> Xbox 360 Virtual {slot_num}")

    try:
        while True:
            pygame.event.pump()
            for slot_num, joy, prof, wmap, vpad in active_pads:
                dz_l = float(prof.get("deadzone_left", 0.05))
                dz_r = float(prof.get("deadzone_right", 0.05))
                co = prof.get("center_offset", {})
                axes_cfg = wmap.get("axes", {})

                def _ax(key, dz, off_k):
                    c = axes_cfg.get(key)
                    if not c:
                        return 0.0
                    raw = joy.get_axis(c["index"]) * c.get("direction", 1)
                    return _apply_deadzone(raw, dz, float(co.get(off_k, 0.0)))

                lx = _ax("leftx", dz_l, "lx")
                ly = _ax("lefty", dz_l, "ly")
                rx = _ax("rightx", dz_r, "rx")
                ry = _ax("righty", dz_r, "ry")
                # vgamepad expects +Y up while DirectInput/Linux reports +Y down
                vpad.left_joystick_float(x_value_float=lx, y_value_float=-ly)
                vpad.right_joystick_float(x_value_float=rx, y_value_float=-ry)

                # Buttons & digital triggers
                btns_cfg = wmap.get("buttons", {})
                btn_states = {}
                for b_name, x_btn in btn_const_map.items():
                    idx = btns_cfg.get(b_name)
                    pressed = bool(joy.get_button(idx)) if idx is not None else False
                    btn_states[b_name] = pressed
                    if pressed:
                        vpad.press_button(x_btn)
                    else:
                        vpad.release_button(x_btn)

                # Triggers (axis or digital button)
                for trig, setter in (("lt", vpad.left_trigger_float), ("rt", vpad.right_trigger_float)):
                    if trig in axes_cfg:
                        raw_t = joy.get_axis(axes_cfg[trig]["index"])
                        val = max(0.0, min(1.0, (raw_t + 1.0) / 2.0))
                    elif trig in btns_cfg:
                        val = 1.0 if joy.get_button(btns_cfg[trig]) else 0.0
                    else:
                        val = 0.0
                    setter(value_float=val)

                # D-Pad Hat (pygame get_hat returns +1 for UP, -1 for DOWN)
                hat_idx = wmap.get("hat_idx")
                if hat_idx is not None and joy.get_numhats() > hat_idx:
                    hx, hy = joy.get_hat(hat_idx)
                    for cond, xb in (
                        (hy > 0, XBTN.XUSB_GAMEPAD_DPAD_UP),
                        (hy < 0, XBTN.XUSB_GAMEPAD_DPAD_DOWN),
                        (hx < 0, XBTN.XUSB_GAMEPAD_DPAD_LEFT),
                        (hx > 0, XBTN.XUSB_GAMEPAD_DPAD_RIGHT),
                    ):
                        if cond:
                            vpad.press_button(xb)
                        else:
                            vpad.release_button(xb)

                vpad.update()
                with slots_lock:
                    live_info[slot_num] = {"lx": round(lx, 2), "ly": round(ly, 2), "rx": round(rx, 2), "ry": round(ry, 2), "buttons": btn_states}
            time.sleep(0.008)
    except KeyboardInterrupt:
        print("\nDeteniendo Resiticks Windows...")
    finally:
        srv.shutdown()
        srv.server_close()


def main():
    parser = argparse.ArgumentParser(description="Resiticks para Windows (ViGEmBus)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    run_windows_bridge(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
