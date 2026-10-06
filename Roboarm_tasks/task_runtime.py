import argparse
import atexit
import os
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple


TASK_DIR = Path(__file__).resolve().parent
DEFAULT_SONGS_DIR = TASK_DIR / "songs"

FULL_CLOSE_ANGLES = {
    "thumb": 240.0,
    "index": 520.0,
    "middle": 700.0,
    "ring": 540.0,
    "pinky": -240.0,
}

HALF_CLOSE_ANGLES = {
    finger: angle * 0.5 for finger, angle in FULL_CLOSE_ANGLES.items()
}

CUP_GRIP_ANGLES = dict(HALF_CLOSE_ANGLES)
CUP_GRIP_ANGLES["pinky"] = FULL_CLOSE_ANGLES["pinky"]

MOTOR_NAMES = (
    "thumb",
    "index",
    "middle",
    "ring",
    "pinky",
    "wrist",
    "yaw",
)

SAFE_LIMITS = {
    "thumb": (-20.0, 270.0),
    "index": (-20.0, 570.0),
    "middle": (-20.0, 750.0),
    "ring": (-20.0, 590.0),
    "pinky": (-270.0, 20.0),
    "wrist": (-90.0, 90.0),
    "yaw": (-90.0, 90.0),
}

BASE_POSES = {
    "default": {
        "thumb": 0.0,
        "index": 0.0,
        "middle": 0.0,
        "ring": 0.0,
        "pinky": 0.0,
        "wrist": 0.0,
        "yaw": 0.0,
    },
    "neutral": {
        "thumb": 0.0,
        "index": 0.0,
        "middle": 0.0,
        "ring": 0.0,
        "pinky": 0.0,
        "wrist": 0.0,
        "yaw": 0.0,
    },
    "open_hand": {
        "thumb": 0.0,
        "index": 0.0,
        "middle": 0.0,
        "ring": 0.0,
        "pinky": 0.0,
    },
    "loose_open": {
        "thumb": 24.0,
        "index": 52.0,
        "middle": 70.0,
        "ring": 54.0,
        "pinky": -24.0,
    },
    "half_close": dict(HALF_CLOSE_ANGLES),
    "cup_grip": dict(CUP_GRIP_ANGLES),
    "pinky_closed": {
        "thumb": 0.0,
        "index": 0.0,
        "middle": 0.0,
        "ring": 0.0,
        "pinky": FULL_CLOSE_ANGLES["pinky"],
    },
    "fist": {
        **FULL_CLOSE_ANGLES,
    },
    "closed_grab": {
        "thumb": 168.0,
        "index": 364.0,
        "middle": 490.0,
        "ring": 378.0,
        "pinky": -168.0,
    },
    "pinch": {
        "thumb": 132.0,
        "index": 286.0,
        "middle": 70.0,
        "ring": 54.0,
        "pinky": -24.0,
    },
    "point": {
        "thumb": 120.0,
        "index": 0.0,
        "middle": FULL_CLOSE_ANGLES["middle"],
        "ring": FULL_CLOSE_ANGLES["ring"],
        "pinky": FULL_CLOSE_ANGLES["pinky"],
    },
    "thumbs_up": {
        "thumb": 0.0,
        "index": FULL_CLOSE_ANGLES["index"],
        "middle": FULL_CLOSE_ANGLES["middle"],
        "ring": FULL_CLOSE_ANGLES["ring"],
        "pinky": FULL_CLOSE_ANGLES["pinky"],
    },
    "scissors": {
        "thumb": FULL_CLOSE_ANGLES["thumb"],
        "index": 0.0,
        "middle": 0.0,
        "ring": FULL_CLOSE_ANGLES["ring"],
        "pinky": FULL_CLOSE_ANGLES["pinky"],
    },
    "paper": {
        "thumb": 0.0,
        "index": 0.0,
        "middle": 0.0,
        "ring": 0.0,
        "pinky": 0.0,
    },
    "rock": {
        **FULL_CLOSE_ANGLES,
    },
}

TARGET_ALIASES = {
    "wrist_pitch": "wrist",
    "wrist_roll": "wrist",
}


def clamp(value, low, high):
    return max(low, min(high, value))


def canonicalize_targets(targets):
    canonical = {}
    for name, value in dict(targets or {}).items():
        canonical_name = TARGET_ALIASES.get(name, name)
        canonical[canonical_name] = value
    return canonical


def normalize_mode(value):
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def choose_mode(value, modes, default):
    if value:
        mode = normalize_mode(value)
        if mode not in modes:
            raise SystemExit(
                "Unknown mode '{}'. Available modes: {}".format(
                    value,
                    ", ".join(sorted(modes)),
                )
            )
        return mode

    print("Available modes: {}".format(", ".join(sorted(modes))))
    answer = input("Mode [{}]: ".format(default)).strip()
    mode = normalize_mode(answer) if answer else default
    if mode not in modes:
        raise SystemExit(
            "Unknown mode '{}'. Available modes: {}".format(
                mode,
                ", ".join(sorted(modes)),
            )
        )
    return mode


def add_common_args(parser):
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--width", type=int, default=960, help="Requested camera width.")
    parser.add_argument("--height", type=int, default=540, help="Requested camera height.")
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Do not open an OpenCV preview window while sampling the camera.",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Use the computer speaker for short spoken lines when possible.",
    )
    parser.add_argument(
        "--songs-dir",
        default=str(DEFAULT_SONGS_DIR),
        help="Folder containing MP3/WAV files for task music.",
    )
    parser.add_argument(
        "--pause-scale",
        type=float,
        default=1.0,
        help="Scale all motion waits. Use 0.25 for fast dry-run rehearsal.",
    )
    parser.add_argument(
        "--skip-countdown",
        action="store_true",
        help="Skip the filming countdown at the start of a mode.",
    )
    parser.add_argument(
        "--driver",
        choices=("console", "ble"),
        default="console",
        help="Motor driver. 'console' prints commands; 'ble' sends them to a Pybricks hub.",
    )
    parser.add_argument(
        "--hub-name",
        default="Pybricks Hub",
        help="BLE name of the hub running Roboarm_tasks/hub_pybricks_receiver.py.",
    )
    parser.add_argument(
        "--hub-timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for BLE hub connection and command readiness.",
    )


def build_parser(description, modes, default_mode):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "mode",
        nargs="?",
        help="Task mode. If omitted, the script asks at runtime.",
    )
    parser.add_argument(
        "--mode",
        dest="mode_option",
        help="Task mode, useful when launching from an IDE.",
    )
    add_common_args(parser)
    parser.set_defaults(default_mode=default_mode)
    return parser


def resolve_mode(args, modes):
    return choose_mode(args.mode_option or args.mode, modes, args.default_mode)


@dataclass
class MotionStep:
    label: str
    pose: Optional[str] = None
    targets: Optional[Mapping[str, float]] = None
    duration: float = 0.45
    hold: float = 0.0
    say: Optional[str] = None
    audio_tags: Optional[Sequence[str]] = None


@dataclass
class ExpressionResult:
    label: str
    confidence: float
    face_frames: int
    smile_frames: int


@dataclass
class SoilResult:
    is_dry: bool
    dry_score: float
    mean_hsv: Tuple[float, float, float]


@dataclass
class BlobResult:
    found: bool
    x_offset: float
    y_offset: float
    area_ratio: float


class ArmController:
    def __init__(
        self,
        task_name,
        songs_dir=DEFAULT_SONGS_DIR,
        pause_scale=1.0,
        voice=False,
        driver="console",
        hub_name="Pybricks Hub",
        hub_timeout=15.0,
    ):
        self.task_name = task_name
        self.songs_dir = Path(songs_dir)
        self.pause_scale = max(0.0, float(pause_scale))
        self.voice = bool(voice)
        self.current = dict(BASE_POSES["neutral"])
        self.step_index = 0
        self.driver = driver
        self.bridge = None
        if self.driver == "ble":
            from spike_ble_bridge import SpikeBleBridge

            self.bridge = SpikeBleBridge(hub_name=hub_name, timeout=hub_timeout)
            self.bridge.start()
            atexit.register(self.close)
            print("[{}] BLE motion driver ready".format(self.task_name))
        else:
            print("[{}] console motion driver ready".format(self.task_name))
        print("[{}] songs folder: {}".format(self.task_name, self.songs_dir))

    def countdown(self, label="Action"):
        print("[{}] {} starts in".format(self.task_name, label))
        for value in (3, 2, 1):
            print("  {}".format(value))
            self.beep(520 + value * 80, 120)
            self.sleep(0.35)

    def sleep(self, seconds):
        time.sleep(max(0.0, seconds * self.pause_scale))

    def beep(self, frequency=620, duration_ms=120):
        if sys.platform.startswith("win"):
            try:
                import winsound

                winsound.Beep(int(frequency), int(duration_ms))
                return
            except Exception:
                pass
        print("\a", end="", flush=True)

    def say(self, text):
        print("[say] {}".format(text))
        if not self.voice:
            return

        if sys.platform.startswith("win"):
            safe_text = text.replace("'", "''")
            command = (
                "Add-Type -AssemblyName System.Speech; "
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Rate=0; $s.Speak('{}')".format(safe_text)
            )
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=12,
                )
            except Exception:
                pass

    def move(self, label, targets=None, duration=0.45, note=None):
        targets = canonicalize_targets(targets)
        clamped_targets = {}
        for motor_name, value in targets.items():
            if motor_name in SAFE_LIMITS:
                low, high = SAFE_LIMITS[motor_name]
                clamped_targets[motor_name] = clamp(float(value), low, high)

        self.current.update(clamped_targets)
        self.step_index += 1
        changed = self._format_targets(clamped_targets)
        print(
            "[motion {:02d}] {:<24} {:<58} {:.2f}s".format(
                self.step_index,
                label,
                changed,
                duration,
            )
        )
        if note:
            print("           note: {}".format(note))
        if self.bridge is not None:
            self.bridge.send_motion(self.current, duration)
        self.sleep(duration)

    def pose(self, pose_name, label=None, overrides=None, duration=0.45, note=None):
        if pose_name not in BASE_POSES:
            raise ValueError("Unknown pose '{}'".format(pose_name))
        targets = dict(BASE_POSES[pose_name])
        targets.update(dict(overrides or {}))
        self.move(label or pose_name, targets, duration=duration, note=note)

    def pause(self, seconds, label="hold"):
        self.step_index += 1
        print("[motion {:02d}] {:<24} hold {:.2f}s".format(self.step_index, label, seconds))
        self.sleep(seconds)

    def run(self, steps):
        for step in steps:
            if step.say:
                self.say(step.say)
            if step.pose:
                self.pose(step.pose, step.label, step.targets, step.duration)
            elif step.targets:
                self.move(step.label, step.targets, step.duration)
            if step.audio_tags:
                self.play_audio(step.audio_tags)
            if step.hold:
                self.pause(step.hold, step.label + " hold")

    def reset(self):
        self.pose("default", "return default", duration=0.6)

    def close(self):
        if self.bridge is not None:
            self.bridge.stop()
            self.bridge = None

    def play_audio(self, tags, fallback_label="demo music"):
        path = find_audio_file(self.songs_dir, tags)
        if path is None:
            print("[audio] no matching song for tags {}; using beep cue".format(list(tags)))
            for frequency in (440, 554, 659):
                self.beep(frequency, 140)
                self.sleep(0.05)
            return None

        print("[audio] playing {}".format(path))
        try:
            if path.suffix.lower() == ".wav" and sys.platform.startswith("win"):
                import winsound

                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform.startswith("win"):
                os.startfile(str(path))  # noqa: S606 - opens a local user-selected media file.
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            print("[audio] could not launch media player: {}".format(exc))
        return path

    def _format_targets(self, targets):
        if not targets:
            return "(no motor change)"
        parts = []
        for name in MOTOR_NAMES:
            if name in targets:
                parts.append("{}={:+05.1f}".format(name, targets[name]))
        return " ".join(parts)


def find_audio_file(songs_dir, tags):
    songs_dir = Path(songs_dir)
    if not songs_dir.exists():
        return None

    audio_files = []
    for suffix in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.flac"):
        audio_files.extend(songs_dir.glob(suffix))

    if not audio_files:
        return None

    lower_tags = [tag.lower() for tag in tags]
    for tag in lower_tags:
        for path in audio_files:
            if tag in path.stem.lower():
                return path
    return audio_files[0]


def make_controller(args, task_name):
    return ArmController(
        task_name=task_name,
        songs_dir=args.songs_dir,
        pause_scale=args.pause_scale,
        voice=args.voice,
        driver=args.driver,
        hub_name=args.hub_name,
        hub_timeout=args.hub_timeout,
    )


def open_camera(camera_index, width, height):
    cv2 = import_cv2()
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            "Could not open camera index {}. Try --camera 1 or check permissions.".format(
                camera_index
            )
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cv2, cap


def import_cv2():
    try:
        import cv2

        return cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for camera modes. Install project dependencies first."
        ) from exc


def import_numpy():
    try:
        import numpy as np

        return np
    except ImportError as exc:
        raise RuntimeError(
            "NumPy is required for camera modes. Install project dependencies first."
        ) from exc


def sample_smile_expression(camera_index=0, width=960, height=540, seconds=4.0, preview=True):
    cv2, cap = open_camera(camera_index, width, height)
    face_cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )
    smile_cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_smile.xml")
    )

    if face_cascade.empty() or smile_cascade.empty():
        cap.release()
        return ExpressionResult("unknown", 0.0, 0, 0)

    face_frames = 0
    smile_frames = 0
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
        if len(faces):
            face_frames += 1
            x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
            roi_gray = gray[y : y + h, x : x + w]
            smiles = smile_cascade.detectMultiScale(
                roi_gray,
                scaleFactor=1.7,
                minNeighbors=18,
                minSize=(25, 15),
            )
            if len(smiles):
                smile_frames += 1
            if preview:
                color = (80, 220, 80) if len(smiles) else (70, 170, 255)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(
                    frame,
                    "smile" if len(smiles) else "neutral/sad",
                    (x, max(24, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2,
                    cv2.LINE_AA,
                )
        if preview:
            cv2.imshow("Expression sample", frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break

    cap.release()
    if preview:
        cv2.destroyWindow("Expression sample")

    confidence = smile_frames / max(1, face_frames)
    if face_frames == 0:
        label = "unknown"
    elif confidence >= 0.28:
        label = "happy"
    else:
        label = "sad"
    return ExpressionResult(label, confidence, face_frames, smile_frames)


def sample_soil_dryness(
    camera_index=0,
    width=960,
    height=540,
    seconds=3.0,
    preview=True,
    dry_threshold=0.48,
):
    cv2, cap = open_camera(camera_index, width, height)
    np = import_numpy()
    hsv_samples = []
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        roi_w = max(60, int(w * 0.28))
        roi_h = max(60, int(h * 0.26))
        x1 = (w - roi_w) // 2
        y1 = (h - roi_h) // 2
        roi = frame[y1 : y1 + roi_h, x1 : x1 + roi_w]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hsv_samples.append(hsv.reshape(-1, 3).mean(axis=0))

        if preview:
            cv2.rectangle(frame, (x1, y1), (x1 + roi_w, y1 + roi_h), (80, 220, 80), 2)
            cv2.putText(
                frame,
                "place soil in box",
                (x1, max(24, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (80, 220, 80),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("Soil check", frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break

    cap.release()
    if preview:
        cv2.destroyWindow("Soil check")

    if not hsv_samples:
        return SoilResult(False, 0.0, (0.0, 0.0, 0.0))

    mean_h, mean_s, mean_v = np.vstack(hsv_samples).mean(axis=0)
    brightness_score = clamp((float(mean_v) - 55.0) / 125.0, 0.0, 1.0)
    saturation_score = clamp((float(mean_s) - 35.0) / 150.0, 0.0, 1.0)
    dry_score = 0.72 * brightness_score + 0.28 * saturation_score
    return SoilResult(dry_score >= dry_threshold, dry_score, (float(mean_h), float(mean_s), float(mean_v)))


def find_dark_brown_blob(camera_index=0, width=960, height=540, seconds=4.0, preview=True):
    cv2, cap = open_camera(camera_index, width, height)
    np = import_numpy()
    best = BlobResult(False, 0.0, 0.0, 0.0)
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        brown = cv2.inRange(hsv, np.array([5, 35, 20]), np.array([32, 255, 155]))
        dark = cv2.inRange(hsv, np.array([0, 20, 0]), np.array([180, 255, 85]))
        mask = cv2.bitwise_or(brown, dark)
        mask = cv2.medianBlur(mask, 7)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(contour)
            frame_area = frame.shape[0] * frame.shape[1]
            if area / max(1, frame_area) > best.area_ratio and area > 300:
                moments = cv2.moments(contour)
                if moments["m00"]:
                    cx = int(moments["m10"] / moments["m00"])
                    cy = int(moments["m01"] / moments["m00"])
                    best = BlobResult(
                        True,
                        (cx / frame.shape[1]) * 2.0 - 1.0,
                        (cy / frame.shape[0]) * 2.0 - 1.0,
                        area / frame_area,
                    )
            if preview:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (60, 190, 255), 2)
        if preview:
            cv2.putText(
                frame,
                "scan for dark/brown target",
                (18, 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (60, 190, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("Object scan", frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break

    cap.release()
    if preview:
        cv2.destroyWindow("Object scan")
    return best


def camera_alignment_preview(
    camera_index=0,
    width=960,
    height=540,
    seconds=2.0,
    preview=True,
    label="align shot",
):
    if not preview:
        return

    try:
        cv2, cap = open_camera(camera_index, width, height)
    except RuntimeError as exc:
        print("[camera] {}".format(exc))
        return

    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        cv2.putText(
            frame,
            label,
            (18, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (80, 220, 80),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow("Camera alignment", frame)
        if cv2.waitKey(1) & 0xFF in (27, ord("q")):
            break

    cap.release()
    cv2.destroyWindow("Camera alignment")


def most_common_stable(values, minimum_count=5):
    values = [value for value in values if value]
    if not values:
        return None
    value, count = Counter(values).most_common(1)[0]
    if count >= minimum_count:
        return value
    return None
