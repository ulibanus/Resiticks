#!/usr/bin/env python3
"""
Shared evdev, profile, configuration, and system-diagnostic utilities for Resiticks.
"""
import os
import sys
import glob
import json
import re
import copy
import threading
import fcntl
import struct
import shutil
import subprocess
import grp
import pwd

HEX4_RE = re.compile(r"^[0-9a-f]{4}$")
_PROFILES_CACHE_LOCK = threading.Lock()
_PROFILES_CACHE = {}  # realpath(pdir) -> (dir_sig, parsed_dict)

EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EVIOCGRAB = 0x40044590

# Known device-name exclusions checked case-insensitively to prevent laptop buttons/touchpads matching
EXCLUDED_NAME_TOKENS = (
    "motion sensors",
    "(imu)",
    "touchpad",
    "trackpad",
    "mouse",
    "resiticks",
    "keyboard",
    "thinkpad",
    "ideapad",
    "extra buttons",
    "wmi hotkeys",
    "power button",
    "sleep button",
    "lid switch",
    "video bus",
    "pc speaker",
    "intel hid",
)

GAMEPAD_NAME_TOKENS = (
    "gamepad",
    "joystick",
    "controller",
    "x-box",
    "xbox",
    "dualshock",
    "dualsense",
    "pro controller",
    "8bitdo",
    "shanwan",
    "dragonrise",
    "microntek",
    "gasia",
    "redragon",
    "bda ",
    "logitech",
    "hori",
)


def resolve_app_root():
    """Return the Resiticks root folder regardless of whether scripts live in 1_Linux/ or root."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    if os.path.isdir(os.path.join(parent_dir, "profiles")) or os.path.isdir(os.path.join(parent_dir, "2_Windows")):
        return parent_dir
    return script_dir


def resolve_profiles_dir():
    """Resolve canonical profiles/ path without relying on symlinks or hardcoded home paths."""
    app_root = resolve_app_root()
    profiles_dir = os.path.join(app_root, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    return profiles_dir


def resolve_config_path():
    """Return path to runtime configuration file kept outside profiles/*.json."""
    return os.path.join(resolve_app_root(), "resiticks_config.json")


def load_config():
    """Load persistent runtime preferences (bridge toggle, slot pins)."""
    cfg_path = resolve_config_path()
    default = {"bridge_enabled": True, "slot_pins": {}}
    if not os.path.exists(cfg_path):
        return default
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            return default
        default.update(loaded)
        if not isinstance(default.get("slot_pins"), dict):
            default["slot_pins"] = {}
        return default
    except Exception as e:
        print(f"[Config] Error leyendo {cfg_path}: {e}", file=sys.stderr)
        return default


def save_config(cfg):
    """Atomically persist runtime configuration."""
    cfg_path = resolve_config_path()
    tmp_path = cfg_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, cfg_path)


def _validate_hex_id(value, label="id"):
    """Validate and normalize a 1..4-digit USB/BT vendor or product hex identifier."""
    if value is None:
        raise ValueError(f"{label} inválido: None")
    raw = str(value).strip().lower()
    if not raw or len(raw) > 4:
        raise ValueError(f"{label} inválido (se esperan 1..4 dígitos hexadecimales): {value!r}")
    norm = raw.zfill(4)
    if not HEX4_RE.fullmatch(norm):
        raise ValueError(f"{label} inválido (se esperan dígitos hexadecimales): {value!r}")
    return norm


def invalidate_profiles_cache(profiles_dir=None):
    """Clear cached profile snapshots so next load_profiles() re-reads disk."""
    with _PROFILES_CACHE_LOCK:
        if profiles_dir is None:
            _PROFILES_CACHE.clear()
        else:
            _PROFILES_CACHE.pop(os.path.realpath(profiles_dir), None)


def normalize_profile_data(data, filepath=None):
    """Validate and apply non-destructive defaults to a loaded controller profile."""
    if not isinstance(data, dict):
        raise ValueError("El perfil debe ser un objeto JSON")
    if "vendor" not in data or "product" not in data or "mapping" not in data:
        raise ValueError("Faltan campos obligatorios (vendor, product, mapping)")
    if not isinstance(data["mapping"], dict):
        raise ValueError("El campo mapping debe ser un diccionario")

    vendor = _validate_hex_id(data["vendor"], "vendor")
    product = _validate_hex_id(data["product"], "product")
    data["vendor"] = vendor
    data["product"] = product
    data.setdefault("name", f"Mando {vendor}:{product}")
    data.setdefault("deadzone_left", 0.05)
    data.setdefault("deadzone_right", 0.05)
    data.setdefault("rumble_enabled", True)
    data.setdefault("center_offset", {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0})
    if filepath:
        data["_file"] = filepath
    return data


def _compute_profiles_dir_sig(pdir):
    """Build lightweight (filename, mtime_ns, size) signature to avoid redundant JSON parses."""
    sig = []
    for p in sorted(glob.glob(os.path.join(pdir, "*.json"))):
        try:
            st = os.stat(p)
            sig.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            continue
    return tuple(sig)


def load_profiles(profiles_dir=None):
    """Load all valid JSON controller profiles using mtime caching and deep-copied outputs."""
    pdir = os.path.realpath(profiles_dir or resolve_profiles_dir())
    sig = _compute_profiles_dir_sig(pdir)

    with _PROFILES_CACHE_LOCK:
        cached = _PROFILES_CACHE.get(pdir)
        if cached and cached[0] == sig:
            return {k: copy.deepcopy(v) for k, v in cached[1].items()}

    profiles = {}
    for p, _, _ in sig:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            norm = normalize_profile_data(data, filepath=p)
            key = f"{norm['vendor']}:{norm['product']}"
            profiles[key] = norm
        except Exception as e:
            print(f"[Perfiles] Ignorando archivo inválido {os.path.basename(p)}: {e}", file=sys.stderr)

    with _PROFILES_CACHE_LOCK:
        _PROFILES_CACHE[pdir] = (sig, profiles)
    return {k: copy.deepcopy(v) for k, v in profiles.items()}


def save_profile(profile_data, profiles_dir=None):
    """Atomically write a controller profile JSON to profiles/."""
    pdir = profiles_dir or resolve_profiles_dir()
    os.makedirs(pdir, exist_ok=True)
    clean = {k: v for k, v in profile_data.items() if not k.startswith("_")}
    norm = normalize_profile_data(clean)
    norm_clean = {k: v for k, v in norm.items() if not k.startswith("_")}
    filename = f"{norm_clean['vendor']}_{norm_clean['product']}.json"
    out_path = os.path.join(pdir, filename)
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(norm_clean, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, out_path)
    invalidate_profiles_cache(pdir)
    return out_path


def delete_profile(vendor, product, profiles_dir=None):
    """Remove a profile JSON file by validated VID:PID if present."""
    pdir = profiles_dir or resolve_profiles_dir()
    v = _validate_hex_id(vendor, "vendor")
    p = _validate_hex_id(product, "product")
    target = os.path.join(pdir, f"{v}_{p}.json")
    if os.path.exists(target):
        os.remove(target)
        invalidate_profiles_cache(pdir)
        return True
    return False


def get_abs_info(fd, axes=None):
    """Query kernel EVIOCGABS metadata for all or requested absolute axes."""
    info = {}
    targets = axes if axes is not None else range(64)
    for axis in targets:
        try:
            buf = bytearray(24)
            fcntl.ioctl(fd, 0x80184540 + axis, buf)
            val, minimum, maximum, fuzz, flat, res = struct.unpack("iiiiii", buf)
            info[axis] = {
                "min": minimum,
                "max": maximum,
                "val": val,
                "fuzz": fuzz,
                "flat": flat,
            }
        except OSError:
            pass
    return info


def get_ff_support(fd):
    """Return True if kernel evdev reports EV_FF (0x15) capability on fd."""
    try:
        # EVIOCGBIT(0, 4) -> _IOC(_IOC_READ, 'E', 0x20, 4) = 0x80044520
        buf = bytearray(4)
        fcntl.ioctl(fd, 0x80044520, buf)
        bits = int.from_bytes(buf, "little")
        return bool(bits & (1 << 0x15))
    except OSError:
        return False


def _is_gamepad_entry(info):
    """Determine if a parsed /proc/bus/input/devices entry is a real physical gamepad."""
    if "event" not in info:
        return False
    sysfs = info.get("sysfs", "").lower()
    if "virtual" in sysfs:
        return False

    name = info.get("name", "")
    name_l = name.lower()
    if any(tok in name_l for tok in EXCLUDED_NAME_TOKENS):
        return False

    handlers = info.get("handlers", [])
    if "kbd" in handlers and "js" not in info:
        return False

    return "js" in info or any(tok in name_l for tok in GAMEPAD_NAME_TOKENS)


def get_connected_gamepads(proc_path="/proc/bus/input/devices"):
    """Parse /proc/bus/input/devices and return physical gamepads with unique identifiers."""
    gamepads = []
    try:
        with open(proc_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return []

    entries = content.strip().split("\n\n")
    for entry in entries:
        lines = entry.split("\n")
        info = {"handlers": []}
        for line in lines:
            if line.startswith("I:"):
                m = re.search(r"Vendor=([0-9a-fA-F]+)\s+Product=([0-9a-fA-F]+)", line)
                if m:
                    info["vendor"] = m.group(1).lower().zfill(4)
                    info["product"] = m.group(2).lower().zfill(4)
            elif line.startswith("N:"):
                m = re.search(r'Name="([^"]+)"', line)
                if m:
                    info["name"] = m.group(1)
            elif line.startswith("P:"):
                m = re.search(r"Phys=(.*)", line)
                if m:
                    info["phys"] = m.group(1).strip()
            elif line.startswith("S:"):
                m = re.search(r"Sysfs=(.*)", line)
                if m:
                    info["sysfs"] = m.group(1).strip()
            elif line.startswith("H:"):
                m = re.search(r"Handlers=(.*)", line)
                if m:
                    handlers = m.group(1).split()
                    info["handlers"] = handlers
                    for h in handlers:
                        if h.startswith("event"):
                            info["event"] = h
                        elif h.startswith("js"):
                            info["js"] = h

        if not _is_gamepad_entry(info):
            continue

        info["dev_path"] = f"/dev/input/{info['event']}"
        # sysfs path distinguishes Twin USB dual adapters sharing identical Phys strings
        info["identifier"] = info.get("sysfs") or f"{info.get('phys', '')}::{info['dev_path']}"
        # pin_key remains stable across reboots for the same physical USB port or BT address
        phys = info.get("phys", "")
        vid_pid = f"{info.get('vendor', '0000')}:{info.get('product', '0000')}"
        info["pin_key"] = f"{vid_pid}@{phys}" if phys else vid_pid
        gamepads.append(info)

    return gamepads


def detect_terminal_cmd():
    """Return available terminal launcher tuple (binary, exec_flag) or None."""
    candidates = [
        ("alacritty", "-e"),
        ("kitty", "-e"),
        ("foot", "-e"),
        ("ghostty", "-e"),
        ("wezterm", "start"),
        ("gnome-terminal", "--"),
        ("konsole", "-e"),
        ("xfce4-terminal", "-e"),
        ("x-terminal-emulator", "-e"),
        ("xterm", "-e"),
    ]
    for binary, flag in candidates:
        path = shutil.which(binary)
        if path:
            return (path, flag)
    return None


def launch_browser_url(url, window_size="1120,820"):
    """Open the Resiticks web UI using Chromium app mode with multi-browser fallback."""
    for browser in ("chromium", "chromium-browser", "google-chrome"):
        path = shutil.which(browser)
        if path:
            try:
                subprocess.Popen([path, f"--app={url}", f"--window-size={window_size}"])
                return browser
            except Exception:
                pass

    for fallback in ("firefox", "xdg-open"):
        path = shutil.which(fallback)
        if path:
            try:
                subprocess.Popen([path, url])
                return fallback
            except Exception:
                pass

    return None


def _read_recent_usb_errors():
    """Check kernel logs non-destructively for USB hub undervoltage or DragonRise error -71/-32."""
    cmds = [
        ["dmesg", "-T"],
        ["journalctl", "-k", "-n", "120", "--no-pager"],
    ]
    for cmd in cmds:
        if not shutil.which(cmd[0]):
            continue
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=1.5).decode("utf-8", errors="replace")
            hits = []
            for line in out.splitlines()[-150:]:
                low = line.lower()
                if any(k in low for k in ("error -71", "error -32", "over-current", "unable to enumerate usb", "attempt power cycle")):
                    hits.append(line.strip())
            return {"readable": True, "errors": hits[-8:]}
        except Exception:
            continue
    return {"readable": False, "errors": []}


def diagnose_system():
    """Run system readiness & hardware health checks for Linux evdev/uinput/USB."""
    uinput_exists = os.path.exists("/dev/uinput")
    uinput_rw = os.access("/dev/uinput", os.R_OK | os.W_OK) if uinput_exists else False

    user_info = pwd.getpwuid(os.getuid())
    username = user_info.pw_name
    user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
    try:
        user_groups.append(grp.getgrgid(user_info.pw_gid).gr_name)
    except KeyError:
        pass
    in_input_group = "input" in user_groups

    old_scheme_path = "/sys/module/usbcore/parameters/old_scheme_first"
    old_scheme = None
    if os.path.exists(old_scheme_path):
        try:
            with open(old_scheme_path, "r") as f:
                old_scheme = f.read().strip()
        except Exception:
            pass

    gamepads = get_connected_gamepads()
    device_checks = []
    for gp in gamepads:
        p = gp["dev_path"]
        device_checks.append({
            "name": gp.get("name"),
            "dev_path": p,
            "readable": os.access(p, os.R_OK),
            "writable": os.access(p, os.W_OK),
        })

    usb_diag = _read_recent_usb_errors()
    udev_installed = any(
        os.path.exists(p)
        for p in ("/etc/udev/rules.d/99-resiticks-uinput.rules", "/etc/udev/rules.d/99-uinput.rules")
    )

    return {
        "username": username,
        "uinput_exists": uinput_exists,
        "uinput_rw": uinput_rw,
        "in_input_group": in_input_group,
        "udev_installed": udev_installed,
        "usbcore_old_scheme_first": old_scheme,
        "usb_log_readable": usb_diag["readable"],
        "usb_errors": usb_diag["errors"],
        "device_checks": device_checks,
        "terminal_detected": (detect_terminal_cmd() or [None])[0],
        "profiles_dir": resolve_profiles_dir(),
    }
