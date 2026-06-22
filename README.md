# Augmented Reality HMI HUD Dashboard for Ultralight eVTOL Aircraft

This repository contains the prototype implementation of an **Augmented Reality (AR) Heads-Up Display (HUD) Interface** designed for electric Vertical Takeoff and Landing (eVTOL) aircraft. 

Implemented in Python using the **PyQt6** framework, this application models a head-worn pilot overlay that visualizes critical flight telemetry in real-time. By externalizing traditional cockpit instruments into a lightweight AR display, this system directly addresses the strict weight and space constraints of ultralight aviation platforms (e.g., FAR Part 103 regulations).

---

## 1. System Architecture & UI Layout

The application utilizes a **split-screen layout** designed for testing, simulation, and real-time visualization:
1. **Simulation Control Panel (Left)**: An interactive ground-station control interface equipped with telemetry sliders (Speed, Altitude, Heading, Target Heading, Pitch, Roll, Battery) and warning injectors.
2. **Pilot AR HUD (Right)**: The primary pilot visor display, superimposing glowing vector symbology over a dynamic flight environment. The center of the HUD is kept **80% clear** to preserve the pilot's primary field-of-view, with instruments pushed to the margins.

```
+-------------------------------------------------------------------------+
|                          MAIN DASHBOARD WINDOW                          |
+-----------------------------------+-------------------------------------+
|      SIMULATION CONTROL PANEL     |            PILOT AR HUD             |
|                                   |                                     |
|  - Speed / Altitude Sliders       |  - Nav & Battery Status Pills (Top) |
|  - Target Hdg / Attitude Sliders  |  - Thin Compass Tape (Top Center)   |
|  - Flight State Dropdown          |  - Thin Altimeter Tape (Right edge)  |
|  - Alert Level Injector Buttons   |  - Split Speed/Battery Dial (Left)  |
|  - Interface Selector (UDP / TCP) |  - Real-time Pseudo-3D Horizon Grid |
|                                   |  - Wide Alerts Box (Bottom Center)  |
+-----------------------------------+-------------------------------------+
```

---

## 2. HMI Component Specifications & Mathematics

Rather than rendering heavy 3D assets or pre-rendered textures, the HUD draws vector graphics dynamically using the **PyQt6 QPainter** API. This ensures zero loading overhead and keeps rendering latency under **15 milliseconds** (silky smooth 60 FPS refresh rate).

### A. Combined Dial Cluster (Left Edge)
To optimize horizontal workspace, the dial merges two primary telemetry gauges into a single, vertically separated circular cluster (Radius $R = 65$ px):
* **Speedometer (Top Half)**: Renders speed on a $180^\circ$ (left) to $0^\circ$ (right) clockwise arc. The needle's endpoint is mapped using standard trigonometry:
  $$\theta = 180^\circ - \left( \frac{\text{Speed}}{120} \times 180^\circ \right)$$
  $$x = \text{spd\_cx} + (R + 2) \times \cos(\theta), \quad y = (\text{cy} - 22) - (R + 2) \times \sin(\theta)$$
* **Battery Ring (Bottom Half)**: Renders state of charge (SoC) on a $180^\circ$ (left) to $360^\circ$ (right) counter-clockwise progress arc. The arc changes color dynamically: Green ($>50\%$), Yellow/Amber ($20\text{-}50\%$), and flashing Red ($\le 20\%$).
* **Gap Separator**: A horizontal divider line sits at Y-center (`cy`) separating the two gauges. Small labels read `"SPEED"` above the line and `"BATTERY"` below it.

### B. Dynamic Pseudo-3D Horizon
* **Horizon Translation & Rotation**: The sky and ground gradients are shifted and rotated in the painter context to represent wing bank (Roll) and pitch angles:
  ```python
  painter.translate(cx, cy)
  painter.rotate(-roll)
  pitch_shift_y = pitch * 2.5  # 1 degree of pitch = 2.5 pixels
  painter.translate(0, pitch_shift_y)
  ```
* **Wireframe Mountains**: Rendered as a continuous line path (`QPolygonF`) scrolling horizontally based on Heading:
  $$y = \text{horizon} - \left| 22 \times \sin(\text{angle}) + 7 \times \cos(\text{angle} \times 2.3) \right|$$
* **Ground Grid**: Radial perspective lines expand from the vanishing center, and horizontal depth lines scroll downwards at a rate tied to the current forward velocity.

### C. Pitch Ladder & Roll Scale
* **Pitch Ladder (Center)**: Ticks drawn every $10^\circ$ representing climb/descent pitch. Positive pitch ticks are drawn as solid cyan brackets, and negative pitch ticks are drawn as dashed cyan brackets.
* **Bank Scale (Top-Center)**: A fixed semi-arc at radius $100$ px with tick marks at $\pm 10^\circ, \pm 20^\circ, \pm 30^\circ$. A green pointer arrow rotates with the aircraft to indicate the exact bank angle.

### D. Compass Tape (Top Center) & Target Nav Bug
* **Compass Ribbon**: A horizontal sliding scale indicating the current heading. Ticks scroll left/right relative to a center arrow.
* **Target Heading Bug (Orange Pointer)**: Calculates the shortest angular distance to the target destination heading:
  $$\text{diff} = (\text{TargetHeading} - \text{CurrentHeading} + 180^\circ) \pmod{360^\circ} - 180^\circ$$
* **Edge Guides**: If the target heading goes off-screen ($\text{diff} > \text{visible\_span}$), the HUD draws guide arrows at the margins (e.g., `L 240°` or `240° R`) to direct the pilot's turn.

---

## 3. Network Communication Protocols

The dashboard processes network telemetry in background threads (`QThread`) to prevent data processing from blocking the GUI thread.

### A. UDP Mode (Structured JSON) - Port 5005
Designed for modern, extensible telemetry streaming. Telemetry data is broadcast as JSON packets:
```json
{
  "speed": 68.5,
  "altitude": 150.0,
  "heading": 235.0,
  "target_heading": 240.0,
  "pitch": 4.2,
  "roll": -5.0,
  "battery": 82,
  "state": "IN-FLIGHT",
  "alert": {
    "level": "WARNING",
    "message": "Strong crosswinds detected."
  }
}
```

### B. TCP Mode (Unity-Bridge Compatibility) - Port 10005
Designed as a drop-in client to receive data from ROS-to-TCP relays. It opens a TCP socket connection and automatically parses each line (separated by `\n`):
1. **JSON Object Format (Full Telemetry)**: If the line starts with `{`, it parses it as a JSON telemetry object containing all flight variables. This is the format output by the simulated `ros2.py` node.
2. **Legacy Comma-Delimited Format**: If JSON parsing fails, it falls back to parsing:
   ```
   "SPEED,ALTITUDE" -> E.g., "45.2,120.5\n"
   ```

---

## 4. ROS 2 Direct Ingestion Pipeline

To bypass intermediate TCP socket bridges, you can run a native ROS 2 subscriber node directly inside a background PyQt `QThread` using `rclpy`:

```python
import rclpy
import json
from rclpy.node import Node
from std_msgs.msg import String
from PyQt6.QtCore import QThread, pyqtSignal

class ROS2TelemetrySubscriber(Node):
    def __init__(self, callback):
        super().__init__('ar_hud_subscriber')
        self.callback = callback
        self.subscription = self.create_subscription(
            String,
            '/mostavio/telemetry_raw',
            self.listener_callback,
            10
        )

    def listener_callback(self, msg):
        try:
            # Try parsing as JSON first (full flight telemetry package)
            payload = json.loads(msg.data)
            self.callback(payload)
        except json.JSONDecodeError:
            try:
                # Fallback: Parse legacy comma-separated "SPEED,ALTITUDE"
                parts = msg.data.split(",")
                payload = {
                    "speed": float(parts[0]),
                    "altitude": float(parts[1]),
                    "heading": 180.0,
                    "target_heading": 240.0,
                    "pitch": 0.0,
                    "roll": 0.0,
                    "battery": 85,
                    "state": "IN-FLIGHT"
                }
                self.callback(payload)  # Send payload back to the main UI thread
            except Exception as e:
                print(f"[ROS2] Fallback parsing error: {e}")

class ROS2ReceiverThread(QThread):
    telemetry_received = pyqtSignal(dict)
    log_message = pyqtSignal(str)

    def run(self):
        self.log_message.emit("Initializing ROS2 Context...")
        rclpy.init()
        self.node = ROS2TelemetrySubscriber(self.telemetry_received.emit)
        self.log_message.emit("ROS2 node active on '/mostavio/telemetry_raw'...")
        rclpy.spin(self.node)

    def stop(self):
        self.node.destroy_node()
        rclpy.shutdown()
        self.wait()
```
