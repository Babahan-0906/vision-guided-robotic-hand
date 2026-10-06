import asyncio
import sys
from pybricksdev.connections.pybricks import PybricksHubBLE
from pybricksdev.ble import find_device

async def ainput(prompt: str) -> str:
    # Helper to read stdin non-blockingly
    print(prompt, end="", flush=True)
    return await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

async def main():
    hub_name = "monday"
    script_path = "tests/simple_hub_program.py"

    print(f"Searching for hub '{hub_name}'...")
    try:
        # Search for the specific hub by name
        device = await find_device(hub_name)
    except Exception as e:
        print(f"Could not find hub: {e}")
        return

    # Use PybricksHubBLE and pass the device to the constructor
    hub = PybricksHubBLE(device)
    
    print(f"Connecting to {hub_name}...")
    await hub.connect()
    
    try:
        print(f"Uploading and running {script_path}...")
        # Start the program on the hub without waiting for it to finish
        await hub.run(script_path, wait=False)
        
        print("\nConnection established!")
        print("Type an angle (e.g., 90) and press Enter to move the motor.")
        print("Type 'exit' or press Ctrl+C to quit.")

        while True:
            line = await ainput("> ")
            
            if not line: # EOF
                break

            cmd = line.strip()
            if cmd.lower() in ['exit', 'quit']:
                break
            
            if cmd:
                # Send the input to the hub as a line
                await hub.write_line(cmd)
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Error during communication: {e}")
    finally:
        print("\nDisconnecting...")
        await hub.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
