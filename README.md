# Robotic Arm Hand Tracking

Webcam hand-tracking prototype for controlling and visualizing a robotic arm with MediaPipe and OpenCV.

The main app, `robot_hand_tracking.py`, shows the camera feed beside an isometric robot model. Yaw tracking and finger tracking are intentionally separate:

- Wrist roll comes from palm orientation.
- Elbow yaw comes from calibrated horizontal wrist displacement plus wrist/palm yaw.
- Finger motion only drives a fixed-link finger visualization, so joints keep stable segment lengths instead of stretching.
- The neutral robot hand is drawn in a vertical handshake position.

## Requirements

- Python 3.9, 3.10, or 3.11
- A webcam
- `uv` for environment setup

## Install `uv`

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installing, restart the terminal if `uv` is not found immediately.

## Setup

```bash
git clone https://github.com/himanii777/Robotic-Arm.git
cd Robotic-Arm
uv sync
```

## Run The Robot View

```bash
uv run --no-sync python robot_hand_tracking.py
```

Controls while running:

- `c` calibrates the current hand pose as neutral roll/yaw
- `r` resets neutral pose and filters
- `q` or `Esc` quits

Useful tuning example:

```bash
uv run --no-sync python robot_hand_tracking.py \
  --roll-limit 45 \
  --yaw-limit 50 \
  --yaw-translation-gain 130 \
  --yaw-wrist-gain 0.8 \
  --yaw-smoothing 0.12 \
  --finger-smoothing 0.35
```

## Run Basic Hand Tracking

```bash
uv run --no-sync python hand_tracking.py
```

If the default camera does not open:

```bash
uv run --no-sync python robot_hand_tracking.py --camera 1
```

For faster testing on slower machines:

```bash
uv run --no-sync python robot_hand_tracking.py --width 640 --height 360 --max-hands 1
```

## Camera Permissions

On macOS, the terminal app may need camera permission:

1. Open System Settings.
2. Go to Privacy & Security > Camera.
3. Enable camera access for Terminal, iTerm, VS Code, or whichever app is launching the script.
4. Restart that app and rerun the command.

## Troubleshooting

If MediaPipe fails with `Output tensor range is required`, verify the pinned version:

```bash
uv sync
uv run --no-sync python -c "import mediapipe as mp; print(mp.__version__)"
```

The expected version is `0.10.9`.

## Hub Mapping

### Hub "friday" — Fingers & Roll

The primary hub uses this port layout:

- Port A: Thumb
- Port B: Index finger
- Port C: Middle finger
- Port D: Ring finger
- Port E: Pinky finger
- Port F: Wrist roll

### Hub "monday" — Yaw

The second hub is reserved for wrist yaw:

- Port F: Wrist yaw

Port F is used here to stay consistent with the code's `MOTOR_PORTS` definition.

## Running with Hardware (BLE)

To control a physical SPIKE Prime arm, you must run the BLE bridge and the tracking script in separate terminals.

### 1. Start the BLE Bridge
This script connects to your hub and waits for commands from the tracking script.
```bash
uv run --no-sync run_ble_bridge.py --hub monday
```

### 2. Start the Hand Tracking
Once the bridge is active, start the tracking engine:
```bash
uv run --no-sync robot_hand_tracking.py
```

---

## Command Line Arguments Reference

### Motion Tuning
* `--roll-tolerance` (float, default: `1.5`): Degrees around neutral to command as zero roll (deadband).

### Motor Output Scaling
Use these to adjust sensitivity or reverse motor direction (using negative values).
* `--scale-yaw` (float, default: `1.0`): Final scaling factor applied to elbow yaw.
* `--scale-roll` (float, default: `1.0`): Final scaling factor applied to wrist roll.
* `--scale-thumb` (float, default: `1.0`): Scaling factor for the thumb motor.
* `--scale-index` (float, default: `1.0`): Scaling factor for the index finger motor.
* `--scale-middle` (float, default: `1.0`): Scaling factor for the middle finger motor.
* `--scale-ring` (float, default: `1.0`): Scaling factor for the ring finger motor.
* `--scale-pinky` (float, default: `1.0`): Scaling factor for the pinky finger motor.

### Hardware & Connection
* `--update-rate-ms` (int, default: `500`): Milliseconds between command updates.
* `--hub-name` (string, default: `"monday"`): BLE name of the SPIKE hub.

### Roll Snapping (not tested)
* `--snap-roll`: If passed, snaps wrist roll to fixed max values instead of continuous tracking.
* `--snap-roll-value` (float, default: `120.0`): The degree value to snap to when `--snap-roll` is active.

                      