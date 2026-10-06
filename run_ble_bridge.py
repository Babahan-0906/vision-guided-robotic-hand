import argparse
import asyncio
import os
import time
from pybricksdev.connections.pybricks import PybricksHubBLE
from pybricksdev.ble import find_device

async def main():
    parser = argparse.ArgumentParser(description="BLE Bridge for Pybricks Hub via File IPC.")
    parser.add_argument("--hub", default="monday", help="BLE name of the SPIKE hub (e.g., monday or friday).")
    parser.add_argument("--poll-interval", type=float, default=0.050, help="Seconds between file reads.")
    args = parser.parse_args()

    hub_name = args.hub
    script_path = "spike_hub_arm.py"
    command_file = "ble_command.txt"
    poll_interval = args.poll_interval
    
    # Initialize the file with a neutral command if it doesn't exist
    if not os.path.exists(command_file):
        with open(command_file, "w") as f:
            f.write("0,0,0,0,0,0,0")

    print(f"Searching for hub '{hub_name}'...")
    try:
        device = await find_device(hub_name)
    except Exception as e:
        print(f"Could not find hub '{hub_name}': {e}")
        return

    hub = PybricksHubBLE(device)
    print(f"Connecting to {hub_name}...")
    await hub.connect()
    
    last_sent_cmd = None
    
    try:
        print(f"Uploading and running {script_path} on hub...")
        await hub.run(script_path, wait=False)
        
        print(f"\n--- FILE BRIDGE ACTIVE ---")
        print(f"Hub: {hub_name}")
        print(f"Monitoring: {command_file}")
        print(f"Poll Interval: {poll_interval}s")
        print("Type Ctrl+C in this terminal to stop.")

        while True:
            try:
                # Read the latest command from the file
                with open(command_file, "r") as f:
                    cmd = f.read().strip()
                
                # Only send if the command has changed
                if cmd and cmd != last_sent_cmd:
                    print(f"[{time.strftime('%H:%M:%S')}] Sending: {cmd}")
                    await hub.write_line(cmd)
                    last_sent_cmd = cmd
                
            except Exception as e:
                # Silently catch file read errors (e.g. file busy)
                pass
            
            # Wait before checking again
            await asyncio.sleep(poll_interval)
                
    except asyncio.CancelledError:
        pass
    finally:
        print("\nDisconnecting...")
        await hub.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
