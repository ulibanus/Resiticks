#!/usr/bin/env python3
import os
import sys
import struct
import select

EVENT_FORMAT = "qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

# Find connected gamepad
dev_path = "/dev/input/event19"
if not os.path.exists(dev_path):
    print("No existe /dev/input/event19")
    sys.exit(1)

print("=" * 60)
print(" 🔍 SNIFFER DE EVENTOS EN VIVO")
print(f" Escuchando {dev_path}...")
print(" Presioná los botones que NO te tomaba en el joystick.")
print(" Presioná Ctrl+C para salir.")
print("=" * 60)

fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)

try:
    while True:
        r, _, _ = select.select([fd], [], [])
        data = os.read(fd, EVENT_SIZE * 32)
        if not data:
            continue
        n = len(data) // EVENT_SIZE
        for i in range(n):
            tv_sec, tv_usec, ev_type, code, value = struct.unpack(EVENT_FORMAT, data[i*EVENT_SIZE:(i+1)*EVENT_SIZE])
            if ev_type == 1: # EV_KEY
                state = "PRESIONADO (1)" if value == 1 else ("SOLTADO (0)" if value == 0 else f"VALOR {value}")
                print(f"👉 BOTÓN: Código {code} (0x{code:03x}) -> {state}")
            elif ev_type == 3: # EV_ABS
                # Mostrar solo si no es ruido
                if code in (16, 17) or abs(value - 128) > 20 or (code in (2, 5) and value > 10):
                    print(f"📊 EJE/TRIGGER: Código {code} -> Valor {value}")
except KeyboardInterrupt:
    print("\nSniffer finalizado.")
finally:
    os.close(fd)
