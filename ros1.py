# This script sets up a ROS 2 node that listens to the /mostavio/telemetry_raw topic and relays the data to a Unity HMI via TCP. It uses a background thread to handle incoming TCP connections, allowing for real-time data transmission without blocking the ROS 2 event loop. The script also includes error handling to manage disconnections gracefully.

#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import socket
import threading

class RosTcpRelay(Node):
    def __init__(self):
        super().__init__('ros_tcp_relay')
        self.subscription = self.create_subscription(
            String, '/mostavio/telemetry_raw', self.listener_callback, 10)
        
        # Setup TCP Server Socket
        self.host = '127.0.0.1' # Localhost
        self.port = 10005       # Specialized port for Unity
        self.server = socket.socket(socket.AF_SOCKET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(1)
        
        self.client_socket = None
        self.get_logger().info(f"TCP Relay Online. Listening on {self.host}:{self.port}...")
        
        # Accept client connections on a separate background thread
        threading.Thread(target=self.accept_connections, daemon=True).start()

    def accept_connections(self):
        while True:
            client, addr = self.server.accept()
            self.get_logger().info(f"Connected to Unity HMI at: {addr}")
            self.client_socket = client

    def listener_callback(self, msg):
        if self.client_socket:
            try:
                # Serializer: Append a newline separator (\n) so Unity knows when the transmission ends
                payload = f"{msg.data}\n"
                self.client_socket.sendall(payload.encode('utf-8'))
            except (socket.error, BrokenPipeError):
                self.get_logger().warn("Unity HMI disconnected. Waiting for reconnection...")
                self.client_socket = None

def main(args=None):
    rclpy.init(args=args)
    node = RosTcpRelay()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()