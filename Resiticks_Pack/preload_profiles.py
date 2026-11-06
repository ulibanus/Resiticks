#!/usr/bin/env python3
import json
import os

PROFILES_DIR = os.path.expanduser("~/joybridge/profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

# 1. Base PS4 DualShock 4 mapping
ps4_mapping = {
    "lt": {"type": "axis", "code": 2, "direction": 1, "is_trigger": True},
    "rt": {"type": "axis", "code": 5, "direction": 1, "is_trigger": True},
    "lb": {"type": "btn", "code": 310},
    "rb": {"type": "btn", "code": 311},
    "dpup": {"type": "hat", "code": 17, "value": -1},
    "dpdown": {"type": "hat", "code": 17, "value": 1},
    "dpleft": {"type": "hat", "code": 16, "value": -1},
    "dpright": {"type": "hat", "code": 16, "value": 1},
    "a": {"type": "btn", "code": 304}, # Cruz
    "b": {"type": "btn", "code": 305}, # Círculo
    "x": {"type": "btn", "code": 308}, # Cuadrado
    "y": {"type": "btn", "code": 307}, # Triángulo
    "back": {"type": "btn", "code": 314}, # Share
    "start": {"type": "btn", "code": 315}, # Options
    "guide": {"type": "btn", "code": 316}, # PS Button
    "thumbl": {"type": "btn", "code": 317}, # L3
    "thumbr": {"type": "btn", "code": 318}, # R3
    "leftx": {"type": "axis", "code": 0, "direction": 1},
    "lefty": {"type": "axis", "code": 1, "direction": 1},
    "rightx": {"type": "axis", "code": 3, "direction": 1},
    "righty": {"type": "axis", "code": 4, "direction": 1}
}

# 2. Base Xbox (360 Wireless / Xbox One / Series S/X) mapping
xbox_mapping = {
    "lt": {"type": "axis", "code": 2, "direction": 1, "is_trigger": True},
    "rt": {"type": "axis", "code": 5, "direction": 1, "is_trigger": True},
    "lb": {"type": "btn", "code": 310},
    "rb": {"type": "btn", "code": 311},
    "dpup": {"type": "hat", "code": 17, "value": -1},
    "dpdown": {"type": "hat", "code": 17, "value": 1},
    "dpleft": {"type": "hat", "code": 16, "value": -1},
    "dpright": {"type": "hat", "code": 16, "value": 1},
    "a": {"type": "btn", "code": 304},
    "b": {"type": "btn", "code": 305},
    "x": {"type": "btn", "code": 307},
    "y": {"type": "btn", "code": 308},
    "back": {"type": "btn", "code": 314},
    "start": {"type": "btn", "code": 315},
    "guide": {"type": "btn", "code": 316},
    "thumbl": {"type": "btn", "code": 317},
    "thumbr": {"type": "btn", "code": 318},
    "leftx": {"type": "axis", "code": 0, "direction": 1},
    "lefty": {"type": "axis", "code": 1, "direction": 1},
    "rightx": {"type": "axis", "code": 3, "direction": 1},
    "righty": {"type": "axis", "code": 4, "direction": 1}
}

devices = [
    # PS4
    ("054c", "05c4", "Sony DualShock 4 (V1)", ps4_mapping),
    ("054c", "09cc", "Sony DualShock 4 (V2 / Slim / Pro)", ps4_mapping),
    ("054c", "0ba0", "Sony DualShock 4 USB Wireless Adapter", ps4_mapping),
    # Xbox
    ("045e", "0291", "Xbox 360 Wireless Receiver", xbox_mapping),
    ("045e", "0719", "Xbox 360 Wireless Controller Adapter", xbox_mapping),
    ("045e", "02d1", "Xbox One Controller", xbox_mapping),
    ("045e", "02dd", "Xbox One Controller (Firmware 2015)", xbox_mapping),
    ("045e", "02ea", "Xbox One S Controller", xbox_mapping),
    ("045e", "0b12", "Xbox Series X|S Controller", xbox_mapping),
]

for vendor, product, name, mapping in devices:
    profile_data = {
        "name": name,
        "vendor": vendor,
        "product": product,
        "mapping": mapping
    }
    path = os.path.join(PROFILES_DIR, f"{vendor}_{product}.json")
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(profile_data, f, indent=2)
        print(f"Creado perfil estándar: {name} -> {vendor}_{product}.json")

print("Listo: perfiles oficiales precargados.")
