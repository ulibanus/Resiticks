# 🎮 RESITICKS — Hub Universal de Joysticks

Hub universal multiplataforma para gestionar y normalizar mandos genéricos USB y Bluetooth para **PES 6** (hasta 8 jugadores), **Steam**, emuladores y juegos de PC.

---

## 🚀 1. Cómo usarlo para jugar

1. Conectá todos los joysticks (USB o Bluetooth).
2. Ejecutá en la terminal:
   ```bash
   ./iniciar_resiticks.sh
   # O directamente:
   python3 app.py
   ```
3. Se abrirá la ventana con los **8 slots de jugadores** en vivo y diagnóstico anti-drift.
4. Dejá Resiticks abierto de fondo y abrí el juego.

---

## ⚽ 2. Configuración en PES 6 Settings (`settings.exe`)

En PES Settings, asigná cada jugador con su mando virtual oficial de Xbox 360:

| Pestaña en PES Settings | Opción a seleccionar en Device | Slot en Resiticks |
| :--- | :--- | :--- |
| **Player 1** | `Controller (XBOX 360 For Windows)` | Jugador 1 [P1] |
| **Player 2** | `Controller (XBOX 360 For Windows) - 2` | Jugador 2 [P2] |
| **Player 3** | `Controller (XBOX 360 For Windows) - 3` | Jugador 3 [P3] |
| **Player 4** | `Controller (XBOX 360 For Windows) - 4` | Jugador 4 [P4] |
| *(Hasta Player 8)* | `Controller (XBOX 360 For Windows) - X` | Jugador X [PX] |

> [!IMPORTANT]
> **No elijas nombres como "Microntek" o "Gasia":** Esos son los mandos físicos en bruto con botones cruzados. Eligiendo los que dicen `Controller (XBOX 360...)` tenés garantizadas las 4 direcciones de palancas y botones ordenados al 100%.

---

## 🎯 3. Cómo calibrar un joystick nuevo por consola (`calibrate.py`)

Si cae un amigo con un joystick que nunca antes conectaron:

1. Enchufá el joystick nuevo.
2. En la terminal ejecutá:
   ```bash
   ./calibrar_nuevo_mando.sh
   # O directamente:
   python3 calibrate.py
   ```
3. Seleccioná el número correspondiente en la lista.
4. Seguí el orden exacto de PES Settings que te pide en pantalla:
   * **Columna Izquierda:** L2 → L1 → Flechas (Arriba, Izq, Abajo, Der) → Stick Izq (Arriba, Izq, Abajo, Der) → L3 → Select.
   * **Columna Derecha:** R2 → R1 → Triángulo → Cuadrado → Cruz → Círculo → Stick Der (Arriba, Izq, Abajo, Der) → R3 → Start.
   *(Podés presionar `Enter` en el teclado para saltear cualquier botón que no tenga).*
5. Al final te pedirá:
   `"¿Qué nombre querés ponerle a este joystick?:"`
   Escribí el nombre de tu amigo (ej: *"Joystick de Lucas"*) y dale `Enter`.

El perfil se guarda automáticamente en `profiles/` y nunca más vas a tener que volver a calibrarlo.

---

## 📂 4. Mandos ya calibrados incluidos en este Pack

* 🎮 **Joystick Aitor** (`0079:0006` - DragonRise / Microntek)
* 🎮 **JOYSTICK GMX Julian G** (`0e8f:0008` - Gasia)
* 🎮 **Joystick Ramiro-Chino** (`20d6:576d` - BDA OPP)
* 🎮 **Redragon Fausto** (`057e:2009` - Switch Pro Mode)
* 🎮 **Redragon Mate** (`045e:028e` - Xbox Mode)
* 🎮 **Joystick camuflado Daco** (`054c:0268` - PS3 DualShock 3)
* 🎮 **Sony DualShock 4** (PS4 V1, V2 y Dongle USB)
* 🎮 **Mandos oficiales Xbox** (Xbox 360, Xbox One, Series X|S)
