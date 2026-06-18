# This script simulates telemetry data for a drone, publishing speed and altitude in a compact format to a ROS2 topic. It includes realistic sensor drift and clamps values to ensure they remain within expected ranges for testing purposes.

#!/usr/bin/env python3

# Import necessary libraries
import rclpy # ROS2 client library for Python
from rclpy.node import Node
from std_msgs.msg import String
import json
import random

# Define the TelemetryPublisher class; it inherits from Node, which is a fundamental building block in ROS2 for creating publishers and subscribers.
class TelemetryPublisher(Node):
    # Initialize the node and set up the publisher and timer
    def __init__(self):
        super().__init__('telemetry_publisher')
        # Publisher for a single standardized JSON string topic
        # This publisher will send telemetry data in a compact format to the '/mostavio/telemetry_raw' topic, which is designed for high-frequency updates.
        self.publisher_ = self.create_publisher(String, '/mostavio/telemetry_raw', 10)
        self.timer = self.create_timer(0.05, self.publish_telemetry) # 20Hz refresh rate
        
        # Initial Flight States, set to typical values for a drone in flight
        self.current_speed = 158.0
        self.current_alt = 3280.0

    # Function to publish telemetry data, including speed and altitude
    def publish_telemetry(self):
        msg = String()
        
        # Publish telemetry data
        # Simulate realistic drone sensor drift
        self.current_speed += random.uniform(-0.5, 0.5)
        self.current_alt += random.uniform(-2.0, 2.0)
        
        # If you have a specific gauge with a maximum threshold, you can clamp the values to ensure they don't exceed that limit. For example, if your gauge can only display up to 60 KPH, you would clamp the speed value accordingly. This prevents unrealistic readings and ensures that the telemetry data remains within the expected range for testing purposes.
        # Clamp speed to your gauge's maximum threshold (0-60 KPH for testing)
        if self.current_speed < 0: self.current_speed = 0
        if self.current_speed > 60: self.current_speed = 60
        
        # Format values into an optimized, lightweight data string
        # Data format: "SPEED,ALTITUDE"
        msg.data = f"{self.current_speed:.2f},{self.current_alt:.2f}"
        
        # Publish the telemetry data to the ROS2 topic
        self.publisher_.publish(msg)
        # Log telemetry data for debugging purposes
        self.get_logger().info(f'Broadcasting Telemetry Payload: {msg.data}')

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