#!/usr/bin/env python3
"""
Preload standard Sony DualShock 4 and Microsoft Xbox controller JSON profiles
into Resiticks's resolved profiles directory without overwriting existing files.
"""
import json
import os

from evdev_utils import resolve_profiles_dir

ps4_mapping = {
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
    "x": {"type": "btn", "code": 308},
    "y": {"type": "btn", "code": 307},
    "back": {"type": "btn", "code": 314},
    "start": {"type": "btn", "code": 315},
    "guide": {"type": "btn", "code": 316},
    "thumbl": {"type": "btn", "code": 317},
    "thumbr": {"type": "btn", "code": 318},
    "leftx": {"type": "axis", "code": 0, "direction": 1},
    "lefty": {"type": "axis", "code": 1, "direction": 1},
    "rightx": {"type": "axis", "code": 3, "direction": 1},
    "righty": {"type": "axis", "code": 4, "direction": 1},
}

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
    "righty": {"type": "axis", "code": 4, "direction": 1},
}

DEVICES = [
    ("054c", "05c4", "Sony DualShock 4 (V1)", ps4_mapping),
    ("054c", "09cc", "Sony DualShock 4 (V2 / Slim / Pro)", ps4_mapping),
    ("054c", "0ba0", "Sony DualShock 4 USB Wireless Adapter", ps4_mapping),
    ("045e", "0291", "Xbox 360 Wireless Receiver", xbox_mapping),
    ("045e", "0719", "Xbox 360 Wireless Controller Adapter", xbox_mapping),
    ("045e", "02d1", "Xbox One Controller", xbox_mapping),
    ("045e", "02dd", "Xbox One Controller (Firmware 2015)", xbox_mapping),
    ("045e", "02ea", "Xbox One S Controller", xbox_mapping),
    ("045e", "0b12", "Xbox Series X|S Controller", xbox_mapping),
]


def main():
    """Populate missing official controller profiles into the profiles directory."""
    profiles_dir = resolve_profiles_dir()
    created = 0
    for vendor, product, name, mapping in DEVICES:
        profile_data = {
            "name": name,
            "vendor": vendor,
            "product": product,
            "mapping": mapping,
        }
        path = os.path.join(profiles_dir, f"{vendor}_{product}.json")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2)
            print(f"Creado perfil estándar: {name} -> {vendor}_{product}.json")
            created += 1
    print(f"Listo ({profiles_dir}): {created} perfil(es) nuevo(s) agregado(s).")


if __name__ == "__main__":
    main()
