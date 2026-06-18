# Developer Manual: Ultralight eVTOL Pilot AR HUD Dashboard (PyQt6 & ROS2)

This manual provides a beginner-friendly, step-by-step guide to the architecture, math, code mechanics, and data integration of the **Mostavio eVTOL pilot AR HUD Dashboard**.

Developed in Python using **PyQt6**, this prototype showcases how physical cockpit instrumentation can be offloaded to a lightweight, head-worn Augmented Reality display, adhering to the strict empty-weight regulations (e.g., FAR Part 103) of ultralight aircraft.

---

## 1. System Architecture

To make the system easy to demonstrate and ensure it doesn't clutter the pilot's field-of-view, the dashboard features a **split-screen UI**:
* **Simulation Control Panel (Left)**: Interactive sliders for Speed, Altitude, Heading, Pitch, Roll, and Battery, along with flight state actions and warning injectors.
* **Pilot AR HUD (Right)**: Superimposes modern, clean HUD vector overlays directly on top of a **dynamic pseudo-3D flight environment** (sky, scrolling ground grid, and wireframe mountains).

The center of the HUD is kept **80% clear** for pilot visibility, only showing a clean central attitude reticle. All telemetry values are pushed to the margins using thin tapes and status pills.

```
+-------------------------------------------------------------------------+
|                          MAIN DASHBOARD WINDOW                          |
+-----------------------------------+-------------------------------------+
|      SIMULATION CONTROL PANEL     |            PILOT AR HUD             |
|                                   |                                     |
|  - Speed / Altitude Sliders       |  - Nav & Battery Status Pills (Top) |
|  - Pitch / Roll / Battery Sliders |  - Thin Compass Tape (Top Center)   |
|  - Flight State Dropdown          |  - Thin Altimeter Tape (Right edge)  |
|  - Alert Level Injector Buttons   |  - Semi-Circular Speedometer (Left) |
|  - [X] Enable UDP Port 5005       |  - Real-time Pseudo-3D Terrain Grid |
|                                   |  - Wide Alerts Box (Bottom Center)  |
+-----------------------------------+-------------------------------------+
```

---

## 2. Installation & Quick Start Guide

### Step 1: Install Python Dependencies
Open your command prompt or PowerShell inside the project directory and run:
```bash
pip install PyQt6
```

### Step 2: Launch the Integrated Dashboard
Run the main application:
```bash
python dashboard_app.py
```
*You can interact with the sliders, change flight states (e.g., Takeoff, Autonomous), and click alert injection buttons to test the display immediately.*

### Step 3: Run the Networked Telemetry Demo
1. In the Dashboard window, check the box labeled **"Enable UDP Receiver Port 5005"**. The control sliders will disable, and the system logs will show `UDP Receiver active on 127.0.0.1:5005`.
2. Open a separate terminal and start the mock flight simulator:
```bash
python udp_sender.py
```
3. Watch the dashboard come alive! The aircraft will cycle through flight phases:
   - **Pre-flight checking (ARMED)**
   - **Nose up and climbing (TAKEOFF)**
   - **Cruising and banking (IN-FLIGHT)**
   - **Autonomous cruise (AUTONOMOUS)**
   - **Nose down and descending (LANDING)**
   - **Safe landing (DISARMED)**
4. Note the dynamic warnings popping up in red and amber (e.g., "Battery SoC drops below 50%") inside the pilot alerts feed, now triggered by the *actual* simulated battery charge level instead of step intervals.

---

## 3. How the PyQt6 Custom Painting Works (HMI Logic)

PyQt6 uses a system called **QPainter** to draw shapes, text, and gradients manually on a canvas. This is critical for aviation interfaces because it renders vector graphics directly, keeping latency under 16 milliseconds (running at a smooth 60 FPS).

Here is the breakdown of the custom paint widgets in [dashboard_app.py](file:///c:/Users/bilxl/Downloads/mstv/dashboard_app.py):

### A. The Pseudo-3D Terrain Background
To simulate what the pilot sees looking out the visor, the widget dynamically draws a moving wireframe environment:
1. **Sky & Ground Gradients:** We translate the painter to the center of the widget and rotate it by `-roll`. We then draw a sky gradient above the horizon and a ground gradient below it. The horizon line shifts up/down based on pitch ($y = \text{pitch} \times 2.5 \text{ pixels}$).
2. **Wireframe Horizon Mountains:** Drawn as a continuous line path (`QPolygonF`) using a sine-wave algorithm:
   $$y = \text{horizon} - \left| 22 \times \sin(\text{angle}) + 7 \times \cos(\text{angle} \times 2.3) \right|$$
   As heading changes, the angles shift, making the mountains scroll left/right relative to the pilot's view.
3. **Scrolling Ground Grid:** We draw perspective lines from the vanishing point. To simulate flying forward, we draw horizontal depth lines that scroll downwards at a rate tied to the current aircraft speed.

### B. The Semi-Circular Speedometer
Rather than sweeping in a full circle (where values like 0 and 120 overlap at the bottom), the speedometer is styled as a clean top-half semi-circle:
* **The Gauge Arc:** Starts at $180^\circ$ (left edge) and sweeps $-180^\circ$ (clockwise) to $0^\circ$ (right edge) using `painter.drawArc`.
* **The Scale Ticks:** Spaced every 20 knots. We convert each speed tick percentage into radians to draw the dial ticks:
  $$\theta = 180^\circ - \left( \frac{\text{TickValue}}{120} \times 180^\circ \right)$$
  $$\text{inner\_x} = \text{spd\_cx} + (R - 4) \times \cos(\theta), \quad \text{inner\_y} = \text{spd\_cy} - (R - 4) \times \sin(\theta)$$
* **The Needle:** Points to the active speed percentage on the same $180^\circ \to 0^\circ$ path. This aligns the progress bar and needle perfectly.

### C. Compact Tapes & Margin Pills
* **Altimeter Tape (Right edge):** Made 30% thinner (width 32px) and pushed to the right margin. Ticks slide vertically relative to the fixed center box representing current altitude.
* **Compass Ribbon (Top Center):** A thin horizontal compass scale.
* **Status Pills (Margins):** 
  - **Top-Left (Navigation):** Calculates the distance remaining and ETA dynamically.
  - **Top-Right (Power Metrics):** Calculates battery remaining time dynamically:
    $$\text{Minutes Remaining} = \left(\frac{\text{Battery SoC}}{100}\right) \times 25 \text{ minutes}$$
  - **Top-Center (Diagnostics):** Displays a live digital clock and overall systems green status.

---

## 4. Transitioning to ROS2 (Robot Operating System)

When you connect this dashboard to the flight controller computer (e.g., PX4 or Pixhawk running ROS2), you will replace the UDP socket listener thread with a **ROS2 Subscription Node**.

### Integration Pattern: QThread Bridge
PyQt6 and ROS2 both use blocking event loops (`app.exec()` and `rclpy.spin()`). Running them on the same thread will freeze the application. The solution is to spin the ROS2 Node inside a background `QThread` and use PyQt's `pyqtSignal` to safely emit parsed JSON data to the GUI thread.

Here is the exact code structure:

```python
import sys
import json
from PyQt6.QtCore import QThread, pyqtSignal
import rclpy
from rclpy.node import Node
from std_msgs.msg import String  # Or a custom message type

class ROS2TelemetrySubscriber(Node):
    def __init__(self, telemetry_callback):
        super().__init__('ar_hud_subscriber')
        self.callback = telemetry_callback
        
        # Subscribe to 'flight_telemetry' topic (buffers 10 messages)
        self.subscription = self.create_subscription(
            String,
            'flight_telemetry',
            self.listener_callback,
            10
        )

    def listener_callback(self, msg):
        try:
            # Parse incoming JSON payload
            payload = json.loads(msg.data)
            self.callback(payload)  # Send parsed telemetry dict to PyQt QThread
        except Exception as e:
            print(f"[ROS2] Message parsing failure: {e}")

class ROS2SubscriberThread(QThread):
    # Declare a custom signal to communicate with the PyQt main window
    telemetry_received = pyqtSignal(dict)
    log_message = pyqtSignal(str)

    def run(self):
        self.log_message.emit("Initializing ROS2 Context...")
        rclpy.init(args=None)
        
        # Instantiate subscriber, mapping callback to our pyqtSignal emitter
        self.node = ROS2TelemetrySubscriber(self.telemetry_received.emit)
        self.log_message.emit("ROS2 Subscriber Node Listening on 'flight_telemetry'...")
        
        # Keep node active
        rclpy.spin(self.node)

    def stop(self):
        # Shutdown triggers
        if rclpy.ok():
            self.node.destroy_node()
            rclpy.shutdown()
        self.wait()
```

---

## 5. Key Talking Points for Younes

When presenting this dashboard to Younes, emphasize these design upgrades:

1. **Clean Pilot Field-of-View**: By moving the speedometer to a compact semi-circle on the left margin, thinning the altimeter tape on the right, and using margin pills for secondary metrics (time, navigation), the center of the HUD is completely clear. The pilot has maximum visibility of the actual sky.
2. **Dynamic Pseudo-3D Environment**: The horizon line, sky/ground grids, and mountains tilt, shift, and scroll in real-time, giving an immersive visual simulation of flight movement that runs at a silky smooth 60 FPS using clean coordinate drawing rather than heavy video resources.
3. **Dynamic Alert Triggers**: The warning alerts log is no longer hardcoded to steps; it dynamically reads real-time battery status and flags low and critical levels accurately (at <50% and <20%), flashing red/amber based on safety parameters.
4. **Decoupled Telemetry Thread**: The socket thread runs independently of the paint loop. That means heavy sensor telemetry streams (e.g. 50Hz attitude data) will never cause the pilot interface to drop frames or lag.
