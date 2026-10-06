import sys
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import wait

# Initialize motor on Port F
motor = Motor(Port.F)

# Optional: Reset motor angle to 0 on start
motor.reset_angle(0)

print("Hub ready for input...")

while True:
    # Read line from standard input (Bluetooth)
    line = sys.stdin.readline().strip()
    
    if line:
        try:
            # Convert text input to an integer degree
            target_angle = int(line)
            
            # Smoothly track the target angle non-blockingly
            motor.track_target(target_angle)
        except (ValueError, TypeError):
            # Ignore inputs that aren't valid integers
            pass
    
    # Small wait to prevent CPU hogging
    wait(10)
