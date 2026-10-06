import argparse
import os
import sys
import time

import cv2
import mediapipe as mp
import numpy as np

from robot_arm_view import RobotArmIsoView, RobotRollMapper, select_primary_hand
from Roboarm_tasks.task_runtime import BASE_POSES, clamp

COMMAND_FILE = "ble_command.txt"
MAX_FINGER_CURL = 450.0


HUD_BG = (18, 18, 28)
HUD_BORDER = (255, 170, 70)
HUD_TEXT = (245, 247, 255)
LANDMARK_COLOR = (255, 235, 80)
CONNECTION_COLOR = (230, 80, 255)
WRIST_GLOW = (255, 180, 30)
PRIMARY_HAND_COLOR = (110, 230, 170)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Hand tracking with a side-by-side robot arm visualization."
    )
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--width", type=int, default=960, help="Requested camera width.")
    parser.add_argument("--height", type=int, default=540, help="Requested camera height.")
    parser.add_argument("--max-hands", type=int, default=2, help="Maximum hands to track.")
    parser.add_argument(
        "--robot-panel-width",
        type=int,
        default=420,
        help="Width in pixels for the isometric robot panel.",
    )
    parser.add_argument(
        "--roll-limit",
        type=float,
        default=70.0,
        help="Symmetric robot roll limit in degrees.",
    )
    parser.add_argument(
        "--yaw-limit",
        type=float,
        default=60.0,
        help="Symmetric elbow yaw limit in degrees.",
    )
    parser.add_argument(
        "--yaw-gain",
        type=float,
        default=1.0,
        help="Overall multiplier applied after translation and wrist yaw are combined.",
    )
    parser.add_argument(
        "--yaw-translation-gain",
        type=float,
        default=140.0,
        help="Degrees of elbow yaw per full-frame horizontal wrist displacement.",
    )
    parser.add_argument(
        "--yaw-wrist-gain",
        type=float,
        default=0.85,
        help="Multiplier from wrist/palm yaw angle to elbow yaw.",
    )
    parser.add_argument(
        "--roll-smoothing",
        type=float,
        default=0.22,
        help="Smoothing factor for the robot roll command. Higher is more responsive.",
    )
    parser.add_argument(
        "--yaw-smoothing",
        type=float,
        default=0.14,
        help="Smoothing factor for elbow yaw. Lower is steadier.",
    )
    parser.add_argument(
        "--finger-smoothing",
        type=float,
        default=0.35,
        help="Smoothing factor for displayed robot fingers. Higher is more responsive.",
    )
    parser.add_argument(
        "--roll-tolerance",
        type=float,
        default=1.5,
        help="Degrees around neutral to command as zero roll.",
    )
    parser.add_argument(
        "--model-complexity",
        type=int,
        default=0,
        choices=(0, 1),
        help="0 is faster; 1 may be more accurate.",
    )
    parser.add_argument(
        "--update-rate-ms",
        type=int,
        default=25,
        help="Milliseconds between console updates.",
    )
    parser.add_argument(
        "--hub-name",
        default="monday",
        help="BLE name of the SPIKE hub (e.g. monday).",
    )
    parser.add_argument(
        "--hub-timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for BLE hub connection.",
    )
    # Motor Scaling Factors
    parser.add_argument("--scale-yaw", type=float, default=1.5, help="Scaling factor for elbow yaw.")
    parser.add_argument("--scale-roll", type=float, default=1.0, help="Scaling factor for wrist roll.")
    parser.add_argument("--scale-thumb", type=float, default=-6.5, help="Scaling factor for thumb.")
    parser.add_argument("--scale-index", type=float, default=2.5, help="Scaling factor for index finger.")
    parser.add_argument("--scale-middle", type=float, default=2.5, help="Scaling factor for middle finger.")
    parser.add_argument("--scale-ring", type=float, default=1.9, help="Scaling factor for ring finger.")
    parser.add_argument("--scale-pinky", type=float, default=1.9, help="Scaling factor for pinky finger.")

    # Roll Snapping
    parser.add_argument("--snap-roll", action="store_true", help="Snap wrist roll to fixed values instead of continuous tracking.")
    parser.add_argument("--snap-roll-value", type=float, default=120.0, help="The degree value to snap to when --snap-roll is active.")
    
    return parser.parse_args()


def open_camera(camera_index):
    cap = cv2.VideoCapture(camera_index)
    if cap.isOpened():
        return cap

    message = f"Could not open camera index {camera_index}."
    if sys.platform == "darwin":
        message += (
            " macOS is blocking camera access for this terminal/app. "
            "Enable Camera permission in System Settings > Privacy & Security > Camera, "
            "then restart the terminal and rerun this script."
        )
    else:
        message += " Try --camera 1 or check camera permissions."
    raise RuntimeError(message)


def draw_hud(frame, fps, has_primary):
    cv2.rectangle(frame, (12, 12), (472, 58), HUD_BG, -1)
    cv2.rectangle(frame, (12, 12), (472, 58), HUD_BORDER, 1)
    status = "ROLL + ELBOW YAW" if has_primary else "SHOW HAND TO CONTROL ARM"
    status_color = PRIMARY_HAND_COLOR if has_primary else HUD_TEXT
    cv2.putText(
        frame,
        f"FPS {fps:4.1f}",
        (26, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        HUD_TEXT,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        status,
        (160, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        status_color,
        2,
        cv2.LINE_AA,
    )


def main():
    args = parse_args()
    cap = open_camera(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    landmark_style = mp_drawing.DrawingSpec(
        color=LANDMARK_COLOR,
        thickness=2,
        circle_radius=3,
    )
    connection_style = mp_drawing.DrawingSpec(
        color=CONNECTION_COLOR,
        thickness=3,
        circle_radius=2,
    )

    robot_mapper = RobotRollMapper(
        min_roll_deg=-args.roll_limit,
        max_roll_deg=args.roll_limit,
        min_yaw_deg=-args.yaw_limit,
        max_yaw_deg=args.yaw_limit,
        yaw_gain=args.yaw_gain,
        yaw_translation_gain=args.yaw_translation_gain,
        yaw_wrist_gain=args.yaw_wrist_gain,
        smoothing=args.roll_smoothing,
        yaw_smoothing=args.yaw_smoothing,
        finger_smoothing=args.finger_smoothing,
        deadband_deg=args.roll_tolerance,
    )
    robot_view = RobotArmIsoView(width=args.robot_panel_width)

    print(f"File-based command mode active. Commands writing to: {COMMAND_FILE}")
    # Ensure directory exists if there is one
    cmd_dir = os.path.dirname(COMMAND_FILE)
    if cmd_dir:
        os.makedirs(cmd_dir, exist_ok=True)
    
    prev_time = time.perf_counter()
    last_send_time = 0.0
    fps = 0.0

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=args.max_hands,
        model_complexity=args.model_complexity,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera frame read failed.")
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            results = hands.process(rgb_frame)
            rgb_frame.flags.writeable = True

            primary_hand = None
            hand_landmarks_list = results.multi_hand_landmarks or []
            if hand_landmarks_list:
                primary_hand = select_primary_hand(
                    hand_landmarks_list,
                    mp_hands.HandLandmark,
                )

                for hand_landmarks in hand_landmarks_list:
                    is_primary = hand_landmarks is primary_hand
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        landmark_style,
                        connection_style,
                    )

                    wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                    wrist_xy = (
                        int(wrist.x * frame.shape[1]),
                        int(wrist.y * frame.shape[0]),
                    )
                    wrist_color = PRIMARY_HAND_COLOR if is_primary else WRIST_GLOW
                    wrist_radius = 16 if is_primary else 12
                    wrist_thickness = 3 if is_primary else 2
                    cv2.circle(
                        frame,
                        wrist_xy,
                        wrist_radius,
                        wrist_color,
                        wrist_thickness,
                        cv2.LINE_AA,
                    )

            robot_state = robot_mapper.update(primary_hand, mp_hands.HandLandmark)
            robot_panel = robot_view.draw(frame.shape[0], robot_state)

            now = time.perf_counter()
            dt = now - prev_time
            prev_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps else 1.0 / dt

            if robot_state["has_signal"]:
                if (now - last_send_time) * 1000 >= args.update_rate_ms:
                    last_send_time = now
                    targets = dict(BASE_POSES["neutral"])
                    
                    # Apply scaling and clamping to Yaw/Roll
                    targets["yaw"] = clamp(
                        robot_state["command_yaw_deg"] * args.scale_yaw,
                        -args.yaw_limit,
                        args.yaw_limit
                    )
                    
                    # Handle Roll Snapping or Continuous Tracking
                    raw_roll = robot_state["command_roll_deg"] * args.scale_roll
                    if args.snap_roll:
                        if raw_roll > args.roll_tolerance:
                            targets["wrist_roll"] = args.snap_roll_value
                        elif raw_roll < -args.roll_tolerance:
                            targets["wrist_roll"] = -args.snap_roll_value
                        else:
                            targets["wrist_roll"] = 0.0
                    else:
                        targets["wrist_roll"] = clamp(
                            raw_roll,
                            -args.roll_limit,
                            args.roll_limit
                        )

                    if robot_state["finger_pose"]:
                        finger_scales = {
                            "thumb": args.scale_thumb,
                            "index": args.scale_index,
                            "middle": args.scale_middle,
                            "ring": args.scale_ring,
                            "pinky": args.scale_pinky,
                        }
                        for finger in ("thumb", "index", "middle", "ring", "pinky"):
                            curl = robot_state["finger_pose"].get(finger, 0.0)
                            # Multiply by scale first, then clamp using the constant
                            scaled_curl = curl * MAX_FINGER_CURL * finger_scales[finger]
                            targets[finger] = clamp(scaled_curl, -MAX_FINGER_CURL, MAX_FINGER_CURL)

                    # Format: yaw,roll,thumb,index,middle,ring,pinky
                    order = ("yaw", "wrist_roll", "thumb", "index", "middle", "ring", "pinky")
                    values = [str(int(targets.get(k, 0.0))) for k in order]
                    cmd_line = ",".join(values)

                    try:
                        with open(COMMAND_FILE, "w") as f:
                            f.write(cmd_line)
                    except Exception as e:
                        print(f"Error writing to command file: {e}")

                    print(
                        "[file] {} | [throttle] yaw: {:+05.1f} | roll: {:+05.1f} | "
                        "thumb: {:03.0f} | idx: {:03.0f} | mid: {:03.0f} | ring: {:03.0f} | pinky: {:03.0f}".format(
                            cmd_line,
                            targets["yaw"],
                            targets["wrist_roll"],
                            targets["thumb"],
                            targets["index"],
                            targets["middle"],
                            targets["ring"],
                            targets["pinky"],
                        )
                    )

            draw_hud(frame, fps, primary_hand is not None)
            display_frame = np.hstack((frame, robot_panel))

            cv2.imshow("Robot Hand Tracking", display_frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("c"):
                robot_mapper.calibrate_to_current()
            elif key == ord("r"):
                robot_mapper.reset()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
