#!/usr/bin/env python3
"""
Automated end-to-end test suite for Resiticks (Linux uinput, EV_FF rumble,
concurrency safety, calibration math, Windows translation, HTTP API, Web UI).
"""
import glob
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
import fcntl

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RESITICKS_ROOT = os.path.dirname(TESTS_DIR)
LINUX_DIR = os.path.join(RESITICKS_ROOT, "1_Linux")
WIN_DIR = os.path.join(RESITICKS_ROOT, "2_Windows")
PROFILES_DIR = os.path.join(RESITICKS_ROOT, "profiles")

sys.path.insert(0, LINUX_DIR)
sys.path.insert(0, WIN_DIR)

import app as res_app
import calibration_core
import evdev_utils
import resiticks_windows
import virtual_xbox

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_ABSBIT = 0x40045567
UI_ABS_SETUP = 0x401c5504
UI_DEV_SETUP = 0x405c5503
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)


def _get_uinput_sysname(fd):
    buf = bytearray(64)
    fcntl.ioctl(fd, 0x8040552c, buf)
    return buf.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def _find_event_path(sysname):
    paths = glob.glob(f"/sys/devices/virtual/input/{sysname}/event*")
    if paths:
        return "/dev/input/" + os.path.basename(paths[0])
    return None


def _open_event_wait_udev(path, timeout=1.5):
    """Open /dev/input/eventX waiting briefly for udev to apply input-group permissions."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.03)


def _create_mock_uinput_pad(name="Mock Pad", vendor=0x0079, product=0x0006, axes=None, keys=None):
    fd = os.open("/dev/uinput", os.O_RDWR | os.O_NONBLOCK)
    for ev in (0, 1, 3):
        fcntl.ioctl(fd, UI_SET_EVBIT, ev)
    for k in (keys or list(range(288, 300))):
        fcntl.ioctl(fd, UI_SET_KEYBIT, k)
    for ax, (mn, mx, val) in (axes or {0: (0, 255, 128), 1: (0, 255, 128), 2: (0, 255, 128), 5: (0, 255, 128), 16: (-1, 1, 0), 17: (-1, 1, 0)}).items():
        fcntl.ioctl(fd, UI_SET_ABSBIT, ax)
        fcntl.ioctl(fd, UI_ABS_SETUP, struct.pack("HHiiiiii", ax, 0, val, mn, mx, 0, 0, 0))
    fcntl.ioctl(fd, UI_DEV_SETUP, struct.pack("HHHH80sI", 0x03, vendor, product, 0x0110, name.encode("utf-8")[:79], 0))
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.12)
    sysname = _get_uinput_sysname(fd)
    return fd, _find_event_path(sysname)


def _emit(fd, ev_type, code, val):
    os.write(fd, struct.pack(EVENT_FORMAT, 0, 0, ev_type, code, val))


def _uinput_writable():
    return os.path.exists("/dev/uinput") and os.access("/dev/uinput", os.R_OK | os.W_OK)


class TestProfilesAndUtils(unittest.TestCase):
    def test_all_profiles_valid_and_consistent(self):
        profiles = evdev_utils.load_profiles(PROFILES_DIR)
        self.assertGreaterEqual(len(profiles), 15)
        for key, prof in profiles.items():
            m = prof["mapping"]
            for axis in ("leftx", "lefty", "rightx", "righty"):
                self.assertIn(axis, m, f"{key} missing {axis}")
                self.assertEqual(m[axis]["type"], "axis")
                self.assertLessEqual(m[axis]["code"], 63, f"{key} bad code on {axis}")
            warns = calibration_core.validate_calibration_consistency(m)
            self.assertEqual(warns, [], f"{key} consistency warnings: {warns}")

    def test_no_fragile_symlink_in_linux_dir(self):
        self.assertFalse(os.path.islink(os.path.join(LINUX_DIR, "profiles")))
        self.assertEqual(os.path.realpath(evdev_utils.resolve_profiles_dir()), os.path.realpath(PROFILES_DIR))

    def test_gamepad_filter_case_insensitive_and_twin_usb(self):
        sample = (
            "I: Bus=0018 Vendor=04f3 Product=3128 Version=0100\n"
            'N: Name="ELAN1200:00 04F3:3128 TouchPad"\n'
            "S: Sysfs=/devices/platform/touchpad0\n"
            "H: Handlers=mouse0 event12\n\n"
            "I: Bus=0019 Vendor=17aa Product=5054 Version=4101\n"
            'N: Name="Ideapad Extra Buttons"\n'
            "S: Sysfs=/devices/platform/ideapad/input/input9\n"
            "H: Handlers=kbd event9\n\n"
            "I: Bus=0003 Vendor=0810 Product=0001 Version=0110\n"
            'N: Name="Twin USB Joystick"\n'
            "P: Phys=usb-0000:00:14.0-2/input0\n"
            "S: Sysfs=/devices/pci0000:00/usb1/input/input20\n"
            "H: Handlers=event15 js0\n\n"
            "I: Bus=0003 Vendor=0810 Product=0001 Version=0110\n"
            'N: Name="Twin USB Joystick"\n'
            "P: Phys=usb-0000:00:14.0-2/input0\n"
            "S: Sysfs=/devices/pci0000:00/usb1/input/input21\n"
            "H: Handlers=event16 js1\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(sample)
            p = tf.name
        try:
            gps = evdev_utils.get_connected_gamepads(proc_path=p)
            self.assertEqual(len(gps), 2)
            self.assertNotEqual(gps[0]["identifier"], gps[1]["identifier"])
        finally:
            os.remove(p)


class TestCalibrationCore(unittest.TestCase):
    def test_xbox_one_10bit_trigger_does_not_false_fire_at_rest(self):
        abs_info = {2: {"min": 0, "max": 1023, "val": 0}}
        self.assertIsNone(calibration_core.detect_input_event(3, 2, 0, abs_info))
        self.assertIsNone(calibration_core.detect_input_event(3, 2, 200, abs_info))
        res = calibration_core.detect_input_event(3, 2, 700, abs_info)
        self.assertEqual(res["type"], "axis")
        self.assertTrue(res["is_trigger"])

    def test_digital_mode_warning_triggers(self):
        self.assertIsNotNone(calibration_core.detect_digital_mode_warning("dpup", {"type": "axis", "code": 1}))
        self.assertIsNotNone(calibration_core.detect_digital_mode_warning("right_right", {"type": "btn", "code": 289}))
        self.assertIsNone(calibration_core.detect_digital_mode_warning("dpup", {"type": "hat", "code": 17, "value": -1}))

    def test_derive_canonical_axes_preserves_inverted_direction_and_skips_btns(self):
        inv_map = {
            "left_up": {"type": "axis", "code": 1, "direction": 1},
            "left_down": {"type": "axis", "code": 1, "direction": -1},
            "left_left": {"type": "axis", "code": 0, "direction": 1},
            "right_right": {"type": "btn", "code": 289},
        }
        canon = calibration_core.derive_canonical_axes(inv_map)
        self.assertEqual(canon["lefty"], {"type": "axis", "code": 1, "direction": -1})
        self.assertEqual(canon["leftx"], {"type": "axis", "code": 0, "direction": -1})
        self.assertNotIn("rightx", canon)


@unittest.skipUnless(_uinput_writable(), "/dev/uinput not writable")
class TestUInputAndWorkerE2E(unittest.TestCase):
    def test_virtual_xbox_utf8_and_double_close(self):
        vp = virtual_xbox.VirtualXboxPad(player_num=1, custom_name="Mando " + ("🎮" * 20), enable_rumble=True)
        sn = _get_uinput_sysname(vp.fd)
        with open(f"/sys/devices/virtual/input/{sn}/name", "rb") as f:
            kname = f.read().strip()
        # Decoding strict utf-8 must NOT raise UnicodeDecodeError
        decoded = kname.decode("utf-8")
        self.assertTrue(decoded.startswith("Resiticks 1 - Mando"))
        vp.close()
        self.assertIsNone(vp.fd)
        vp.close()  # Idempotent second close

    def test_worker_e2e_no_crash_autorepeat_hat_flip_and_deadzone(self):
        with open(os.path.join(PROFILES_DIR, "0079_0006.json"), "r", encoding="utf-8") as f:
            prof = json.load(f)
        prof["deadzone_left"] = 0.10
        prof["center_offset"] = {"lx": 0.10, "ly": 0.0, "rx": 0.0, "ry": 0.0}

        mfd, mev = _create_mock_uinput_pad()
        try:
            dev_info = {"vendor": "0079", "product": "0006", "name": "Mock Aitor", "dev_path": mev, "identifier": "test/aitor", "pin_key": "0079:0006@test"}
            w = res_app.GamepadWorker(dev_info, prof, player_num=1, bridge_mode=True)
            w.start()
            for _ in range(40):
                if w.vpad is not None:
                    break
                time.sleep(0.03)
            self.assertIsNotNone(w.vpad)

            osys = _get_uinput_sysname(w.vpad.fd)
            oev = _find_event_path(osys)
            ord_fd = _open_event_wait_udev(oev)
            try:
                # 1. Autorepeat value=2 must keep button pressed
                _emit(mfd, 1, 290, 1)
                _emit(mfd, 0, 0, 0)
                time.sleep(0.04)
                _emit(mfd, 1, 290, 2)
                _emit(mfd, 0, 0, 0)
                time.sleep(0.04)
                self.assertTrue(w.live_state["buttons"]["a"])

                # 2. Direct hat flip -1 -> +1 must clear dpleft!
                _emit(mfd, 3, 16, -1)
                _emit(mfd, 0, 0, 0)
                time.sleep(0.03)
                _emit(mfd, 3, 16, 1)
                _emit(mfd, 0, 0, 0)
                time.sleep(0.03)
                self.assertFalse(w.live_state["buttons"]["dpleft"])
                self.assertTrue(w.live_state["buttons"]["dpright"])

                # 3. Right stick full RX=+max, RY=up (min)
                _emit(mfd, 3, 2, 255)
                _emit(mfd, 3, 5, 0)
                _emit(mfd, 0, 0, 0)
                time.sleep(0.05)

                # Drain and inspect output events
                raw = os.read(ord_fd, EVENT_SIZE * 128)
                evts = [struct.unpack(EVENT_FORMAT, raw[i * EVENT_SIZE:(i + 1) * EVENT_SIZE])[2:] for i in range(len(raw) // EVENT_SIZE)]
                self.assertIn((3, virtual_xbox.ABS_RX, 32767), evts)
                self.assertIn((3, virtual_xbox.ABS_RY, -32767), evts)
                # Ensure autorepeat didn't emit a release (304, 0)
                self.assertNotIn((1, virtual_xbox.BTN_A, 0), evts)

                # 4. Simulate EV_FF upload handshake on virtual pad (must not hang!)
                ff_eff = bytearray(48)
                struct.pack_into("HhHHHHH", ff_eff, 0, virtual_xbox.FF_RUMBLE, -1, 0, 0, 0, 200, 0)
                struct.pack_into("HH", ff_eff, 16, 0x8000, 0x4000)
                fcntl.ioctl(ord_fd, virtual_xbox.EVIOCSFF, ff_eff)
                eff_id = struct.unpack_from("h", ff_eff, 2)[0]
                self.assertGreaterEqual(eff_id, 0)
            finally:
                os.close(ord_fd)

            # Stopping cleanly must NOT raise TypeError
            w.stop(wait=True)
            self.assertIsNone(w.dev_fd)
            self.assertIsNone(w.vpad)
        finally:
            fcntl.ioctl(mfd, UI_DEV_DESTROY)
            os.close(mfd)

    def test_monitor_mode_updates_digital_lt_without_vpad(self):
        with open(os.path.join(PROFILES_DIR, "0079_0006.json"), "r", encoding="utf-8") as f:
            prof = json.load(f)
        mfd, mev = _create_mock_uinput_pad()
        try:
            w = res_app.GamepadWorker({"vendor": "0079", "product": "0006", "name": "Mon", "dev_path": mev, "identifier": "test/mon"}, prof, 2, bridge_mode=False)
            w.start()
            for _ in range(30):
                if res_app.state.active_slots.get(2) is not None:
                    break
                time.sleep(0.03)
            self.assertIsNone(w.vpad)
            _emit(mfd, 1, 294, 1)
            _emit(mfd, 0, 0, 0)
            time.sleep(0.05)
            self.assertEqual(w.live_state["lt"], 100)
            w.stop(wait=True)
        finally:
            fcntl.ioctl(mfd, UI_DEV_DESTROY)
            os.close(mfd)


class TestHTTPAndWebUI(unittest.TestCase):
    def test_http_endpoints_and_chromium_dom(self):
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), res_app.ResiticksHTTPHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"
        try:
            with urllib.request.urlopen(base + "/api/status", timeout=3) as r:
                self.assertEqual(r.status, 200)
                self.assertEqual(r.headers.get("Content-Type"), "application/json")
                self.assertIsNotNone(r.headers.get("Content-Length"))
                j = json.loads(r.read().decode())
                for k in ("bridge_enabled", "active_slots", "live_inputs", "connected_devices", "uncalibrated_devices", "device_errors", "profile_revision"):
                    self.assertIn(k, j)

            with urllib.request.urlopen(base + "/api/profiles", timeout=3) as r:
                plist = json.loads(r.read().decode())
                self.assertGreaterEqual(len(plist), 15)

            with urllib.request.urlopen(base + "/api/system/diagnose", timeout=4) as r:
                diag = json.loads(r.read().decode())
                self.assertIn("uinput_exists", diag)

            with urllib.request.urlopen(base + "/api/export_pack", timeout=5) as r:
                zf = zipfile.ZipFile(io.BytesIO(r.read()))
                names = zf.namelist()
                self.assertIn("Resiticks/1_Linux/app.py", names)
                self.assertIn("Resiticks/2_Windows/resiticks_windows.py", names)
                self.assertIn("Resiticks/profiles/0079_0006.json", names)

            if shutil.which("chromium"):
                dom = subprocess.check_output(
                    ["chromium", "--headless=new", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=1500", "--dump-dom", base + "/"],
                    stderr=subprocess.DEVNULL, timeout=15
                ).decode("utf-8", errors="replace")
                # 8 slots rendered + 15+ rows rendered
                self.assertGreaterEqual(dom.count('id="slot-card-'), 8)
                self.assertGreaterEqual(dom.count("<td><strong>"), 15)
        finally:
            srv.shutdown()
            srv.server_close()


class TestWindowsTranslation(unittest.TestCase):
    def test_sdl_guid_and_aitor_mapping(self):
        guid = "03000000790000000600000000000000"
        self.assertEqual(resiticks_windows.parse_sdl_guid_vid_pid(guid), "0079:0006")
        with open(os.path.join(PROFILES_DIR, "0079_0006.json"), "r", encoding="utf-8") as f:
            aitor = json.load(f)
        wmap = resiticks_windows.build_windows_translation(aitor, num_axes=4, num_buttons=12, num_hats=1)
        # Linux axes [0, 1, 2, 5] compact neatly to Windows DirectInput indices [0, 1, 2, 3]
        self.assertEqual(wmap["axes"]["leftx"]["index"], 0)
        self.assertEqual(wmap["axes"]["lefty"]["index"], 1)
        self.assertEqual(wmap["axes"]["rightx"]["index"], 2)
        self.assertEqual(wmap["axes"]["righty"]["index"], 3)
        self.assertEqual(wmap["buttons"]["y"], 0)   # 288 -> 0
        self.assertEqual(wmap["buttons"]["a"], 2)   # 290 -> 2
        self.assertEqual(wmap["buttons"]["lt"], 6)  # 294 -> 6
        self.assertEqual(wmap["buttons"]["start"], 9)  # 297 -> 9
        self.assertEqual(wmap["hat_idx"], 0)


class TestExtendedIntegration(unittest.TestCase):
    def _post(self, base, path, obj=None):
        data = json.dumps(obj or {}).encode("utf-8")
        req = urllib.request.Request(
            base + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status, json.loads(r.read().decode())

    @unittest.skipUnless(_uinput_writable(), "/dev/uinput not writable")
    def test_fausto_profile_e2e_16bit_and_axis_dpad(self):
        with open(os.path.join(PROFILES_DIR, "057e_2009.json"), "r", encoding="utf-8") as f:
            fausto = json.load(f)

        axes_16 = {
            0: (-32768, 32767, 0),
            1: (-32768, 32767, 0),
            3: (-32768, 32767, 0),
            4: (-32768, 32767, 0),
            16: (-1, 1, 0),
            17: (-1, 1, 0),
        }
        mfd, mev = _create_mock_uinput_pad(name="Mock Switch Pro", vendor=0x057e, product=0x2009, axes=axes_16, keys=[304, 305, 307, 308, 310, 311, 312, 313, 314, 315, 317, 318])
        try:
            w = res_app.GamepadWorker({"vendor": "057e", "product": "2009", "name": "Fausto", "dev_path": mev, "identifier": "test/fausto"}, fausto, 1)
            w.start()
            for _ in range(30):
                if w.vpad is not None:
                    break
                time.sleep(0.03)
            self.assertIsNotNone(w.vpad)
            osys = _get_uinput_sysname(w.vpad.fd)
            oev = _find_event_path(osys)
            ord_fd = _open_event_wait_udev(oev)
            try:
                _emit(mfd, 3, 4, -32768)  # right stick UP
                _emit(mfd, 3, 3, 32767)   # right stick RIGHT
                _emit(mfd, 0, 0, 0)
                time.sleep(0.05)
                raw = os.read(ord_fd, EVENT_SIZE * 64)
                evts = [struct.unpack(EVENT_FORMAT, raw[i * EVENT_SIZE:(i + 1) * EVENT_SIZE])[2:] for i in range(len(raw) // EVENT_SIZE)]
                self.assertIn((3, virtual_xbox.ABS_RX, 32767), evts)
                self.assertIn((3, virtual_xbox.ABS_RY, -32767), evts)
            finally:
                os.close(ord_fd)
            w.stop(wait=True)
        finally:
            fcntl.ioctl(mfd, UI_DEV_DESTROY)
            os.close(mfd)

        # Axis D-pad check
        axis_dpad_prof = {
            "name": "Axis DPad Pad",
            "vendor": "9999",
            "product": "0001",
            "mapping": {
                "dpup": {"type": "axis", "code": 1, "direction": -1},
                "dpdown": {"type": "axis", "code": 1, "direction": 1},
                "dpleft": {"type": "axis", "code": 0, "direction": -1},
                "dpright": {"type": "axis", "code": 0, "direction": 1},
            },
        }
        mfd2, mev2 = _create_mock_uinput_pad(name="Mock Axis DPad", vendor=0x9999, product=0x0001)
        try:
            w2 = res_app.GamepadWorker({"vendor": "9999", "product": "0001", "name": "AxisDP", "dev_path": mev2, "identifier": "test/adp"}, axis_dpad_prof, 3)
            w2.start()
            for _ in range(30):
                if w2.vpad is not None:
                    break
                time.sleep(0.03)
            _emit(mfd2, 3, 1, 0)  # full up on axis 1
            _emit(mfd2, 0, 0, 0)
            time.sleep(0.05)
            self.assertTrue(w2.live_state["buttons"]["dpup"])
            w2.stop(wait=True)
        finally:
            fcntl.ioctl(mfd2, UI_DEV_DESTROY)
            os.close(mfd2)

    @unittest.skipUnless(_uinput_writable(), "/dev/uinput not writable")
    def test_api_mutations_and_web_calibration_isolated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdir = os.path.join(tmpdir, "profiles")
            os.makedirs(pdir)
            cfg_file = os.path.join(tmpdir, "resiticks_config.json")

            orig_resolve_pdir = evdev_utils.resolve_profiles_dir
            orig_app_pdir = res_app.resolve_profiles_dir
            orig_cfg_path = evdev_utils.resolve_config_path
            orig_get_gps_app = res_app.get_connected_gamepads
            orig_load_profs_app = res_app.load_profiles
            orig_save_prof_app = res_app.save_profile
            orig_del_prof_app = res_app.delete_profile

            mfd, mev = _create_mock_uinput_pad(name="Mock Cal Pad", vendor=0x1234, product=0xabcd)
            fake_gps = [{
                "vendor": "1234", "product": "abcd", "name": "Mock Cal Pad",
                "phys": "usb-mock/0", "sysfs": "/sys/mock/cal", "event": os.path.basename(mev),
                "dev_path": mev, "identifier": "/sys/mock/cal", "pin_key": "1234:abcd@usb-mock/0"
            }]

            try:
                evdev_utils.resolve_profiles_dir = lambda: pdir
                evdev_utils.resolve_config_path = lambda: cfg_file
                res_app.resolve_profiles_dir = lambda: pdir
                res_app.load_profiles = lambda: evdev_utils.load_profiles(pdir)
                res_app.save_profile = lambda d: evdev_utils.save_profile(d, pdir)
                res_app.delete_profile = lambda v, p: evdev_utils.delete_profile(v, p, pdir)
                res_app.get_connected_gamepads = lambda: fake_gps

                from http.server import ThreadingHTTPServer
                srv = ThreadingHTTPServer(("127.0.0.1", 0), res_app.ResiticksHTTPHandler)
                base = f"http://127.0.0.1:{srv.server_address[1]}"
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                try:
                    # Import -> Tune -> Rename -> Delete
                    sample_prof = {"vendor": "1234", "product": "abcd", "name": "Cal Temp", "mapping": {"a": {"type": "btn", "code": 290}}}
                    st, out = self._post(base, "/api/profiles/import", sample_prof)
                    self.assertEqual(st, 200)
                    self._post(base, "/api/profile/tune", {"vendor": "1234", "product": "abcd", "deadzone_left": 0.14, "rumble_enabled": False})
                    loaded = evdev_utils.load_profiles(pdir)["1234:abcd"]
                    self.assertAlmostEqual(loaded["deadzone_left"], 0.14)
                    self.assertFalse(loaded["rumble_enabled"])

                    self._post(base, "/api/profiles/rename", {"vendor": "1234", "product": "abcd", "name": "Cal Nuevo"})
                    self.assertEqual(evdev_utils.load_profiles(pdir)["1234:abcd"]["name"], "Cal Nuevo")

                    self._post(base, "/api/slots/pin", {"slot": 4, "pin_key": "1234:abcd@usb-mock/0"})
                    self.assertTrue(os.path.exists(cfg_file))

                    # Bridge toggle twice to restore original state
                    _, b1 = self._post(base, "/api/bridge/toggle")
                    _, b2 = self._post(base, "/api/bridge/toggle")
                    self.assertNotEqual(b1["bridge_enabled"], b2["bridge_enabled"])

                    # Web calibration: start -> skip LT, LB -> dpup gets Digital Mode warning on axis 1!
                    _, c0 = self._post(base, "/api/calibrate/web/start", {"dev_path": mev})
                    self.assertTrue(c0["active"])
                    self._post(base, "/api/calibrate/web/skip")  # LT skipped (LB is step 1 -> skip disabled, trigger btn 292!)
                    with urllib.request.urlopen(base + "/api/calibrate/web/poll", timeout=3) as r:
                        _ = json.loads(r.read())  # release wait_neutral
                    _emit(mfd, 1, 292, 1)
                    _emit(mfd, 0, 0, 0)
                    time.sleep(0.03)
                    with urllib.request.urlopen(base + "/api/calibrate/web/poll", timeout=3) as r:
                        c_lb = json.loads(r.read())
                    self.assertEqual(c_lb["current_step"]["key"], "dpup")
                    _emit(mfd, 1, 292, 0)
                    _emit(mfd, 0, 0, 0)
                    time.sleep(0.03)
                    with urllib.request.urlopen(base + "/api/calibrate/web/poll", timeout=3) as r:
                        _ = json.loads(r.read())  # clear waiting_neutral

                    # Move axis 1 during dpup -> should detect Digital Mode warning!
                    _emit(mfd, 3, 1, 0)
                    _emit(mfd, 0, 0, 0)
                    time.sleep(0.03)
                    with urllib.request.urlopen(base + "/api/calibrate/web/poll", timeout=3) as r:
                        c_warn = json.loads(r.read())
                    self.assertIsNotNone(c_warn["warning"])
                    self._post(base, "/api/calibrate/web/accept_warning")
                    _, c_prev = self._post(base, "/api/calibrate/web/prev")
                    self.assertEqual(c_prev["current_step"]["key"], "dpup")
                    _, saved = self._post(base, "/api/calibrate/web/save", {"name": "WebCal Test"})
                    self.assertTrue(saved["saved"])
                    self.assertEqual(evdev_utils.load_profiles(pdir)["1234:abcd"]["name"], "WebCal Test")

                    self._post(base, "/api/profiles/delete", {"vendor": "1234", "product": "abcd"})
                    self.assertNotIn("1234:abcd", evdev_utils.load_profiles(pdir))
                finally:
                    srv.shutdown()
                    srv.server_close()
            finally:
                res_app.cal_session.cancel()
                evdev_utils.resolve_profiles_dir = orig_resolve_pdir
                evdev_utils.resolve_config_path = orig_cfg_path
                res_app.resolve_profiles_dir = orig_app_pdir
                res_app.get_connected_gamepads = orig_get_gps_app
                res_app.load_profiles = orig_load_profs_app
                res_app.save_profile = orig_save_prof_app
                res_app.delete_profile = orig_del_prof_app
                fcntl.ioctl(mfd, UI_DEV_DESTROY)
                os.close(mfd)

    def test_single_instance_port_in_use_exits_zero(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        busy_port = sock.getsockname()[1]
        sock.listen(1)
        try:
            proc = subprocess.run(
                [sys.executable, os.path.join(LINUX_DIR, "app.py"), "--port", str(busy_port), "--no-browser"],
                capture_output=True, text=True, timeout=5
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("ya está corriendo", proc.stdout)
        finally:
            sock.close()


class TestSecurityAndPerformance(unittest.TestCase):
    def test_rejects_path_traversal_vendor_product(self):
        for bad in ("../../etc", "../x", "zzzz", "123g", ""):
            with self.assertRaises(ValueError):
                evdev_utils.normalize_profile_data({"vendor": bad, "product": "0001", "mapping": {}})
            with self.assertRaises(ValueError):
                evdev_utils.delete_profile(bad, "0001")

    def test_load_profiles_cache_and_mutation_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evdev_utils.save_profile(
                {"vendor": "abcd", "product": "1234", "name": "Original", "mapping": {"a": {"type": "btn", "code": 290}}},
                profiles_dir=tmpdir,
            )
            p1 = evdev_utils.load_profiles(tmpdir)
            self.assertEqual(p1["abcd:1234"]["name"], "Original")
            # Mutating returned dict must NOT corrupt cached snapshot
            p1["abcd:1234"]["name"] = "MutatedInRam"
            p2 = evdev_utils.load_profiles(tmpdir)
            self.assertEqual(p2["abcd:1234"]["name"], "Original")
            # Deleting must invalidate cache immediately
            self.assertTrue(evdev_utils.delete_profile("abcd", "1234", profiles_dir=tmpdir))
            self.assertEqual(evdev_utils.load_profiles(tmpdir), {})

    def test_http_csrf_dns_rebinding_and_security_headers(self):
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), res_app.ResiticksHTTPHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"
        try:
            # Security headers check & no wildcard CORS
            with urllib.request.urlopen(base + "/api/status", timeout=3) as r:
                self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
                self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"))

            # Cross-origin POST CSRF must be blocked with 403
            req = urllib.request.Request(
                base + "/api/bridge/toggle",
                data=b"{}",
                headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=3)
            self.assertEqual(ctx.exception.code, 403)
            ctx.exception.close()

            # DNS rebinding Host header must be blocked with 403
            req_host = urllib.request.Request(
                base + "/api/status",
                headers={"Host": "attacker.example:8765"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx2:
                urllib.request.urlopen(req_host, timeout=3)
            self.assertEqual(ctx2.exception.code, 403)
            ctx2.exception.close()
        finally:
            srv.shutdown()
            srv.server_close()


class TestFases234Features(unittest.TestCase):
    def test_sse_stream_delivers_status_json(self):
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), res_app.ResiticksHTTPHandler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stream", timeout=3) as r:
                self.assertEqual(r.status, 200)
                self.assertTrue(r.headers.get("Content-Type", "").startswith("text/event-stream"))
                line = b""
                for _ in range(10):
                    raw = r.readline()
                    if raw.startswith(b"data: "):
                        line = raw
                        break
                self.assertTrue(line.startswith(b"data: "))
                payload = json.loads(line[6:].decode("utf-8"))
                self.assertIn("active_slots", payload)
                self.assertIn("polling_hz", payload)
                self.assertIn("lan_protected", payload)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_lan_token_auth_blocks_and_authorizes(self):
        from http.server import ThreadingHTTPServer
        orig_token = res_app.state.lan_token
        res_app.state.lan_token = "secret_lan_tok"
        srv = ThreadingHTTPServer(("127.0.0.1", 0), res_app.ResiticksHTTPHandler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(base + "/api/status", timeout=3)
            self.assertEqual(ctx.exception.code, 401)
            ctx.exception.close()

            with urllib.request.urlopen(base + "/?token=secret_lan_tok", timeout=3) as r:
                self.assertEqual(r.status, 200)
                cookie = r.headers.get("Set-Cookie", "")
                self.assertIn("resiticks_token=secret_lan_tok", cookie)
                self.assertIn("HttpOnly", cookie)

            req_cookie = urllib.request.Request(
                base + "/api/status",
                headers={"Cookie": "resiticks_token=secret_lan_tok"},
            )
            with urllib.request.urlopen(req_cookie, timeout=3) as rc:
                self.assertEqual(rc.status, 200)

            req_bearer = urllib.request.Request(
                base + "/api/status",
                headers={"Authorization": "Bearer secret_lan_tok"},
            )
            with urllib.request.urlopen(req_bearer, timeout=3) as r2:
                self.assertEqual(r2.status, 200)
                data = json.loads(r2.read().decode())
                self.assertTrue(data["lan_protected"])
        finally:
            res_app.state.lan_token = orig_token
            srv.shutdown()
            srv.server_close()

    def test_stick_curves_and_outer_scale(self):
        # Diagonal circular stick (~0.707) scaled by 1.35x clamps nicely toward full outer reach
        diag = evdev_utils.apply_stick_curve(0.75, deadzone=0.05, outer_scale=1.35, curve="linear")
        self.assertGreater(diag, 0.95)
        self.assertLessEqual(diag, 1.0)

        lin = evdev_utils.apply_stick_curve(0.50, deadzone=0.0, outer_scale=1.0, curve="linear")
        prec = evdev_utils.apply_stick_curve(0.50, deadzone=0.0, outer_scale=1.0, curve="precise")
        aggr = evdev_utils.apply_stick_curve(0.50, deadzone=0.0, outer_scale=1.0, curve="aggressive")
        self.assertLess(prec, lin)
        self.assertLess(lin, aggr)
        self.assertAlmostEqual(prec, 0.5 ** 1.45, places=3)

    def test_windows_swaps_and_curve(self):
        prof = {
            "vendor": "057e",
            "product": "2009",
            "nintendo_swap": True,
            "trigger_bumper_swap": True,
            "mapping": {
                "a": {"type": "btn", "code": 304},
                "b": {"type": "btn", "code": 305},
                "x": {"type": "btn", "code": 307},
                "y": {"type": "btn", "code": 308},
                "lb": {"type": "btn", "code": 310},
                "lt": {"type": "btn", "code": 312},
            },
        }
        wmap = resiticks_windows.build_windows_translation(prof, num_axes=4, num_buttons=12, num_hats=1)
        # a(304->0) and b(305->1) are swapped; lb(310->4) and lt(312->compact 5) are swapped
        self.assertEqual(wmap["buttons"]["a"], 1)
        self.assertEqual(wmap["buttons"]["b"], 0)
        self.assertEqual(wmap["buttons"]["lb"], 5)
        self.assertEqual(wmap["buttons"]["lt"], 4)
        self.assertAlmostEqual(
            resiticks_windows._apply_deadzone(0.5, 0.0, outer_scale=1.0, curve="precise"),
            0.5 ** 1.45,
            places=3,
        )

    @unittest.skipUnless(_uinput_writable(), "/dev/uinput not writable")
    def test_worker_swaps_and_test_rumble_e2e(self):
        with open(os.path.join(PROFILES_DIR, "0079_0006.json"), "r", encoding="utf-8") as f:
            prof = json.load(f)
        prof["nintendo_swap"] = True
        prof["trigger_bumper_swap"] = True

        mfd, mev = _create_mock_uinput_pad()
        try:
            w = res_app.GamepadWorker({"vendor": "0079", "product": "0006", "name": "SwapTest", "dev_path": mev, "identifier": "test/swap"}, prof, 1, bridge_mode=True)
            w.start()
            for _ in range(40):
                if w.vpad is not None:
                    break
                time.sleep(0.03)
            self.assertIsNotNone(w.vpad)
            # Physical code 290 is "a" -> with nintendo_swap moves to "b"
            _emit(mfd, 1, 290, 1)
            # Physical code 294 is "lt" -> with trigger_bumper_swap moves to "lb"
            _emit(mfd, 1, 294, 1)
            _emit(mfd, 0, 0, 0)
            time.sleep(0.05)
            self.assertTrue(w.live_state["buttons"]["b"])
            self.assertFalse(w.live_state["buttons"]["a"])
            self.assertTrue(w.live_state["buttons"]["lb"])
            # Non-blocking test rumble pulse returns clean boolean without raising
            ok, msg = w.trigger_test_rumble()
            self.assertIsInstance(ok, bool)
            self.assertIsInstance(msg, str)
            time.sleep(0.05)
            w.stop(wait=True)
        finally:
            fcntl.ioctl(mfd, UI_DEV_DESTROY)
            os.close(mfd)

    def test_cli_help_lists_lan_and_daemon(self):
        import subprocess
        out = subprocess.check_output([sys.executable, os.path.join(LINUX_DIR, "app.py"), "--help"], text=True, timeout=5)
        self.assertIn("--lan", out)
        self.assertIn("--daemon", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
