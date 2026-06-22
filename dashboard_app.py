import sys
import math
import socket
import json
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QSlider, QPushButton, QComboBox, QCheckBox, QTextEdit, 
    QFrame, QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF, QRectF, QDateTime
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPolygonF, QLinearGradient

# ---------------------------------------------------------
# CONSTANTS & STYLES (Modern Sci-Fi HUD Palette)
# ---------------------------------------------------------
COLOR_BG_DARK = QColor(10, 14, 23, 255)       # Main window background
COLOR_PANEL_BG = QColor(21, 27, 38, 255)      # Ground control panel background
COLOR_HUD_CYAN = QColor(0, 240, 255, 255)     # Safe/Telemetry normal (Cyan)
COLOR_HUD_GREEN = QColor(0, 255, 102, 255)    # Active states (Emerald Green)
COLOR_HUD_AMBER = QColor(255, 179, 0, 255)    # Warnings (Amber/Yellow)
COLOR_HUD_RED = QColor(255, 51, 102, 255)     # Critical Alarms (Neon Red)
COLOR_HUD_PURPLE = QColor(189, 0, 255, 255)   # Autonomous / Special states
COLOR_HUD_ORANGE = QColor(255, 102, 0, 255)   # Target Nav Bug (Bright Orange)
COLOR_MUTED_BLUE = QColor(40, 55, 75, 120)    # Visual grid lines / scales (Semi-transparent)

# QSS (Style Sheet) for Control Panel
PANEL_QSS = """
QFrame#control_panel {
    background-color: #151B26;
    border-right: 2px solid #1E2736;
}
QLabel {
    color: #A0AAB5;
    font-family: 'Segoe UI', Arial;
    font-size: 11px;
}
QLabel#panel_title {
    color: #00F0FF;
    font-size: 16px;
    font-weight: bold;
    padding-bottom: 5px;
    border-bottom: 1px solid #1E2736;
}
QGroupBox {
    border: 1px solid #28374B;
    border-radius: 4px;
    margin-top: 8px;
    padding: 8px;
    color: #00F0FF;
    font-weight: bold;
}
QSlider::groove:horizontal {
    border: 1px solid #28374B;
    height: 4px;
    background: #0C101B;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00F0FF;
    border: 1px solid #00F0FF;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
QPushButton {
    background-color: #1E2736;
    color: #E2E8F0;
    border: 1px solid #28374B;
    padding: 5px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton:hover {
    background-color: #2D3A4F;
    border-color: #00F0FF;
}
QPushButton:pressed {
    background-color: #00F0FF;
    color: #0C101B;
}
QComboBox {
    background-color: #1E2736;
    color: #E2E8F0;
    border: 1px solid #28374B;
    padding: 3px;
    border-radius: 4px;
    font-size: 11px;
}
QComboBox::drop-down {
    border: none;
}
QCheckBox {
    color: #E2E8F0;
    font-size: 11px;
}
QTextEdit {
    background-color: #0C101B;
    color: #FF3366;
    border: 1px solid #28374B;
    border-radius: 4px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}
"""

# ---------------------------------------------------------
# PILOT AR HUD VIEW (Unified Custom Painting & Visuals)
# ---------------------------------------------------------

class PilotHUDView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(780, 600)
        
        # Telemetry values
        self.speed = 45.0
        self.altitude = 120.0
        self.heading = 180.0
        self.pitch = 5.0
        self.roll = 0.0
        self.battery_soc = 85
        self.flight_state = "HOVERING"
        self.target_heading = 240.0 # Target heading bug
        self.alerts = []
        
        # Animation loop parameters
        self.grid_offset = 0.0
        self.alert_blink_state = False

    def update_telemetry(self, speed, alt, hdg, pitch, roll, bat, state, target_hdg=240.0):
        self.speed = speed
        self.altitude = alt
        self.heading = hdg
        self.pitch = pitch
        self.roll = roll
        self.battery_soc = bat
        self.flight_state = state
        self.target_heading = target_hdg
        self.update()

    def advance_animation(self):
        # Scroll grid lines according to speed (simulates forward motion)
        self.grid_offset = (self.grid_offset + self.speed * 0.1) % 40
        self.update()

    def add_alert(self, level, message):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.alerts.append((timestamp, level, message))
        if len(self.alerts) > 6:
            self.alerts.pop(0) # Keep log short
        self.update()

    def clear_alerts(self):
        self.alerts.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w // 2
        cy = h // 2

        # -------------------------------------------------
        # 1. PSEUDO-3D FLIGHT SKY & GROUND ENVIRONMENT
        # -------------------------------------------------
        painter.save()
        
        # Apply flight rotation (roll) and translation (pitch)
        # 1 degree of pitch = 2.5 pixels shift
        pitch_y_shift = self.pitch * 2.5
        painter.translate(cx, cy)
        painter.rotate(-self.roll)

        # Draw Sky Gradient Background
        sky_grad = QLinearGradient(0, -600 + pitch_y_shift, 0, pitch_y_shift)
        sky_grad.setColorAt(0, QColor(8, 15, 30))
        sky_grad.setColorAt(1, QColor(16, 28, 52))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(sky_grad))
        painter.drawRect(-w, -600 + int(pitch_y_shift), w * 2, 600)

        # Draw Ground Gradient Background
        ground_grad = QLinearGradient(0, pitch_y_shift, 0, 600 + pitch_y_shift)
        ground_grad.setColorAt(0, QColor(15, 18, 26))
        ground_grad.setColorAt(1, QColor(5, 6, 10))
        painter.setBrush(QBrush(ground_grad))
        painter.drawRect(-w, int(pitch_y_shift), w * 2, 600)

        # Draw Horizon Line
        painter.setPen(QPen(QColor(0, 240, 255, 120), 1.5))
        painter.drawLine(-w, int(pitch_y_shift), w, int(pitch_y_shift))

        # Draw Wireframe Mountains scrolling with heading on the Horizon
        painter.setPen(QPen(QColor(0, 240, 255, 60), 1.2))
        mountain_path = QPolygonF()
        for mx in range(-w, w + 30, 30):
            angle_rad = math.radians(mx + self.heading * 4)
            h_val = 22 * math.sin(angle_rad) + 7 * math.cos(angle_rad * 2.3)
            mountain_path.append(QPointF(mx, pitch_y_shift - abs(h_val)))
        painter.drawPolyline(mountain_path)

        # Draw Ground 3D Grid lines
        painter.setPen(QPen(QColor(0, 240, 255, 25), 1))
        for angle in range(-80, 81, 10):
            rad = math.radians(angle + (self.heading % 10))
            ex = 800 * math.sin(rad)
            ey = 800 * math.cos(rad)
            if ey > 0: # Points downward
                painter.drawLine(QPointF(0, pitch_y_shift), QPointF(ex, pitch_y_shift + ey))

        # Horizontal depth grid lines (simulating scrolling forward)
        for i in range(1, 15):
            depth_y = (i * 35 - self.grid_offset)
            if depth_y > 0:
                scaled_y = (depth_y ** 1.35) * 0.15 + pitch_y_shift
                painter.drawLine(QPointF(-w, scaled_y), QPointF(w, scaled_y))

        # -------------------------------------------------
        # 2. PITCH LADDER WIDGET (Rotates and shifts dynamically)
        # -------------------------------------------------
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        for p in [-20, -10, 10, 20]:
            py = -p * 2.5
            
            if p > 0:
                painter.setPen(QPen(COLOR_HUD_CYAN, 1.2, Qt.PenStyle.SolidLine))
            else:
                painter.setPen(QPen(COLOR_HUD_CYAN, 1.2, Qt.PenStyle.DashLine))
                
            tag_h = 4 if p > 0 else -4
            
            # Left bracket tick
            painter.drawLine(-35, int(py), -12, int(py))
            painter.drawLine(-35, int(py), -35, int(py + tag_h))
            # Right bracket tick
            painter.drawLine(12, int(py), 35, int(py))
            painter.drawLine(35, int(py), 35, int(py + tag_h))
            
            # Degree labels
            painter.setPen(COLOR_HUD_CYAN)
            painter.drawText(-52, int(py - 5), 15, 10, Qt.AlignmentFlag.AlignRight, str(abs(p)))
            painter.drawText(37, int(py - 5), 15, 10, Qt.AlignmentFlag.AlignLeft, str(abs(p)))

        # Restore painter coordinate frame back to fixed screen space
        painter.restore()

        # -------------------------------------------------
        # 3. FIXED CENTRAL AIRCRAFT POINTER RETICLE (Green)
        # -------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.setPen(QPen(COLOR_HUD_GREEN, 2))
        painter.drawEllipse(-3, -3, 6, 6)
        painter.drawLine(-30, 0, -8, 0)
        painter.drawLine(8, 0, 30, 0)
        painter.drawLine(-8, 0, -8, 4)
        painter.drawLine(8, 0, 8, 4)
        painter.restore()

        # -------------------------------------------------
        # 4. FIXED BANK ANGLE SCALE (Roll indicator)
        # -------------------------------------------------
        roll_r = 100
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1, Qt.PenStyle.SolidLine))
        painter.drawArc(cx - roll_r, cy - roll_r, roll_r * 2, roll_r * 2, 60 * 16, 60 * 16)
        
        # Draw ticks on the roll scale (-30, -20, -10, 0, 10, 20, 30)
        painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        for phi in [-30, -20, -10, 0, 10, 20, 30]:
            angle_rad = math.radians(90 - phi)
            x1 = cx + 96 * math.cos(angle_rad)
            y1 = cy - 96 * math.sin(angle_rad)
            x2 = cx + 101 * math.cos(angle_rad)
            y2 = cy - 101 * math.sin(angle_rad)
            
            painter.setPen(QPen(COLOR_HUD_CYAN if phi == 0 else COLOR_MUTED_BLUE, 1))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            
            if phi in [-30, 0, 30]:
                lx = cx + 108 * math.cos(angle_rad)
                ly = cy - 108 * math.sin(angle_rad)
                painter.setPen(COLOR_HUD_CYAN)
                lbl = "0" if phi == 0 else f"{abs(phi)}"
                painter.drawText(int(lx - 10), int(ly - 5), 20, 10, Qt.AlignmentFlag.AlignCenter, lbl)

        # Draw moving roll pointer triangle
        pointer_rad = math.radians(90 - self.roll)
        pt = QPointF(cx + 94 * math.cos(pointer_rad), cy - 94 * math.sin(pointer_rad))
        p_base1 = QPointF(cx + 88 * math.cos(pointer_rad - 0.04), cy - 88 * math.sin(pointer_rad - 0.04))
        p_base2 = QPointF(cx + 88 * math.cos(pointer_rad + 0.04), cy - 88 * math.sin(pointer_rad + 0.04))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(COLOR_HUD_GREEN))
        painter.drawPolygon(QPolygonF([pt, p_base1, p_base2]))

        # -------------------------------------------------
        # 5. STATUS INFORMATION MARGIN PILLS (Aligned Text)
        # -------------------------------------------------
        pill_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(pill_font)
        
        pill_y = 12
        pill_h = 24
        
        # Top-Left Pill: Navigation & Flight Target
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1))
        painter.setBrush(QBrush(QColor(15, 20, 30, 200)))
        painter.drawRoundedRect(15, pill_y, 220, pill_h, 4, 4)
        
        dist_left = max(0.5, 4.2 - (self.altitude * 0.002))
        eta_sec = int((dist_left / max(1.0, self.speed)) * 3600)
        eta_str = f"{eta_sec//60:02d}:{eta_sec%60:02d}" if self.speed > 5 else "--:--"
        
        painter.setPen(COLOR_HUD_CYAN)
        painter.drawText(15, pill_y, 220, pill_h, Qt.AlignmentFlag.AlignCenter, f"NAV: WP-03 | DIST: {dist_left:.1f} NM | ETA: {eta_str}")

        # Top-Center Pill: Systems Diagnostics & Time
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1))
        painter.drawRoundedRect(cx - 70, pill_y, 140, pill_h, 4, 4)
        local_time = QDateTime.currentDateTime().toString("hh:mm:ss AP")
        painter.setPen(COLOR_HUD_GREEN if self.flight_state != "DISARMED" else COLOR_HUD_CYAN)
        painter.drawText(cx - 70, pill_y, 140, pill_h, Qt.AlignmentFlag.AlignCenter, f"SYS OK | {local_time}")

        # Top-Right Pill: Power & Battery State of Charge
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1))
        painter.drawRoundedRect(w - 235, pill_y, 220, pill_h, 4, 4)
        
        bat_color = COLOR_HUD_GREEN
        if self.battery_soc <= 20:
            bat_color = COLOR_HUD_RED
        elif self.battery_soc <= 50:
            bat_color = COLOR_HUD_AMBER
            
        painter.setPen(bat_color)
        bat_rem_min = int((self.battery_soc / 100.0) * 25.0)
        painter.drawText(w - 235, pill_y, 220, pill_h, Qt.AlignmentFlag.AlignCenter, f"POWER: {self.battery_soc}% | {bat_rem_min} MIN REM | 48.2 V")

        # -------------------------------------------------
        # 6. COMPACT scale tapes (Altimeter & Compass)
        # -------------------------------------------------
        # COMPASS TAPE (Top-Center strip, height 24, width 340)
        comp_w = 340
        comp_h = 24
        comp_x = cx - comp_w // 2
        comp_y = 48
        
        # Transparent background
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1))
        painter.setBrush(QBrush(QColor(15, 20, 30, 160)))
        painter.drawRoundedRect(comp_x, comp_y, comp_w, comp_h, 3, 3)
        
        # Draw ticks inside compass tape
        px_per_deg = 1.6
        deg_span = (comp_w / 2) / px_per_deg
        min_deg = self.heading - deg_span
        max_deg = self.heading + deg_span
        
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        for angle in range(int(min_deg - 1), int(max_deg + 1)):
            norm_angle = angle % 360
            if angle % 5 == 0:
                x_pos = cx + (angle - self.heading) * px_per_deg
                if comp_x <= x_pos <= comp_x + comp_w:
                    is_major = (angle % 30 == 0)
                    line_len = 7 if is_major else 4
                    painter.setPen(QPen(COLOR_HUD_CYAN if is_major else COLOR_MUTED_BLUE, 1))
                    painter.drawLine(int(x_pos), comp_y + comp_h, int(x_pos), comp_y + comp_h - line_len)
                    
                    if is_major:
                        lbl = str(norm_angle)
                        if norm_angle == 0: lbl = "N"
                        elif norm_angle == 90: lbl = "E"
                        elif norm_angle == 180: lbl = "S"
                        elif norm_angle == 270: lbl = "W"
                        painter.setPen(COLOR_HUD_CYAN)
                        painter.drawText(int(x_pos - 12), comp_y + 13, 24, 10, Qt.AlignmentFlag.AlignCenter, lbl)
                        
        # TARGET NAVIGATION HDG BUG
        hdg_diff = (self.target_heading - self.heading + 180) % 360 - 180
        target_x = cx + hdg_diff * px_per_deg
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(COLOR_HUD_ORANGE))
        
        if comp_x + 6 <= target_x <= comp_x + comp_w - 6:
            bug = QPolygonF([
                QPointF(target_x, comp_y),
                QPointF(target_x - 5, comp_y - 6),
                QPointF(target_x + 5, comp_y - 6)
            ])
            painter.drawPolygon(bug)
            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.setPen(COLOR_HUD_ORANGE)
            painter.drawText(int(target_x - 8), comp_y - 14, 16, 8, Qt.AlignmentFlag.AlignCenter, "T")
        else:
            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.setPen(COLOR_HUD_ORANGE)
            if hdg_diff < 0:
                guide = QPolygonF([
                    QPointF(comp_x + 4, comp_y + comp_h // 2),
                    QPointF(comp_x + 9, comp_y + comp_h // 2 - 4),
                    QPointF(comp_x + 9, comp_y + comp_h // 2 + 4)
                ])
                painter.drawPolygon(guide)
                painter.drawText(comp_x + 12, comp_y + 4, 30, 16, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"L {int(self.target_heading)}°")
            else:
                guide = QPolygonF([
                    QPointF(comp_x + comp_w - 4, comp_y + comp_h // 2),
                    QPointF(comp_x + comp_w - 9, comp_y + comp_h // 2 - 4),
                    QPointF(comp_x + comp_w - 9, comp_y + comp_h // 2 + 4)
                ])
                painter.drawPolygon(guide)
                painter.drawText(comp_x + comp_w - 42, comp_y + 4, 30, 16, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{int(self.target_heading)}° R")
        
        # Central current heading pointer
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(COLOR_HUD_GREEN))
        painter.drawPolygon(QPolygonF([
            QPointF(cx, comp_y + comp_h),
            QPointF(cx - 4, comp_y + comp_h + 4),
            QPointF(cx + 4, comp_y + comp_h + 4)
        ]))
        
        # Readout text below pointer
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.ExtraBold))
        painter.setPen(COLOR_HUD_GREEN)
        painter.drawText(cx - 20, comp_y + comp_h + 6, 40, 14, Qt.AlignmentFlag.AlignCenter, f"{int(self.heading)}°")

        # ALTIMETER TAPE (Right margin, width 42, height 220)
        alt_w = 42
        alt_h = 220
        alt_x = w - 62
        alt_y = cy - alt_h // 2
        
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1))
        painter.setBrush(QBrush(QColor(15, 20, 30, 160)))
        painter.drawRoundedRect(alt_x, alt_y, alt_w, alt_h, 3, 3)
        
        alt_pixels_per_foot = 0.8
        alt_cy = alt_y + alt_h // 2
        min_alt = int(self.altitude - (alt_h / 2) / alt_pixels_per_foot)
        max_alt = int(self.altitude + (alt_h / 2) / alt_pixels_per_foot)
        
        start_tick = (min_alt // 10) * 10
        start_tick = max(0, start_tick)
        
        painter.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        for tick in range(start_tick, int(max_alt), 10):
            y_pos = alt_cy + (self.altitude - tick) * alt_pixels_per_foot
            if alt_y <= y_pos <= alt_y + alt_h:
                is_major = (tick % 50 == 0)
                line_len = 10 if is_major else 5
                painter.setPen(QPen(COLOR_HUD_CYAN if is_major else COLOR_MUTED_BLUE, 1))
                painter.drawLine(alt_x, int(y_pos), alt_x + line_len, int(y_pos))
                
                if is_major:
                    painter.setPen(COLOR_HUD_CYAN)
                    painter.drawText(alt_x + 8, int(y_pos - 5), 32, 10, Qt.AlignmentFlag.AlignLeft, str(tick))
                    
        # Fixed center pointer readout
        painter.setPen(QPen(COLOR_HUD_GREEN, 1.5))
        painter.setBrush(QBrush(COLOR_BG_DARK))
        painter.drawRect(alt_x - 6, alt_cy - 12, alt_w + 12, 24)
        
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.ExtraBold))
        painter.setPen(COLOR_HUD_GREEN)
        painter.drawText(alt_x - 6, alt_cy - 12, alt_w + 12, 24, Qt.AlignmentFlag.AlignCenter, f"{int(self.altitude)}")

        # -------------------------------------------------
        # 4. COMBINED DIAL CLUSTER (Left Edge: Separated Speedometer Top / Battery Ring Bottom)
        # -------------------------------------------------
        spd_cx = 90
        spd_cy_top = cy - 22
        spd_cy_bat = cy + 22
        spd_r = 65
        
        # --- A. SPEEDOMETER (TOP HALF - SHIFTED UP) ---
        # Background arc (180 deg to 0 deg, top semi-circle)
        painter.setPen(QPen(COLOR_MUTED_BLUE, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawArc(spd_cx - spd_r, spd_cy_top - spd_r, spd_r * 2, spd_r * 2, 180 * 16, -180 * 16)
        
        # Active speed progress arc
        speed_percent = min(1.0, self.speed / 120.0)
        active_span = -180 * speed_percent * 16
        
        spd_color = COLOR_HUD_CYAN
        if self.speed >= 90:
            spd_color = COLOR_HUD_RED
        elif self.speed >= 75:
            spd_color = COLOR_HUD_AMBER
            
        painter.setPen(QPen(spd_color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(spd_cx - spd_r, spd_cy_top - spd_r, spd_r * 2, spd_r * 2, 180 * 16, int(active_span))
        
        # Ticks & values (0 to 120, steps of 20)
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        for val in range(0, 121, 20):
            val_pct = val / 120.0
            angle_deg = 180 - val_pct * 180
            angle_rad = math.radians(angle_deg)
            
            # Tick lines
            inner_x = spd_cx + (spd_r - 4) * math.cos(angle_rad)
            inner_y = spd_cy_top - (spd_r - 4) * math.sin(angle_rad)
            outer_x = spd_cx + (spd_r + 4) * math.cos(angle_rad)
            outer_y = spd_cy_top - (spd_r + 4) * math.sin(angle_rad)
            
            painter.setPen(QPen(COLOR_HUD_CYAN if val <= 90 else COLOR_HUD_RED, 1.2))
            painter.drawLine(QPointF(inner_x, inner_y), QPointF(outer_x, outer_y))
            
            # Value Labels
            lbl_x = spd_cx + (spd_r - 14) * math.cos(angle_rad)
            lbl_y = spd_cy_top - (spd_r - 14) * math.sin(angle_rad)
            painter.drawText(int(lbl_x - 10), int(lbl_y - 5), 20, 10, Qt.AlignmentFlag.AlignCenter, str(val))
            
        # Speedometer Needle
        needle_deg = 180 - speed_percent * 180
        needle_rad = math.radians(needle_deg)
        needle_len = spd_r + 2
        needle_x = spd_cx + needle_len * math.cos(needle_rad)
        needle_y = spd_cy_top - needle_len * math.sin(needle_rad)
        
        painter.setPen(QPen(spd_color, 2))
        painter.drawLine(QPointF(spd_cx, spd_cy_top), QPointF(needle_x, needle_y))
        
        # Top needle center cap
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(spd_color))
        painter.drawEllipse(spd_cx - 3, spd_cy_top - 3, 6, 6)

        # --- B. BATTERY INDICATOR (BOTTOM HALF - SHIFTED DOWN) ---
        # Background arc (180 deg to 360 deg, bottom semi-circle)
        painter.setPen(QPen(COLOR_MUTED_BLUE, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawArc(spd_cx - spd_r, spd_cy_bat - spd_r, spd_r * 2, spd_r * 2, 180 * 16, 180 * 16)
        
        # Active battery progress arc
        bat_percent = min(1.0, self.battery_soc / 100.0)
        bat_active_span = 180 * bat_percent * 16
        
        bat_color = COLOR_HUD_GREEN
        if self.battery_soc <= 20:
            bat_color = COLOR_HUD_RED
        elif self.battery_soc <= 50:
            bat_color = COLOR_HUD_AMBER
            
        painter.setPen(QPen(bat_color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(spd_cx - spd_r, spd_cy_bat - spd_r, spd_r * 2, spd_r * 2, 180 * 16, int(bat_active_span))
        
        # Ticks & values (0 to 100, steps of 20)
        painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        for val in range(0, 101, 20):
            val_pct = val / 100.0
            angle_deg = 180 + val_pct * 180
            angle_rad = math.radians(angle_deg)
            
            # Tick lines
            inner_x = spd_cx + (spd_r - 4) * math.cos(angle_rad)
            inner_y = spd_cy_bat - (spd_r - 4) * math.sin(angle_rad)
            outer_x = spd_cx + (spd_r + 4) * math.cos(angle_rad)
            outer_y = spd_cy_bat - (spd_r + 4) * math.sin(angle_rad)
            
            painter.setPen(QPen(bat_color, 1.2))
            painter.drawLine(QPointF(inner_x, inner_y), QPointF(outer_x, outer_y))
            
            # Value Labels
            lbl_x = spd_cx + (spd_r - 14) * math.cos(angle_rad)
            lbl_y = spd_cy_bat - (spd_r - 14) * math.sin(angle_rad)
            painter.drawText(int(lbl_x - 10), int(lbl_y - 5), 20, 10, Qt.AlignmentFlag.AlignCenter, str(val))
            
        # Bottom needle center cap
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bat_color))
        painter.drawEllipse(spd_cx - 3, spd_cy_bat - 3, 6, 6)

        # --- C. MIDDLE GAP DIVIDER & TEXT LABELS ---
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1, Qt.PenStyle.SolidLine))
        painter.drawLine(spd_cx - spd_r + 5, cy, spd_cx + spd_r - 5, cy)
        
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(COLOR_HUD_CYAN)
        painter.drawText(spd_cx - 30, cy - 12, 60, 10, Qt.AlignmentFlag.AlignCenter, "SPEED")
        
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(bat_color)
        painter.drawText(spd_cx - 30, cy + 2, 60, 10, Qt.AlignmentFlag.AlignCenter, "BATTERY")

        # --- D. READOUT VALUES ---
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.ExtraBold))
        painter.setPen(spd_color)
        painter.drawText(spd_cx - 30, spd_cy_top - 25, 60, 16, Qt.AlignmentFlag.AlignCenter, f"{int(self.speed)}")
        painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        painter.setPen(COLOR_MUTED_BLUE)
        painter.drawText(spd_cx - 30, spd_cy_top - 10, 60, 10, Qt.AlignmentFlag.AlignCenter, "KNOTS")
        
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.ExtraBold))
        painter.setPen(bat_color)
        bat_volts = 48.0 * (self.battery_soc / 100.0)
        painter.drawText(spd_cx - 35, spd_cy_bat + 15, 70, 15, Qt.AlignmentFlag.AlignCenter, f"{int(self.battery_soc)}%")
        painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        painter.setPen(COLOR_MUTED_BLUE)
        painter.drawText(spd_cx - 30, spd_cy_bat + 29, 60, 10, Qt.AlignmentFlag.AlignCenter, f"{bat_volts:.1f} V")

        # -------------------------------------------------
        # 8. ACTIVE FLIGHT STATE INDICATOR (Center-Bottom)
        # -------------------------------------------------
        state_y = cy + 100
        painter.setPen(QPen(COLOR_MUTED_BLUE, 1))
        state_color = COLOR_HUD_CYAN
        bg_color = QColor(0, 240, 255, 30)
        if self.flight_state == "DISARMED":
            state_color = QColor(160, 170, 181)
            bg_color = QColor(80, 90, 100, 30)
        elif self.flight_state in ["ARMED", "IN-FLIGHT"]:
            state_color = COLOR_HUD_GREEN
            bg_color = QColor(0, 255, 102, 30)
        elif self.flight_state in ["TAKEOFF", "LANDING"]:
            state_color = COLOR_HUD_AMBER
            bg_color = QColor(255, 179, 0, 30)
        elif self.flight_state == "AUTONOMOUS":
            state_color = COLOR_HUD_PURPLE
            bg_color = QColor(189, 0, 255, 30)
            
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(cx - 60, state_y, 120, 24, 4, 4)
        
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.ExtraBold))
        painter.setPen(state_color)
        painter.drawText(cx - 60, state_y, 120, 24, Qt.AlignmentFlag.AlignCenter, self.flight_state)

        # -------------------------------------------------
        # 9. PILOT ALERTS PANEL LOGS (Bottom Center, Padded)
        # -------------------------------------------------
        log_y = h - 110
        log_h = 95
        log_w = w - 40
        
        has_critical = any(a[1] == "CRITICAL" for a in self.alerts)
        outline_pen = QPen(COLOR_HUD_RED if (has_critical and self.alert_blink_state) else COLOR_MUTED_BLUE, 1.2)
        
        painter.setPen(outline_pen)
        painter.setBrush(QBrush(QColor(12, 17, 26, 220)))
        painter.drawRoundedRect(20, log_y, log_w, log_h, 4, 4)
        
        painter.setFont(QFont("Consolas", 8))
        text_y_offset = log_y + 10
        for entry in self.alerts[-5:]:
            time_str, lvl, msg = entry
            
            lvl_color = COLOR_HUD_CYAN
            if lvl == "WARNING":
                lvl_color = COLOR_HUD_AMBER
            elif lvl == "CRITICAL":
                lvl_color = COLOR_HUD_RED
                
            painter.setPen(lvl_color)
            painter.drawText(35, text_y_offset, f"[{time_str}] [{lvl}]")
            
            painter.setPen(QColor(226, 232, 240))
            painter.drawText(160, text_y_offset, msg)
            
            text_y_offset += 16


# ---------------------------------------------------------
# NETWORKING THREADS (UDP Telemetry Receiver)
# ---------------------------------------------------------

class UDPReceiverThread(QThread):
    telemetry_received = pyqtSignal(dict)
    log_message = pyqtSignal(str)

    def __init__(self, host="127.0.0.1", port=5005):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.sock = None

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.sock.bind((self.host, self.port))
            self.running = True
            self.log_message.emit(f"UDP Receiver active on {self.host}:{self.port}")
        except Exception as e:
            self.log_message.emit(f"Socket Bind Failed: {str(e)}")
            return

        while self.running:
            try:
                self.sock.settimeout(0.5)
                data, addr = self.sock.recvfrom(1024)
                payload = json.loads(data.decode("utf-8"))
                self.telemetry_received.emit(payload)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log_message.emit(f"Data error: {str(e)}")

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()
        self.wait()


# ---------------------------------------------------------
# NETWORKING THREADS (TCP Receiver - Unity Bridge Compatibility Mode)
# ---------------------------------------------------------

class TCPReceiverThread(QThread):
    """
    Background worker thread to connect as a TCP client to a ROS-to-TCP bridge 
    server (like ros1.py on port 10005) and parse "SPEED,ALTITUDE\n" strings.
    """
    telemetry_received = pyqtSignal(dict)
    log_message = pyqtSignal(str)

    def __init__(self, host="127.0.0.1", port=10005):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.client_socket = None

    def run(self):
        self.running = True
        self.log_message.emit(f"TCP client connecting to {self.host}:{self.port}...")
        
        while self.running:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.host, self.port))
                self.log_message.emit("Connected to ROS TCP Bridge Server!")
                
                buffer = ""
                while self.running:
                    data = self.client_socket.recv(1024)
                    if not data:
                        self.log_message.emit("TCP connection closed by server.")
                        break
                    
                    buffer += data.decode("utf-8")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            try:
                                # Try parsing as JSON (supporting full telemetry payload)
                                payload = json.loads(line)
                                self.telemetry_received.emit(payload)
                            except json.JSONDecodeError:
                                # Fallback: Parse comma-separated "SPEED,ALTITUDE" format
                                parts = line.split(",")
                                if len(parts) >= 2:
                                    try:
                                        payload = {
                                            "speed": float(parts[0]),
                                            "altitude": float(parts[1]),
                                            # Default fallback values for missing attributes
                                            "heading": 180.0,
                                            "target_heading": 240.0,
                                            "pitch": 0.0,
                                            "roll": 0.0,
                                            "battery": 85,
                                            "state": "IN-FLIGHT"
                                        }
                                        self.telemetry_received.emit(payload)
                                    except ValueError:
                                        continue
            except socket.error as e:
                self.log_message.emit(f"TCP connection failed. Retrying in 2 seconds...")
                time.sleep(2.0)
            finally:
                if self.client_socket:
                    self.client_socket.close()
                    self.client_socket = None

    def stop(self):
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.client_socket.close()
        self.wait()


# ---------------------------------------------------------
# MAIN APPLICATION WINDOW
# ---------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mostavio eVTOL Pilot AR HUD Dashboard")
        self.resize(1180, 680)
        self.setStyleSheet(f"background-color: #0A0E17;")
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -------------------------------------------------
        # LEFT PANEL: GROUND CONTROL SIMULATOR
        # -------------------------------------------------
        self.control_frame = QFrame()
        self.control_frame.setObjectName("control_panel")
        self.control_frame.setStyleSheet(PANEL_QSS)
        self.control_frame.setFixedWidth(300)
        control_layout = QVBoxLayout(self.control_frame)
        control_layout.setContentsMargins(10, 10, 10, 10)

        title_lbl = QLabel("SIMULATION CONTROL")
        title_lbl.setObjectName("panel_title")
        control_layout.addWidget(title_lbl)

        # Group 1: Telemetry Sliders
        telemetry_group = QGroupBox("TELEMETRY GENERATOR")
        tel_grid = QGridLayout(telemetry_group)
        tel_grid.setSpacing(6)

        # Speed slider (0 to 120 kt)
        tel_grid.addWidget(QLabel("SPEED (KT)"), 0, 0)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(0, 120)
        self.speed_slider.setValue(45)
        self.speed_val_lbl = QLabel("45 KT")
        tel_grid.addWidget(self.speed_slider, 0, 1)
        tel_grid.addWidget(self.speed_val_lbl, 0, 2)

        # Altitude slider (0 to 500 ft)
        tel_grid.addWidget(QLabel("ALTITUDE (FT)"), 1, 0)
        self.alt_slider = QSlider(Qt.Orientation.Horizontal)
        self.alt_slider.setRange(0, 500)
        self.alt_slider.setValue(120)
        self.alt_val_lbl = QLabel("120 FT")
        tel_grid.addWidget(self.alt_slider, 1, 1)
        tel_grid.addWidget(self.alt_val_lbl, 1, 2)

        # Heading slider (0 to 360 deg)
        tel_grid.addWidget(QLabel("HEADING (DEG)"), 2, 0)
        self.hdg_slider = QSlider(Qt.Orientation.Horizontal)
        self.hdg_slider.setRange(0, 360)
        self.hdg_slider.setValue(180)
        self.hdg_val_lbl = QLabel("180°")
        tel_grid.addWidget(self.hdg_slider, 2, 1)
        tel_grid.addWidget(self.hdg_val_lbl, 2, 2)

        # Target Heading bug slider (0 to 360 deg)
        tel_grid.addWidget(QLabel("TARGET HDG"), 3, 0)
        self.target_hdg_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_hdg_slider.setRange(0, 360)
        self.target_hdg_slider.setValue(240)
        self.target_hdg_val_lbl = QLabel("240°")
        tel_grid.addWidget(self.target_hdg_slider, 3, 1)
        tel_grid.addWidget(self.target_hdg_val_lbl, 3, 2)

        # Pitch slider (-30 to 30 deg)
        tel_grid.addWidget(QLabel("PITCH (DEG)"), 4, 0)
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-30, 30)
        self.pitch_slider.setValue(5)
        self.pitch_val_lbl = QLabel("5°")
        tel_grid.addWidget(self.pitch_slider, 4, 1)
        tel_grid.addWidget(self.pitch_val_lbl, 4, 2)

        # Roll slider (-45 to 45 deg)
        tel_grid.addWidget(QLabel("ROLL (DEG)"), 5, 0)
        self.roll_slider = QSlider(Qt.Orientation.Horizontal)
        self.roll_slider.setRange(-45, 45)
        self.roll_slider.setValue(0)
        self.roll_val_lbl = QLabel("0°")
        tel_grid.addWidget(self.roll_slider, 5, 1)
        tel_grid.addWidget(self.roll_val_lbl, 5, 2)

        # Battery SoC slider (0 to 100 %)
        tel_grid.addWidget(QLabel("BATTERY (%)"), 6, 0)
        self.bat_slider = QSlider(Qt.Orientation.Horizontal)
        self.bat_slider.setRange(0, 100)
        self.bat_slider.setValue(85)
        self.bat_val_lbl = QLabel("85%")
        tel_grid.addWidget(self.bat_slider, 6, 1)
        tel_grid.addWidget(self.bat_val_lbl, 6, 2)

        control_layout.addWidget(telemetry_group)

        # Group 2: Flight State Control
        state_group = QGroupBox("FLIGHT STATE ACTIONS")
        state_layout = QVBoxLayout(state_group)
        
        self.state_combo = QComboBox()
        self.state_combo.addItems([
            "DISARMED", "ARMED", "TAKEOFF", "HOVERING", 
            "IN-FLIGHT", "LANDING", "AUTONOMOUS"
        ])
        self.state_combo.setCurrentText("HOVERING")
        state_layout.addWidget(QLabel("SET CURRENT STATE:"))
        state_layout.addWidget(self.state_combo)

        control_layout.addWidget(state_group)

        # Group 3: Trigger Warnings
        warning_group = QGroupBox("PILOT ALERTS INJECTOR")
        warn_layout = QVBoxLayout(warning_group)

        btn_info = QPushButton("Inject Info: GPS Lock Established")
        btn_warn = QPushButton("Inject Warning: Wind Shear Alert")
        btn_crit = QPushButton("Inject Critical: Battery Low Reserve")
        btn_clear = QPushButton("Clear Alert Logs")

        warn_layout.addWidget(btn_info)
        warn_layout.addWidget(btn_warn)
        warn_layout.addWidget(btn_crit)
        warn_layout.addWidget(btn_clear)
        control_layout.addWidget(warning_group)

        # Group 4: Network Reception (UDP JSON / TCP String Selector)
        net_group = QGroupBox("EXTERNAL TELEMETRY LINK")
        net_layout = QVBoxLayout(net_group)
        
        net_layout.addWidget(QLabel("SELECT INTERFACE PROTOCOL:"))
        self.net_mode_combo = QComboBox()
        self.net_mode_combo.addItems([
            "UDP JSON Feed (Port 5005)",
            "TCP Unity-Bridge (Port 10005)"
        ])
        net_layout.addWidget(self.net_mode_combo)
        
        self.net_connect_btn = QPushButton("Connect Telemetry Link")
        self.net_connect_btn.setCheckable(True)
        net_layout.addWidget(self.net_connect_btn)
        
        self.net_log_box = QTextEdit()
        self.net_log_box.setReadOnly(True)
        self.net_log_box.setFixedHeight(70)
        self.net_log_box.setPlaceholderText("Network events log...")
        net_layout.addWidget(self.net_log_box)

        control_layout.addWidget(net_group)

        # Add Control Panel Frame to Main Grid Layout
        main_layout.addWidget(self.control_frame)

        # -------------------------------------------------
        # RIGHT PANEL: UNIFIED HUD WIDGET
        # -------------------------------------------------
        self.hud_view = PilotHUDView()
        main_layout.addWidget(self.hud_view)

        # -------------------------------------------------
        # SIGNAL CONNECTIONS (Local simulation)
        # -------------------------------------------------
        self.speed_slider.valueChanged.connect(self.handle_speed_slider)
        self.alt_slider.valueChanged.connect(self.handle_alt_slider)
        self.hdg_slider.valueChanged.connect(self.handle_hdg_slider)
        self.target_hdg_slider.valueChanged.connect(self.handle_target_hdg_slider)
        self.pitch_slider.valueChanged.connect(self.handle_pitch_slider)
        self.roll_slider.valueChanged.connect(self.handle_roll_slider)
        self.bat_slider.valueChanged.connect(self.handle_bat_slider)
        self.state_combo.currentTextChanged.connect(self.handle_state_combo)

        # Warnings Injectors
        btn_info.clicked.connect(lambda: self.hud_view.add_alert("INFO", "GPS Lock status: 12 satellites locked."))
        btn_warn.clicked.connect(lambda: self.hud_view.add_alert("WARNING", "Wind shear warning: 22 knots gusting at altitude."))
        btn_crit.clicked.connect(lambda: self.hud_view.add_alert("CRITICAL", "LOW BATTERY SYSTEM FAULT - Land eVTOL Immediately!"))
        btn_clear.clicked.connect(self.hud_view.clear_alerts)

        self.net_connect_btn.clicked.connect(self.toggle_network_connection)

        # Screen Animation Timer (60 FPS refresh for moving wires grid sky landscape)
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.hud_view.advance_animation)
        self.animation_timer.start(16) # ~60 Hz

        # Flashing Alert timer (500 ms)
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink_state)
        self.blink_timer.start(500)

        # Thread variable
        self.net_thread = None

        # Sync initial visuals from widgets
        self.refresh_ui_from_sliders()

    # -------------------------------------------------
    # CONTROL HANDLERS
    # -------------------------------------------------
    def refresh_ui_from_sliders(self):
        self.hud_view.update_telemetry(
            self.speed_slider.value(),
            self.alt_slider.value(),
            self.hdg_slider.value(),
            self.pitch_slider.value(),
            self.roll_slider.value(),
            self.bat_slider.value(),
            self.state_combo.currentText(),
            self.target_hdg_slider.value()
        )

    def handle_speed_slider(self, val):
        self.speed_val_lbl.setText(f"{val} KT")
        self.refresh_ui_from_sliders()
        
    def handle_alt_slider(self, val):
        self.alt_val_lbl.setText(f"{val} FT")
        self.refresh_ui_from_sliders()

    def handle_hdg_slider(self, val):
        self.hdg_val_lbl.setText(f"{val}°")
        self.refresh_ui_from_sliders()

    def handle_target_hdg_slider(self, val):
        self.target_hdg_val_lbl.setText(f"{val}°")
        self.refresh_ui_from_sliders()

    def handle_pitch_slider(self, val):
        self.pitch_val_lbl.setText(f"{val}°")
        self.refresh_ui_from_sliders()

    def handle_roll_slider(self, val):
        self.roll_val_lbl.setText(f"{val}°")
        self.refresh_ui_from_sliders()

    def handle_bat_slider(self, val):
        self.bat_val_lbl.setText(f"{val}%")
        self.refresh_ui_from_sliders()

    def handle_state_combo(self, state_text):
        self.refresh_ui_from_sliders()
        self.hud_view.add_alert("INFO", f"Flight State transitioned: {state_text}")

    def toggle_blink_state(self):
        self.hud_view.alert_blink_state = not self.hud_view.alert_blink_state
        self.hud_view.update()

    # -------------------------------------------------
    # NETWORK FEED TOGGLES (UDP / TCP CLIENT BRIDGES)
    # -------------------------------------------------
    def toggle_network_connection(self):
        is_connecting = self.net_connect_btn.isChecked()
        if is_connecting:
            mode = self.net_mode_combo.currentIndex()
            self.net_connect_btn.setText("Disconnect Telemetry Link")
            self.net_connect_btn.setStyleSheet("background-color: #FF3366; color: #0C101B;")
            self.net_mode_combo.setEnabled(False)
            self.set_sliders_enabled(False)
            
            if mode == 0:  # UDP JSON Port 5005
                self.net_log_box.append("Starting UDP Socket Thread...")
                self.net_thread = UDPReceiverThread()
            else:          # TCP Port 10005 (Unity compatibility mode)
                self.net_log_box.append("Starting TCP Client Thread...")
                self.net_thread = TCPReceiverThread()
                
            self.net_thread.telemetry_received.connect(self.process_network_telemetry)
            self.net_thread.log_message.connect(self.net_log_box.append)
            self.net_thread.start()
        else:
            self.net_connect_btn.setText("Connect Telemetry Link")
            self.net_connect_btn.setStyleSheet("")
            self.net_mode_combo.setEnabled(True)
            self.net_log_box.append("Stopping telemetry thread...")
            if self.net_thread:
                self.net_thread.stop()
                self.net_thread = None
            self.set_sliders_enabled(True)

    def set_sliders_enabled(self, enabled):
        self.speed_slider.setEnabled(enabled)
        self.alt_slider.setEnabled(enabled)
        self.hdg_slider.setEnabled(enabled)
        self.target_hdg_slider.setEnabled(enabled)
        self.pitch_slider.setEnabled(enabled)
        self.roll_slider.setEnabled(enabled)
        self.bat_slider.setEnabled(enabled)
        self.state_combo.setEnabled(enabled)

    def process_network_telemetry(self, payload):
        try:
            # Block slider signal triggers during network sync to prevent loops
            self.speed_slider.blockSignals(True)
            self.alt_slider.blockSignals(True)
            self.hdg_slider.blockSignals(True)
            self.target_hdg_slider.blockSignals(True)
            self.pitch_slider.blockSignals(True)
            self.roll_slider.blockSignals(True)
            self.bat_slider.blockSignals(True)
            self.state_combo.blockSignals(True)
            
            if "speed" in payload:
                self.speed_slider.setValue(int(payload["speed"]))
                self.speed_val_lbl.setText(f"{int(payload['speed'])} KT")
            if "altitude" in payload:
                self.alt_slider.setValue(int(payload["altitude"]))
                self.alt_val_lbl.setText(f"{int(payload['altitude'])} FT")
            if "heading" in payload:
                self.hdg_slider.setValue(int(payload["heading"]))
                self.hdg_val_lbl.setText(f"{int(payload['heading'])}°")
            if "target_heading" in payload:
                self.target_hdg_slider.setValue(int(payload["target_heading"]))
                self.target_hdg_val_lbl.setText(f"{int(payload['target_heading'])}°")
            if "pitch" in payload:
                self.pitch_slider.setValue(int(payload["pitch"]))
                self.pitch_val_lbl.setText(f"{int(payload['pitch'])}°")
            if "roll" in payload:
                self.roll_slider.setValue(int(payload["roll"]))
                self.roll_val_lbl.setText(f"{int(payload['roll'])}°")
            if "battery" in payload:
                self.bat_slider.setValue(int(payload["battery"]))
                self.bat_val_lbl.setText(f"{int(payload['battery'])}%")
            if "state" in payload:
                self.state_combo.setCurrentText(payload["state"])
                
            self.speed_slider.blockSignals(False)
            self.alt_slider.blockSignals(False)
            self.hdg_slider.blockSignals(False)
            self.target_hdg_slider.blockSignals(False)
            self.pitch_slider.blockSignals(False)
            self.roll_slider.blockSignals(False)
            self.bat_slider.blockSignals(False)
            self.state_combo.blockSignals(False)
            
            self.refresh_ui_from_sliders()
            
            if "alert" in payload:
                alert_type = payload["alert"].get("level", "INFO")
                alert_msg = payload["alert"].get("message", "")
                if alert_msg:
                    self.hud_view.add_alert(alert_type, alert_msg)
        except Exception as e:
            self.net_log_box.append(f"Data process error: {str(e)}")

    def closeEvent(self, event):
        if self.net_thread:
            self.net_thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
