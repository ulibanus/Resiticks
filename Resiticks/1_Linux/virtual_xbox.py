#!/usr/bin/env python3
"""
Linux uinput Xbox 360 virtual controller emulation with safe UTF-8 naming,
idempotent cleanup, and optional EV_FF (rumble) passthrough.
"""
import os
import fcntl
import struct
import time

# Linux input & uinput constants (x86_64)
UI_SET_EVBIT   = 0x40045564
UI_SET_KEYBIT  = 0x40045565
UI_SET_ABSBIT  = 0x40045567
UI_SET_FFBIT   = 0x4004556b
UI_ABS_SETUP   = 0x401c5504
UI_DEV_SETUP   = 0x405c5503
UI_DEV_CREATE  = 0x5501
UI_DEV_DESTROY = 0x5502

UI_BEGIN_FF_UPLOAD = 0xc06855c8
UI_END_FF_UPLOAD   = 0x406855c9
UI_BEGIN_FF_ERASE  = 0xc00c55ca
UI_END_FF_ERASE    = 0x400c55cb
EVIOCSFF           = 0x40304580
EVIOCRMFF          = 0x40044581

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
EV_FF  = 0x15
EV_UINPUT = 0x0101

SYN_REPORT   = 0x00
UI_FF_UPLOAD = 1
UI_FF_ERASE  = 2
FF_RUMBLE    = 0x50

# Xbox 360 button codes
BTN_A      = 0x130
BTN_B      = 0x131
BTN_X      = 0x133
BTN_Y      = 0x134
BTN_TL     = 0x136  # LB
BTN_TR     = 0x137  # RB
BTN_SELECT = 0x13a  # Back
BTN_START  = 0x13b  # Start
BTN_MODE   = 0x13c  # Guide
BTN_THUMBL = 0x13d  # L3
BTN_THUMBR = 0x13e  # R3

# Xbox 360 axis codes
ABS_X     = 0x00  # Stick Izquierdo X (-32768..32767)
ABS_Y     = 0x01  # Stick Izquierdo Y (-32768..32767)
ABS_Z     = 0x02  # Gatillo LT (0..255)
ABS_RX    = 0x03  # Stick Derecho X (-32768..32767)
ABS_RY    = 0x04  # Stick Derecho Y (-32768..32767)
ABS_RZ    = 0x05  # Gatillo RT (0..255)
ABS_HAT0X = 0x10  # D-Pad X (-1..1)
ABS_HAT0Y = 0x11  # D-Pad Y (-1..1)

EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)


def _utf8_truncate(text, max_bytes=79):
    """Truncate text so its UTF-8 encoding never exceeds max_bytes or splits a multi-byte char."""
    encoded = text.encode("utf-8", errors="ignore")
    if len(encoded) <= max_bytes:
        return encoded
    cut = encoded[:max_bytes]
    # Trim trailing UTF-8 continuation bytes (10xxxxxx) or incomplete leading byte
    while cut:
        try:
            cut.decode("utf-8")
            return cut
        except UnicodeDecodeError:
            cut = cut[:-1]
    return b""


class VirtualXboxPad:
    """Represents a single uinput Xbox 360 controller visible to Wine/Proton/Steam."""

    def __init__(self, player_num=1, custom_name=None, enable_rumble=True):
        """Initialize and register the virtual Xbox 360 device via /dev/uinput."""
        self.player_num = player_num
        self.custom_name = custom_name
        self.enable_rumble = bool(enable_rumble)
        self.fd = None
        self._ff_map = {}  # virtual effect id -> physical effect id
        self._batch = bytearray()
        self._last_values = {}  # (ev_type, code) -> last emitted value

        flags = (os.O_RDWR if self.enable_rumble else os.O_WRONLY) | os.O_NONBLOCK
        self.fd = os.open("/dev/uinput", flags)
        try:
            self._configure_device()
        except Exception:
            self.close()
            raise

    def _configure_device(self):
        """Configure capabilities, axes, optional force-feedback, and create uinput node."""
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_SYN)

        if self.enable_rumble:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_FF)
            fcntl.ioctl(self.fd, UI_SET_FFBIT, FF_RUMBLE)

        buttons = (
            BTN_A, BTN_B, BTN_X, BTN_Y,
            BTN_TL, BTN_TR, BTN_SELECT, BTN_START,
            BTN_MODE, BTN_THUMBL, BTN_THUMBR,
        )
        for btn in buttons:
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, btn)

        for axis in (ABS_X, ABS_Y, ABS_RX, ABS_RY):
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
            setup = struct.pack("HHiiiiii", axis, 0, 0, -32768, 32767, 16, 128, 0)
            fcntl.ioctl(self.fd, UI_ABS_SETUP, setup)

        for axis in (ABS_Z, ABS_RZ):
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
            setup = struct.pack("HHiiiiii", axis, 0, 0, 0, 255, 0, 0, 0)
            fcntl.ioctl(self.fd, UI_ABS_SETUP, setup)

        for axis in (ABS_HAT0X, ABS_HAT0Y):
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
            setup = struct.pack("HHiiiiii", axis, 0, 0, -1, 1, 0, 0, 0)
            fcntl.ioctl(self.fd, UI_ABS_SETUP, setup)

        if self.custom_name:
            display_name = f"Resiticks {self.player_num} - {self.custom_name}"
        else:
            display_name = f"Resiticks {self.player_num} (Xbox 360)"

        name_bytes = _utf8_truncate(display_name, 79)
        ff_max = 16 if self.enable_rumble else 0
        setup_data = struct.pack("HHHH80sI", 0x03, 0x045e, 0x028e, 0x0114, name_bytes, ff_max)
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup_data)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)

    def _write_raw(self, payload):
        """Write packed input_event bytes to uinput, retrying briefly if non-blocking buffer is full."""
        fd = self.fd
        if fd is None or not payload:
            return
        view = memoryview(payload)
        offset = 0
        while offset < len(view):
            wrote = False
            for _ in range(4):
                try:
                    n = os.write(fd, view[offset:])
                    offset += n
                    wrote = True
                    break
                except BlockingIOError:
                    time.sleep(0.0005)
                except OSError:
                    return
            if not wrote:
                return

    def emit(self, ev_type, code, value):
        """Queue a changed EV_KEY/EV_ABS event (or flush on EV_SYN) to reduce syscalls and noise."""
        if self.fd is None:
            return
        if ev_type == EV_SYN:
            self.sync()
            return
        key = (ev_type, code)
        if self._last_values.get(key) == value:
            return
        self._last_values[key] = value
        self._batch.extend(struct.pack(EVENT_FORMAT, 0, 0, ev_type, code, value))

    def sync(self):
        """Commit queued events with SYN_REPORT in a single syscall; no-op when queue is empty."""
        if self.fd is None or not self._batch:
            return
        self._batch.extend(struct.pack(EVENT_FORMAT, 0, 0, EV_SYN, SYN_REPORT, 0))
        payload = bytes(self._batch)
        self._batch.clear()
        self._write_raw(payload)

    def emit_key(self, code, is_pressed):
        """Emit a digital key event."""
        self.emit(EV_KEY, code, 1 if is_pressed else 0)

    def emit_abs(self, code, value):
        """Emit an absolute axis or hat event."""
        self.emit(EV_ABS, code, value)

    def handle_ff_events(self, phys_fd=None, forward_rumble=False):
        """
        Service pending Force Feedback / EV_UINPUT upload & erase requests from games.
        Must always ACK uploads/erases so Wine/Steam games never stall even if physical rumble is off.
        """
        fd = self.fd
        if fd is None or not self.enable_rumble:
            return
        try:
            raw = os.read(fd, EVENT_SIZE * 16)
        except OSError:
            return
        if not raw:
            return

        n = len(raw) // EVENT_SIZE
        for i in range(n):
            _, _, ev_type, code, value = struct.unpack(EVENT_FORMAT, raw[i * EVENT_SIZE : (i + 1) * EVENT_SIZE])
            if ev_type == EV_UINPUT and code == UI_FF_UPLOAD:
                self._handle_ff_upload(value, phys_fd if forward_rumble else None)
            elif ev_type == EV_UINPUT and code == UI_FF_ERASE:
                self._handle_ff_erase(value, phys_fd if forward_rumble else None)
            elif ev_type == EV_FF and forward_rumble and phys_fd is not None:
                phys_id = self._ff_map.get(code)
                if phys_id is not None:
                    try:
                        os.write(phys_fd, struct.pack(EVENT_FORMAT, 0, 0, EV_FF, phys_id, value))
                    except OSError:
                        pass

    def _handle_ff_upload(self, req_id, phys_fd):
        """Complete UI_BEGIN_FF_UPLOAD/UI_END_FF_UPLOAD handshake and forward effect to physical pad."""
        buf = bytearray(104)
        struct.pack_into("I", buf, 0, req_id)
        try:
            fcntl.ioctl(self.fd, UI_BEGIN_FF_UPLOAD, buf)
        except OSError:
            return

        virt_eff = bytearray(buf[8:56])
        virt_id = struct.unpack_from("h", virt_eff, 2)[0]
        if phys_fd is not None:
            phys_eff = bytearray(virt_eff)
            existing = self._ff_map.get(virt_id, -1)
            struct.pack_into("h", phys_eff, 2, existing)
            try:
                fcntl.ioctl(phys_fd, EVIOCSFF, phys_eff)
                phys_id = struct.unpack_from("h", phys_eff, 2)[0]
                if phys_id >= 0:
                    self._ff_map[virt_id] = phys_id
            except OSError:
                pass

        struct.pack_into("i", buf, 4, 0)
        try:
            fcntl.ioctl(self.fd, UI_END_FF_UPLOAD, buf)
        except OSError:
            pass

    def _handle_ff_erase(self, req_id, phys_fd):
        """Complete UI_BEGIN_FF_ERASE/UI_END_FF_ERASE handshake and remove physical FF effect."""
        buf = bytearray(12)
        struct.pack_into("I", buf, 0, req_id)
        try:
            fcntl.ioctl(self.fd, UI_BEGIN_FF_ERASE, buf)
        except OSError:
            return

        virt_id = struct.unpack_from("I", buf, 8)[0]
        phys_id = self._ff_map.pop(virt_id, None)
        if phys_fd is not None and phys_id is not None:
            try:
                fcntl.ioctl(phys_fd, EVIOCRMFF, phys_id)
            except OSError:
                pass

        struct.pack_into("i", buf, 4, 0)
        try:
            fcntl.ioctl(self.fd, UI_END_FF_ERASE, buf)
        except OSError:
            pass

    def close(self):
        """Safely destroy the uinput device and close its descriptor idempotently."""
        fd = self.fd
        if fd is None:
            return
        self.fd = None
        try:
            fcntl.ioctl(fd, UI_DEV_DESTROY)
        except OSError:
            pass
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
