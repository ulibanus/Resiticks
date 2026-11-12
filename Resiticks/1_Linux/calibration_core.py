#!/usr/bin/env python3
"""
Shared PES-order calibration definitions, smart input detection, digital-mode detection,
center-return gating, and canonical profile assembly for CLI and Web UI calibration.
"""
import os
import select
import struct
import time

EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

EV_KEY = 0x01
EV_ABS = 0x03
ABS_HAT0X = 16
ABS_HAT0Y = 17

# Official 2-column Konami PES Settings order (+ optional Guide at end)
CALIBRATION_STEPS = [
    # Left column
    {"key": "lt", "col": "left", "badge": "L2 / LT", "prompt": "1. [Lado Izq] Presioná Gatillo L2 / LT", "allow_skip": True},
    {"key": "lb", "col": "left", "badge": "L1 / LB", "prompt": "2. [Lado Izq] Presioná Botón L1 / LB", "allow_skip": False},
    {"key": "dpup", "col": "left", "badge": "▲ D-Pad", "prompt": "3. [Lado Izq] D-Pad: Flecha ARRIBA", "allow_skip": False},
    {"key": "dpleft", "col": "left", "badge": "◀ D-Pad", "prompt": "4. [Lado Izq] D-Pad: Flecha IZQUIERDA", "allow_skip": False},
    {"key": "dpdown", "col": "left", "badge": "▼ D-Pad", "prompt": "5. [Lado Izq] D-Pad: Flecha ABAJO", "allow_skip": False},
    {"key": "dpright", "col": "left", "badge": "▶ D-Pad", "prompt": "6. [Lado Izq] D-Pad: Flecha DERECHA", "allow_skip": False},
    {"key": "left_up", "col": "left", "badge": "L-Stick ▲", "prompt": "7. [Lado Izq] Stick Izquierdo: Mové hacia ARRIBA", "allow_skip": True},
    {"key": "left_left", "col": "left", "badge": "L-Stick ◀", "prompt": "8. [Lado Izq] Stick Izquierdo: Mové hacia IZQUIERDA", "allow_skip": True},
    {"key": "left_down", "col": "left", "badge": "L-Stick ▼", "prompt": "9. [Lado Izq] Stick Izquierdo: Mové hacia ABAJO", "allow_skip": True},
    {"key": "left_right", "col": "left", "badge": "L-Stick ▶", "prompt": "10. [Lado Izq] Stick Izquierdo: Mové hacia DERECHA", "allow_skip": True},
    {"key": "thumbl", "col": "left", "badge": "L3", "prompt": "11. [Lado Izq] Click Stick Izquierdo (L3)", "allow_skip": True},
    {"key": "back", "col": "left", "badge": "SELECT", "prompt": "12. [Lado Izq] Botón SELECT / BACK", "allow_skip": False},
    # Right column
    {"key": "rt", "col": "right", "badge": "R2 / RT", "prompt": "13. [Lado Der] Presioná Gatillo R2 / RT", "allow_skip": True},
    {"key": "rb", "col": "right", "badge": "R1 / RB", "prompt": "14. [Lado Der] Presioná Botón R1 / RB", "allow_skip": False},
    {"key": "y", "col": "right", "badge": "△ / Y", "prompt": "15. [Lado Der] Botón TRIÁNGULO / Y (Superior)", "allow_skip": False},
    {"key": "x", "col": "right", "badge": "▢ / X", "prompt": "16. [Lado Der] Botón CUADRADO / X (Izquierdo)", "allow_skip": False},
    {"key": "a", "col": "right", "badge": "✕ / A", "prompt": "17. [Lado Der] Botón CRUZ / A (Inferior)", "allow_skip": False},
    {"key": "b", "col": "right", "badge": "◯ / B", "prompt": "18. [Lado Der] Botón CÍRCULO / B (Derecho)", "allow_skip": False},
    {"key": "right_up", "col": "right", "badge": "R-Stick ▲", "prompt": "19. [Lado Der] Stick Derecho: Mové hacia ARRIBA", "allow_skip": True},
    {"key": "right_left", "col": "right", "badge": "R-Stick ◀", "prompt": "20. [Lado Der] Stick Derecho: Mové hacia IZQUIERDA", "allow_skip": True},
    {"key": "right_down", "col": "right", "badge": "R-Stick ▼", "prompt": "21. [Lado Der] Stick Derecho: Mové hacia ABAJO", "allow_skip": True},
    {"key": "right_right", "col": "right", "badge": "R-Stick ▶", "prompt": "22. [Lado Der] Stick Derecho: Mové hacia DERECHA", "allow_skip": True},
    {"key": "thumbr", "col": "right", "badge": "R3", "prompt": "23. [Lado Der] Click Stick Derecho (R3)", "allow_skip": True},
    {"key": "start", "col": "right", "badge": "START", "prompt": "24. [Lado Der] Botón START", "allow_skip": False},
    {"key": "guide", "col": "right", "badge": "HOME / XBOX", "prompt": "25. [Opcional] Botón HOME / PS / XBOX (Enter para saltear)", "allow_skip": True},
]


def is_axis_at_rest(code, value, abs_info):
    """Return True if an EV_ABS value has returned near its rest position (handles sticks & triggers)."""
    if code in (ABS_HAT0X, ABS_HAT0Y):
        return value == 0
    info = abs_info.get(code)
    if not info:
        return True
    val_min = info.get("min", 0)
    val_max = info.get("max", 255)
    rest_val = info.get("val", 0)
    full_span = val_max - val_min
    if full_span <= 0:
        return True
    rest_ratio = (rest_val - val_min) / full_span
    # Unipolar trigger resting near min (0..255 or 0..1023)
    if val_min >= 0 and rest_ratio < 0.25:
        return (value - val_min) / full_span < 0.20
    # Inverted unipolar trigger resting near max
    if val_min >= 0 and rest_ratio > 0.85:
        return (val_max - value) / full_span < 0.20
    mid = (val_min + val_max) / 2.0
    half_span = full_span / 2.0
    return abs((value - mid) / half_span) < 0.22


def drain_and_wait_neutral(fd, abs_info, live_abs=None, held_keys=None, max_wait=1.5):
    """Wait briefly until buffered events settle and held axes/buttons return to neutral."""
    live_abs = live_abs if live_abs is not None else {}
    held_keys = held_keys if held_keys is not None else set()
    deadline = time.monotonic() + max_wait
    quiet_since = time.monotonic()

    while time.monotonic() < deadline:
        r, _, _ = select.select([fd], [], [], 0.04)
        if r:
            try:
                raw = os.read(fd, EVENT_SIZE * 64)
            except BlockingIOError:
                raw = b""
            except OSError:
                break
            n = len(raw) // EVENT_SIZE
            for i in range(n):
                _, _, ev_type, code, value = struct.unpack(
                    EVENT_FORMAT, raw[i * EVENT_SIZE : (i + 1) * EVENT_SIZE]
                )
                if ev_type == EV_KEY:
                    if value == 0:
                        held_keys.discard(code)
                    else:
                        held_keys.add(code)
                elif ev_type == EV_ABS:
                    live_abs[code] = value
            quiet_since = time.monotonic()
            continue

        all_axes_neutral = all(is_axis_at_rest(c, v, abs_info) for c, v in live_abs.items())
        if not held_keys and all_axes_neutral and (time.monotonic() - quiet_since) >= 0.08:
            break


def detect_input_event(ev_type, code, value, abs_info):
    """
    Classify a raw Linux input event into a canonical calibration entry.
    Supports buttons, hats, 8/10/16-bit unipolar triggers, and centered sticks.
    """
    if ev_type == EV_KEY and value == 1:
        return {"type": "btn", "code": code}

    if ev_type == EV_ABS and code in (ABS_HAT0X, ABS_HAT0Y):
        if value != 0:
            return {"type": "hat", "code": code, "value": 1 if value > 0 else -1}
        return None

    if ev_type == EV_ABS and code not in (ABS_HAT0X, ABS_HAT0Y):
        info = abs_info.get(code, {"min": 0, "max": 255, "val": 0})
        val_min = info.get("min", 0)
        val_max = info.get("max", 255)
        rest_val = info.get("val", 0)
        full_span = val_max - val_min
        if full_span <= 0:
            return None

        rest_ratio = (rest_val - val_min) / full_span
        # Handles 8-bit (0..255), 10-bit Xbox One (0..1023), and 16-bit unipolar triggers
        if val_min >= 0 and rest_ratio < 0.25:
            if (value - val_min) / full_span > 0.55:
                return {"type": "axis", "code": code, "direction": 1, "value": value, "is_trigger": True}
            return None

        if val_min >= 0 and rest_ratio > 0.85:
            if (val_max - value) / full_span > 0.55:
                return {"type": "axis", "code": code, "direction": -1, "value": value, "is_trigger": True}
            return None

        mid = (val_min + val_max) / 2.0
        half_span = full_span / 2.0
        deviation = (value - mid) / half_span
        if abs(deviation) > 0.48:
            direction = 1 if deviation > 0 else -1
            return {"type": "axis", "code": code, "direction": direction, "value": value}

    return None


def detect_digital_mode_warning(step_key, detected):
    """Detect common DragonRise/generic Digital Mode (ANALOG LED OFF) accidents."""
    if not detected:
        return None
    if step_key in ("dpup", "dpdown", "dpleft", "dpright"):
        if detected.get("type") == "axis" and detected.get("code") in (0, 1):
            return (
                "Se detectó el Stick Izquierdo al presionar la cruceta (D-Pad). "
                "En joysticks genéricos/DragonRise esto indica que la luz roja ANALOG está apagada. "
                "Encendé el botón ANALOG/MODE antes de calibrar este paso."
            )
    if step_key in ("right_up", "right_left", "right_down", "right_right"):
        if detected.get("type") == "btn" and detected.get("code") in (288, 289, 290, 291):
            return (
                "Se detectaron botones frontales (△/◯/✕/▢) al mover el Stick Derecho. "
                "Esto pasa cuando la luz roja ANALOG/MODE está apagada. "
                "Encendé el LED ANALOG en el mando y repetí este paso."
            )
    return None


def derive_canonical_axes(mapping):
    """
    Build leftx/lefty/rightx/righty safely from calibrated directional entries,
    validating axis type and preserving the actual hardware axis direction.
    """
    out = dict(mapping)
    specs = [
        ("leftx", "left_right", "left_left"),
        ("lefty", "left_down", "left_up"),
        ("rightx", "right_right", "right_left"),
        ("righty", "right_down", "right_up"),
    ]
    for canon, pos_key, neg_key in specs:
        pos = out.get(pos_key)
        neg = out.get(neg_key)
        if pos and pos.get("type") == "axis":
            out[canon] = {
                "type": "axis",
                "code": pos["code"],
                "direction": pos.get("direction", 1),
            }
        elif neg and neg.get("type") == "axis":
            out[canon] = {
                "type": "axis",
                "code": neg["code"],
                "direction": -neg.get("direction", 1),
            }
        else:
            # Do not store broken button codes as axis mappings
            out.pop(canon, None)
    return out


def validate_calibration_consistency(mapping):
    """Return list of human-readable warnings if opposing stick directions point to mismatched axes."""
    warnings = []
    pairs = [
        ("Stick Izq Horizontal", "left_left", "left_right"),
        ("Stick Izq Vertical", "left_up", "left_down"),
        ("Stick Der Horizontal", "right_left", "right_right"),
        ("Stick Der Vertical", "right_up", "right_down"),
    ]
    for label, k1, k2 in pairs:
        v1, v2 = mapping.get(k1), mapping.get(k2)
        if not v1 or not v2:
            continue
        if v1.get("type") == "axis" and v2.get("type") == "axis":
            if v1.get("code") != v2.get("code"):
                warnings.append(f"{label}: {k1} usó eje {v1.get('code')} pero {k2} usó eje {v2.get('code')}.")
            elif v1.get("direction") == v2.get("direction"):
                warnings.append(f"{label}: {k1} y {k2} registraron la misma dirección ({v1.get('direction')}).")
    return warnings
