# BLE protocol

The repo uses two laptop→hub protocols. Both are plain ASCII lines sent to the Pybricks program's **stdin** over Pybricks' BLE service.

| | Live tracking (demo) | Scripted task demos |
|---|---|---|
| Laptop side | `run_ble_bridge.py` (pybricksdev) | `Roboarm_tasks/spike_ble_bridge.py` (bleak) |
| Hub side | `spike_hub_arm.py` | `Roboarm_tasks/hub_pybricks_receiver.py` |
| Program start | Uploaded and started by the bridge | Loaded via Pybricks Code, started with the hub button |
| Line format | `yaw,roll,thumb,index,middle,ring,pinky` | `M,<ms>,thumb,index,middle,ring,pinky,wrist,yaw`, `STOP`, `BYE` |
| Flow control | None (send on change) | Waits for the hub's `rdy` before each write |

## 1. Live tracking protocol

### Command format

One line of **7 comma-separated integers**, with no spaces and newline-terminated on the wire:

```
yaw,roll,thumb,index,middle,ring,pinky
```

Example (neutral): `0,0,0,0,0,0,0`

| Field | Name | Produced by `robot_hand_tracking.py` | Range in code | Hub motor |
|---|---|---|---|---|
| 1 | yaw | `clamp(command_yaw × --scale-yaw, ±--yaw-limit)` | ±60 by default | none (yaw disabled) |
| 2 | roll | `clamp(command_roll × --scale-roll, ±--roll-limit)`, or `±--snap-roll-value`/0 with `--snap-roll` | ±70 by default (±120 when snapping) | Port F |
| 3–7 | thumb … pinky | `clamp(curl × 450 × --scale-<finger>, −450, 450)` | −450…450 | Ports A–E |

Values are **motor angles in degrees**, relative to each motor's position when the hub program started (`reset_angle(0)`). Each value is truncated to an integer before it is written.

### How the hub parses it (`spike_hub_arm.py`)

```python
line = sys.stdin.readline().strip()
parts = line.split(",")
if len(parts) == 7:
    for i, name in enumerate(("yaw", "wrist_roll", "thumb", "index", "middle", "ring", "pinky")):
        if name in motors:
            motors[name].track_target(int(float(parts[i])))
```

- Lines that don't have exactly 7 fields are ignored.
- A field that doesn't parse is skipped. The other fields in the line still apply.
- Fields for motors that aren't mapped or connected are skipped. Today that means yaw.
- `track_target` sets a new target right away and doesn't block, so a new line replaces the previous target.
- The hub sends no reply or acknowledgement.

### Transport and upload flow (`run_ble_bridge.py`)

1. If `ble_command.txt` is missing, create it with `0,0,0,0,0,0,0`.
2. `find_device(<--hub>)` scans for a BLE device with that name. If the hub isn't found, the bridge prints an error and exits.
3. `PybricksHubBLE(device).connect()`.
4. `hub.run("spike_hub_arm.py", wait=False)`: pybricksdev compiles the file, downloads it to the hub and starts it. You don't need Pybricks Code or the hub button. The hub only needs Pybricks firmware.
5. Every `--poll-interval` (default 50 ms): read the file. If the line is new, `hub.write_line(line)` sends it to the program's stdin.
6. Ctrl+C: `hub.disconnect()`.

Only one hub connects per bridge process. Driving the second (`monday`, yaw) hub would mean a second bridge process with `--hub monday` and the yaw mapping re-enabled in `spike_hub_arm.py`. **This two-bridge setup is TBD (not exercised in the committed code).**

### Hardware smoke test

`tests/simple_laptop_send.py` uploads `tests/simple_hub_program.py` to the hub named `monday` (hard-coded). You then type an angle, e.g. `90`, which the hub applies to the motor on Port F with `track_target`. Run it from the repo root.

## 2. Task-demo protocol (`Roboarm_tasks/`)

Laptop → hub lines (`SpikeBleBridge`):

| Line | Meaning |
|---|---|
| `M,<duration_ms>,<thumb>,<index>,<middle>,<ring>,<pinky>,<wrist>,<yaw>` | Move all motors to absolute targets (1 decimal place). `duration_ms` is the laptop-side hold time. The hub does not use it. |
| `STOP` | Stop all motors. Sent by `SpikeBleBridge.stop()`. |
| `BYE` | Stop all motors and exit the receiver loop. |

Details:

- Writes go to the Pybricks command characteristic `c5f50002-8280-46da-89f4-6d8051e4aeef`, prefixed with byte `0x06` (stdin write), with `response=True`.
- Before each write, the hub prints `rdy`. It arrives as a notification with a `0x01` (stdout) prefix, and the laptop waits for it (timeout `--hub-timeout`, 15 s by default). Other hub output (`OK`, `ERR short`, `ERR unknown`, `STOPPED`, `receiver ready`) is printed as `[hub] …`.
- The hub applies `M` with `run_target(MOTOR_SPEED[name], target, then=Stop.HOLD, wait=False)`. Speeds: 500 deg/s for fingers, 240 for wrist, 260 for yaw. Yaw has no port in the default receiver, so it is ignored.
