# This script simulates telemetry data for a drone, publishing speed, altitude, pitch, roll, heading, target heading, battery level, state, and alerts in a JSON format to a ROS2 topic. It includes realistic flight phases, sensor drift, and bounds clamping.

#!/usr/bin/env python3

# Import necessary libraries
import rclpy # ROS2 client library for Python
from rclpy.node import Node
from std_msgs.msg import String
import json
import random

class TelemetryPublisher(Node):
    # Initialize the node and set up the publisher and timer
    def __init__(self):
        super().__init__('telemetry_publisher')
        # Publisher for a single standardized JSON string topic
        self.publisher_ = self.create_publisher(String, '/mostavio/telemetry_raw', 10)
        self.timer = self.create_timer(0.1, self.publish_telemetry) # 10Hz refresh rate
        
        # Flight simulation parameters modeled after udp_sender.py
        self.phases = [
            {"state": "DISARMED", "duration": 4.0},
            {"state": "ARMED", "duration": 4.0},
            {"state": "TAKEOFF", "duration": 10.0},
            {"state": "HOVERING", "duration": 8.0},
            {"state": "IN-FLIGHT", "duration": 20.0},
            {"state": "AUTONOMOUS", "duration": 12.0},
            {"state": "LANDING", "duration": 12.0},
            {"state": "DISARMED", "duration": 5.0}
        ]
        
        # Initial Flight States
        self.speed = 0.0
        self.altitude = 0.0
        self.heading = 180.0
        self.pitch = 0.0
        self.roll = 0.0
        self.battery = 100.0
        
        self.step = 0
        self.phase_idx = 0
        self.phase_timer = 0.0
        self.update_rate = 0.1 # 10 Hz
        
        # Flags to prevent repeating alerts
        self.sent_low_battery_warning = False
        self.sent_critical_battery_warning = False
        
        self.get_logger().info("ROS2 Telemetry Simulator Node Started. Publishing to '/mostavio/telemetry_raw'...")

    # Function to publish telemetry data
    def publish_telemetry(self):
        if self.phase_idx >= len(self.phases):
            # Loop the simulation from the beginning for continuous testing
            self.phase_idx = 0
            self.phase_timer = 0.0
            self.battery = 100.0
            self.sent_low_battery_warning = False
            self.sent_critical_battery_warning = False
            self.get_logger().info("Resetting simulation loop...")

        current_phase = self.phases[self.phase_idx]
        state = current_phase["state"]
        
        # 1. State transition logic & telemetry values morphing
        if state == "DISARMED":
            self.speed = 0.0
            self.altitude = 0.0
            self.pitch = 0.0
            self.roll = 0.0
            if self.step % 20 == 0:
                self.get_logger().info("Aircraft Disarmed. Awaiting arm sequence...")
                
        elif state == "ARMED":
            self.battery -= 0.02
            if self.step % 20 == 0:
                self.get_logger().info("Pre-flight system checks green. Motors ARMED.")
                
        elif state == "TAKEOFF":
            self.altitude += 0.5
            self.speed = 12.0 + random.uniform(-1, 1)
            self.pitch = 12.5 # Nose up
            self.roll = random.uniform(-2, 2)
            self.battery -= 0.08
            
        elif state == "HOVERING":
            self.altitude = 25.0 + random.uniform(-0.2, 0.2)
            self.speed = 3.0 + random.uniform(-0.5, 0.5)
            self.pitch = 1.0
            self.roll = random.uniform(-1, 1)
            self.battery -= 0.05
            
        elif state == "IN-FLIGHT":
            if self.altitude < 150.0:
                self.altitude += 1.0
            self.speed = min(self.speed + 0.8, 85.0 + random.uniform(-2, 2))
            self.heading = (self.heading + 0.3) % 360
            self.pitch = 4.0
            self.roll = 10.0 # Right bank roll
            self.battery -= 0.1
            
        elif state == "AUTONOMOUS":
            self.altitude = 150.0 + random.uniform(-0.5, 0.5)
            self.speed = 70.0 + random.uniform(-1, 1)
            self.heading = (self.heading - 0.5) % 360
            self.pitch = 0.0
            self.roll = -5.0 # Left bank roll
            self.battery -= 0.08
            
        elif state == "LANDING":
            if self.altitude > 0.5:
                self.altitude -= 1.2
            self.speed = max(5.0, self.speed - 1.0)
            self.pitch = -6.0 # Nose down
            self.roll = random.uniform(-2, 2)
            self.battery -= 0.06
            
        # Ensure values stay bounded
        self.altitude = max(0.0, self.altitude)
        self.battery = max(0.0, self.battery)

        # 2. Alert Injection Events
        alert_payload = {}
        if self.step == 20: # Just armed
            alert_payload = {"level": "INFO", "message": "Pre-flight sensors checked: ok. Radio link active."}
        elif self.step == 45: # Taking off
            alert_payload = {"level": "INFO", "message": "Vertical thrust nominal. Altitude climbing."}
        elif self.step == 110: # Cruising
            alert_payload = {"level": "WARNING", "message": "Strong thermal activity detected. Engage stabilization."}
        elif self.step == 180: # Autonomy mode
            alert_payload = {"level": "INFO", "message": "Autonomous Navigation: Route waypoint WP3 reached."}

        # Dynamic battery alerts based on ACTUAL battery SoC
        if self.battery < 20.0 and not self.sent_critical_battery_warning:
            alert_payload = {"level": "CRITICAL", "message": "BATTERY RESERVE POWER ACTIVE - Land Immediately!"}
            self.sent_critical_battery_warning = True
        elif self.battery < 50.0 and not self.sent_low_battery_warning:
            alert_payload = {"level": "WARNING", "message": f"Battery SoC drops below 50% ({int(self.battery)}%). Proceed to landing."}
            self.sent_low_battery_warning = True

        # 3. Formulate JSON payload
        payload = {
            "speed": round(self.speed, 1),
            "altitude": round(self.altitude, 1),
            "heading": round(self.heading, 1),
            "target_heading": 240,
            "pitch": round(self.pitch, 1),
            "roll": round(self.roll, 1),
            "battery": int(self.battery),
            "state": state
        }
        if alert_payload:
            payload["alert"] = alert_payload

        # 4. Transmit payload as String message
        msg = String()
        msg.data = json.dumps(payload)
        self.publisher_.publish(msg)
        
        # Log telemetry data occasionally
        if self.step % 10 == 0:
            self.get_logger().info(f"Broadcasting Telemetry: {msg.data[:80]}...")

        # Progress simulation state
        self.step += 1
        self.phase_timer += self.update_rate
        if self.phase_timer >= current_phase["duration"]:
            self.phase_idx += 1
            self.phase_timer = 0.0
            if self.phase_idx < len(self.phases):
                self.get_logger().info(f"Transitioning to phase: {self.phases[self.phase_idx]['state']}")

def main(args=None):
    # Initialize the ROS2 client library
    rclpy.init(args=args)
    # Create a TelemetryPublisher node
    node = TelemetryPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()