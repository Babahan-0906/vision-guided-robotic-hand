# Hardware

## Components

- **LEGO SPIKE Prime hub(s)** flashed with **Pybricks** firmware (install from <https://code.pybricks.com>). The code refers to two hubs by BLE name: **`friday`** and **`monday`**.
- **LEGO SPIKE motors**: one per finger (5), one for wrist roll, and one planned for yaw.
- A laptop with a **webcam** and **Bluetooth LE**.
- The LEGO arm/hand mechanism itself. Build details are **TBD**; the hardware was built by a team member whose name is TBD.

## The 6-port limit and the two-hub design

A SPIKE Prime hub has six motor ports (A–F). The hand has seven axes: five fingers, wrist roll and elbow/wrist yaw. The plan was to split them across two hubs:

| Hub | Role |
|---|---|
| `friday` | 5 fingers + wrist roll (all six ports) |
| `monday` | Yaw on Port F |

**Yaw is disabled in the current code** (commit `85c6786`, "disable yaw, lack of hardware"). The yaw mapping in `spike_hub_arm.py` is commented out, so the program maps the same six ports on any hub. Each command line still carries a yaw value (field 1), and the hub ignores it.

## Port map: live tracking (`spike_hub_arm.py`)

| Port | Motor | Command field |
|---|---|---|
| A | Thumb | 3 |
| B | Index | 4 |
| C | Middle | 5 |
| D | Ring | 6 |
| E | Pinky | 7 |
| F | Wrist roll (`monday`: yaw, if re-enabled) | 2 (yaw: 1) |

To re-enable yaw, uncomment the `if hub_name == "monday": MOTOR_PORTS["yaw"] = Port.F` block in `spike_hub_arm.py` and run a second bridge (`--hub monday`). **This setup is untested (TBD).**

## Port map: scripted task demos (`Roboarm_tasks/hub_pybricks_receiver.py`)

This receiver uses a different single-hub map, described in its docstring as "the calibrated build":

| Port | Motor |
|---|---|
| A | Wrist |
| B | Thumb |
| C | Index |
| D | Ring |
| E | Pinky |
| F | Middle |

Yaw is accepted in the command but ignored, because no port is free. Re-wire or edit `MOTOR_PORTS` when you switch between the two programs.

Task-demo motor limits (`SAFE_LIMITS` in `task_runtime.py`, degrees): thumb −20…270, index −20…570, middle −20…750, ring −20…590, pinky −270…20, wrist ±90, yaw ±90. Fully closed angles (`FULL_CLOSE_ANGLES`): thumb 240, index 520, middle 700, ring 540, pinky −240. In this build the pinky closes with negative angles. In the live pipeline, the thumb is the reversed one instead (negative `--scale-thumb`).

## Zero position

Both hub programs call `reset_angle(0)` on every motor at startup. **Whatever pose the hand is in when the program starts becomes zero.** Before you start the bridge (or the receiver), put the hand in the neutral pose (fingers open, wrist centred), which matches `curl = 0` and `roll = 0`.

## Calibration procedure (live tracking)

1. **Mechanical zero.** Open the fingers, centre the wrist, then start `run_ble_bridge.py`. This uploads the program and zeroes the motors.
2. **Start the tracker** from the repo root: `uv run --no-sync python robot_hand_tracking.py`.
3. **Neutral pose.** Hold your hand in the pose that should map to the robot's neutral (for example, upright, like a handshake) and press **`c`**. This stores the current roll, wrist x-position and wrist-yaw angle as neutral. Press **`r`** to clear it and re-capture on the next frame.
4. **Finger direction and range.** Make a fist and open your hand. If a finger motor turns the wrong way, flip the sign of its `--scale-<finger>`. If it under- or over-travels, change the size. Motor target = `clamp(curl × 450 × scale, −450, 450)`.
   Defaults from the final build: `--scale-thumb -6.5`, `--scale-index 2.5`, `--scale-middle 2.5`, `--scale-ring 1.9`, `--scale-pinky 1.9`.
5. **Roll.** Tune `--scale-roll` (default 1.0) and `--roll-limit` (default 70). Raise `--roll-tolerance` (default 1.5°) if the wrist jitters around neutral. `--snap-roll` / `--snap-roll-value 120` turns roll into three fixed positions. The original notes mark it as not tested.
6. **Responsiveness vs. jitter.** Raise `--roll-smoothing` (0.22), `--yaw-smoothing` (0.14) or `--finger-smoothing` (0.35) for faster response. Lower them for steadier motion.
7. **Yaw** (only if a yaw motor is enabled): `--scale-yaw` (1.5), `--yaw-limit` (60), `--yaw-translation-gain` (140), `--yaw-wrist-gain` (0.85), `--yaw-gain` (1.0).

Example:

```bash
uv run --no-sync python robot_hand_tracking.py --scale-thumb -6.5 --scale-index 2.5 \
  --scale-middle 2.5 --scale-ring 1.9 --scale-pinky 1.9 --roll-limit 70 --roll-tolerance 1.5
```

## Hardware tests

- `tests/simple_laptop_send.py` + `tests/simple_hub_program.py`: connects to hub `monday` (hard-coded), uploads the test program, and moves the motor on **Port F** to each angle you type.
- Task demos with `--driver console` print the full motor timeline without any hardware. This is useful for rehearsing.

## Unknowns (TBD)

- Motor models (medium/large angular motor) for each axis.
- Gear ratios and tendon/linkage design of the fingers.
- Which physical hub (`friday` or `monday`) was used for the final demo run. The bridge default is `monday`, while the README's hub map assigns fingers + roll to `friday`.
