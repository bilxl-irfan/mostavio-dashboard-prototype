import socket
import time
import json
import random

def run_simulation(host="127.0.0.1", port=5005):
    print(f"Starting eVTOL Telemetry Simulator. Sending data to {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Define our flight phases in sequence
    phases = [
        {"state": "DISARMED", "duration": 4},
        {"state": "ARMED", "duration": 4},
        {"state": "TAKEOFF", "duration": 10},
        {"state": "HOVERING", "duration": 8},
        {"state": "IN-FLIGHT", "duration": 20},
        {"state": "AUTONOMOUS", "duration": 12},
        {"state": "LANDING", "duration": 12},
        {"state": "DISARMED", "duration": 5}
    ]

    # Telemetry baseline values
    speed = 0.0
    altitude = 0.0
    heading = 180.0
    pitch = 0.0
    roll = 0.0
    battery = 100.0
    
    step = 0
    phase_idx = 0
    phase_timer = 0.0
    update_rate = 0.1 # 10 Hz telemetry sending rate

    # Flags to prevent repeating alerts
    sent_low_battery_warning = False
    sent_critical_battery_warning = False

    while phase_idx < len(phases):
        current_phase = phases[phase_idx]
        state = current_phase["state"]
        
        # 1. State transition logic & telemetry values morphing
        if state == "DISARMED":
            speed = 0.0
            altitude = 0.0
            pitch = 0.0
            roll = 0.0
            if step % 20 == 0:
                print(f"[Sim] Aircraft Disarmed. Awaiting arm sequence...")
                
        elif state == "ARMED":
            battery -= 0.02
            if step % 20 == 0:
                print(f"[Sim] Pre-flight system checks green. Motors ARMED.")
                
        elif state == "TAKEOFF":
            altitude += 0.5
            speed = 12.0 + random.uniform(-1, 1)
            pitch = 12.5 # Nose up
            roll = random.uniform(-2, 2)
            battery -= 0.08
            
        elif state == "HOVERING":
            altitude = 25.0 + random.uniform(-0.2, 0.2)
            speed = 3.0 + random.uniform(-0.5, 0.5)
            pitch = 1.0
            roll = random.uniform(-1, 1)
            battery -= 0.05
            
        elif state == "IN-FLIGHT":
            if altitude < 150.0:
                altitude += 1.0
            speed = min(speed + 0.8, 85.0 + random.uniform(-2, 2))
            heading = (heading + 0.3) % 360
            pitch = 4.0
            roll = 10.0 # Right bank roll
            battery -= 0.1
            
        elif state == "AUTONOMOUS":
            altitude = 150.0 + random.uniform(-0.5, 0.5)
            speed = 70.0 + random.uniform(-1, 1)
            heading = (heading - 0.5) % 360
            pitch = 0.0
            roll = -5.0 # Left bank roll
            battery -= 0.08
            
        elif state == "LANDING":
            if altitude > 0.5:
                altitude -= 1.2
            speed = max(5.0, speed - 1.0)
            pitch = -6.0 # Nose down
            roll = random.uniform(-2, 2)
            battery -= 0.06
            
        # Ensure values stay bounded
        altitude = max(0.0, altitude)
        battery = max(0.0, battery)

        # 2. Alert Injection Events
        alert_payload = {}
        if step == 20: # Just armed
            alert_payload = {"level": "INFO", "message": "Pre-flight sensors checked: ok. Radio link active."}
        elif step == 45: # Taking off
            alert_payload = {"level": "INFO", "message": "Vertical thrust nominal. Altitude climbing."}
        elif step == 110: # Cruising
            alert_payload = {"level": "WARNING", "message": "Strong thermal activity detected. Engage stabilization."}
        elif step == 180: # Autonomy mode
            alert_payload = {"level": "INFO", "message": "Autonomous Navigation: Route waypoint WP3 reached."}

        # Dynamic battery alerts based on ACTUAL battery SoC
        if battery < 20.0 and not sent_critical_battery_warning:
            alert_payload = {"level": "CRITICAL", "message": "BATTERY RESERVE POWER ACTIVE - Land Immediately!"}
            sent_critical_battery_warning = True
        elif battery < 50.0 and not sent_low_battery_warning:
            alert_payload = {"level": "WARNING", "message": f"Battery SoC drops below 50% ({int(battery)}%). Proceed to landing."}
            sent_low_battery_warning = True

        # 3. Formulate JSON payload
        payload = {
            "speed": round(speed, 1),
            "altitude": round(altitude, 1),
            "heading": round(heading, 1),
            "target_heading": 240,
            "pitch": round(pitch, 1),
            "roll": round(roll, 1),
            "battery": int(battery),
            "state": state
        }
        if alert_payload:
            payload["alert"] = alert_payload

        # 4. Transmit payload
        try:
            data = json.dumps(payload).encode("utf-8")
            sock.sendto(data, (host, port))
        except Exception as e:
            print(f"Transmission error: {e}")
            break

        # Progress timeline
        time.sleep(update_rate)
        step += 1
        phase_timer += update_rate
        
        # Advance state phases
        if phase_timer >= current_phase["duration"]:
            phase_idx += 1
            phase_timer = 0.0
            if phase_idx < len(phases):
                print(f"\n[Sim] Transitioning to phase: {phases[phase_idx]['state']}\n")

    print("\n[Sim] Simulation flight plan completed. Shutting down sender.")
    sock.close()

if __name__ == "__main__":
    run_simulation()
