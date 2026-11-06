import os
import fcntl
import struct

# Linux input & uinput constants
UI_SET_EVBIT   = 0x40045564
UI_SET_KEYBIT  = 0x40045565
UI_SET_ABSBIT  = 0x40045567
UI_ABS_SETUP   = 0x401c5504
UI_DEV_SETUP   = 0x405c5503
UI_DEV_CREATE  = 0x5501
UI_DEV_DESTROY = 0x5502

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0x00

# Xbox 360 button codes
BTN_A      = 0x130
BTN_B      = 0x131
BTN_X      = 0x133
BTN_Y      = 0x134
BTN_TL     = 0x136 # LB
BTN_TR     = 0x137 # RB
BTN_SELECT = 0x13a # Back
BTN_START  = 0x13b # Start
BTN_MODE   = 0x13c # Guide
BTN_THUMBL = 0x13d # L3
BTN_THUMBR = 0x13e # R3

# Xbox 360 axis codes
ABS_X     = 0x00 # Stick Izquierdo X (-32768..32767)
ABS_Y     = 0x01 # Stick Izquierdo Y (-32768..32767)
ABS_Z     = 0x02 # Gatillo LT (0..255)
ABS_RX    = 0x03 # Stick Derecho X (-32768..32767)
ABS_RY    = 0x04 # Stick Derecho Y (-32768..32767)
ABS_RZ    = 0x05 # Gatillo RT (0..255)
ABS_HAT0X = 0x10 # D-Pad X (-1..1)
ABS_HAT0Y = 0x11 # D-Pad Y (-1..1)

EVENT_FORMAT = "qqHHi"

class VirtualXboxPad:
    def __init__(self, player_num=1, custom_name=None):
        self.player_num = player_num
        self.custom_name = custom_name
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)

        # Enable Event Types
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_SYN)

        # Enable Buttons
        buttons = [
            BTN_A, BTN_B, BTN_X, BTN_Y,
            BTN_TL, BTN_TR, BTN_SELECT, BTN_START,
            BTN_MODE, BTN_THUMBL, BTN_THUMBR
        ]
        for btn in buttons:
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, btn)

        # Enable and configure Axes
        stick_axes = [ABS_X, ABS_Y, ABS_RX, ABS_RY]
        for axis in stick_axes:
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
            setup = struct.pack("HHiiiiii", axis, 0, 0, -32768, 32767, 16, 128, 0)
            fcntl.ioctl(self.fd, UI_ABS_SETUP, setup)

        triggers = [ABS_Z, ABS_RZ]
        for axis in triggers:
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
            setup = struct.pack("HHiiiiii", axis, 0, 0, 0, 255, 0, 0, 0)
            fcntl.ioctl(self.fd, UI_ABS_SETUP, setup)

        dpad_axes = [ABS_HAT0X, ABS_HAT0Y]
        for axis in dpad_axes:
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
            setup = struct.pack("HHiiiiii", axis, 0, 0, -1, 1, 0, 0, 0)
            fcntl.ioctl(self.fd, UI_ABS_SETUP, setup)

        # Nombre identificatorio claro para PES, Steam y Windows
        if custom_name:
            display_name = f"Resiticks {player_num} - {custom_name}"
        else:
            display_name = f"Resiticks {player_num} (Xbox 360)"

        name_bytes = display_name.encode("utf-8")[:79]
        setup_data = struct.pack("HHHH80sI", 0x03, 0x045e, 0x028e, 0x0114, name_bytes, 0)
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup_data)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)

    def emit(self, ev_type, code, value):
        data = struct.pack(EVENT_FORMAT, 0, 0, ev_type, code, value)
        os.write(self.fd, data)

    def sync(self):
        self.emit(EV_SYN, SYN_REPORT, 0)

    def emit_key(self, code, is_pressed):
        self.emit(EV_KEY, code, 1 if is_pressed else 0)

    def emit_abs(self, code, value):
        self.emit(EV_ABS, code, value)

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
            os.close(self.fd)
        except:
            pass
