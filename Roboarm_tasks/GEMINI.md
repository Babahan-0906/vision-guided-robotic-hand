# Roboarm Tasks Context

## Project Overview
This directory contains a suite of Python scripts that control a robotic arm built with LEGO SPIKE Prime hardware. The system uses a laptop to run complex logic (including OpenCV and MediaPipe computer vision tasks) and sends motor commands over Bluetooth Low Energy (BLE) to SPIKE Prime hubs running Pybricks firmware.

The robot's hand architecture encompasses 7 logical axes:
- 5 independent fingers (thumb, index, middle, ring, pinky)
- 1 wrist yaw (limit: ±70 degrees)
- 1 wrist roll (limit: ±80 degrees)
*(Note: There is no pitch motor in the current hardware).*

### Dual-Hub Architecture
Due to the 6-port limit of a single SPIKE Prime hub, the 7 motors are distributed across two hubs:
1. **Hub "friday"**: Controls the 5 fingers and wrist roll.
2. **Hub "monday"**: Controls the wrist yaw.

## Building and Running
The scripts rely on dependencies specified in the workspace root (`requirements.txt` / `pyproject.toml`). Key libraries include `bleak` for BLE, `opencv-python`, and `mediapipe`.

### Execution
Scripts can be executed in two primary modes:
1. **Console (Rehearsal) Mode**: Default. Prints the motor timeline for rehearsal without requiring hardware.
   `python Roboarm_tasks/Handshake.py --driver console`
2. **BLE (Hardware) Mode**: Sends commands to the SPIKE hub.
   `python Roboarm_tasks/Handshake.py --driver ble --hub-name "friday"`

### Hardware Setup Prerequisites
Before BLE mode will work:
1. The SPIKE Prime hubs must be flashed with Pybricks firmware via https://code.pybricks.com.
2. `Roboarm_tasks/hub_pybricks_receiver.py` must be loaded and running on the hubs.
3. The laptop must be disconnected from Pybricks Code.

## Development Conventions
- **Shared Runtime**: All new scripts should utilize `task_runtime.py` to inherit the common CLI argument parser (`build_parser`), controller (`make_controller`), and core helpers.
- **Motor Safety**: Always respect the boundaries defined in `SAFE_LIMITS` within `task_runtime.py`. The `ArmController` clamps motor targets automatically.
- **Poses**: Prefer composing motions from predefined `BASE_POSES` (e.g., `neutral`, `closed_grab`, `thumbs_up`) combined with `overrides`.
- **Vision Integration**: Vision functions (e.g., `sample_smile_expression`, `find_dark_brown_blob`) should gracefully degrade or mock responses when the camera fails or when invoked in rehearsal mode without proper hardware.
