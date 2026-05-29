import sys
import os
import math
import random
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (QPainter, QColor, QPen, QRadialGradient, QBrush,
                            QFont, QLinearGradient, QFontDatabase, QPolygonF,
                            QPainterPath, QRegion)


# ── Particle ────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, cx, cy, radius):
        self.reset(cx, cy, radius)

    def reset(self, cx, cy, radius):
        angle = random.uniform(0, math.tau)
        r = random.uniform(radius * 0.6, radius * 1.1)
        self.x = cx + r * math.cos(angle)
        self.y = cy + r * math.sin(angle)
        speed = random.uniform(0.3, 1.2)
        self.vx = random.uniform(-speed, speed)
        self.vy = random.uniform(-speed, speed)
        self.life = random.uniform(0.4, 1.0)
        self.decay = random.uniform(0.004, 0.012)
        self.size = random.uniform(1.0, 3.5)
        self.base_speed = speed
        self.cx = cx
        self.cy = cy
        self.radius = radius

    def update(self, speaking=False):
        mult = 3.0 if speaking else 1.0
        self.x += self.vx * mult
        self.y += self.vy * mult
        decay_mult = 1.8 if speaking else 1.0
        self.life -= self.decay * decay_mult
        if self.life <= 0:
            self.reset(self.cx, self.cy, self.radius)


# ── Data stream ticker ───────────────────────────────────────────────────────
class DataStream:
    CHARS = "01ABCDEF<>[]{}!#$%"

    def __init__(self, x, y_range, speed, color):
        self.x = x
        self.y = random.uniform(*y_range)
        self.y_range = y_range
        self.speed = speed
        self.color = color
        self.chars = [random.choice(self.CHARS) for _ in range(random.randint(3, 8))]
        self.alpha = random.uniform(60, 160)

    def update(self):
        self.y += self.speed
        if self.y > self.y_range[1]:
            self.y = self.y_range[0]
            self.chars = [random.choice(self.CHARS) for _ in range(random.randint(3, 8))]

    def mutate(self):
        if random.random() < 0.05:
            idx = random.randint(0, len(self.chars) - 1)
            self.chars[idx] = random.choice(self.CHARS)


# ── Main widget ──────────────────────────────────────────────────────────────
class JarvisWidget(QWidget):
    def __init__(self, parent=None, window=None):
        super().__init__(parent)
        self.main_win = window
        self.state = ""
        self.angle = 0.0
        self.pulse = 0.0
        self.breath = 0.0
        self.scan_y = 0.0
        self.glitch = 0.0
        self.frame = 0
        self.speak_pulse = 0.0       # dedicated fast pulse for SPEAKING
        self.speak_intensity = 0.0   # smooth ramp-up intensity

        # Particles
        self.particles: list[Particle] = []

        # Data streams (left/right columns)
        self.streams: list[DataStream] = []

        self._build_streams()

        # State file
        self.state_file = os.path.join(os.path.dirname(__file__), "state.txt")
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._check_state)
        self.state_timer.start(100) # Faster check for snappier transitions

        # Initial check to set visibility immediately
        self._check_state()

        # Animation timer 60fps
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start(16)

    # ── setup ────────────────────────────────────────────────────────────────
    def _build_streams(self):
        for i in range(6):
            x = 10 + i * 18
            self.streams.append(DataStream(x, (20, 380), random.uniform(0.5, 1.5),
                                           QColor(0, 180, 255)))
        for i in range(6):
            x = 290 + i * 18
            self.streams.append(DataStream(x, (20, 380), random.uniform(0.5, 1.5),
                                           QColor(0, 220, 180)))

    def _rebuild_particles(self, cx, cy, radius, count=60):
        self.particles = [Particle(cx, cy, radius) for _ in range(count)]

    # ── state ────────────────────────────────────────────────────────────────
    def _check_state(self):
        if os.path.exists(self.state_file):
            try:
                s = ""
                with open(self.state_file, "r", encoding="utf-8-sig") as f:
                    s = f.read().strip()
                
                if s and s != self.state:
                    self.state = s
                    print(f"DEBUG: State changed to {self.state}")
                    # Opacity-based visibility control (เนียนกว่า Show/Hide)
                    win = self.main_win if self.main_win else self.window()
                    if win:
                        if self.state == "SPEAKING":
                            win.setWindowOpacity(1.0)
                        else:
                            # ล่องหนสำหรับสถานะอื่น (จะไม่มีการซ่อนหน้าต่างถ้าไฟล์ว่างเปล่า)
                            win.setWindowOpacity(0.0)
            except Exception as e:
                print(f"DEBUG: Error in _check_state: {e}")

    # ── tick ─────────────────────────────────────────────────────────────────
    def _tick(self):
        speaking = self.state == "SPEAKING"
        # Extremely slow speed 0.2 for speaking, 0.0 for idle
        speed = {"THINKING": 1.0, "LISTENING": 0.5, "SPEAKING": 0.2}.get(self.state, 0.0)
        
        self.angle += 0.5 * speed
        # Extremely slow pulse
        pulse_speed = 0.05 if speaking else 0.02
        self.pulse  = (math.sin(self.angle * pulse_speed) + 1) / 2
        
        if speaking:
            self.speak_intensity = min(1.0, self.speak_intensity + 0.1)
        else:
            self.speak_intensity = max(0.0, self.speak_intensity - 0.05)
        self.breath = (math.sin(self.angle * 0.04) + 1) / 2
        self.scan_y = (self.scan_y + 1.2 * speed) % self.height()
        self.glitch = max(0.0, self.glitch - 0.05)
        self.frame += 1

        # ── SPEAKING-specific enhancements ──
        # Smooth ramp: intensity rises to 1.0 quickly, falls slowly
        target_intensity = 1.0 if speaking else 0.0
        self.speak_intensity += (target_intensity - self.speak_intensity) * (0.15 if speaking else 0.05)
        # Back to smooth stable frequency
        freq = 0.6 if speaking else 0.8
        self.speak_pulse = (math.sin(self.angle * freq) + 1) / 2 * self.speak_intensity

        # Override pulse when speaking for classic feel
        if speaking:
            self.pulse = (0.5 + 0.5 * self.speak_pulse)

        # More frequent glitch when speaking
        glitch_chance = 0.04 if speaking else 0.008 * speed
        if random.random() < glitch_chance:
            self.glitch = random.uniform(0.5 if speaking else 0.3, 1.0)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        if not self.particles:
            self._rebuild_particles(cx, cy, 120)

        # During speaking, spawn extra particles
        if speaking and len(self.particles) < 120:
            for _ in range(3):
                self.particles.append(Particle(cx, cy, 120))
        elif not speaking and len(self.particles) > 60:
            self.particles = self.particles[:60]

        for pt in self.particles:
            pt.cx, pt.cy, pt.radius = cx, cy, 120
            pt.update(speaking=speaking)

        for s in self.streams:
            s.update()
            s.mutate()

        self.update()

    # ── color palette ────────────────────────────────────────────────────────
    def _palette(self):
        if self.state == "LISTENING":
            return QColor(0, 255, 180), QColor(0, 100, 255)
        if self.state == "THINKING":
            return QColor(255, 180, 0), QColor(255, 80, 0)
        if self.state == "SPEAKING":
            return QColor(0, 200, 255), QColor(100, 0, 255)
        return QColor(0, 200, 255), QColor(0, 80, 180)

    # ── paint ────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        speaking = self.state == "SPEAKING"
        primary, secondary = self._palette()

        # ── 1. Transparent background (no fill — hologram floats) ──────────
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 0))

        # ── 2. Moving scan beam (clipped to circle) ───────────────────────────
        scan_grad = QLinearGradient(0, self.scan_y - 30, 0, self.scan_y + 30)
        scan_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        scan_grad.setColorAt(0.5, QColor(primary.red(), primary.green(), primary.blue(), 18))
        scan_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(QPointF(cx, cy), 165, 165)
        p.setClipPath(clip_path)
        p.fillRect(0, int(self.scan_y) - 30, w, 60, QBrush(scan_grad))
        p.restore()

        # ── 3. Corner Brackets (HUD overlay) ──────────────────────────────────
        self._draw_corner_brackets(p, w, h, primary)

        # ── 4. Bottom Status Bar ──────────────────────────────────────────────
        self._draw_status_bar(p, w, h, primary, secondary)

        # ── 5. Hex grid background ────────────────────────────────────────────
        self._draw_hex_grid(p, cx, cy, primary)

        # ── 6. Outer atmosphere glow ──────────────────────────────────────────
        atmo_r = 205 + 8 * self.breath
        atmo = QRadialGradient(cx, cy, atmo_r)
        atmo.setColorAt(0.0, QColor(0, 0, 0, 0))
        atmo.setColorAt(0.6, QColor(primary.red(), primary.green(), primary.blue(),
                                    int(10 + 8 * self.pulse)))
        atmo.setColorAt(0.85, QColor(primary.red(), primary.green(), primary.blue(),
                                     int(25 + 15 * self.pulse)))
        atmo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(atmo))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), atmo_r, atmo_r)

        # ── 7. Rotating rings ─────────────────────────────────────────────────
        rings = [
            (160, 2, primary,   150, 48, 6, 1, -0.25, [(20,55),(200,235)]),
            (143, 1, secondary, 100, 30, 8, 1,  0.4,  [(90,130),(270,310)]),
            (125, 3, primary,   200, 60, 5, 1, -0.7,  [(150,175)]),
            (105, 2, secondary, 170, 40, 10,2,  1.0,  [(0,35),(180,215)]),
            (88,  1, primary,   130, 36, 12,2, -1.4,  [(60,90),(240,270)]),
        ]
        for (rad, thick, col, alpha, ticks, tlen, tw, spd, gaps) in rings:
            self._draw_ring(p, cx, cy, rad, thick, col, alpha,
                            ticks, tlen, tw, self.angle * spd, gaps)

        # ── 8. Particles ──────────────────────────────────────────────────────
        p.setPen(Qt.NoPen)
        for pt in self.particles:
            a = int(pt.life * 200)
            c = QColor(primary.red(), primary.green(), primary.blue(), a)
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(pt.x, pt.y), pt.size, pt.size)

        # ── 9. Dynamic Circular Soundwave (SPEAKING Mode) ────────────────────
        core_r = 58
        if speaking:
            p.save()
            p.translate(cx, cy)
            # Create three layers of circular ripples matching speaking intensity
            for wave_idx in range(3):
                wave_path = QPainterPath()
                points_count = 72
                amp = (12.0 - wave_idx * 3.0) * self.speak_pulse
                freq = 3.0 + wave_idx * 1.5
                phase = self.angle * 0.12 + wave_idx * math.pi / 2
                
                for i in range(points_count + 1):
                    deg = i * (360 / points_count)
                    rad_angle = math.radians(deg)
                    # Add circular sine wave distortion
                    wave_r = (core_r * 0.72) + math.sin(math.radians(deg * freq) + phase) * amp
                    x = wave_r * math.cos(rad_angle)
                    y = wave_r * math.sin(rad_angle)
                    if i == 0:
                        wave_path.moveTo(x, y)
                    else:
                        wave_path.lineTo(x, y)
                
                wave_alpha = int(180 - wave_idx * 40)
                wave_pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), wave_alpha), 1.2)
                p.setPen(wave_pen)
                p.setBrush(Qt.NoBrush)
                p.drawPath(wave_path)
            p.restore()

        # ── 10. Inner core ────────────────────────────────────────────────────
        core_glow = QRadialGradient(cx, cy, core_r)
        core_glow_a = int(60 + 40 * self.pulse)
        core_glow.setColorAt(0.0, QColor(primary.red(), primary.green(), primary.blue(),
                                         min(core_glow_a, 255)))
        core_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(core_glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_r, core_r)

        pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 240), 2.5)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), core_r, core_r)

        # Core inner fill
        core_fill = QRadialGradient(cx, cy, core_r * 0.7)
        core_fill.setColorAt(0.0, QColor(primary.red(), primary.green(), primary.blue(),
                                         int(50 + 30 * self.pulse)))
        core_fill.setColorAt(0.6, QColor(primary.red(), primary.green(), primary.blue(),
                                         int(20 + 15 * self.pulse)))
        core_fill.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(core_fill))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_r * 0.7, core_r * 0.7)

        # Rotating inner cross lines
        p.save()
        p.translate(cx, cy)
        p.rotate(self.angle * 1.5)
        cross_pen = QPen(QColor(primary.red(), primary.green(), primary.blue(),
                                int(100 + 60 * self.pulse)), 1)
        p.setPen(cross_pen)
        for i in range(4):
            a = math.radians(i * 45)
            p.drawLine(QPointF(0, 0),
                       QPointF(core_r * 0.8 * math.cos(a), core_r * 0.8 * math.sin(a)))
        p.restore()

        # ── 12. Glitch effect ─────────────────────────────────────────────────
        if self.glitch > 0.1:
            for _ in range(int(self.glitch * 5)):
                gy = random.randint(int(cy - 150), int(cy + 150))
                gx = random.randint(int(cx - 150), int(cx + 150))
                gw = random.randint(20, 80)
                ga = int(self.glitch * 60)
                gc = QColor(primary.red(), primary.green(), primary.blue(), ga)
                p.fillRect(gx, gy, gw, 2, gc)

        # ── 13. J.A.R.V.I.S. text ────────────────────────────────────────────
        # Text glow shadow
        for offset, alpha in [(4, 20), (2, 50), (0, 255)]:
            if offset > 0:
                shadow_c = QColor(primary.red(), primary.green(), primary.blue(), alpha)
                sfont = QFont("Consolas", 15, QFont.Bold)
                sfont.setLetterSpacing(QFont.AbsoluteSpacing, 6)
                p.setFont(sfont)
                p.setPen(shadow_c)
                p.drawText(QRectF(offset, cy - 13, w, 26), Qt.AlignCenter, "J.A.R.V.I.S.")
            else:
                tc = QColor(primary.red(), primary.green(), primary.blue(),
                            int(200 + 55 * self.pulse))
                font = QFont("Consolas", 15, QFont.Bold)
                font.setLetterSpacing(QFont.AbsoluteSpacing, 6)
                p.setFont(font)
                p.setPen(tc)
                p.drawText(QRectF(0, cy - 13, w, 26), Qt.AlignCenter, "J.A.R.V.I.S.")

        # ── 14. Status label ──────────────────────────────────────────────────
        state_map = {
            "LISTENING": "◉  LISTENING",
            "THINKING":  "⟳  PROCESSING",
            "SPEAKING":  "▶  SPEAKING",
        }
        label = state_map.get(self.state, "")
        if label:
            sfont2 = QFont("Consolas", 8)
            sfont2.setLetterSpacing(QFont.AbsoluteSpacing, 3)
            p.setFont(sfont2)
            lc = QColor(primary.red(), primary.green(), primary.blue(),
                        int(140 + 60 * self.pulse))
            p.setPen(lc)
            p.drawText(QRectF(0, cy + 20, w, 22), Qt.AlignCenter, label)

        p.end()

    # ── helper: hexagonal grid ───────────────────────────────────────────────
    def _draw_hex_grid(self, p, cx, cy, color):
        size = 22
        cols = 11
        rows = 11
        hex_alpha = int(12 + 8 * self.pulse)
        pen = QPen(QColor(color.red(), color.green(), color.blue(), hex_alpha), 0.5)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        dx = size * 1.732
        dy = size * 1.5
        for row in range(-rows // 2, rows // 2 + 1):
            for col in range(-cols // 2, cols // 2 + 1):
                hx = cx + col * dx + (row % 2) * dx / 2
                hy = cy + row * dy
                dist = math.hypot(hx - cx, hy - cy)
                if dist > 185:
                    continue
                pts = []
                for i in range(6):
                    a = math.radians(60 * i - 30)
                    pts.append(QPointF(hx + size * math.cos(a),
                                       hy + size * math.sin(a)))
                p.drawPolygon(QPolygonF(pts))

    # ── helper: corner brackets ──────────────────────────────────────────────
    def _draw_corner_brackets(self, p, w, h, color):
        length = 25
        thick = 2
        alpha = int(180 + 75 * self.pulse)
        pen = QPen(QColor(color.red(), color.green(), color.blue(), alpha), thick)
        p.setPen(pen)
        corners = [(8, 8), (w - 8, 8), (8, h - 8), (w - 8, h - 8)]
        dirs = [(1, 1), (-1, 1), (1, -1), (-1, -1)]
        for (x, y), (sx, sy) in zip(corners, dirs):
            p.drawLine(QPointF(x, y), QPointF(x + sx * length, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + sy * length))

    # ── helper: bottom status bar ────────────────────────────────────────────
    def _draw_status_bar(self, p, w, h, primary, secondary):
        bar_y = h - 28
        # bar background
        bar_grad = QLinearGradient(0, bar_y, w, bar_y)
        bar_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        bar_grad.setColorAt(0.5, QColor(primary.red(), primary.green(), primary.blue(), 25))
        bar_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(0, bar_y, w, 20, QBrush(bar_grad))

        # progress segments
        segs = 20
        seg_w = (w - 40) / segs
        active = int(segs * ((self.frame % 120) / 120.0))
        for i in range(segs):
            sx = 20 + i * seg_w
            if i <= active:
                sa = int(180 * (i / segs))
                c = QColor(secondary.red(), secondary.green(), secondary.blue(), sa)
            else:
                c = QColor(primary.red(), primary.green(), primary.blue(), 25)
            p.fillRect(int(sx), bar_y + 6, int(seg_w - 2), 4, c)

        # version label
        font_v = QFont("Consolas", 6)
        font_v.setLetterSpacing(QFont.AbsoluteSpacing, 1)
        p.setFont(font_v)
        vc = QColor(primary.red(), primary.green(), primary.blue(), 80)
        p.setPen(vc)
        p.drawText(QRectF(0, h - 14, w, 14), Qt.AlignCenter, "STARK INDUSTRIES  v7.0.1")

    # ── helper: ring with gaps ────────────────────────────────────────────────
    def _draw_ring(self, p, cx, cy, radius, thickness,
                   color, alpha, ticks, tick_len, tick_w, rotate, gap_angles=None):
        p.save()
        p.translate(cx, cy)
        p.rotate(rotate)

        ring_c = QColor(color.red(), color.green(), color.blue(), alpha)
        pen = QPen(ring_c, thickness)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        if gap_angles:
            step = 2
            for deg in range(0, 360, step):
                in_gap = any(gs <= deg < ge for gs, ge in gap_angles)
                if not in_gap:
                    a1 = math.radians(deg)
                    a2 = math.radians(deg + step)
                    p.drawLine(QPointF(radius * math.cos(a1), radius * math.sin(a1)),
                               QPointF(radius * math.cos(a2), radius * math.sin(a2)))
        else:
            p.drawEllipse(QPointF(0, 0), radius, radius)

        tick_pen = QPen(QColor(color.red(), color.green(), color.blue(),
                               max(alpha - 50, 30)), tick_w)
        p.setPen(tick_pen)
        for i in range(ticks):
            deg = (i * (360 / ticks)) % 360
            if gap_angles and any(gs <= deg < ge for gs, ge in gap_angles):
                continue
            a = math.radians(deg)
            inner = radius - tick_len
            p.drawLine(QPointF(inner * math.cos(a), inner * math.sin(a)),
                       QPointF(radius * math.cos(a), radius * math.sin(a)))

        p.restore()
# ── Window ───────────────────────────────────────────────────────────────────
class JarvisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFixedSize(420, 420)
        self.setWindowTitle("JARVIS_HOLO_SYSTEM")

        # Position logic
        self.pos_file = os.path.join(os.path.dirname(__file__), "pos.txt")
        if os.path.exists(self.pos_file):
            try:
                with open(self.pos_file, "r") as f:
                    x, y = map(int, f.read().split(","))
                self.move(x, y)
            except Exception:
                screen = QApplication.primaryScreen().availableGeometry()
                self.move(screen.width() - 440, screen.height() - 460)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.width() - 440, screen.height() - 460)

        self.widget = JarvisWidget(self, window=self)
        self.setCentralWidget(self.widget)
        self._drag_pos = None
        
        # เริ่มต้นแบบล่องหน (Opacity 0) แต่หน้าต่างรันอยู่จริง
        self.setWindowOpacity(0.0)
        self.show()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            import ctypes
            hwnd = int(self.winId())
            # DWMWA_BORDER_COLOR = 34, DWMWA_COLOR_NONE = 0xFFFFFFFE
            # ลบเส้นขอบ 1px ที่ Windows 11 วาดรอบหน้าต่าง
            val = ctypes.c_uint32(0xFFFFFFFE)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 34, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass
            
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None
        try:
            with open(self.pos_file, "w") as f:
                f.write(f"{self.x()},{self.y()}")
        except Exception:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = JarvisWindow()
    # Removed win.show() - visibility is now managed by JarvisWidget._check_state
    sys.exit(app.exec())


