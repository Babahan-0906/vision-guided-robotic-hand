import sys
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

hub = PrimeHub()
hub_name = hub.system.name()

# Base mapping for fingers
MOTOR_PORTS = {
    "thumb": Port.A,
    "index": Port.B,
    "middle": Port.C,
    "ring": Port.D,
    "pinky": Port.E,
}

# Dynamically map Port F based on hub name
# NOTE: YAW DISABLED
# if hub_name == "monday":
#     MOTOR_PORTS["yaw"] = Port.F
# else:
#     "friday"
MOTOR_PORTS["wrist_roll"] = Port.F

# Initialize connected motors
motors = {}
for name, port in MOTOR_PORTS.items():
    try:
        m = Motor(port)
        m.reset_angle(0)
        motors[name] = m
    except OSError:
        pass # Motor not connected

# Order of values in the comma-delimited string:
# yaw, roll, thumb, index, middle, ring, pinky
VALUE_ORDER = ("yaw", "wrist_roll", "thumb", "index", "middle", "ring", "pinky")

while True:
    # Read line from standard input (Bluetooth)
    line = sys.stdin.readline().strip()
    if not line:
        wait(10)
        continue
    
    parts = line.split(",")
    if len(parts) == 7:
        for i, name in enumerate(VALUE_ORDER):
            if name in motors:
                try:
                    # Parse and track target smoothly
                    target_angle = int(float(parts[i]))
                    motors[name].track_target(target_angle)
                except (ValueError, TypeError):
                    pass
    
    # Small wait to prevent CPU hogging
    wait(10)
