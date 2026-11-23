"""
Curvy Hardware Notch Overlay Window & QPainter Rendering Engine.
Features:
- Complete auto-hide when there is no music playing
- Auto pop-up when notifications arrive (with 4-second dismiss & re-hide)
- Smooth hover-to-expand at top screen bezel with auto-retract
- Moving animated gradient effect flowing across the canvas
- Custom vector playback buttons (zero ugly emoji boxes)
- Proper high-resolution 26-bar audio visualizer
- Clean typography: zero green active dot, zero top-right options, zero unwanted text.
"""

import os
import sys
import math
import time
import datetime
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageFilter, ImageEnhance

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QPoint, QPointF, QRectF, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtSignal, pyqtProperty, QEvent
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath,
    QRadialGradient, QLinearGradient, QFontMetrics, QFont,
    QGuiApplication, QShortcut, QKeySequence, QCursor,
    QPixmap, QImage
)

from ui.styles import (
    COMPACT_IDLE_WIDTH, COMPACT_MUSIC_WIDTH, COMPACT_HEIGHT,
    TOAST_WIDTH, TOAST_HEIGHT, TOAST_R_TOP, TOAST_R_BOT,
    EXPANDED_WIDTH, EXPANDED_HEIGHT,
    OSD_HUD_WIDTH, OSD_HUD_HEIGHT, OSD_HUD_R_TOP, OSD_HUD_R_BOT,
    CALL_LIVE_WIDTH, CALL_LIVE_HEIGHT, CALL_LIVE_R_TOP, CALL_LIVE_R_BOT,
    OTP_PILL_WIDTH, OTP_PILL_HEIGHT, OTP_PILL_R_TOP, OTP_PILL_R_BOT,
    FILE_SHELF_WIDTH, FILE_SHELF_HEIGHT, FILE_SHELF_R_TOP, FILE_SHELF_R_BOT,
    DEVICE_POPUP_WIDTH, DEVICE_POPUP_HEIGHT,
    SIDE_COMPACT_IDLE_W, SIDE_COMPACT_IDLE_H, SIDE_COMPACT_MUSIC_W, SIDE_COMPACT_MUSIC_H,
    SIDE_TOAST_W, SIDE_TOAST_H, SIDE_EXPANDED_W, SIDE_EXPANDED_H,
    SIDE_OSD_HUD_W, SIDE_OSD_HUD_H, SIDE_CALL_LIVE_W, SIDE_CALL_LIVE_H,
    SIDE_OTP_PILL_W, SIDE_OTP_PILL_H, SIDE_FILE_SHELF_W, SIDE_FILE_SHELF_H,
    SIDE_DEVICE_POPUP_W, SIDE_DEVICE_POPUP_H,
    CORNER_COMPACT_IDLE_W, CORNER_COMPACT_IDLE_H,
    CORNER_COMPACT_MUSIC_W, CORNER_COMPACT_MUSIC_H,
    CORNER_ARM_THICKNESS, CORNER_INNER_RADIUS,
    CORNER_COMPACT_IDLE_SIZE, CORNER_COMPACT_MUSIC_SIZE, CORNER_TOAST_SIZE,
    CORNER_EXPANDED_SIZE, CORNER_OSD_HUD_SIZE, CORNER_CALL_LIVE_SIZE,
    CORNER_OTP_PILL_SIZE, CORNER_FILE_SHELF_SIZE, CORNER_DEVICE_POPUP_SIZE,
    NOTCH_RADIUS_TOP, NOTCH_RADIUS_BOT, EXPANDED_RADIUS,
    COLOR_BEZEL, COLOR_CANVAS, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED, COLOR_ACCENT_YELLOW,
    GLOW_STATES, get_microlabel_font, get_display_font,
    get_subtext_font, get_monospaced_font, DASHBOARD_STYLESHEET
)
from ui.components.visualizer import AudioVisualizerWidget
from ui.device_popup import DeviceConnectionPopup
from services.media_service import MediaService
from services.system_service import SystemService
from services.settings_service import settings


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def format_seconds(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# -------------------------------------------------------------
# Windows Fullscreen Detection (Games, Full-Screen Videos, etc.)
# -------------------------------------------------------------
try:
    _user32 = ctypes.windll.user32
    _shell32 = ctypes.windll.shell32

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ('cbSize', wintypes.DWORD),
            ('rcMonitor', wintypes.RECT),
            ('rcWork', wintypes.RECT),
            ('dwFlags', wintypes.DWORD)
        ]

    def is_fullscreen_app_active(self_hwnd=None) -> bool:
        """
        Detects if the foreground window is running in true exclusive full-screen mode
        (games, full-screen video in Chrome/Edge/Firefox/YouTube/VLC/Netflix).
        """
        try:
            # 1. Direct3D / exclusive fullscreen game / presentation check (Windows Shell API)
            qstate = ctypes.c_int()
            if _shell32.SHQueryUserNotificationState(ctypes.byref(qstate)) == 0:
                if qstate.value in (2, 3, 4):  # QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE
                    return True

            hwnd = _user32.GetForegroundWindow()
            if not hwnd or (self_hwnd and hwnd == self_hwnd):
                return False

            class_buf = ctypes.create_unicode_buffer(256)
            _user32.GetClassNameW(hwnd, class_buf, 256)
            cls = class_buf.value
            if cls in ('Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd'):
                return False

            rect = wintypes.RECT()
            if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return False

            hmon = _user32.MonitorFromWindow(hwnd, 1)  # MONITOR_DEFAULTTONEAREST
            if not hmon:
                return False

            mi = _MONITORINFO()
            mi.cbSize = ctypes.sizeof(_MONITORINFO)
            if not _user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                return False

            rc = mi.rcMonitor
            # True fullscreen F11 / video covers entire physical monitor and obscures the taskbar
            # Standard maximized windows leave the taskbar visible (rect.bottom <= mi.rcWork.bottom)
            if rect.left <= rc.left and rect.top <= rc.top and rect.right >= rc.right and rect.bottom >= rc.bottom:
                if mi.rcWork.bottom < rc.bottom and rect.bottom >= rc.bottom:
                    return True
        except Exception:
            pass
        return False
except Exception:
    def is_fullscreen_app_active(self_hwnd=None) -> bool:
        return False


def extract_album_swatches(image_path_or_pixmap) -> tuple[QColor, QColor]:
    """
    Extracts the vibrant accent color and secondary harmonizing swatch
    from an album cover, enforcing an automatic luminance floor.
    """
    default_vibrant = QColor("#FFD600")
    default_secondary = QColor("#FF8C00")

    if not image_path_or_pixmap or not os.path.exists(str(image_path_or_pixmap)):
        return default_vibrant, default_secondary

    try:
        from PIL import Image
        import colorsys

        img = Image.open(str(image_path_or_pixmap)).convert("RGB")
        img = img.resize((32, 32), Image.Resampling.BOX)

        pixels = list(img.getdata())
        scored = []
        for r, g, b in pixels:
            rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
            h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
            # Filter near-black, near-white, or washed-out grays
            if v < 0.15 or s < 0.18:
                continue
            score = (s ** 1.3) * (v ** 0.8)
            scored.append((score, h, s, v, r, g, b))

        if not scored:
            return default_vibrant, default_secondary

        scored.sort(key=lambda item: item[0], reverse=True)
        _, h1, s1, v1, r1, g1, b1 = scored[0]

        # Automatic luminance floor: guarantee brightness >= 0.72 so dark covers stay vivid
        v_floor = max(0.72, v1)
        s_floor = max(0.65, min(1.0, s1 * 1.15))
        rf, gf, bf = colorsys.hsv_to_rgb(h1, s_floor, v_floor)
        c_vibrant = QColor(int(rf * 255), int(gf * 255), int(bf * 255))

        # Secondary swatch: complementary or harmonic hue shift
        h2 = (h1 + 0.12) % 1.0  # 43 degree hue shift for harmonic dual-vortex
        rf2, gf2, bf2 = colorsys.hsv_to_rgb(h2, max(0.55, s1), max(0.55, v1 * 0.85))
        c_secondary = QColor(int(rf2 * 255), int(gf2 * 255), int(bf2 * 255))

        return c_vibrant, c_secondary
    except Exception:
        return default_vibrant, default_secondary


class CoverArtWidget(QWidget):
    """
    Apple-inspired media thumbnail card supporting:
    - 16:9 widescreen video thumbnail (92x52px, radius 8px) for YouTube & video.
    - 1:1 squircle cover art (52x52px, radius 12px) for music & audio tracks.
    Smooth bilinear transform and 1px inner specular border.
    """
    def __init__(self, size=52, parent=None):
        super().__init__(parent)
        self.card_size = size
        self._is_video = False
        self.setFixedSize(size, size)
        self._pixmap: Optional[QPixmap] = None

    def set_card_size(self, size: int):
        self.card_size = size
        if not self._is_video:
            self.setFixedSize(size, size)
            self.updateGeometry()
            self.update()

    def set_video_mode(self, is_video: bool):
        if self._is_video != is_video:
            self._is_video = is_video
            if is_video:
                # 16:9 widescreen ratio: 52 * 16 / 9 ≈ 92.4px -> 92x52px
                self.setFixedSize(92, 52)
            else:
                self.setFixedSize(self.card_size, self.card_size)
            self.updateGeometry()
            self.update()

    def set_pixmap(self, pixmap: Optional[QPixmap]):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        try:
            self._do_paint(event)
        except Exception:
            try:
                import traceback
                err = traceback.format_exc()
                log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n--- PAINT GLITCH CAUGHT {time.ctime()} ---\n{err}\n")
            except Exception:
                pass
            try:
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.fillRect(0, 0, self.width(), self.height(), QColor(10, 10, 14, 240))
                p.end()
            except Exception:
                pass

    def _do_paint(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w = float(self.width())
        h = float(self.height())
        rect = QRectF(0, 0, w, h)
        radius = 8.0 if self._is_video else 12.0

        # 1. Rounded squircle clip
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(path)

        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(
                rect.toRect(),
                self._pixmap.scaled(
                    int(w), int(h),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        else:
            painter.fillRect(rect, QColor(22, 24, 32))
            cx, cy = w / 2.0, h / 2.0
            if self._is_video:
                # Minimalist video play glyph
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 60))
                tri = QPainterPath()
                tri.moveTo(cx - 5.0, cy - 7.0)
                tri.lineTo(cx + 7.0, cy)
                tri.lineTo(cx - 5.0, cy + 7.0)
                tri.closeSubpath()
                painter.drawPath(tri)
            else:
                # Minimalist vector musical note when idle
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 60))
                note_path = QPainterPath()
                note_path.addEllipse(QPointF(cx - 5.0, cy + 3.0), 3.5, 2.5)
                note_path.addEllipse(QPointF(cx + 4.0, cy + 0.5), 3.5, 2.5)
                painter.drawPath(note_path)
                painter.setPen(QPen(QColor(255, 255, 255, 60), 1.8))
                painter.drawLine(QPointF(cx - 2.5, cy + 3.0), QPointF(cx - 2.5, cy - 6.0))
                painter.drawLine(QPointF(cx + 6.5, cy + 0.5), QPointF(cx + 6.5, cy - 8.5))
                painter.drawLine(QPointF(cx - 2.5, cy - 6.0), QPointF(cx + 6.5, cy - 8.5))

        painter.restore()

        # 2. Subtle 1px inner specular border
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)


class TimelineScrubber(QWidget):
    """
    Apple-inspired interactive scrubbing timeline bar.
    Hit-test area: 14px vertically for comfortable seeking.
    Subtle 3.5px track expanding to 4.5px with a clean white thumb on hover/scrub.
    """
    seek_requested = pyqtSignal(float)  # Normalized position 0.0 to 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self.setMouseTracking(True)
        self._progress = 0.0  # 0.0 to 1.0
        self._hovered = False
        self._scrubbing = False
        self._scrub_progress = 0.0
        self._accent_color = QColor(255, 255, 255)

    def set_accent_color(self, col: QColor):
        self._accent_color = QColor(col)
        self.update()

    def set_progress(self, progress: float):
        if not self._scrubbing:
            self._progress = max(0.0, min(1.0, progress))
            self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._scrubbing:
            self._hovered = False
            self.unsetCursor()
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._scrubbing = True
            self._hovered = True
            pos_x = event.position().x()
            self._scrub_progress = max(0.0, min(1.0, pos_x / max(1.0, float(self.width()))))
            self.update()
            self.seek_requested.emit(self._scrub_progress)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._hovered or self._scrubbing:
            pos_x = event.position().x()
            self._scrub_progress = max(0.0, min(1.0, pos_x / max(1.0, float(self.width()))))
            if self._scrubbing:
                self.seek_requested.emit(self._scrub_progress)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._scrubbing:
            self._scrubbing = False
            self._progress = self._scrub_progress
            self.seek_requested.emit(self._progress)
            if not self.rect().contains(event.position().toPoint()):
                self._hovered = False
                self.unsetCursor()
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        try:
            self._do_paint(event)
        except Exception:
            try:
                import traceback
                err = traceback.format_exc()
                log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n--- PAINT GLITCH CAUGHT {time.ctime()} ---\n{err}\n")
            except Exception:
                pass
            try:
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.fillRect(0, 0, self.width(), self.height(), QColor(10, 10, 14, 240))
                p.end()
            except Exception:
                pass

    def _do_paint(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        cy = h / 2.0

        is_active = self._hovered or self._scrubbing
        track_h = 4.0 if is_active else 3.0
        disp_progress = self._scrub_progress if is_active else self._progress

        # Track background
        track_rect = QRectF(0, cy - track_h / 2.0, w, track_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 36))
        painter.drawRoundedRect(track_rect, track_h / 2.0, track_h / 2.0)

        # Track filled (clean white)
        fill_w = max(0.0, min(w, w * disp_progress))
        if fill_w > 0:
            fill_rect = QRectF(0, cy - track_h / 2.0, fill_w, track_h)
            painter.setBrush(QColor(255, 255, 255, 230))
            painter.drawRoundedRect(fill_rect, track_h / 2.0, track_h / 2.0)

        # Clean, refined thumb circle (8px) on hover/scrub
        if is_active:
            thumb_radius = 4.5
            thumb_x = max(thumb_radius, min(w - thumb_radius, fill_w))

            # Subtle contact shadow
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 90))
            painter.drawEllipse(QRectF(thumb_x - thumb_radius, cy - thumb_radius + 1.0, thumb_radius * 2.0, thumb_radius * 2.0))

            # Solid white thumb
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawEllipse(QRectF(thumb_x - thumb_radius, cy - thumb_radius, thumb_radius * 2.0, thumb_radius * 2.0))


class VectorMediaButton(QPushButton):
    """
    Apple-inspired tactile playback control button.
    Renders clean, anti-aliased vector glyphs in pure white on subtle translucent glass.
    """
    def __init__(self, mode="play", is_primary=False, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.is_primary = is_primary
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if is_primary:
            self.setFixedSize(54, 36)
        else:
            self.setFixedSize(38, 32)

    def set_accent_color(self, col: QColor):
        pass  # Kept for signature compatibility

    def set_mode(self, mode: str):
        if self.mode != mode:
            self.mode = mode
            self.update()

    def paintEvent(self, event):
        try:
            self._do_paint(event)
        except Exception:
            try:
                import traceback
                err = traceback.format_exc()
                log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n--- PAINT GLITCH CAUGHT {time.ctime()} ---\n{err}\n")
            except Exception:
                pass
            try:
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.fillRect(0, 0, self.width(), self.height(), QColor(10, 10, 14, 240))
                p.end()
            except Exception:
                pass

    def _do_paint(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0

        rect = QRectF(0, 0, w, h)
        rad = h / 2.0

        is_down = self.isDown()
        is_hover = self.underMouse()

        if self.is_primary:
            # Clean Apple frosted capsule: subtle white glass with sharp white glyph
            bg_alpha = 55 if is_down else (42 if is_hover else 26)
            border_alpha = 80 if is_hover else 40
            painter.setPen(QPen(QColor(255, 255, 255, border_alpha), 1.0))
            painter.setBrush(QColor(255, 255, 255, bg_alpha))
            painter.drawRoundedRect(rect, rad, rad)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 245))
            if self.mode == "pause":
                bar_w = 3.5
                bar_h = 13.0
                gap = 3.5
                painter.drawRoundedRect(QRectF(cx - gap - bar_w / 2.0, cy - bar_h / 2.0, bar_w, bar_h), 1.2, 1.2)
                painter.drawRoundedRect(QRectF(cx + gap - bar_w / 2.0, cy - bar_h / 2.0, bar_w, bar_h), 1.2, 1.2)
            else:
                tri = QPainterPath()
                tri.moveTo(cx - 4.5, cy - 6.5)
                tri.lineTo(cx + 6.5, cy)
                tri.lineTo(cx - 4.5, cy + 6.5)
                tri.closeSubpath()
                painter.drawPath(tri)
        else:
            bg_alpha = 42 if is_down else (28 if is_hover else 14)
            border_alpha = 60 if is_hover else 25
            painter.setPen(QPen(QColor(255, 255, 255, border_alpha), 1.0))
            painter.setBrush(QColor(255, 255, 255, bg_alpha))
            painter.drawRoundedRect(rect, rad, rad)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 220))
            if self.mode == "prev":
                painter.drawRoundedRect(QRectF(cx - 6.5, cy - 5.5, 2.0, 11.0), 1.0, 1.0)
                tri = QPainterPath()
                tri.moveTo(cx + 4.5, cy - 5.5)
                tri.lineTo(cx - 3.5, cy)
                tri.lineTo(cx + 4.5, cy + 5.5)
                tri.closeSubpath()
                painter.drawPath(tri)
            elif self.mode == "next":
                painter.drawRoundedRect(QRectF(cx + 4.5, cy - 5.5, 2.0, 11.0), 1.0, 1.0)
                tri = QPainterPath()
                tri.moveTo(cx - 4.5, cy - 5.5)
                tri.lineTo(cx + 3.5, cy)
                tri.lineTo(cx - 4.5, cy + 5.5)
                tri.closeSubpath()
                painter.drawPath(tri)


class DynamicIslandWidget(QWidget):
    """
    Curvy hardware notch desktop overlay with moving gradient effect,
    hover-to-expand, and auto-hide when there is no music.
    """
    state_changed = pyqtSignal(str)

    def __init__(self, media_service: MediaService, system_service: SystemService, device_service: Optional[Any] = None):
        super().__init__()
        self.media_service = media_service
        self.system_service = system_service
        self.device_service = device_service

        # States: "compact", "toast", "expanded", "device_popup"
        self._island_state = "compact"
        self._glow_state = "idle"

        # Liquid Edge Docking & Dragging Physics
        self._dock_edge = "top"          # "top", "bottom", "left", "right", "floating"
        self._dock_morph = 1.0           # 1.0 = fully notched ears, 0.0 = pure liquid floating capsule
        self._target_morph = 1.0
        self._dock_ratio_x = 0.5         # Horizontal center ratio along screen (0.0 to 1.0)
        self._dock_ratio_y = 0.5         # Vertical center ratio along screen (0.0 to 1.0)
        self._is_dragging = False
        self._drag_start_global = None
        self._drag_start_pos = None
        self._drag_last_pos = None
        self._liquid_vx = 0.0            # Fluid drag velocity x
        self._liquid_vy = 0.0            # Fluid drag velocity y

        # Device Connection Pop-up Cache & Auto-Dismiss Timer (Native Dynamic Island Pop-up)
        self._device_info: Dict[str, Any] = {}
        self._device_pixmaps: Dict[str, QPixmap] = {}
        self._device_close_hovered = False
        self._device_done_hovered = False
        self._toast_close_hovered = False
        self._load_device_pixmaps()

        self._device_dismiss_timer = QTimer(self)
        self._device_dismiss_timer.setSingleShot(True)
        self._device_dismiss_timer.timeout.connect(self._on_device_dismiss_timeout)

        # Hover-to-expand / Hover-to-retract timers
        self._hover_expand_timer = QTimer(self)
        self._hover_expand_timer.setSingleShot(True)
        self._hover_expand_timer.timeout.connect(self._on_hover_expand_triggered)

        self._hover_collapse_timer = QTimer(self)
        self._hover_collapse_timer.setSingleShot(True)
        self._hover_collapse_timer.timeout.connect(self._on_hover_collapse_triggered)

        # Ambient Glow Engine
        idle_glow = GLOW_STATES["idle"]
        self._current_glow_c1 = QColor(idle_glow["color1"])
        self._current_glow_c2 = QColor(idle_glow["color2"])
        self._current_glow_opacity = idle_glow["opacity"]
        self._target_glow_c1 = QColor(idle_glow["color1"])
        self._target_glow_c2 = QColor(idle_glow["color2"])
        self._target_glow_opacity = idle_glow["opacity"]

        # Moving Gradient Phase (Undulating liquid light effect)
        self._gradient_shift = 0.0

        # Album Art & Frosted Glass
        self._album_art_pixmap: Optional[QPixmap] = None
        self._glass_bg_pixmap: Optional[QPixmap] = None
        self._current_art_path: Optional[str] = None

        # Battery Status
        self._battery_info = self.system_service.get_battery_info()

        # Mini Equalizer Physics for Compact Mode
        self._mini_eq_heights = [0.2, 0.4, 0.6, 0.3]
        self._mini_eq_phase = 0.0
        self._mini_eq_peak = 0.0
        self._vertical_eq_heights = [0.15] * 12
        self._corner_eq_heights = self._vertical_eq_heights

        # Animation & Physics
        self._geo_animation: Optional[QPropertyAnimation] = None
        self._ticker_offset = 0.0
        self._ticker_pause = 90
        self._last_media_track_id = ""
        self._hovered = False

        # Current Data Cache
        self._time_str = "12:37"
        self._date_str = "Today"
        self._media_info: Dict[str, Any] = {
            "has_media": False,
            "is_playing": False,
            "title": "",
            "artist": "",
            "album": "",
            "position": 0,
            "duration": 210,
            "album_art_path": None
        }
        self._toast_info: Dict[str, Any] = {
            "app": "",
            "title": "",
            "message": "",
            "time": 0
        }
        self._toast_dismiss_timer = QTimer(self)
        self._toast_dismiss_timer.setSingleShot(True)
        self._toast_dismiss_timer.timeout.connect(self._on_toast_timeout)

        # New UI States Data Caches & Timers (OSD, Live Call, 2FA OTP, File Shelf)
        self._osd_info: Dict[str, Any] = {"glyph": "🔊", "value": 0.5, "label": "50%", "type": "volume"}
        self._osd_dismiss_timer = QTimer(self)
        self._osd_dismiss_timer.setSingleShot(True)
        self._osd_dismiss_timer.timeout.connect(self._on_osd_timeout)

        self._call_info: Dict[str, Any] = {"name": "Mom", "status": "iPhone • Incoming Call", "avatar": "👤"}
        self._call_pulse = 0.0

        self._otp_info: Dict[str, Any] = {"code": "482 910", "app": "Messages", "copied": False}
        self._otp_dismiss_timer = QTimer(self)
        self._otp_dismiss_timer.setSingleShot(True)
        self._otp_dismiss_timer.timeout.connect(self._on_otp_timeout)

        self._shelf_files: list[Dict[str, Any]] = []
        self._shelf_hover_clear = False

        # 3D Accessory Connection Sheet Enhancements
        self._device_route = "device"  # "device" (e.g. AirPods) ↔ "speakers"
        self._device_route_pos = 0.0   # 0.0 to 1.0 slide indicator

        # Micro-Interactions & Hardware Status
        self._tilt_x = 0.0
        self._tilt_y = 0.0
        self._tilt_target_x = 0.0
        self._tilt_target_y = 0.0
        self._download_progress = 0.0
        self._auto_hide_enabled = False
        self._active_vibrant_c = QColor("#FFD600")
        self._active_secondary_c = QColor("#FF8C00")

        self._phone_battery = 84
        self._phone_connected = False
        self._privacy_mic = False
        self._privacy_cam = False

        # Theme & Visual Customization Matrix
        self._bg_style = "ambient"  # "ambient", "solid", "gradient"
        self._solid_color = QColor("#08080C")
        self._gradient_c1 = QColor(14, 14, 18, 252)
        self._gradient_c2 = QColor(2, 2, 4, 255)
        self._ambient_enabled = True
        self._ambient_opacity = 0.24

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._on_flash_timeout)
        self._flash_message: Optional[str] = None

        # Music idle debounce timer (smooth hide without flicker)
        self._music_idle_timer = QTimer(self)
        self._music_idle_timer.setSingleShot(True)
        self._music_idle_timer.setInterval(1200)
        self._music_idle_timer.timeout.connect(self._on_music_idle_timeout)

        # Live playback progress tracking (real-time position ticker)
        self._live_pos = 0.0
        self._live_dur = 0.0
        self._last_live_time = time.time()
        self._live_progress_timer = QTimer(self)
        self._live_progress_timer.setInterval(250)
        self._live_progress_timer.timeout.connect(self._tick_live_progress)
        self._live_progress_timer.start()

        # Fullscreen detection timer (completely hide in games & full-screen videos)
        self._is_fullscreen_suppressed = False
        self._fullscreen_timer = QTimer(self)
        self._fullscreen_timer.setInterval(350)
        self._fullscreen_timer.timeout.connect(self._check_fullscreen_mode)
        self._fullscreen_timer.start()

        # Setup Window Flags & Attributes
        self._setup_window_flags()

        # Build Interactive Dashboard Layout (Expanded State)
        self._init_dashboard_ui()

        # 60 FPS Render Timer
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._on_render_tick)
        self._render_timer.start()

        # Ticker Timer: 60 FPS silky smooth scrolling
        self._ticker_timer = QTimer(self)
        self._ticker_timer.setInterval(16)
        self._ticker_timer.timeout.connect(self._on_ticker_tick)
        self._ticker_timer.start()

        # Connect Service Signals
        self._connect_signals()

        # Keyboard Shortcuts
        self._shortcut = QShortcut(QKeySequence("Alt+Space"), self)
        self._shortcut.activated.connect(self.toggle_expanded)
        self._esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._esc_shortcut.activated.connect(self.collapse_to_compact)

        # Initial Positioning
        self._apply_geometry_for_state("compact", animate=False)

        # Multi-monitor & Resolution Awareness
        app = QGuiApplication.instance()
        if app:
            app.screenAdded.connect(self._on_screens_changed)
            app.screenRemoved.connect(self._on_screens_changed)
            primary = app.primaryScreen()
            if primary:
                primary.geometryChanged.connect(self._on_screens_changed)

        # Always visible at launch in compact mode
        self.show()
        self.raise_()
        self._apply_geometry_for_state("compact", animate=False)

    def _load_device_pixmaps(self):
        """Preloads device artwork for instant display."""
        for cat in ["airpods", "headphones", "speaker", "iem"]:
            p = resource_path(os.path.join("assets", "devices", f"{cat}.png"))
            if not os.path.exists(p):
                p = resource_path(os.path.join("assets", "devices", f"{cat}_white.png"))
            if os.path.exists(p):
                pix = QPixmap(p)
                if not pix.isNull():
                    self._device_pixmaps[cat] = pix

    def _on_device_dismiss_timeout(self):
        """Auto-collapse the device pop-up after timeout."""
        if self._island_state == "device_popup":
            self.collapse_to_compact()

    def _is_music_active(self) -> bool:
        """True only if media session exists AND is actively playing."""
        return bool(self._media_info.get("has_media", False) and self._media_info.get("is_playing", False))

    def _on_music_idle_timeout(self):
        """Called when music has been stopped/paused after grace duration."""
        if not self._is_music_active() and self._island_state not in ("toast", "expanded", "device_popup"):
            self._apply_geometry_for_state("compact", animate=True)
            self.update()

    def _on_screens_changed(self, *args):
        """Auto-recenter when monitor resolution changes or displays are plugged/unplugged."""
        self._apply_geometry_for_state(self._island_state, animate=False)

    def _check_fullscreen_mode(self):
        """
        Periodically checks if a full-screen game, video, or presentation is active.
        Completely hides the island if so, and restores when exiting.
        """
        try:
            self_hwnd = int(self.winId()) if self.effectiveWinId() else None
        except Exception:
            self_hwnd = None

        is_fs = is_fullscreen_app_active(self_hwnd)
        if is_fs != self._is_fullscreen_suppressed:
            self._is_fullscreen_suppressed = is_fs
            if is_fs:
                # Fullscreen game or video is active: completely hide!
                if self.isVisible():
                    self.hide()
            else:
                # Exited fullscreen game/video: restore immediately!
                if not self.isVisible():
                    self.show()
                    self.raise_()
        elif not self._is_fullscreen_suppressed and self.isVisible():
            self._ensure_behind_taskbar()

    def wake_up(self):
        """Forces the Dynamic Island to become visible, raise to top, and expand."""
        self._is_fullscreen_suppressed = False
        self.show()
        self.raise_()
        self.activateWindow()
        self.set_island_state("expanded")
        self.set_glow_state("notification", duration_sec=3.0)

    # -------------------------------------------------------------
    # Window Flags & Positioning Flush at Top (y = 0)
    # -------------------------------------------------------------
    def _setup_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(DASHBOARD_STYLESHEET)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    def _ensure_behind_taskbar(self):
        """
        Ensures Dynamic Island is placed immediately behind the Windows Taskbar in Z-order.
        Keeps Dynamic Island topmost over all standard application windows, but allows the
        Windows Taskbar (Shell_TrayWnd) to sit on top so taskbar icons are never obstructed.
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
            tray = user32.FindWindowW("Shell_TrayWnd", None)
            if not tray:
                hdesk = user32.OpenDesktopW("default", 0, False, 0x01FF)
                if hdesk:
                    old_desk = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
                    user32.SetThreadDesktop(hdesk)
                    tray = user32.FindWindowW("Shell_TrayWnd", None)
                    user32.SetThreadDesktop(old_desk)
                    user32.CloseDesktop(hdesk)
            if tray:
                hwnd = int(self.winId())
                if hwnd and tray != hwnd:
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_NOACTIVATE = 0x0010
                    user32.SetWindowPos(hwnd, tray, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

    def raise_(self):
        super().raise_()
        self._ensure_behind_taskbar()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_behind_taskbar()

    def _get_target_rect(self, state: str) -> tuple[int, int, int, int]:
        cur_center = self.geometry().center()
        screen = QGuiApplication.screenAt(cur_center) or QGuiApplication.primaryScreen()
        screen_geo = screen.geometry() if screen else QRectF(0, 0, 1920, 1080).toRect()

        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")
        has_media = self._is_music_active() or self._media_info.get("has_media", False)

        if is_corner:
            # L-Bracket Geometry for Screen Corners ("Edges")
            if state == "compact":
                w = CORNER_COMPACT_MUSIC_W if has_media else CORNER_COMPACT_IDLE_W
                h = CORNER_COMPACT_MUSIC_H if has_media else CORNER_COMPACT_IDLE_H
            elif state == "toast":
                w = h = CORNER_TOAST_SIZE
            elif state == "device_popup":
                w = h = CORNER_DEVICE_POPUP_SIZE
            elif state == "osd_hud":
                w = h = CORNER_OSD_HUD_SIZE
            elif state == "call_live":
                w = h = CORNER_CALL_LIVE_SIZE
            elif state == "otp_pill":
                w = h = CORNER_OTP_PILL_SIZE
            elif state == "file_shelf":
                w = h = CORNER_FILE_SHELF_SIZE
            else:  # expanded
                w = h = CORNER_EXPANDED_SIZE

        elif is_side:
            # Vertical Proportions for Left / Right Screen Bezels
            if state == "compact":
                w = SIDE_COMPACT_MUSIC_W if has_media else SIDE_COMPACT_IDLE_W
                h = SIDE_COMPACT_MUSIC_H if has_media else SIDE_COMPACT_IDLE_H
            elif state == "toast":
                w = SIDE_TOAST_W
                h = SIDE_TOAST_H
            elif state == "device_popup":
                w = SIDE_DEVICE_POPUP_W
                h = SIDE_DEVICE_POPUP_H
            elif state == "osd_hud":
                w = SIDE_OSD_HUD_W
                h = SIDE_OSD_HUD_H
            elif state == "call_live":
                w = SIDE_CALL_LIVE_W
                h = SIDE_CALL_LIVE_H
            elif state == "otp_pill":
                w = SIDE_OTP_PILL_W
                h = SIDE_OTP_PILL_H
            elif state == "file_shelf":
                w = SIDE_FILE_SHELF_W
                h = SIDE_FILE_SHELF_H
            else:  # expanded
                w = SIDE_EXPANDED_W
                h = SIDE_EXPANDED_H

        else:
            # Horizontal Dynamic Pill for Top / Bottom / Floating
            if state == "compact":
                w = COMPACT_MUSIC_WIDTH if has_media else COMPACT_IDLE_WIDTH
                h = COMPACT_HEIGHT
            elif state == "toast":
                w = TOAST_WIDTH
                h = TOAST_HEIGHT
            elif state == "device_popup":
                w = DEVICE_POPUP_WIDTH
                h = DEVICE_POPUP_HEIGHT
            elif state == "osd_hud":
                w = OSD_HUD_WIDTH
                h = OSD_HUD_HEIGHT
            elif state == "call_live":
                w = CALL_LIVE_WIDTH
                h = CALL_LIVE_HEIGHT
            elif state == "otp_pill":
                w = OTP_PILL_WIDTH
                h = OTP_PILL_HEIGHT
            elif state == "file_shelf":
                w = FILE_SHELF_WIDTH
                h = FILE_SHELF_HEIGHT
            else:  # expanded
                w = EXPANDED_WIDTH
                h = EXPANDED_HEIGHT

        ratio_x = getattr(self, "_dock_ratio_x", 0.5)
        ratio_y = getattr(self, "_dock_ratio_y", 0.5)

        if edge == "top":
            center_x = screen_geo.x() + screen_geo.width() * ratio_x
            x = int(center_x - w / 2)
            x = max(int(screen_geo.left()), min(int(screen_geo.right() - w), x))
            if getattr(self, "_auto_hide_enabled", False) and state == "compact" and not self._hovered:
                # 4px translucent tab handle at screen edge
                y = int(screen_geo.top() - h + 4)
            else:
                y = int(screen_geo.top())

        elif edge == "bottom":
            center_x = screen_geo.x() + screen_geo.width() * ratio_x
            x = int(center_x - w / 2)
            x = max(int(screen_geo.left()), min(int(screen_geo.right() - w), x))
            if getattr(self, "_auto_hide_enabled", False) and state == "compact" and not self._hovered:
                y = int(screen_geo.bottom() - 4)
            else:
                y = int(screen_geo.bottom() - h + 1)

        elif edge == "left":
            if getattr(self, "_auto_hide_enabled", False) and state == "compact" and not self._hovered:
                x = int(screen_geo.left() - w + 4)
            else:
                x = int(screen_geo.left())
            center_y = screen_geo.y() + screen_geo.height() * ratio_y
            y = int(center_y - h / 2)
            y = max(int(screen_geo.top()), min(int(screen_geo.bottom() - h), y))

        elif edge == "right":
            if getattr(self, "_auto_hide_enabled", False) and state == "compact" and not self._hovered:
                x = int(screen_geo.right() - 4)
            else:
                x = int(screen_geo.right() - w + 1)
            center_y = screen_geo.y() + screen_geo.height() * ratio_y
            y = int(center_y - h / 2)
            y = max(int(screen_geo.top()), min(int(screen_geo.bottom() - h), y))

        elif edge in ("top-left", "corner-tl"):
            x = int(screen_geo.left())
            y = int(screen_geo.top())

        elif edge in ("top-right", "corner-tr"):
            x = int(screen_geo.right() - w + 1)
            y = int(screen_geo.top())

        elif edge in ("bottom-left", "corner-bl"):
            x = int(screen_geo.left())
            y = int(screen_geo.bottom() - h + 1)

        elif edge in ("bottom-right", "corner-br"):
            x = int(screen_geo.right() - w + 1)
            y = int(screen_geo.bottom() - h + 1)

        else:  # floating
            old_center = getattr(self, "_floating_center", cur_center)
            x = int(old_center.x() - w / 2)
            y = int(old_center.y() - h / 2)
            x = max(int(screen_geo.left() + 10), min(int(screen_geo.right() - w - 10), x))
            y = max(int(screen_geo.top() + 10), min(int(screen_geo.bottom() - h - 10), y))

        return x, y, w, h

    def get_expand_progress(self) -> float:
        return getattr(self, "_expand_progress_val", 0.0)

    def set_expand_progress(self, val: float):
        self._expand_progress_val = max(0.0, min(1.0, float(val)))
        p = self._expand_progress_val

        # Smooth cross-fade active child container from p=0.25 to 1.0
        cont_op = max(0.0, min(1.0, (p - 0.25) / 0.75))
        for eff in (getattr(self, "_dashboard_opacity_effect", None),
                    getattr(self, "_side_opacity_effect", None),
                    getattr(self, "_corner_opacity_effect", None)):
            if eff is not None:
                eff.setOpacity(cont_op)

        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")
        active_c = getattr(self, "dashboard_container_corner", None) if is_corner else (
            getattr(self, "dashboard_container_side", None) if is_side else getattr(self, "dashboard_container", None)
        )
        if active_c is not None:
            if p >= 0.25 and not active_c.isVisible():
                active_c.show()
                active_c.raise_()
            elif p < 0.25 and active_c.isVisible():
                active_c.hide()

        self.update()

    expand_progress = pyqtProperty(float, get_expand_progress, set_expand_progress)

    def _on_geo_anim_finished(self):
        target = getattr(self, "_anim_target_state", self._island_state)
        self._update_child_visibility(target)
        self._ensure_behind_taskbar()

    def _apply_geometry_for_state(self, state: str, animate=True):
        x, y, w, h = self._get_target_rect(state)
        self._anim_target_state = state

        if not animate:
            self.setGeometry(x, y, w, h)
            self.set_expand_progress(1.0 if state == "expanded" else 0.0)
            self._update_child_visibility(state)
            self._ensure_behind_taskbar()
            return

        if self._geo_animation and self._geo_animation.state() == QPropertyAnimation.State.Running:
            self._geo_animation.stop()

        if hasattr(self, "_expand_anim") and self._expand_anim.state() == QPropertyAnimation.State.Running:
            self._expand_anim.stop()

        duration = 320 if state in ("expanded", "device_popup") else 260
        easing = QEasingCurve.Type.OutCubic if state == "expanded" else QEasingCurve.Type.OutQuad

        self._geo_animation = QPropertyAnimation(self, b"geometry")
        self._geo_animation.setDuration(duration)
        self._geo_animation.setEasingCurve(easing)
        self._geo_animation.setStartValue(self.geometry())
        self._geo_animation.setEndValue(QRectF(x, y, w, h).toRect())

        target_p = 1.0 if state == "expanded" else 0.0
        start_p = self.get_expand_progress()

        self._expand_anim = QPropertyAnimation(self, b"expand_progress")
        self._expand_anim.setDuration(duration)
        self._expand_anim.setEasingCurve(easing)
        self._expand_anim.setStartValue(start_p)
        self._expand_anim.setEndValue(target_p)

        if state == "expanded":
            self._update_child_visibility("expanded")

        try:
            self._geo_animation.finished.disconnect()
        except Exception:
            pass
        self._geo_animation.finished.connect(self._on_geo_anim_finished)

        self._geo_animation.start()
        self._expand_anim.start()

    def _update_child_visibility(self, state: str):
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        active_container = getattr(self, "dashboard_container_corner", None) if is_corner else (
            getattr(self, "dashboard_container_side", None) if is_side else getattr(self, "dashboard_container", None)
        )
        all_containers = [
            getattr(self, "dashboard_container", None),
            getattr(self, "dashboard_container_side", None),
            getattr(self, "dashboard_container_corner", None)
        ]

        if state == "expanded":
            for c in all_containers:
                if c is not None:
                    if c is active_container:
                        c.show()
                        c.raise_()
                    else:
                        c.hide()
        else:
            for c in all_containers:
                if c is not None:
                    c.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        w = float(self.width())
        h = float(self.height())

        if is_corner:
            c = getattr(self, "dashboard_container_corner", None)
            if c is not None:
                target_w = 252.0
                target_h = 252.0
                c_w = min(target_w, max(10.0, w - 28.0))
                c_h = min(target_h, max(10.0, h - 28.0))
                is_right = edge in ("top-right", "corner-tr", "bottom-right", "corner-br")
                is_bottom = edge in ("bottom-left", "corner-bl", "bottom-right", "corner-br")
                x = (w - 14.0 - c_w) if is_right else 14.0
                y = (h - 14.0 - c_h) if is_bottom else 14.0
                c.setGeometry(int(x), int(y), int(c_w), int(c_h))
        elif is_side:
            c = getattr(self, "dashboard_container_side", None)
            if c is not None:
                target_w = 202.0
                target_h = 326.0
                c_w = min(target_w, max(10.0, w - 28.0))
                c_h = min(target_h, max(10.0, h - 44.0))
                x = (w - 14.0 - c_w) if edge == "right" else 14.0
                y = max(4.0, (h - c_h) / 2.0)
                c.setGeometry(int(x), int(y), int(c_w), int(c_h))
        else:
            c = getattr(self, "dashboard_container", None)
            if c is not None:
                target_w = 428.0
                target_h = 168.0
                c_w = min(target_w, max(10.0, w - 32.0))
                c_h = min(target_h, max(10.0, h - 32.0))
                x = max(16.0, (w - c_w) / 2.0)
                y = (h - 12.0 - c_h) if edge == "bottom" else (20.0 if edge == "top" else max(10.0, (h - c_h) / 2.0))
                c.setGeometry(int(x), int(y), int(c_w), int(c_h))

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow() and self._island_state == "expanded" and not getattr(self, "_is_dragging", False):
                self.collapse_to_compact()
        super().changeEvent(event)

    # -------------------------------------------------------------
    # Hover-to-Expand & Retract Logic
    # -------------------------------------------------------------
    def enterEvent(self, event):
        if self._is_fullscreen_suppressed:
            return
        self._hovered = True
        self._hover_collapse_timer.stop()
        if self._island_state == "device_popup":
            self._device_dismiss_timer.stop()
        elif self._island_state == "compact":
            self._hover_expand_timer.start(100)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._device_close_hovered = False
        self._device_done_hovered = False
        self._toast_close_hovered = False
        self._hover_expand_timer.stop()
        if self._island_state == "device_popup":
            self._device_dismiss_timer.start(2500)
        elif self._island_state == "expanded":
            self._hover_collapse_timer.start(450)
        self.update()
        super().leaveEvent(event)

    def _on_hover_expand_triggered(self):
        if self._hovered and self._island_state == "compact":
            self.set_island_state("expanded")

    def _on_hover_collapse_triggered(self):
        if not self._hovered and self._island_state == "expanded":
            self.set_island_state("compact")

    # -------------------------------------------------------------
    # Theme & Visual Customization Controls
    # -------------------------------------------------------------
    def set_theme_ambient(self, opacity: float = 0.24, auto_save: bool = True):
        self._bg_style = "ambient"
        self._ambient_enabled = True
        self._ambient_opacity = opacity
        self.update()
        if auto_save:
            self.save_current_settings()

    def set_theme_solid(self, color: QColor, auto_save: bool = True):
        self._bg_style = "solid"
        self._solid_color = QColor(color)
        self.update()
        if auto_save:
            self.save_current_settings()

    def set_theme_gradient(self, color1: QColor, color2: QColor, auto_save: bool = True):
        self._bg_style = "gradient"
        self._gradient_c1 = QColor(color1)
        self._gradient_c2 = QColor(color2)
        self.update()
        if auto_save:
            self.save_current_settings()

    def set_ambient_opacity(self, opacity: float):
        self._ambient_opacity = max(0.0, min(1.0, opacity))
        self._ambient_enabled = (self._ambient_opacity > 0.0)
        self.update()
        self.save_current_settings()

    def apply_saved_settings(self, cfg: dict):
        """Restores dock position, edge, screen monitor, and theme cleanly from saved settings."""
        if not cfg or not isinstance(cfg, dict):
            return

        edge = cfg.get("dock_edge", "top")
        self._dock_edge = edge
        self._target_morph = 1.0 if edge != "floating" else 0.0
        self._dock_morph = self._target_morph
        self._dock_ratio_x = float(cfg.get("dock_ratio_x", 0.5))
        self._dock_ratio_y = float(cfg.get("dock_ratio_y", 0.5))
        self._auto_hide_enabled = bool(cfg.get("auto_hide", False))

        fx = cfg.get("floating_x", -1)
        fy = cfg.get("floating_y", -1)
        if fx >= 0 and fy >= 0:
            self._floating_center = QPointF(float(fx), float(fy))

        # Restore monitor/screen
        screen_idx = int(cfg.get("screen_index", 0))
        screens = QGuiApplication.screens()
        if 0 <= screen_idx < len(screens):
            s_geo = screens[screen_idx].geometry()
            self.move(s_geo.center())

        # Restore theme
        theme_mode = cfg.get("theme_mode", "ambient")
        if theme_mode == "ambient":
            self.set_theme_ambient(float(cfg.get("ambient_opacity", 0.24)), auto_save=False)
        elif theme_mode in ("obsidian", "titanium", "solid"):
            col_hex = cfg.get("solid_color", "#08080C")
            self.set_theme_solid(QColor(col_hex), auto_save=False)

        self._apply_geometry_for_state(self._island_state, animate=False)
        self.update()

    def save_current_settings(self):
        """Flushes the current position, screen, dock edge, and theme to persistent settings."""
        try:
            center = self.geometry().center()
            screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
            screens = QGuiApplication.screens()
            screen_idx = screens.index(screen) if screen in screens else 0

            bg_style = getattr(self, "_bg_style", "ambient")
            solid_col = getattr(self, "_solid_color", QColor("#08080C"))
            solid_hex = solid_col.name() if hasattr(solid_col, "name") else "#08080C"

            updates = {
                "dock_edge": getattr(self, "_dock_edge", "top"),
                "dock_ratio_x": getattr(self, "_dock_ratio_x", 0.5),
                "dock_ratio_y": getattr(self, "_dock_ratio_y", 0.5),
                "screen_index": screen_idx,
                "auto_hide": getattr(self, "_auto_hide_enabled", False),
                "theme_mode": bg_style,
                "solid_color": solid_hex,
                "ambient_opacity": getattr(self, "_ambient_opacity", 0.24),
            }
            if hasattr(self, "_floating_center") and self._floating_center:
                updates["floating_x"] = float(self._floating_center.x())
                updates["floating_y"] = float(self._floating_center.y())
            settings.update(updates)
        except Exception as e:
            import logging
            logging.error(f"Error saving island settings: {e}")

    # -------------------------------------------------------------
    # State Management & Auto-Hide
    # -------------------------------------------------------------
    def set_island_state(self, state: str):
        if self._island_state == state:
            return
        old_state = self._island_state
        self._island_state = state

        if old_state == "toast" and state != "toast":
            self._toast_dismiss_timer.stop()
        if old_state == "device_popup" and state != "device_popup":
            self._device_dismiss_timer.stop()

        if state == "compact":
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        self._apply_geometry_for_state(state, animate=True)
        self._evaluate_glow_state()
        self.state_changed.emit(state)

    def toggle_expanded(self):
        if self._is_fullscreen_suppressed:
            return
        if self._island_state == "expanded":
            self.set_island_state("compact")
        else:
            if not self.isVisible():
                self.show()
                self.raise_()
            self.set_island_state("expanded")

    def collapse_to_compact(self):
        self._hover_collapse_timer.stop()
        self._device_dismiss_timer.stop()
        if self._island_state != "compact":
            self.set_island_state("compact")

    def trigger_toast(self, app: str, title: str, message: str):
        """
        Pops up the notch immediately on incoming notification toast,
        unless currently suppressed by a full-screen game or video!
        """
        if self._is_fullscreen_suppressed:
            return
        self._toast_info = {
            "app": app,
            "title": title,
            "message": message,
            "time": time.time()
        }
        self.set_glow_state("notification")
        if not self.isVisible():
            self.show()
            self.raise_()
        self.set_island_state("toast")
        self._toast_dismiss_timer.start(4500)

    def _on_toast_timeout(self):
        if self._island_state == "toast":
            self.collapse_to_compact()

    def set_glow_state(self, glow_name: str, duration_sec: Optional[float] = None):
        if glow_name not in GLOW_STATES:
            glow_name = "idle"

        self._glow_state = glow_name
        cfg = GLOW_STATES[glow_name]
        self._target_glow_c1 = QColor(cfg["color1"])
        self._target_glow_c2 = QColor(cfg["color2"])
        self._target_glow_opacity = cfg["opacity"]

        if duration_sec and duration_sec > 0:
            self._flash_timer.start(int(duration_sec * 1000))

    def _on_flash_timeout(self):
        self._flash_message = None
        self._evaluate_glow_state()

    def _evaluate_glow_state(self):
        if self._flash_timer.isActive():
            return
        if self._island_state == "toast":
            self.set_glow_state("notification")
        elif self._media_info.get("is_playing", False):
            self.set_glow_state("music")
        elif self._island_state == "expanded":
            self.set_glow_state("reminders")
        else:
            self.set_glow_state("idle")

    def _get_time_colors(self) -> Tuple[QColor, QColor]:
        """
        Returns (col_hr, col_min) for prominent dual-color clock rendering.
        Hours: Crisp pure white (#FFFFFF).
        Minutes: Vibrant accent color derived from track artwork, or dynamic amber (#FF9F0A).
        """
        col_hr = QColor(255, 255, 255)
        accent_hex = self._media_info.get("accent_color")
        if accent_hex and self._media_info.get("is_playing", False):
            c = QColor(accent_hex)
            h, s, v, _ = c.getHsv()
            v = max(v, 225)
            s = max(min(s, 220), 130)
            col_min = QColor.fromHsv(h, s, v)
        else:
            col_min = QColor("#FF9F0A")  # Apple Watch vibrant amber
        return col_hr, col_min

    def _get_24h_time_parts(self) -> Tuple[str, str]:
        """
        Returns (hh, mm) in 24-hour format with guaranteed 2 digits (e.g. '15', '49' or '03', '05').
        """
        try:
            now = datetime.datetime.now()
            return now.strftime("%H"), now.strftime("%M")
        except Exception:
            parts = self._time_str.split(" ")[0].split(":")
            hh = parts[0].zfill(2) if len(parts) > 0 else "00"
            mm = parts[1].zfill(2) if len(parts) > 1 else "00"
            return hh, mm

    # -------------------------------------------------------------
    # Frosted Glass Album Art Generator & Accent Extractor
    # -------------------------------------------------------------
    def _update_album_art(self, art_path: Optional[str]):
        if not art_path or not os.path.exists(art_path):
            if self._album_art_pixmap is not None or self._glass_bg_pixmap is not None:
                self._album_art_pixmap = None
                self._glass_bg_pixmap = None
                self._current_art_path = None
                for ca in (getattr(self, "cover_art", None), getattr(self, "cover_art_side", None), getattr(self, "cover_art_corner", None)):
                    if ca:
                        ca.set_pixmap(None)
                self.update()
            return

        if art_path == self._current_art_path and self._album_art_pixmap is not None:
            return

        self._current_art_path = art_path
        try:
            pix = QPixmap(art_path)
            if not pix.isNull():
                self._album_art_pixmap = pix
                for ca in (getattr(self, "cover_art", None), getattr(self, "cover_art_side", None), getattr(self, "cover_art_corner", None)):
                    if ca:
                        ca.set_pixmap(pix)

            # Dynamic Accent Extraction & Color Synchronization (400ms transition)
            vibrant_c, secondary_c = extract_album_swatches(art_path)
            self._active_vibrant_c = vibrant_c
            self._active_secondary_c = secondary_c

            if self._glow_state == "music" or self._media_info.get("is_playing", False):
                self._target_glow_c1 = vibrant_c
                self._target_glow_c2 = secondary_c

            for vz in (getattr(self, "visualizer", None), getattr(self, "visualizer_side", None), getattr(self, "visualizer_corner", None)):
                if vz:
                    vz.set_accent_colors(vibrant_c, secondary_c)
            for sc in (getattr(self, "timeline_scrubber", None), getattr(self, "timeline_scrubber_side", None), getattr(self, "timeline_scrubber_corner", None)):
                if sc:
                    sc.set_accent_color(vibrant_c)
            for bp in (getattr(self, "btn_play", None), getattr(self, "btn_play_side", None), getattr(self, "btn_play_corner", None)):
                if bp:
                    bp.set_accent_color(vibrant_c)

            im = Image.open(art_path)
            w = max(440, EXPANDED_WIDTH)
            h = max(200, EXPANDED_HEIGHT)
            bg = im.resize((w, h), Image.Resampling.BILINEAR)
            blurred = bg.filter(ImageFilter.GaussianBlur(radius=24))
            darkened = ImageEnhance.Brightness(blurred).enhance(0.40)
            rgba = darkened.convert("RGBA")
            qimg = QImage(
                rgba.tobytes("raw", "RGBA"),
                rgba.width,
                rgba.height,
                QImage.Format.Format_RGBA8888
            ).copy()
            self._glass_bg_pixmap = QPixmap.fromImage(qimg)
            self.update()
        except Exception:
            pass

    # -------------------------------------------------------------
    # Curvy Dashboard UI (Apple-Grade Clean Layout, Zero Nested Cards)
    # -------------------------------------------------------------
    def _init_dashboard_ui(self):
        # ── 1. Top / Horizontal Dashboard (Original, 100% Working) ────────────
        self.dashboard_container = QWidget(self)
        self.dashboard_container.hide()
        self._dashboard_opacity_effect = QGraphicsOpacityEffect(self.dashboard_container)
        self.dashboard_container.setGraphicsEffect(self._dashboard_opacity_effect)
        self._dashboard_opacity_effect.setOpacity(0.0)
        self._dashboard_fade_anim = QPropertyAnimation(self._dashboard_opacity_effect, b"opacity")

        self.lbl_exp_clock = None
        self.lbl_exp_battery = None

        main_layout = QVBoxLayout(self.dashboard_container)
        main_layout.setContentsMargins(14, 10, 14, 12)
        main_layout.setSpacing(10)

        # 1. Main Track & Visualizer Row
        track_row = QHBoxLayout()
        track_row.setContentsMargins(0, 0, 0, 0)
        track_row.setSpacing(12)

        self.cover_art = CoverArtWidget(size=52, parent=self.dashboard_container)
        track_row.addWidget(self.cover_art)

        track_info_box = QVBoxLayout()
        track_info_box.setSpacing(3)
        track_info_box.setContentsMargins(0, 4, 0, 4)

        self.lbl_exp_title = QLabel("No Media Playing", self.dashboard_container)
        self.lbl_exp_title.setFont(get_display_font(12.5))
        self.lbl_exp_title.setFixedHeight(22)
        self.lbl_exp_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_exp_title.setStyleSheet("color: #FFFFFF; font-weight: 600; border: none; background: transparent; padding: 0px;")

        self.lbl_exp_artist = QLabel("Ready", self.dashboard_container)
        self.lbl_exp_artist.setFont(get_subtext_font(10.5))
        self.lbl_exp_artist.setFixedHeight(18)
        self.lbl_exp_artist.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_exp_artist.setStyleSheet("color: rgba(255, 255, 255, 0.60); border: none; background: transparent; padding: 0px;")

        track_info_box.addWidget(self.lbl_exp_title)
        track_info_box.addWidget(self.lbl_exp_artist)
        track_row.addLayout(track_info_box, 1)

        self.visualizer = AudioVisualizerWidget(num_bars=22, bar_width=2.5, bar_spacing=2.5, parent=self.dashboard_container)
        self.visualizer.setFixedHeight(28)
        if hasattr(self, "system_service"):
            self.visualizer.set_spectrum_provider(self.system_service.get_audio_spectrum)
            self.visualizer.set_peak_provider(self.system_service.get_audio_peak)
        track_row.addWidget(self.visualizer, alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(track_row)

        # 2. Timeline Scrubber with Underneath Timestamp Readouts
        scrub_layout = QVBoxLayout()
        scrub_layout.setContentsMargins(0, 2, 0, 0)
        scrub_layout.setSpacing(2)

        self.timeline_scrubber = TimelineScrubber(self.dashboard_container)
        self.timeline_scrubber.seek_requested.connect(self._on_seek_requested)
        scrub_layout.addWidget(self.timeline_scrubber)

        times_row = QHBoxLayout()
        times_row.setContentsMargins(2, 0, 2, 0)

        self.lbl_time_pos = QLabel("0:00", self.dashboard_container)
        self.lbl_time_pos.setFont(get_microlabel_font())
        self.lbl_time_pos.setStyleSheet("color: rgba(255, 255, 255, 0.45); border: none; background: transparent;")

        self.lbl_time_dur = QLabel("0:00", self.dashboard_container)
        self.lbl_time_dur.setFont(get_microlabel_font())
        self.lbl_time_dur.setStyleSheet("color: rgba(255, 255, 255, 0.45); border: none; background: transparent;")

        times_row.addWidget(self.lbl_time_pos)
        times_row.addStretch()
        times_row.addWidget(self.lbl_time_dur)
        scrub_layout.addLayout(times_row)

        main_layout.addLayout(scrub_layout)

        # 3. Centered Playback Controls Row
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 2, 0, 0)
        controls_layout.setSpacing(16)
        controls_layout.addStretch()

        self.btn_prev = VectorMediaButton(mode="prev", is_primary=False, parent=self.dashboard_container)
        self.btn_prev.clicked.connect(self.media_service.previous_track)

        self.btn_play = VectorMediaButton(mode="play", is_primary=True, parent=self.dashboard_container)
        self.btn_play.clicked.connect(self.media_service.toggle_play_pause)

        self.btn_next = VectorMediaButton(mode="next", is_primary=False, parent=self.dashboard_container)
        self.btn_next.clicked.connect(self.media_service.next_track)

        controls_layout.addWidget(self.btn_prev)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

        # ── 2. Side / Vertical Dashboard (Left / Right Bezels, 230x370) ───────
        self.dashboard_container_side = QWidget(self)
        self.dashboard_container_side.hide()
        self._side_opacity_effect = QGraphicsOpacityEffect(self.dashboard_container_side)
        self.dashboard_container_side.setGraphicsEffect(self._side_opacity_effect)
        self._side_opacity_effect.setOpacity(0.0)

        side_layout = QVBoxLayout(self.dashboard_container_side)
        side_layout.setContentsMargins(16, 14, 16, 16)
        side_layout.setSpacing(10)

        # Centered Cover Art (80x80)
        self.cover_art_side = CoverArtWidget(size=80, parent=self.dashboard_container_side)
        side_layout.addWidget(self.cover_art_side, alignment=Qt.AlignmentFlag.AlignCenter)

        # Centered Track Info
        info_side = QVBoxLayout()
        info_side.setSpacing(2)
        info_side.setContentsMargins(0, 0, 0, 0)

        self.lbl_exp_title_side = QLabel("No Media Playing", self.dashboard_container_side)
        self.lbl_exp_title_side.setFont(get_display_font(12.5))
        self.lbl_exp_title_side.setFixedHeight(22)
        self.lbl_exp_title_side.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_exp_title_side.setStyleSheet("color: #FFFFFF; font-weight: 600; border: none; background: transparent; padding: 0px;")

        self.lbl_exp_artist_side = QLabel("Ready", self.dashboard_container_side)
        self.lbl_exp_artist_side.setFont(get_subtext_font(10.0))
        self.lbl_exp_artist_side.setFixedHeight(16)
        self.lbl_exp_artist_side.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_exp_artist_side.setStyleSheet("color: rgba(255, 255, 255, 0.60); border: none; background: transparent; padding: 0px;")

        info_side.addWidget(self.lbl_exp_title_side)
        info_side.addWidget(self.lbl_exp_artist_side)
        side_layout.addLayout(info_side)

        # Centered Visualizer (140x22)
        self.visualizer_side = AudioVisualizerWidget(num_bars=22, bar_width=2.5, bar_spacing=2.5, parent=self.dashboard_container_side)
        self.visualizer_side.setFixedHeight(22)
        self.visualizer_side.setFixedWidth(140)
        if hasattr(self, "system_service"):
            self.visualizer_side.set_spectrum_provider(self.system_service.get_audio_spectrum)
            self.visualizer_side.set_peak_provider(self.system_service.get_audio_peak)
        side_layout.addWidget(self.visualizer_side, alignment=Qt.AlignmentFlag.AlignCenter)

        # Scrubber + Timestamps
        scrub_side = QVBoxLayout()
        scrub_side.setSpacing(2)
        scrub_side.setContentsMargins(0, 0, 0, 0)

        self.timeline_scrubber_side = TimelineScrubber(self.dashboard_container_side)
        self.timeline_scrubber_side.seek_requested.connect(self._on_seek_requested)
        scrub_side.addWidget(self.timeline_scrubber_side)

        times_side = QHBoxLayout()
        times_side.setContentsMargins(2, 0, 2, 0)
        self.lbl_time_pos_side = QLabel("0:00", self.dashboard_container_side)
        self.lbl_time_pos_side.setFont(get_microlabel_font())
        self.lbl_time_pos_side.setStyleSheet("color: rgba(255, 255, 255, 0.45); border: none; background: transparent;")
        self.lbl_time_dur_side = QLabel("0:00", self.dashboard_container_side)
        self.lbl_time_dur_side.setFont(get_microlabel_font())
        self.lbl_time_dur_side.setStyleSheet("color: rgba(255, 255, 255, 0.45); border: none; background: transparent;")
        times_side.addWidget(self.lbl_time_pos_side)
        times_side.addStretch()
        times_side.addWidget(self.lbl_time_dur_side)
        scrub_side.addLayout(times_side)

        side_layout.addLayout(scrub_side)

        # Controls
        ctrls_side = QHBoxLayout()
        ctrls_side.setSpacing(14)
        ctrls_side.setContentsMargins(0, 2, 0, 0)
        ctrls_side.addStretch()

        self.btn_prev_side = VectorMediaButton(mode="prev", is_primary=False, parent=self.dashboard_container_side)
        self.btn_prev_side.clicked.connect(self.media_service.previous_track)
        self.btn_play_side = VectorMediaButton(mode="play", is_primary=True, parent=self.dashboard_container_side)
        self.btn_play_side.clicked.connect(self.media_service.toggle_play_pause)
        self.btn_next_side = VectorMediaButton(mode="next", is_primary=False, parent=self.dashboard_container_side)
        self.btn_next_side.clicked.connect(self.media_service.next_track)

        ctrls_side.addWidget(self.btn_prev_side)
        ctrls_side.addWidget(self.btn_play_side)
        ctrls_side.addWidget(self.btn_next_side)
        ctrls_side.addStretch()
        side_layout.addLayout(ctrls_side)

        # ── 3. Corner / Square Dashboard (Screen Corners, 280x280) ───────────
        self.dashboard_container_corner = QWidget(self)
        self.dashboard_container_corner.hide()
        self._corner_opacity_effect = QGraphicsOpacityEffect(self.dashboard_container_corner)
        self.dashboard_container_corner.setGraphicsEffect(self._corner_opacity_effect)
        self._corner_opacity_effect.setOpacity(0.0)

        corner_layout = QVBoxLayout(self.dashboard_container_corner)
        corner_layout.setContentsMargins(14, 12, 14, 14)
        corner_layout.setSpacing(10)

        # Top row: 60x60 Art + Track Info
        top_row_c = QHBoxLayout()
        top_row_c.setSpacing(12)
        top_row_c.setContentsMargins(0, 0, 0, 0)

        self.cover_art_corner = CoverArtWidget(size=60, parent=self.dashboard_container_corner)
        top_row_c.addWidget(self.cover_art_corner)

        info_corner = QVBoxLayout()
        info_corner.setSpacing(3)
        info_corner.setContentsMargins(0, 2, 0, 2)

        self.lbl_exp_title_corner = QLabel("No Media Playing", self.dashboard_container_corner)
        self.lbl_exp_title_corner.setFont(get_display_font(11.5))
        self.lbl_exp_title_corner.setFixedHeight(36)
        self.lbl_exp_title_corner.setWordWrap(True)
        self.lbl_exp_title_corner.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_exp_title_corner.setStyleSheet("color: #FFFFFF; font-weight: 600; border: none; background: transparent; padding: 0px;")

        self.lbl_exp_artist_corner = QLabel("Ready", self.dashboard_container_corner)
        self.lbl_exp_artist_corner.setFont(get_subtext_font(10.0))
        self.lbl_exp_artist_corner.setFixedHeight(16)
        self.lbl_exp_artist_corner.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_exp_artist_corner.setStyleSheet("color: rgba(255, 255, 255, 0.60); border: none; background: transparent; padding: 0px;")

        info_corner.addWidget(self.lbl_exp_title_corner)
        info_corner.addWidget(self.lbl_exp_artist_corner)
        top_row_c.addLayout(info_corner, 1)

        corner_layout.addLayout(top_row_c)

        # Middle: Spanning Visualizer (210x24)
        self.visualizer_corner = AudioVisualizerWidget(num_bars=22, bar_width=2.5, bar_spacing=2.5, parent=self.dashboard_container_corner)
        self.visualizer_corner.setFixedHeight(24)
        self.visualizer_corner.setMinimumWidth(180)
        self.visualizer_corner.setMaximumWidth(240)
        if hasattr(self, "system_service"):
            self.visualizer_corner.set_spectrum_provider(self.system_service.get_audio_spectrum)
            self.visualizer_corner.set_peak_provider(self.system_service.get_audio_peak)
        corner_layout.addWidget(self.visualizer_corner, alignment=Qt.AlignmentFlag.AlignCenter)

        # Scrubber
        scrub_corner = QVBoxLayout()
        scrub_corner.setSpacing(2)
        scrub_corner.setContentsMargins(0, 0, 0, 0)

        self.timeline_scrubber_corner = TimelineScrubber(self.dashboard_container_corner)
        self.timeline_scrubber_corner.seek_requested.connect(self._on_seek_requested)
        scrub_corner.addWidget(self.timeline_scrubber_corner)

        times_corner = QHBoxLayout()
        times_corner.setContentsMargins(2, 0, 2, 0)
        self.lbl_time_pos_corner = QLabel("0:00", self.dashboard_container_corner)
        self.lbl_time_pos_corner.setFont(get_microlabel_font())
        self.lbl_time_pos_corner.setStyleSheet("color: rgba(255, 255, 255, 0.45); border: none; background: transparent;")
        self.lbl_time_dur_corner = QLabel("0:00", self.dashboard_container_corner)
        self.lbl_time_dur_corner.setFont(get_microlabel_font())
        self.lbl_time_dur_corner.setStyleSheet("color: rgba(255, 255, 255, 0.45); border: none; background: transparent;")
        times_corner.addWidget(self.lbl_time_pos_corner)
        times_corner.addStretch()
        times_corner.addWidget(self.lbl_time_dur_corner)
        scrub_corner.addLayout(times_corner)

        corner_layout.addLayout(scrub_corner)

        # Controls
        ctrls_corner = QHBoxLayout()
        ctrls_corner.setSpacing(16)
        ctrls_corner.setContentsMargins(0, 2, 0, 0)
        ctrls_corner.addStretch()

        self.btn_prev_corner = VectorMediaButton(mode="prev", is_primary=False, parent=self.dashboard_container_corner)
        self.btn_prev_corner.clicked.connect(self.media_service.previous_track)
        self.btn_play_corner = VectorMediaButton(mode="play", is_primary=True, parent=self.dashboard_container_corner)
        self.btn_play_corner.clicked.connect(self.media_service.toggle_play_pause)
        self.btn_next_corner = VectorMediaButton(mode="next", is_primary=False, parent=self.dashboard_container_corner)
        self.btn_next_corner.clicked.connect(self.media_service.next_track)

        ctrls_corner.addWidget(self.btn_prev_corner)
        ctrls_corner.addWidget(self.btn_play_corner)
        ctrls_corner.addWidget(self.btn_next_corner)
        ctrls_corner.addStretch()
        corner_layout.addLayout(ctrls_corner)

        # Install drag filters on child containers so dragging while expanded is fully responsive
        self._setup_child_drag_filters()

    def _setup_child_drag_filters(self):
        self._drag_filter_widgets = set()
        containers = [
            getattr(self, "dashboard_container", None),
            getattr(self, "dashboard_container_side", None),
            getattr(self, "dashboard_container_corner", None)
        ]
        interactive_types = (VectorMediaButton, TimelineScrubber)
        for c in containers:
            if c is None:
                continue
            self._drag_filter_widgets.add(c)
            c.installEventFilter(self)
            for child in c.findChildren(QWidget):
                if not isinstance(child, interactive_types):
                    self._drag_filter_widgets.add(child)
                    child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if hasattr(self, "_drag_filter_widgets") and watched in self._drag_filter_widgets:
            ev_type = event.type()
            if ev_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.mousePressEvent(event)
                return True
            elif ev_type == QEvent.Type.MouseMove and (event.buttons() & Qt.MouseButton.LeftButton):
                self.mouseMoveEvent(event)
                return True
            elif ev_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self.mouseReleaseEvent(event)
                return True
        return super().eventFilter(watched, event)

    # -------------------------------------------------------------
    # Signal Connections & Auto-Hide on No Music
    # -------------------------------------------------------------
    def _connect_signals(self):
        self.media_service.media_updated.connect(self._on_media_updated)
        self.system_service.time_tick.connect(self._on_time_tick)
        self.system_service.battery_tick.connect(self._on_battery_tick)
        self.system_service.volume_changed.connect(self._on_volume_changed)
        self.system_service.screenshot_taken.connect(self._on_screenshot_taken)
        self.system_service.dnd_changed.connect(self._on_dnd_changed)
        self.system_service.notification_received.connect(self._on_notification_received)
        self.system_service.status_alert.connect(self._on_status_alert)
        if hasattr(self, "device_service") and self.device_service:
            self.device_service.device_connected.connect(self._on_device_connected)

    def _on_battery_tick(self, info: dict):
        self._battery_info = info
        pct = info.get("percent", 99)
        plugged = info.get("is_plugged", False)
        icon = "🗲" if plugged else "🔋"
        if hasattr(self, "lbl_exp_battery") and self.lbl_exp_battery is not None:
            self.lbl_exp_battery.setText(f"{icon} {pct}%")
        self.update()

    def _tick_live_progress(self):
        if not self._media_info.get("has_media", False) or not self._media_info.get("is_playing", False):
            self._last_live_time = time.time()
            return
        if getattr(self, "timeline_scrubber", None) and self.timeline_scrubber._scrubbing:
            return

        now = time.time()
        elapsed = now - getattr(self, "_last_live_time", now)
        self._last_live_time = now

        dur = getattr(self, "_live_dur", 0.0)
        if dur <= 0:
            return

        cur_pos = getattr(self, "_live_pos", 0.0) + elapsed
        cur_pos = min(dur, max(0.0, cur_pos))
        self._live_pos = cur_pos

        prog_ratio = cur_pos / dur if dur > 0 else 0.0
        time_pos_str = format_seconds(int(cur_pos))
        time_dur_str = format_seconds(int(dur))

        for sc in (getattr(self, "timeline_scrubber", None), getattr(self, "timeline_scrubber_side", None), getattr(self, "timeline_scrubber_corner", None)):
            if sc:
                sc.set_progress(prog_ratio)
        for tp in (getattr(self, "lbl_time_pos", None), getattr(self, "lbl_time_pos_side", None), getattr(self, "lbl_time_pos_corner", None)):
            if tp:
                tp.setText(time_pos_str)
        for td in (getattr(self, "lbl_time_dur", None), getattr(self, "lbl_time_dur_side", None), getattr(self, "lbl_time_dur_corner", None)):
            if td:
                td.setText(time_dur_str)

    def _on_seek_requested(self, ratio: float):
        dur = getattr(self, "_live_dur", 210.0) or 210.0
        pos = ratio * dur
        self._live_pos = pos
        self._last_live_time = time.time()
        self.media_service.seek(pos)
        self._media_info["position"] = int(pos)
        pos_str = format_seconds(int(pos))
        for tp in (getattr(self, "lbl_time_pos", None), getattr(self, "lbl_time_pos_side", None), getattr(self, "lbl_time_pos_corner", None)):
            if tp:
                tp.setText(pos_str)

    def _on_media_updated(self, info: dict):
        prev_has_media = self._media_info.get("has_media", False)
        self._media_info = info
        is_playing = info.get("is_playing", False)
        has_media = info.get("has_media", False)
        is_video = info.get("is_video", False)
        title = info.get("title", "")
        artist = info.get("artist", "")
        pos = float(info.get("position", 0.0))
        dur = float(info.get("duration", 210.0) or 210.0)

        self._live_pos = pos
        self._live_dur = dur
        self._last_live_time = time.time()

        # 1. Video mode
        for ca in (getattr(self, "cover_art", None), getattr(self, "cover_art_side", None), getattr(self, "cover_art_corner", None)):
            if ca:
                ca.set_video_mode(is_video)

        # 2. Visualizers
        for vz in (getattr(self, "visualizer", None), getattr(self, "visualizer_side", None), getattr(self, "visualizer_corner", None)):
            if vz:
                if is_video:
                    vz.hide()
                    vz.set_playing(False)
                else:
                    vz.show()
                    vz.set_playing(is_playing)

        # 3. Typography for Horizontal (Original Top Dashboard)
        if hasattr(self, "lbl_exp_title"):
            avail_w = max(220, self.lbl_exp_title.width() if self.lbl_exp_title.width() > 50 else (300 if is_video else 250))
            fm_t = QFontMetrics(self.lbl_exp_title.font())
            self.lbl_exp_title.setText(fm_t.elidedText(title, Qt.TextElideMode.ElideRight, avail_w))
            self.lbl_exp_title.setToolTip(title)

        if hasattr(self, "lbl_exp_artist"):
            avail_a_w = max(220, self.lbl_exp_artist.width() if self.lbl_exp_artist.width() > 50 else (300 if is_video else 250))
            fm_a = QFontMetrics(self.lbl_exp_artist.font())
            self.lbl_exp_artist.setText(fm_a.elidedText(artist, Qt.TextElideMode.ElideRight, avail_a_w))
            self.lbl_exp_artist.setToolTip(artist)

        # Typography for Side (Vertical Centered)
        if hasattr(self, "lbl_exp_title_side"):
            fm_ts = QFontMetrics(self.lbl_exp_title_side.font())
            self.lbl_exp_title_side.setText(fm_ts.elidedText(title, Qt.TextElideMode.ElideRight, 190))
            self.lbl_exp_title_side.setToolTip(title)
        if hasattr(self, "lbl_exp_artist_side"):
            fm_as = QFontMetrics(self.lbl_exp_artist_side.font())
            self.lbl_exp_artist_side.setText(fm_as.elidedText(artist, Qt.TextElideMode.ElideRight, 190))
            self.lbl_exp_artist_side.setToolTip(artist)

        # Typography for Corner (1:1 Square Wrapped)
        if hasattr(self, "lbl_exp_title_corner"):
            self.lbl_exp_title_corner.setText(title)
            self.lbl_exp_title_corner.setToolTip(title)
        if hasattr(self, "lbl_exp_artist_corner"):
            fm_ac = QFontMetrics(self.lbl_exp_artist_corner.font())
            self.lbl_exp_artist_corner.setText(fm_ac.elidedText(artist, Qt.TextElideMode.ElideRight, 160))
            self.lbl_exp_artist_corner.setToolTip(artist)

        # 4. Play / Pause buttons
        btn_mode = "pause" if is_playing else "play"
        for bp in (getattr(self, "btn_play", None), getattr(self, "btn_play_side", None), getattr(self, "btn_play_corner", None)):
            if bp:
                bp.set_mode(btn_mode)

        # 5. Scrubbers & Timestamps
        prog_ratio = float(pos / dur) if dur > 0 else 0.0
        time_pos_str = format_seconds(int(pos))
        time_dur_str = format_seconds(int(dur))
        for sc in (getattr(self, "timeline_scrubber", None), getattr(self, "timeline_scrubber_side", None), getattr(self, "timeline_scrubber_corner", None)):
            if sc:
                sc.set_progress(prog_ratio)
        for tp in (getattr(self, "lbl_time_pos", None), getattr(self, "lbl_time_pos_side", None), getattr(self, "lbl_time_pos_corner", None)):
            if tp:
                tp.setText(time_pos_str)
        for td in (getattr(self, "lbl_time_dur", None), getattr(self, "lbl_time_dur_side", None), getattr(self, "lbl_time_dur_corner", None)):
            if td:
                td.setText(time_dur_str)

        # Update Frosted Glass Album Cover & Accent
        art_path = info.get("album_art_path")
        self._update_album_art(art_path)

        # Dynamic Visibility & Sizing: Completely hide when there is no music or in full screen
        if self._is_fullscreen_suppressed:
            if self.isVisible():
                self.hide()
            return

        music_active = self._is_music_active()
        if music_active:
            self._music_idle_timer.stop()
            if not self.isVisible():
                self.show()
                self.raise_()
            if self._island_state == "compact" and not prev_has_media:
                self._apply_geometry_for_state("compact", animate=True)
        else:
            # Music paused or ended: smoothly hide if in compact mode
            if self._island_state == "compact":
                if self.isVisible() and not self._music_idle_timer.isActive():
                    self._music_idle_timer.start()

        curr_track = f"{title}_{artist}"
        if curr_track != getattr(self, "_last_media_track_id", ""):
            self._last_media_track_id = curr_track
            self._ticker_offset = 0.0
            self._ticker_pause = 90  # 1.5s reading pause when track starts/changes
        self._evaluate_glow_state()
        self.update()

    def _on_time_tick(self, time_str: str, date_str: str):
        self._time_str = time_str
        self._date_str = date_str
        if hasattr(self, "lbl_exp_clock") and self.lbl_exp_clock is not None:
            self.lbl_exp_clock.setText(time_str)
        self.update()

    def _on_volume_changed(self, is_muted: bool, level: float):
        state_name = "Muted" if is_muted else f"Vol {int(level * 100)}%"
        self._flash_message = f"{state_name}"
        self.set_glow_state("notification", duration_sec=2.0)
        self.update()

    def _on_screenshot_requested(self):
        self.system_service.take_screenshot()

    def _on_screenshot_taken(self, filepath: str):
        self._flash_message = "SAVED!"
        self.set_glow_state("success", duration_sec=3.0)
        self.trigger_toast("Screen Capture", "Screenshot Saved!", "Copied to clipboard")
        self.update()

    def _on_dnd_changed(self, is_dnd: bool):
        self._flash_message = "DND: ON" if is_dnd else "DND: OFF"
        self.set_glow_state("reminders", duration_sec=2.0)
        self.update()

    def _on_notification_received(self, notif: dict):
        if not self.system_service.is_dnd:
            if self._island_state == "device_popup":
                return
            self.trigger_toast(
                app=notif.get("app", "Alert"),
                title=notif.get("title", "Incoming Alert"),
                message=notif.get("message", "")
            )

    def _on_status_alert(self, category: str, message: str):
        self._flash_message = message.upper()
        if category == "success":
            self.set_glow_state("success", duration_sec=2.5)
        else:
            self.set_glow_state("notification", duration_sec=2.0)
        self.update()

    def _on_device_connected(self, data: dict):
        """Triggered when an external audio device connects."""
        self.trigger_device_popup(data)

    def trigger_device_popup(self, data: dict):
        """Pops up and expands the Dynamic Island into the Apple device accessory card."""
        if self._is_fullscreen_suppressed:
            return
        self._device_info = data
        self.set_glow_state("notification", duration_sec=4.5)
        if not self.isVisible():
            self.show()
            self.raise_()
        self.set_island_state("device_popup")
        self._device_dismiss_timer.start(4500)

    # -------------------------------------------------------------
    # 60 FPS Render Tick
    # -------------------------------------------------------------
    def _on_render_tick(self):
        if not self.isVisible():
            return

        self._gradient_shift += 0.025

        lerp_factor = 0.14
        r = self._current_glow_c1.red() + (self._target_glow_c1.red() - self._current_glow_c1.red()) * lerp_factor
        g = self._current_glow_c1.green() + (self._target_glow_c1.green() - self._current_glow_c1.green()) * lerp_factor
        b = self._current_glow_c1.blue() + (self._target_glow_c1.blue() - self._current_glow_c1.blue()) * lerp_factor
        self._current_glow_c1 = QColor(int(r), int(g), int(b))

        r2 = self._current_glow_c2.red() + (self._target_glow_c2.red() - self._current_glow_c2.red()) * lerp_factor
        g2 = self._current_glow_c2.green() + (self._target_glow_c2.green() - self._current_glow_c2.green()) * lerp_factor
        b2 = self._current_glow_c2.blue() + (self._target_glow_c2.blue() - self._current_glow_c2.blue()) * lerp_factor
        self._current_glow_c2 = QColor(int(r2), int(g2), int(b2))

        self._current_glow_opacity += (self._target_glow_opacity - self._current_glow_opacity) * lerp_factor

        if self._island_state == "compact" and self._media_info.get("is_playing", False):
            has_real_bands = False
            if hasattr(self, "system_service"):
                try:
                    bands, _ = self.system_service.get_audio_spectrum()
                    max_b_val = max(bands) if bands else 0.0
                    if bands and len(bands) >= 22 and max_b_val > 0.0004:
                        has_real_bands = True
                        # Real hardware multi-band frequency mapping:
                        b0 = max(bands[0:5])    # Sub-bass / Kick
                        b1 = max(bands[5:10])   # Low-mids / Bass
                        b2 = max(bands[10:16])  # High-mids / Vocals
                        b3 = max(bands[16:22])  # Treble / Air

                        max_b = max(b0, b1, b2, b3)
                        if max_b > self._mini_eq_peak:
                            self._mini_eq_peak += (max_b - self._mini_eq_peak) * 0.35
                        else:
                            self._mini_eq_peak += (max_b - self._mini_eq_peak) * 0.02
                        eq_gain = 1.0 / max(0.015, min(1.0, self._mini_eq_peak))

                        targets = [
                            max(0.15, min(1.0, 0.08 + (b0 * eq_gain) * 0.92)),
                            max(0.15, min(1.0, 0.08 + (b1 * eq_gain) * 0.92)),
                            max(0.15, min(1.0, 0.08 + (b2 * eq_gain) * 0.92)),
                            max(0.15, min(1.0, 0.08 + (b3 * eq_gain) * 0.92))
                        ]
                        for idx in range(4):
                            t = targets[idx]
                            lerp_spd = 0.82 if t > self._mini_eq_heights[idx] else 0.22
                            self._mini_eq_heights[idx] += (t - self._mini_eq_heights[idx]) * lerp_spd

                        # 12 vertical spectrum bands for corner and side modes
                        vert_slices = [
                            (0, 2), (2, 3), (3, 5), (5, 7), (7, 9),
                            (9, 11), (11, 13), (13, 15), (15, 17), (17, 19),
                            (19, 21), (21, 22)
                        ]
                        vert_targets = []
                        for s_start, s_end in vert_slices:
                            sub = bands[s_start:s_end]
                            val = max(sub) if sub else 0.0
                            vert_targets.append(max(0.12, min(1.0, 0.08 + (val * eq_gain) * 0.92)))

                        if not hasattr(self, "_vertical_eq_heights") or len(self._vertical_eq_heights) != 12:
                            self._vertical_eq_heights = [0.15] * 12
                        for idx in range(12):
                            ct = vert_targets[idx]
                            c_lerp = 0.85 if ct > self._vertical_eq_heights[idx] else 0.20
                            self._vertical_eq_heights[idx] += (ct - self._vertical_eq_heights[idx]) * c_lerp
                        self._corner_eq_heights = self._vertical_eq_heights
                except Exception:
                    has_real_bands = False

            if not has_real_bands:
                # Organic dynamic fallback when stream volume is low or in quiet passages
                self._mini_eq_phase += 0.12
                self._mini_eq_heights[0] = 0.25 + 0.55 * abs(math.sin(self._mini_eq_phase * 1.1))
                self._mini_eq_heights[1] = 0.30 + 0.60 * abs(math.sin(self._mini_eq_phase * 1.4 + 1.2))
                self._mini_eq_heights[2] = 0.28 + 0.58 * abs(math.cos(self._mini_eq_phase * 1.0 + 2.0))
                self._mini_eq_heights[3] = 0.22 + 0.50 * abs(math.sin(self._mini_eq_phase * 1.6 + 0.5))

                if not hasattr(self, "_vertical_eq_heights") or len(self._vertical_eq_heights) != 12:
                    self._vertical_eq_heights = [0.15] * 12
                for idx in range(12):
                    wave = 0.20 + 0.65 * abs(math.sin(self._mini_eq_phase * (0.75 + idx * 0.12) + idx * 0.55))
                    self._vertical_eq_heights[idx] += (wave - self._vertical_eq_heights[idx]) * 0.25
                self._corner_eq_heights = self._vertical_eq_heights

        # Liquid morphing interpolation (lerp factor 0.18 for viscous fluid morphing)
        lerp_morph = 0.18
        old_morph = self._dock_morph
        self._dock_morph += (self._target_morph - self._dock_morph) * lerp_morph
        if abs(self._dock_morph - old_morph) > 0.001:
            self.update()

        # Smooth live stretching & geometry interpolation during dragging
        if getattr(self, "_is_dragging", False) and hasattr(self, "_target_w"):
            dx = abs(self._target_x - self._live_x)
            dy = abs(self._target_y - self._live_y)
            dw = abs(self._target_w - self._live_w)
            dh = abs(self._target_h - self._live_h)
            if dw > 0.5 or dh > 0.5 or dx > 0.5 or dy > 0.5:
                lerp_p = 0.45
                lerp_s = 0.35
                self._live_x += (self._target_x - self._live_x) * lerp_p
                self._live_y += (self._target_y - self._live_y) * lerp_p
                self._live_w += (self._target_w - self._live_w) * lerp_s
                self._live_h += (self._target_h - self._live_h) * lerp_s
                self.setGeometry(int(self._live_x), int(self._live_y), int(self._live_w), int(self._live_h))
                if getattr(self, "_drag_mode", "compact") == "expanded":
                    self._update_child_visibility("expanded")
                if getattr(self, "_dock_edge", "top") in ("bottom", "bottom-left", "bottom-right"):
                    self._ensure_behind_taskbar()
                self.update()

        # Fluid velocity dampening
        self._liquid_vx *= 0.82
        self._liquid_vy *= 0.82

        # Pulse Phase for Live Call & Device Audio Route Slider
        self._call_pulse += 0.08
        target_route_pos = 1.0 if getattr(self, "_device_route", "device") == "speakers" else 0.0
        self._device_route_pos += (target_route_pos - self._device_route_pos) * 0.22

        # Throttled Download Progress Hairline Checker (~1 Hz)
        now = time.time()
        if now - getattr(self, "_last_dl_check", 0) > 1.2:
            self._last_dl_check = now
            dl_dir = os.path.expanduser("~/Downloads")
            try:
                if os.path.exists(dl_dir):
                    part_files = [
                        os.path.join(dl_dir, f) for f in os.listdir(dl_dir)
                        if f.endswith(".crdownload") or f.endswith(".part")
                    ]
                    # Only actively progressing downloads modified in the last 20 seconds
                    active_parts = [
                        f for f in part_files
                        if (now - os.path.getmtime(f)) < 20.0
                    ]
                    if active_parts:
                        latest = max(active_parts, key=os.path.getmtime)
                        sz = os.path.getsize(latest)
                        self._download_progress = min(0.95, (sz % (10 * 1024 * 1024)) / (10 * 1024 * 1024))
                    elif not getattr(self, "_sim_download_active", False):
                        self._download_progress = 0.0
            except Exception:
                pass

        self.update()

    def _on_ticker_tick(self):
        if not self.isVisible():
            return
        if self._island_state == "compact" and self._media_info.get("has_media", False):
            if getattr(self, "_ticker_pause", 0) > 0:
                self._ticker_pause -= 1
                return
            # Silky 60 FPS float increment
            self._ticker_offset += 0.45
            self.update()

    # -------------------------------------------------------------
    # Mouse Interaction: Liquid Drag-and-Drop & Morphing
    # -------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()

            # 1. Check OTP Copy button (Spec 3.3)
            if self._island_state == "otp_pill" and hasattr(self, "_otp_copy_rect"):
                if self._otp_copy_rect.contains(pos):
                    code = self._otp_info.get("code", "482 910")
                    app_inst = QGuiApplication.instance()
                    if app_inst:
                        app_inst.clipboard().setText(code.replace(" ", ""))
                    self._otp_info["copied"] = True
                    self.update()
                    QTimer.singleShot(1500, self.collapse_to_compact)
                    return

            # 2. Check Live Call Answer / Decline buttons (Spec 3.2)
            if self._island_state == "call_live":
                if hasattr(self, "_call_decline_rect") and self._call_decline_rect.contains(pos):
                    self._call_info["status"] = "Call Declined"
                    self.update()
                    QTimer.singleShot(600, self.collapse_to_compact)
                    return
                elif hasattr(self, "_call_answer_rect") and self._call_answer_rect.contains(pos):
                    self._call_info["status"] = "Connected • 00:01"
                    self.update()
                    QTimer.singleShot(2500, self.collapse_to_compact)
                    return

            # 3. Check File Shelf Clear button (Spec 3.4)
            if self._island_state == "file_shelf" and hasattr(self, "_shelf_clear_rect"):
                if self._shelf_clear_rect.contains(pos):
                    self._shelf_files.clear()
                    self.update()
                    return

            # 4. Check Device Audio Route Toggle (Spec 4.2)
            if self._island_state == "device_popup" and hasattr(self, "_device_route_rect"):
                if self._device_route_rect.contains(pos):
                    cur = getattr(self, "_device_route", "device")
                    self._device_route = "speakers" if cur == "device" else "device"
                    self.update()
                    return

            # 5. Check Device Done / Close
            if self._island_state == "device_popup":
                if hasattr(self, "_device_done_rect") and self._device_done_rect.contains(pos):
                    self.collapse_to_compact()
                    return
                elif hasattr(self, "_device_close_rect") and self._device_close_rect.contains(pos):
                    self.collapse_to_compact()
                    return

            # 6. Check Toast Close
            if self._island_state == "toast" and hasattr(self, "_toast_close_rect"):
                if self._toast_close_rect.contains(pos):
                    self.collapse_to_compact()
                    return

            # 7. Check Corner Scrubber Seeking & Click Bounds
            if self._island_state == "compact":
                edge = getattr(self, "_dock_edge", "top")
                is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
                if is_corner:
                    if hasattr(self, "_corner_scrub_rect") and self._corner_scrub_rect.contains(pos):
                        scrub_x = pos.x() - self._corner_scrub_rect.left()
                        ratio = max(0.0, min(1.0, scrub_x / max(1.0, self._corner_scrub_rect.width())))
                        dur = float(self._media_info.get("duration", 0.0))
                        if dur > 0 and hasattr(self, "scrubber"):
                            self.scrubber.seek_requested.emit(ratio)
                        self.update()
                        return

                    # Ignore clicks outside the hardware notch boundary
                    notch_p = self._create_notch_path(float(self.width()), float(self.height()))
                    if not notch_p.contains(pos):
                        event.ignore()
                        return

            cur_pt = event.globalPosition().toPoint()
            self._drag_start_global = cur_pt
            self._drag_start_pos = self.pos()
            self._drag_start_size = self.size()
            self._drag_grab_offset = self.mapFromGlobal(cur_pt)
            self._drag_last_pos = cur_pt
            self._is_dragging = False
            self._drag_mode = "expanded" if self._island_state == "expanded" else "compact"
            self._live_x = float(self.x())
            self._live_y = float(self.y())
            self._live_w = float(self.width())
            self._live_h = float(self.height())
            self._target_x = self._live_x
            self._target_y = self._live_y
            self._target_w = self._live_w
            self._target_h = self._live_h

            # Stop any hover timers & in-flight animations so they never contest user drag
            self._hover_expand_timer.stop()
            self._hover_collapse_timer.stop()
            if getattr(self, "_geo_animation", None) and self._geo_animation.state() == QPropertyAnimation.State.Running:
                self._geo_animation.stop()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 1. Fluid Drag & Edge Snapping with Hysteresis
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start_global is not None:
            try:
                cur_pt = event.globalPosition().toPoint()
                delta = cur_pt - self._drag_start_global
                dist = delta.manhattanLength()

                if not self._is_dragging and dist >= 4:
                    self._is_dragging = True
                    self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                    self._hover_expand_timer.stop()
                    self._hover_collapse_timer.stop()
                    if getattr(self, "_drag_mode", "compact") == "expanded":
                        self._island_state = "expanded"
                        self._expand_progress_val = 1.0
                        for eff in (getattr(self, "_dashboard_opacity_effect", None),
                                    getattr(self, "_side_opacity_effect", None),
                                    getattr(self, "_corner_opacity_effect", None)):
                            if eff is not None:
                                eff.setOpacity(1.0)
                        self._update_child_visibility("expanded")
                    else:
                        self._island_state = "compact"
                        self._expand_progress_val = 0.0
                        self._update_child_visibility("compact")

                if self._is_dragging:
                    last_pt = getattr(self, "_drag_last_pos", cur_pt)
                    vx = float(cur_pt.x() - last_pt.x())
                    vy = float(cur_pt.y() - last_pt.y())
                    self._liquid_vx = self._liquid_vx * 0.7 + vx * 0.3
                    self._liquid_vy = self._liquid_vy * 0.7 + vy * 0.3
                    self._drag_last_pos = cur_pt

                    screen = QGuiApplication.screenAt(cur_pt) or QGuiApplication.primaryScreen()
                    s_geo = screen.geometry() if screen else QRectF(0, 0, 1920, 1080).toRect()

                    c_x = cur_pt.x()
                    c_y = cur_pt.y()
                    d_top = max(0, c_y - s_geo.top())
                    d_bot = max(0, s_geo.bottom() - c_y)
                    d_left = max(0, c_x - s_geo.left())
                    d_right = max(0, s_geo.right() - c_x)

                    prev_edge = getattr(self, "_dock_edge", "top")

                    # Hysteresis thresholds for live edge & corner snapping
                    is_exp = (getattr(self, "_drag_mode", "compact") == "expanded")
                    c_snap = 140 if is_exp else 120
                    c_hold = 170 if is_exp else 150
                    in_tl = (d_top <= c_hold and d_left <= c_hold) if prev_edge in ("top-left", "corner-tl") else (d_top <= c_snap and d_left <= c_snap)
                    in_tr = (d_top <= c_hold and d_right <= c_hold) if prev_edge in ("top-right", "corner-tr") else (d_top <= c_snap and d_right <= c_snap)
                    in_bl = (d_bot <= c_hold and d_left <= c_hold) if prev_edge in ("bottom-left", "corner-bl") else (d_bot <= c_snap and d_left <= c_snap)
                    in_br = (d_bot <= c_hold and d_right <= c_hold) if prev_edge in ("bottom-right", "corner-br") else (d_bot <= c_snap and d_right <= c_snap)

                    if in_tl:
                        target_edge = "top-left"
                    elif in_tr:
                        target_edge = "top-right"
                    elif in_bl:
                        target_edge = "bottom-left"
                    elif in_br:
                        target_edge = "bottom-right"
                    else:
                        e_snap = 90 if is_exp else 75
                        e_hold = 120 if is_exp else 100

                        min_d = min(d_top, d_bot, d_left, d_right)
                        if min_d == d_top:
                            candidate = "top"
                        elif min_d == d_bot:
                            candidate = "bottom"
                        elif min_d == d_left:
                            candidate = "left"
                        else:
                            candidate = "right"

                        thresh = e_hold if prev_edge == candidate else e_snap
                        if min_d <= thresh:
                            target_edge = candidate
                        else:
                            target_edge = "floating"

                    has_media = self._is_music_active() or self._media_info.get("has_media", False)

                    if target_edge in ("top-left", "top-right", "bottom-left", "bottom-right"):
                        if is_exp:
                            target_w = float(CORNER_EXPANDED_SIZE)
                            target_h = float(CORNER_EXPANDED_SIZE)
                        else:
                            target_w = float(CORNER_COMPACT_MUSIC_W if has_media else CORNER_COMPACT_IDLE_W)
                            target_h = float(CORNER_COMPACT_MUSIC_H if has_media else CORNER_COMPACT_IDLE_H)
                    elif target_edge in ("left", "right"):
                        if is_exp:
                            target_w = float(SIDE_EXPANDED_W)
                            target_h = float(SIDE_EXPANDED_H)
                        else:
                            target_w = float(SIDE_COMPACT_MUSIC_W if has_media else SIDE_COMPACT_IDLE_W)
                            target_h = float(SIDE_COMPACT_MUSIC_H if has_media else SIDE_COMPACT_IDLE_H)
                    else:  # "top", "bottom", "floating"
                        if is_exp:
                            target_w = float(EXPANDED_WIDTH)
                            target_h = float(EXPANDED_HEIGHT)
                        else:
                            target_w = float(COMPACT_MUSIC_WIDTH if has_media else COMPACT_IDLE_WIDTH)
                            target_h = float(COMPACT_HEIGHT)

                    start_w = max(1.0, float(getattr(self, "_drag_start_size", self.size()).width()))
                    start_h = max(1.0, float(getattr(self, "_drag_start_size", self.size()).height()))
                    grab_pt = getattr(self, "_drag_grab_offset", QPoint(int(start_w / 2), int(start_h / 2)))
                    ratio_grab_x = max(0.0, min(1.0, grab_pt.x() / start_w))
                    ratio_grab_y = max(0.0, min(1.0, grab_pt.y() / start_h))

                    if target_edge == "top-left":
                        target_x = float(s_geo.left())
                        target_y = float(s_geo.top())
                    elif target_edge == "top-right":
                        target_x = float(s_geo.right() - target_w + 1)
                        target_y = float(s_geo.top())
                    elif target_edge == "bottom-left":
                        target_x = float(s_geo.left())
                        target_y = float(s_geo.bottom() - target_h + 1)
                    elif target_edge == "bottom-right":
                        target_x = float(s_geo.right() - target_w + 1)
                        target_y = float(s_geo.bottom() - target_h + 1)
                    elif target_edge == "top":
                        target_y = float(s_geo.top())
                        target_x = float(c_x - target_w * ratio_grab_x)
                        target_x = max(float(s_geo.left()), min(float(s_geo.right() - target_w + 1), target_x))
                        self._dock_ratio_x = max(0.08, min(0.92, (target_x + target_w / 2.0 - s_geo.left()) / max(1.0, float(s_geo.width()))))
                    elif target_edge == "bottom":
                        target_y = float(s_geo.bottom() - target_h + 1)
                        target_x = float(c_x - target_w * ratio_grab_x)
                        target_x = max(float(s_geo.left()), min(float(s_geo.right() - target_w + 1), target_x))
                        self._dock_ratio_x = max(0.08, min(0.92, (target_x + target_w / 2.0 - s_geo.left()) / max(1.0, float(s_geo.width()))))
                    elif target_edge == "left":
                        target_x = float(s_geo.left())
                        target_y = float(c_y - target_h * ratio_grab_y)
                        target_y = max(float(s_geo.top()), min(float(s_geo.bottom() - target_h + 1), target_y))
                        self._dock_ratio_y = max(0.08, min(0.92, (target_y + target_h / 2.0 - s_geo.top()) / max(1.0, float(s_geo.height()))))
                    elif target_edge == "right":
                        target_x = float(s_geo.right() - target_w + 1)
                        target_y = float(c_y - target_h * ratio_grab_y)
                        target_y = max(float(s_geo.top()), min(float(s_geo.bottom() - target_h + 1), target_y))
                        self._dock_ratio_y = max(0.08, min(0.92, (target_y + target_h / 2.0 - s_geo.top()) / max(1.0, float(s_geo.height()))))
                    else:  # floating
                        target_x = float(c_x - target_w * ratio_grab_x)
                        target_y = float(c_y - target_h * ratio_grab_y)
                        target_x = max(float(s_geo.left() + 10), min(float(s_geo.right() - target_w - 10), target_x))
                        target_y = max(float(s_geo.top() + 10), min(float(s_geo.bottom() - target_h - 10), target_y))
                        self._floating_center = QPointF(float(target_x + target_w / 2.0), float(target_y + target_h / 2.0))

                    self._target_x = target_x
                    self._target_y = target_y
                    self._target_w = target_w
                    self._target_h = target_h

                    if not hasattr(self, "_live_x"):
                        self._live_x = float(self.x())
                        self._live_y = float(self.y())
                        self._live_w = float(self.width())
                        self._live_h = float(self.height())

                    # Fluid stretching and position tracking
                    lerp_p = 0.55
                    lerp_s = 0.35
                    self._live_x += (self._target_x - self._live_x) * lerp_p
                    self._live_y += (self._target_y - self._live_y) * lerp_p
                    self._live_w += (self._target_w - self._live_w) * lerp_s
                    self._live_h += (self._target_h - self._live_h) * lerp_s

                    self._dock_edge = target_edge
                    self._target_morph = 0.0 if target_edge == "floating" else 1.0

                    self.setGeometry(int(self._live_x), int(self._live_y), int(self._live_w), int(self._live_h))

                    if is_exp:
                        self._update_child_visibility("expanded")
                    if target_edge in ("bottom", "bottom-left", "bottom-right"):
                        self._ensure_behind_taskbar()
                    self.update()
                    return
            except Exception as e:
                import traceback
                log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"\n--- DRAG GLITCH {time.ctime()} ---\n{traceback.format_exc()}\n")
                except Exception:
                    pass

        # 2. Interactive Hovers
        pos = event.position()
        if self._island_state == "otp_pill" and hasattr(self, "_otp_copy_rect"):
            if self._otp_copy_rect.contains(pos):
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                return
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif self._island_state == "toast":
            old_th = getattr(self, "_toast_close_hovered", False)
            if hasattr(self, "_toast_close_rect"):
                self._toast_close_hovered = self._toast_close_rect.contains(pos)
            else:
                self._toast_close_hovered = False
            if old_th != self._toast_close_hovered:
                self.update()
            if self._toast_close_hovered:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                return
            elif not self._is_dragging:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif self._island_state == "call_live":
            if (hasattr(self, "_call_decline_rect") and self._call_decline_rect.contains(pos)) or \
               (hasattr(self, "_call_answer_rect") and self._call_answer_rect.contains(pos)):
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                return
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif self._island_state == "file_shelf" and hasattr(self, "_shelf_clear_rect"):
            old_c = getattr(self, "_shelf_hover_clear", False)
            self._shelf_hover_clear = self._shelf_clear_rect.contains(pos)
            if old_c != self._shelf_hover_clear:
                self.update()
            if self._shelf_hover_clear:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                return
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif self._island_state == "device_popup":
            old_d = getattr(self, "_device_done_hovered", False)
            old_c = getattr(self, "_device_close_hovered", False)
            if hasattr(self, "_device_done_rect"):
                self._device_done_hovered = self._device_done_rect.contains(pos)
            else:
                self._device_done_hovered = False
            if hasattr(self, "_device_close_rect"):
                self._device_close_hovered = self._device_close_rect.contains(pos)
            else:
                self._device_close_hovered = False

            if old_d != self._device_done_hovered or old_c != self._device_close_hovered:
                self.update()
            if self._device_done_hovered or self._device_close_hovered or \
               (hasattr(self, "_device_route_rect") and self._device_route_rect.contains(pos)):
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            elif not self._is_dragging:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif self._island_state == "compact" and not self._is_dragging:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                if self._is_dragging:
                    self._is_dragging = False
                    self._drag_start_global = None
                    self._hovered = self.rect().contains(self.mapFromGlobal(QCursor.pos()))

                    # Settle cleanly into docked position with smooth spring easing
                    mode = getattr(self, "_drag_mode", self._island_state)
                    self._apply_geometry_for_state(mode, animate=True)
                    self._ensure_behind_taskbar()
                    self.save_current_settings()
                    if mode == "compact":
                        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
                    else:
                        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                    self.update()
                    return

                self._drag_start_global = None
                if self._island_state == "device_popup":
                    return
                elif self._island_state in ("compact", "toast"):
                    self.set_island_state("expanded")
            super().mouseReleaseEvent(event)
        except Exception as e:
            import traceback
            log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n--- RELEASE GLITCH {time.ctime()} ---\n{traceback.format_exc()}\n")
            except Exception:
                pass

    # -------------------------------------------------------------
    # Drag and Drop File Shelf Handlers (Spec 3.4)
    # -------------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            if self._island_state != "file_shelf":
                self.set_island_state("file_shelf")
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            files = []
            for url in event.mimeData().urls():
                lp = url.toLocalFile()
                if lp and os.path.exists(lp):
                    name = os.path.basename(lp)
                    size = os.path.getsize(lp)
                    files.append({"name": name, "path": lp, "size": size})
            if files:
                self._shelf_files.extend(files)
            event.acceptProposedAction()
            self.update()
        else:
            super().dropEvent(event)

    # -------------------------------------------------------------
    # Organic Curvy Hardware Notch Path Generator
    # -------------------------------------------------------------
    def _create_notch_path(self, w: float, h: float) -> QPainterPath:
        morph = max(0.0, min(1.0, getattr(self, "_dock_morph", 1.0)))
        edge = getattr(self, "_dock_edge", "top")
        r_cap = min(h / 2.0, 22.0)
        p = self.get_expand_progress()

        if self._island_state == "compact":
            target_r_bot = NOTCH_RADIUS_BOT
            base_r_ear = NOTCH_RADIUS_TOP
        elif self._island_state == "device_popup":
            target_r_bot = 32.0
            base_r_ear = NOTCH_RADIUS_TOP
        elif self._island_state == "osd_hud":
            target_r_bot = OSD_HUD_R_BOT
            base_r_ear = OSD_HUD_R_TOP
        elif self._island_state == "toast":
            target_r_bot = TOAST_R_BOT
            base_r_ear = TOAST_R_TOP
        elif self._island_state == "call_live":
            target_r_bot = CALL_LIVE_R_BOT
            base_r_ear = CALL_LIVE_R_TOP
        elif self._island_state == "otp_pill":
            target_r_bot = OTP_PILL_R_BOT
            base_r_ear = OTP_PILL_R_TOP
        elif self._island_state == "file_shelf":
            target_r_bot = FILE_SHELF_R_BOT
            base_r_ear = FILE_SHELF_R_TOP
        else:
            target_r_bot = EXPANDED_RADIUS
            base_r_ear = NOTCH_RADIUS_TOP

        # Smoothly interpolate corner radius with expand_progress so it never pops
        r_bot = NOTCH_RADIUS_BOT + (target_r_bot - NOTCH_RADIUS_BOT) * p

        path = QPainterPath()

        if edge == "top":
            r_ear = base_r_ear * morph
            cur_r_bot = r_bot
            max_sum_h = max(4.0, h - 2.0)
            if r_ear + cur_r_bot > max_sum_h:
                scale = max_sum_h / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)
            max_sum_w = max(4.0, w / 2.0 - 2.0)
            if r_ear + cur_r_bot > max_sum_w:
                scale = max_sum_w / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)

            if r_ear > 0.5:
                path.moveTo(0, 0)
                path.cubicTo(r_ear * 0.4, 0, r_ear, r_ear * 0.4, r_ear, r_ear)
                path.lineTo(r_ear, h - cur_r_bot)
                path.quadTo(r_ear, h, r_ear + cur_r_bot, h)
                path.lineTo(w - r_ear - cur_r_bot, h)
                path.quadTo(w - r_ear, h, w - r_ear, h - cur_r_bot)
                path.lineTo(w - r_ear, r_ear)
                path.cubicTo(w - r_ear, r_ear * 0.4, w - r_ear * 0.4, 0, w, 0)
                path.lineTo(0, 0)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        elif edge == "bottom":
            r_ear = base_r_ear * morph
            cur_r_bot = r_bot
            max_sum_h = max(4.0, h - 2.0)
            if r_ear + cur_r_bot > max_sum_h:
                scale = max_sum_h / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)
            max_sum_w = max(4.0, w / 2.0 - 2.0)
            if r_ear + cur_r_bot > max_sum_w:
                scale = max_sum_w / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)

            if r_ear > 0.5:
                path.moveTo(0, h)
                path.cubicTo(r_ear * 0.4, h, r_ear, h - r_ear * 0.4, r_ear, h - r_ear)
                path.lineTo(r_ear, cur_r_bot)
                path.quadTo(r_ear, 0, r_ear + cur_r_bot, 0)
                path.lineTo(w - r_ear - cur_r_bot, 0)
                path.quadTo(w - r_ear, 0, w - r_ear, cur_r_bot)
                path.lineTo(w - r_ear, h - r_ear)
                path.cubicTo(w - r_ear, h - r_ear * 0.4, w - r_ear * 0.4, h, w, h)
                path.lineTo(0, h)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        elif edge == "left":
            r_ear = base_r_ear * morph
            cur_r_bot = r_bot
            max_sum_w = max(4.0, w - 2.0)
            if r_ear + cur_r_bot > max_sum_w:
                scale = max_sum_w / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)
            max_sum_h = max(4.0, h / 2.0 - 2.0)
            if r_ear + cur_r_bot > max_sum_h:
                scale = max_sum_h / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)

            if r_ear > 0.5:
                # Organic bezier ears blending with left screen bezel
                path.moveTo(0, 0)
                path.cubicTo(0, r_ear * 0.4, r_ear * 0.4, r_ear, r_ear, r_ear)
                path.lineTo(w - cur_r_bot, r_ear)
                path.quadTo(w, r_ear, w, r_ear + cur_r_bot)
                path.lineTo(w, h - r_ear - cur_r_bot)
                path.quadTo(w, h - r_ear, w - cur_r_bot, h - r_ear)
                path.lineTo(r_ear, h - r_ear)
                path.cubicTo(r_ear * 0.4, h - r_ear, 0, h - r_ear * 0.4, 0, h)
                path.lineTo(0, 0)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        elif edge == "right":
            r_ear = base_r_ear * morph
            cur_r_bot = r_bot
            max_sum_w = max(4.0, w - 2.0)
            if r_ear + cur_r_bot > max_sum_w:
                scale = max_sum_w / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)
            max_sum_h = max(4.0, h / 2.0 - 2.0)
            if r_ear + cur_r_bot > max_sum_h:
                scale = max_sum_h / (r_ear + cur_r_bot)
                r_ear = max(1.0, r_ear * scale)
                cur_r_bot = max(1.0, cur_r_bot * scale)

            if r_ear > 0.5:
                # Organic bezier ears blending with right screen bezel
                path.moveTo(w, 0)
                path.cubicTo(w, r_ear * 0.4, w - r_ear * 0.4, r_ear, w - r_ear, r_ear)
                path.lineTo(cur_r_bot, r_ear)
                path.quadTo(0, r_ear, 0, r_ear + cur_r_bot)
                path.lineTo(0, h - r_ear - cur_r_bot)
                path.quadTo(0, h - r_ear, cur_r_bot, h - r_ear)
                path.lineTo(w - r_ear, h - r_ear)
                path.cubicTo(w - r_ear * 0.4, h - r_ear, w, h - r_ear * 0.4, w, h)
                path.lineTo(w, 0)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        elif edge in ("top-left", "corner-tl"):
            r_ear = base_r_ear * morph
            if r_ear > 0.5:
                p = self.get_expand_progress()
                arm_w = CORNER_ARM_THICKNESS
                arm_h = CORNER_ARM_THICKNESS
                r_in = min(CORNER_INNER_RADIUS, arm_w * 0.45) * (1.0 - p)
                r_b = min(r_bot, 12.0) * (1.0 - p) + r_bot * p

                hx = arm_w + (w - r_ear - r_bot - arm_w) * p
                hy = arm_h + (h - r_ear - r_bot - arm_h) * p

                path.moveTo(0, 0)
                path.lineTo(w, 0)
                path.cubicTo(w - r_ear * 0.4, 0, w - r_ear, r_ear * 0.4, w - r_ear, r_ear)
                if p < 0.98:
                    path.lineTo(w - r_ear, hy - r_b)
                    path.quadTo(w - r_ear, hy, w - r_ear - r_b, hy)
                    path.lineTo(hx + r_in, hy)
                    path.quadTo(hx, hy, hx, hy + r_in)
                    path.lineTo(hx, h - r_ear - r_b)
                    path.quadTo(hx, h - r_ear, hx - r_b, h - r_ear)
                else:
                    path.lineTo(w - r_ear, h - r_ear - r_bot)
                    path.quadTo(w - r_ear, h - r_ear, w - r_ear - r_bot, h - r_ear)
                path.lineTo(r_ear, h - r_ear)
                path.cubicTo(r_ear * 0.4, h - r_ear, 0, h - r_ear * 0.4, 0, h)
                path.lineTo(0, 0)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        elif edge in ("top-right", "corner-tr"):
            r_ear = base_r_ear * morph
            if r_ear > 0.5:
                p = self.get_expand_progress()
                arm_w = CORNER_ARM_THICKNESS
                arm_h = CORNER_ARM_THICKNESS
                r_in = min(CORNER_INNER_RADIUS, arm_w * 0.45) * (1.0 - p)
                r_b = min(r_bot, 12.0) * (1.0 - p) + r_bot * p

                hx = (w - arm_w) * (1.0 - p) + (r_ear + r_bot) * p
                hy = arm_h + (h - r_ear - r_bot - arm_h) * p

                path.moveTo(w, 0)
                path.lineTo(0, 0)
                path.cubicTo(r_ear * 0.4, 0, r_ear, r_ear * 0.4, r_ear, r_ear)
                if p < 0.98:
                    path.lineTo(r_ear, hy - r_b)
                    path.quadTo(r_ear, hy, r_ear + r_b, hy)
                    path.lineTo(hx - r_in, hy)
                    path.quadTo(hx, hy, hx, hy + r_in)
                    path.lineTo(hx, h - r_ear - r_b)
                    path.quadTo(hx, h - r_ear, hx + r_b, h - r_ear)
                else:
                    path.lineTo(r_ear, h - r_ear - r_bot)
                    path.quadTo(r_ear, h - r_ear, r_ear + r_bot, h - r_ear)
                path.lineTo(w - r_ear, h - r_ear)
                path.cubicTo(w - r_ear * 0.4, h - r_ear, w, h - r_ear * 0.4, w, h)
                path.lineTo(w, 0)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        elif edge in ("bottom-left", "corner-bl"):
            r_ear = base_r_ear * morph
            if r_ear > 0.5:
                p = self.get_expand_progress()
                arm_w = CORNER_ARM_THICKNESS
                arm_h = CORNER_ARM_THICKNESS
                r_in = min(CORNER_INNER_RADIUS, arm_w * 0.45) * (1.0 - p)
                r_b = min(r_bot, 12.0) * (1.0 - p) + r_bot * p

                hx = arm_w + (w - r_ear - r_bot - arm_w) * p
                hy = (h - arm_h) * (1.0 - p) + (r_ear + r_bot) * p

                path.moveTo(0, h)
                path.lineTo(w, h)
                path.cubicTo(w - r_ear * 0.4, h, w - r_ear, h - r_ear * 0.4, w - r_ear, h - r_ear)
                if p < 0.98:
                    path.lineTo(w - r_ear, hy + r_b)
                    path.quadTo(w - r_ear, hy, w - r_ear - r_b, hy)
                    path.lineTo(hx + r_in, hy)
                    path.quadTo(hx, hy, hx, hy - r_in)
                    path.lineTo(hx, r_ear + r_b)
                    path.quadTo(hx, r_ear, hx - r_b, r_ear)
                else:
                    path.lineTo(w - r_ear, r_ear + r_bot)
                    path.quadTo(w - r_ear, r_ear, w - r_ear - r_bot, r_ear)
                path.lineTo(r_ear, r_ear)
                path.cubicTo(r_ear * 0.4, r_ear, 0, r_ear * 0.4, 0, 0)
                path.lineTo(0, h)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        elif edge in ("bottom-right", "corner-br"):
            r_ear = base_r_ear * morph
            if r_ear > 0.5:
                p = self.get_expand_progress()
                arm_w = CORNER_ARM_THICKNESS
                arm_h = CORNER_ARM_THICKNESS
                r_in = min(CORNER_INNER_RADIUS, arm_w * 0.45) * (1.0 - p)
                r_b = min(r_bot, 12.0) * (1.0 - p) + r_bot * p

                hx = (w - arm_w) * (1.0 - p) + (r_ear + r_bot) * p
                hy = (h - arm_h) * (1.0 - p) + (r_ear + r_bot) * p

                path.moveTo(w, h)
                path.lineTo(0, h)
                path.cubicTo(r_ear * 0.4, h, r_ear, h - r_ear * 0.4, r_ear, h - r_ear)
                if p < 0.98:
                    path.lineTo(r_ear, hy + r_b)
                    path.quadTo(r_ear, hy, r_ear + r_b, hy)
                    path.lineTo(hx - r_in, hy)
                    path.quadTo(hx, hy, hx, hy - r_in)
                    path.lineTo(hx, r_ear + r_b)
                    path.quadTo(hx, r_ear, hx + r_b, r_ear)
                else:
                    path.lineTo(r_ear, r_ear + r_bot)
                    path.quadTo(r_ear, r_ear, r_ear + r_bot, r_ear)
                path.lineTo(w - r_ear, r_ear)
                path.cubicTo(w - r_ear * 0.4, r_ear, w, r_ear * 0.4, w, 0)
                path.lineTo(w, h)
            else:
                path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        else:  # "floating" pure liquid capsule
            path.addRoundedRect(QRectF(0, 0, w, h), r_cap, r_cap)

        path.closeSubpath()
        return path

    def paintEvent(self, event):
        try:
            self._do_paint(event)
        except Exception:
            try:
                import traceback
                err = traceback.format_exc()
                log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n--- PAINT GLITCH CAUGHT {time.ctime()} ---\n{err}\n")
            except Exception:
                pass
            try:
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.fillRect(0, 0, self.width(), self.height(), QColor(10, 10, 14, 240))
                p.end()
            except Exception:
                pass

    def _do_paint(self, event):
        painter = QPainter(self)
        # Maximum quality rendering hints for smooth text and graphics
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w = float(self.width())
        h = float(self.height())
        has_media = bool(self._media_info.get("has_media", False))

        notch_path = self._create_notch_path(w, h)

        # 1. Soft shadow along bottom and sides
        shadow_steps = 4
        for i in range(1, shadow_steps + 1):
            alpha = int(32 * ((shadow_steps - i + 1) / shadow_steps) ** 1.8)
            painter.setPen(QPen(QColor(0, 0, 0, alpha), i * 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(notch_path)

        # 2. Clip inside notch
        painter.save()
        painter.setClipPath(notch_path)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 3. Canvas Surface Fill (Solid / Gradient / Ambient Base)
        bg_style = getattr(self, "_bg_style", "ambient")
        if bg_style == "solid":
            painter.fillRect(0, 0, int(w), int(h), getattr(self, "_solid_color", QColor("#08080C")))
        elif bg_style == "gradient":
            c_grad = QLinearGradient(0, 0, 0, h)
            c_grad.setColorAt(0.0, getattr(self, "_gradient_c1", QColor(14, 14, 18, 252)))
            c_grad.setColorAt(1.0, getattr(self, "_gradient_c2", QColor(2, 2, 4, 255)))
            painter.fillRect(0, 0, int(w), int(h), c_grad)
        else:  # "ambient" (Deep Liquid Obsidian Glass Base)
            canvas_grad = QLinearGradient(0, 0, 0, h)
            canvas_grad.setColorAt(0.0, QColor(14, 14, 18, 252))
            canvas_grad.setColorAt(0.4, QColor(8, 8, 12, 255))
            canvas_grad.setColorAt(1.0, QColor(2, 2, 4, 255))
            painter.fillRect(0, 0, int(w), int(h), canvas_grad)

        # Ambient diffuse album art atmospheric glow when media is playing
        ambient_on = getattr(self, "_ambient_enabled", True)
        ambient_op = getattr(self, "_ambient_opacity", 0.24)
        if ambient_on and ambient_op > 0 and has_media and self._glass_bg_pixmap and not self._glass_bg_pixmap.isNull() and self._island_state == "expanded":
            painter.save()
            painter.setOpacity(ambient_op)
            painter.drawPixmap(0, 0, int(w), int(h), self._glass_bg_pixmap)
            painter.restore()

        # 4. Subtle Specular Highlight Rim
        edge = getattr(self, "_dock_edge", "top")
        morph = getattr(self, "_dock_morph", 1.0)

        if edge == "top" and morph > 0.15:
            r_top = NOTCH_RADIUS_TOP * morph
            meniscus_grad = QLinearGradient(0, 0, w, 0)
            meniscus_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            meniscus_grad.setColorAt(r_top / w, QColor(255, 255, 255, 25))
            meniscus_grad.setColorAt(0.5, QColor(255, 255, 255, 60 if self._hovered else 35))
            meniscus_grad.setColorAt((w - r_top) / w, QColor(255, 255, 255, 25))
            meniscus_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setPen(QPen(QBrush(meniscus_grad), 1.0))
            painter.drawLine(QPointF(0, 0.75), QPointF(w, 0.75))

        elif edge == "bottom" and morph > 0.15:
            r_top = NOTCH_RADIUS_TOP * morph
            meniscus_grad = QLinearGradient(0, h, w, h)
            meniscus_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            meniscus_grad.setColorAt(r_top / w, QColor(255, 255, 255, 25))
            meniscus_grad.setColorAt(0.5, QColor(255, 255, 255, 60 if self._hovered else 35))
            meniscus_grad.setColorAt((w - r_top) / w, QColor(255, 255, 255, 25))
            meniscus_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setPen(QPen(QBrush(meniscus_grad), 1.0))
            painter.drawLine(QPointF(0, h - 0.75), QPointF(w, h - 0.75))

        # 5. State-Specific Content
        if self._island_state == "toast":
            self._paint_toast_notch(painter, w, h)
        elif self._island_state == "device_popup":
            self._paint_device_popup_notch(painter, w, h)
        elif self._island_state == "osd_hud":
            self._paint_osd_hud(painter, w, h)
        elif self._island_state == "call_live":
            self._paint_call_live(painter, w, h)
        elif self._island_state == "otp_pill":
            self._paint_otp_pill(painter, w, h)
        elif self._island_state == "file_shelf":
            self._paint_file_shelf(painter, w, h)
        else:
            p = self.get_expand_progress()
            compact_alpha = max(0.0, min(1.0, (0.28 - p) / 0.28))
            if compact_alpha > 0.01:
                painter.save()
                painter.setOpacity(compact_alpha)
                self._paint_compact_notch(painter, w, h)
                painter.restore()

        # 6. Subtle Download Progress Hairline (Spec 5.2)
        if getattr(self, "_download_progress", 0.0) > 0.01:
            dl_w = w * self._download_progress
            painter.setPen(QPen(QColor(56, 239, 125, 220), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(0, h - 1.0), QPointF(dl_w, h - 1.0))

        painter.restore()

        # 7. Hardware Bezel Stroke
        bezel_pen = QPen(COLOR_BEZEL, 1.5)
        painter.setPen(bezel_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(notch_path)

        # 8. Subtle Milled Edge Inner Highlight
        highlight_alpha = 24 if self._hovered else 14
        painter.setPen(QPen(QColor(255, 255, 255, highlight_alpha), 1.0))
        painter.drawPath(notch_path)

        # 9. Smart Auto-Hide Peek Tab Handle (Spec 5.3)
        if getattr(self, "_auto_hide_enabled", False) and self._island_state == "compact" and not self._hovered:
            handle_w = 48.0
            handle_rect = QRectF((w - handle_w) / 2.0, h - 3.0, handle_w, 2.5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 60)))
            painter.drawRoundedRect(handle_rect, 1.25, 1.25)

    # -------------------------------------------------------------
    # Reverse L (Corner Bracket ⌈) Dynamic Island UI for Screen Corners
    # -------------------------------------------------------------
    def _paint_compact_corner(self, painter: QPainter, w: float, h: float):
        """
        Reverse L (Corner Bracket ⌈) Dynamic Island UI for Screen Corners.
        Top arm: Media track title, interactive progress scrubber with timestamps.
        Side arm: Animated 5-bar vertical audio spectrum visualizer + stacked digital clock/battery.
        Corner hub: Album art squircle with glass specular rim (or vinyl disc).
        """
        edge = getattr(self, "_dock_edge", "top-left")
        is_right = edge in ("top-right", "corner-tr", "bottom-right", "corner-br")
        is_bottom = edge in ("bottom-left", "corner-bl", "bottom-right", "corner-br")

        has_media = bool(self._media_info.get("has_media", False))
        is_playing = bool(self._media_info.get("is_playing", False))

        arm_w = CORNER_ARM_THICKNESS  # 36.0
        arm_h = CORNER_ARM_THICKNESS  # 36.0

        p = self.get_expand_progress()
        compact_alpha = max(0.0, min(1.0, (0.35 - p) / 0.35))
        if compact_alpha < 0.01:
            return

        hub_x = (w - arm_w) if is_right else 0.0
        hub_y = (h - arm_h) if is_bottom else 0.0

        painter.save()
        painter.setOpacity(compact_alpha)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # ── 1. Corner Hub: Album Art Squircle (26x26) ─────────────
        art_size = 26.0
        art_x = hub_x + (arm_w - art_size) / 2.0
        art_y = hub_y + (arm_h - art_size) / 2.0
        art_rect = QRectF(art_x, art_y, art_size, art_size)
        art_rad = 6.5

        if has_media:
            painter.save()
            art_clip = QPainterPath()
            art_clip.addRoundedRect(art_rect, art_rad, art_rad)
            painter.setClipPath(art_clip)

            if self._album_art_pixmap and not self._album_art_pixmap.isNull():
                painter.drawPixmap(
                    art_rect.toRect(),
                    self._album_art_pixmap.scaled(
                        int(art_size), int(art_size),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
            else:
                # Sleek Vinyl disc fallback
                painter.fillRect(art_rect, QColor(22, 24, 30))
                painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(art_rect.adjusted(2.5, 2.5, -2.5, -2.5))
                painter.drawEllipse(art_rect.adjusted(5.5, 5.5, -5.5, -5.5))
                painter.setBrush(QBrush(QColor(255, 45, 85, 220)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(art_x + art_size / 2.0 - 2.5, art_y + art_size / 2.0 - 2.5, 5.0, 5.0))

            # Glass specular rim over the art
            art_spec = QLinearGradient(art_x, art_y, art_x + art_size, art_y + art_size)
            art_spec.setColorAt(0.0, QColor(255, 255, 255, 45))
            art_spec.setColorAt(0.6, QColor(255, 255, 255, 0))
            painter.setPen(QPen(QBrush(art_spec), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(art_rect, art_rad, art_rad)
            painter.restore()
        else:
            # Idle hub complication: Apple Watch styled music note or minimal ring
            painter.save()
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
            painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
            painter.drawRoundedRect(art_rect, art_rad, art_rad)
            cx, cy = art_rect.center().x(), art_rect.center().y()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
            painter.drawEllipse(QPointF(cx, cy), 3.0, 3.0)
            painter.restore()

        # ── 2. Horizontal Arm: Media Progress & Track Info ─────────
        if not is_right:
            h_start_x = arm_w + 6.0
            h_end_x = w - 18.0
        else:
            h_start_x = 18.0
            h_end_x = w - arm_w - 6.0

        h_arm_w = max(10.0, h_end_x - h_start_x)
        top_y_base = hub_y

        if has_media:
            # Title & Artist
            title = (self._media_info.get("title", "") or "Now Playing").strip()
            artist = (self._media_info.get("artist", "") or "").strip()
            display_title = f"{title} · {artist}" if artist else title

            painter.save()
            painter.setFont(get_subtext_font(8.5))
            painter.setPen(COLOR_TEXT_PRIMARY)
            fm = QFontMetrics(painter.font())
            elided_title = fm.elidedText(display_title, Qt.TextElideMode.ElideRight, int(h_arm_w))
            title_rect = QRectF(h_start_x, top_y_base + 3.0, h_arm_w, 13.0)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

            # Scrubber row: [Elapsed] ────●──── [Duration]
            pos_sec = float(self._media_info.get("position", 0.0))
            dur_sec = float(self._media_info.get("duration", 0.0))
            if dur_sec > 0:
                progress = max(0.0, min(1.0, pos_sec / dur_sec))
                pos_str = f"{int(pos_sec)//60:02d}:{int(pos_sec)%60:02d}"
                dur_str = f"{int(dur_sec)//60:02d}:{int(dur_sec)%60:02d}"
            else:
                progress = max(0.0, min(1.0, float(self._media_info.get("percent", 0.0)) / 100.0))
                pos_str = "00:00"
                dur_str = "--:--"

            time_font = get_microlabel_font()
            painter.setFont(time_font)
            painter.setPen(QColor(255, 255, 255, 150))
            fm_t = QFontMetrics(time_font)
            pos_w = fm_t.horizontalAdvance(pos_str)
            dur_w = fm_t.horizontalAdvance(dur_str)

            scrub_y = top_y_base + 18.0
            painter.drawText(QRectF(h_start_x, scrub_y, pos_w + 2, 12.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, pos_str)
            painter.drawText(QRectF(h_end_x - dur_w, scrub_y, dur_w + 2, 12.0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, dur_str)

            # Scrub Bar Track
            track_x = h_start_x + pos_w + 6.0
            track_w = max(10.0, (h_end_x - dur_w - 6.0) - track_x)
            track_h = 2.5
            bar_center_y = scrub_y + 6.0

            # Hit-test rect for mouse seeking
            self._corner_scrub_rect = QRectF(track_x, scrub_y, track_w, 12.0)

            # Background track
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 45)))
            painter.drawRoundedRect(QRectF(track_x, bar_center_y - track_h / 2.0, track_w, track_h), 1.25, 1.25)

            # Active played track
            played_w = max(2.0, track_w * progress)
            accent_hex = self._media_info.get("accent_color", "#FFFFFF")
            accent_col = QColor(accent_hex) if accent_hex else QColor(255, 255, 255)
            painter.setBrush(QBrush(accent_col))
            painter.drawRoundedRect(QRectF(track_x, bar_center_y - track_h / 2.0, played_w, track_h), 1.25, 1.25)

            # Gleaming thumb cap
            thumb_x = track_x + played_w
            painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
            painter.drawEllipse(QPointF(thumb_x, bar_center_y), 2.5, 2.5)
            painter.restore()

        else:
            # Idle Mode: Horizontal Date & System status
            painter.save()
            painter.setFont(get_subtext_font(8.5))
            painter.setPen(COLOR_TEXT_PRIMARY)
            date_str = getattr(self, "_date_str", "Dynamic Island")
            fm_d = QFontMetrics(painter.font())
            painter.drawText(QRectF(h_start_x, top_y_base + 4.0, h_arm_w, 13.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm_d.elidedText(date_str, Qt.TextElideMode.ElideRight, int(h_arm_w)))

            painter.setFont(get_microlabel_font())
            painter.setPen(QColor(255, 255, 255, 150))
            fm_s = QFontMetrics(painter.font())
            painter.drawText(QRectF(h_start_x, top_y_base + 18.0, h_arm_w, 12.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm_s.elidedText("Ready · Standing By", Qt.TextElideMode.ElideRight, int(h_arm_w)))
            painter.restore()

        # ── 3. Vertical Arm: Audio Spectrum Visualizer + Clock/Battery ─
        v_arm_x = hub_x
        if not is_bottom:
            v_start_y = arm_h + 8.0
            v_end_y = h - 18.0
            clock_y = v_end_y - 28.0
            eq_area_top = v_start_y + 4.0
            eq_area_bottom = clock_y - 8.0
        else:
            v_start_y = 18.0
            v_end_y = h - arm_h - 8.0
            clock_y = v_start_y + 4.0
            eq_area_top = clock_y + 28.0 + 8.0
            eq_area_bottom = v_end_y - 4.0

        v_arm_h = max(10.0, v_end_y - v_start_y)

        # Real-time WASAPI Spectrum EQ - Vertical stack running down side arm
        eq_bars = getattr(self, "_corner_eq_heights", [0.4, 0.6, 0.7, 0.5, 0.3, 0.5, 0.7, 0.6, 0.4, 0.2])
        num_v_bars = len(eq_bars)
        bar_h = 2.5
        bar_gap = 3.2
        total_v_h = num_v_bars * bar_h + (num_v_bars - 1) * bar_gap
        eq_h_avail = max(total_v_h, eq_area_bottom - eq_area_top)
        start_y = eq_area_top + (eq_h_avail - total_v_h) / 2.0
        center_x = v_arm_x + arm_w / 2.0
        min_w = 4.0
        max_w = arm_w - 8.0  # 28.0 px

        accent_hex = self._media_info.get("accent_color", "#FFFFFF")
        accent_col = QColor(accent_hex) if accent_hex else QColor(255, 255, 255)
        # Studio tint blend
        ar = int(255 * 0.75 + accent_col.red() * 0.25)
        ag = int(255 * 0.75 + accent_col.green() * 0.25)
        ab = int(255 * 0.75 + accent_col.blue() * 0.25)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(num_v_bars):
            bar_idx = i if not is_bottom else (num_v_bars - 1 - i)
            lvl = eq_bars[bar_idx] if (has_media and is_playing and bar_idx < len(eq_bars)) else 0.12
            bw = max(min_w, min(max_w, min_w + lvl * (max_w - min_w)))
            bx = center_x - bw / 2.0
            by = start_y + i * (bar_h + bar_gap)

            if is_playing:
                grad = QLinearGradient(bx, by, bx + bw, by)
                a_edge = int(120 + 80 * lvl)
                a_mid = int(180 + 75 * lvl)
                grad.setColorAt(0.0, QColor(ar, ag, ab, a_edge))
                grad.setColorAt(0.5, QColor(255, 255, 255, a_mid))
                grad.setColorAt(1.0, QColor(ar, ag, ab, a_edge))
                painter.setBrush(QBrush(grad))
            else:
                painter.setBrush(QBrush(QColor(255, 255, 255, 45)))

            painter.drawRoundedRect(QRectF(bx, by, bw, bar_h), bar_h / 2.0, bar_h / 2.0)
        painter.restore()

        # Stacked Digital Clock
        hh, mm = self._get_24h_time_parts()

        col_hr, col_min = self._get_time_colors()
        painter.save()
        painter.setFont(get_display_font(11.0))
        painter.setPen(col_hr)
        painter.drawText(QRectF(v_arm_x, clock_y, arm_w, 14.0), Qt.AlignmentFlag.AlignCenter, hh)

        painter.setPen(col_min)
        painter.drawText(QRectF(v_arm_x, clock_y + 13.5, arm_w, 14.0), Qt.AlignmentFlag.AlignCenter, mm)
        painter.restore()

        painter.restore()

    # -------------------------------------------------------------
    # Vertical Dynamic Pill UI for Screen Sides (Left / Right Bezels)
    # -------------------------------------------------------------
    def _paint_compact_side(self, painter: QPainter, w: float, h: float):
        """
        Vertical Dynamic Pill UI for Screen Sides (Left / Right Bezels).
        Top: Album art squircle with glass specular rim.
        Middle: Responsive vertical 12-band audio spectrum ladder.
        Bottom: Crisp stacked digital clock (hh over mm), safely positioned above the bezel ear.
        """
        has_media = bool(self._media_info.get("has_media", False))
        is_playing = bool(self._media_info.get("is_playing", False))

        base_r_ear = NOTCH_RADIUS_TOP  # 18.0
        r_ear = base_r_ear

        if has_media:
            # ── 1. Top: Album Art Squircle (22x22) ───────────────────
            art_size = 22.0
            art_x = (w - art_size) / 2.0
            art_y = r_ear + 4.0  # 22.0 px
            art_rect = QRectF(art_x, art_y, art_size, art_size)
            art_rad = 5.5

            painter.save()
            art_clip = QPainterPath()
            art_clip.addRoundedRect(art_rect, art_rad, art_rad)
            painter.setClipPath(art_clip)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            if self._album_art_pixmap and not self._album_art_pixmap.isNull():
                painter.drawPixmap(
                    art_rect.toRect(),
                    self._album_art_pixmap.scaled(
                        int(art_size), int(art_size),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
            else:
                painter.fillRect(art_rect, QColor(22, 24, 30))
                # Vinyl disc fallback
                painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(art_rect.adjusted(2.0, 2.0, -2.0, -2.0))
                painter.drawEllipse(art_rect.adjusted(4.5, 4.5, -4.5, -4.5))
                painter.setBrush(QBrush(QColor(255, 45, 85, 220)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(art_x + art_size / 2.0 - 2.0, art_y + art_size / 2.0 - 2.0, 4.0, 4.0))

            # Glass specular rim over art
            spec_grad = QLinearGradient(art_x, art_y, art_x + art_size, art_y + art_size)
            spec_grad.setColorAt(0.0, QColor(255, 255, 255, 50))
            spec_grad.setColorAt(0.6, QColor(255, 255, 255, 0))
            painter.setPen(QPen(QBrush(spec_grad), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(art_rect, art_rad, art_rad)
            painter.restore()

            # ── 3. Bottom: Stacked Digital Clock (Safely in straight pill body) ─
            # Bottom ear curve starts at h - r_ear (h - 18.0).
            # Placing clock_y at h - 58.0 ensures hh and mm are in the full-width parallel section.
            clock_y = h - 58.0
            hh, mm = self._get_24h_time_parts()

            col_hr, col_min = self._get_time_colors()
            painter.save()
            painter.setFont(get_display_font(11.5))
            painter.setPen(col_hr)
            painter.drawText(QRectF(0, clock_y, w, 14.0), Qt.AlignmentFlag.AlignCenter, hh)

            painter.setPen(col_min)
            painter.drawText(QRectF(0, clock_y + 14.0, w, 14.0), Qt.AlignmentFlag.AlignCenter, mm)
            painter.restore()

            # ── 2. Middle: Vertical 12-Band Audio Spectrum Visualizer ─
            eq_area_top = art_y + art_size + 12.0    # ~56.0
            eq_area_bottom = clock_y - 12.0          # ~190.0
            avail_h = max(30.0, eq_area_bottom - eq_area_top)

            eq_bars = getattr(self, "_vertical_eq_heights", [0.4, 0.6, 0.7, 0.5, 0.3, 0.6, 0.8, 0.6, 0.5, 0.3, 0.2, 0.15])
            num_v_bars = len(eq_bars)
            bar_h = 3.0
            bar_gap = 4.8
            total_v_h = num_v_bars * bar_h + (num_v_bars - 1) * bar_gap  # ~88.8 px

            start_y = eq_area_top + (avail_h - total_v_h) / 2.0
            center_x = w / 2.0
            min_w = 4.0
            max_w = max(min_w, w - 8.0)  # ~24.0 px for w=32

            accent_hex = self._media_info.get("accent_color", "#FFFFFF")
            accent_col = QColor(accent_hex) if accent_hex else QColor(255, 255, 255)
            ar = int(255 * 0.75 + accent_col.red() * 0.25)
            ag = int(255 * 0.75 + accent_col.green() * 0.25)
            ab = int(255 * 0.75 + accent_col.blue() * 0.25)

            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(num_v_bars):
                lvl = eq_bars[i] if (is_playing and i < len(eq_bars)) else 0.12
                bw = max(min_w, min(max_w, min_w + lvl * (max_w - min_w)))
                bx = center_x - bw / 2.0
                by = start_y + i * (bar_h + bar_gap)

                if is_playing:
                    grad = QLinearGradient(bx, by, bx + bw, by)
                    a_edge = int(120 + 80 * lvl)
                    a_mid = int(180 + 75 * lvl)
                    grad.setColorAt(0.0, QColor(ar, ag, ab, a_edge))
                    grad.setColorAt(0.5, QColor(255, 255, 255, a_mid))
                    grad.setColorAt(1.0, QColor(ar, ag, ab, a_edge))
                    painter.setBrush(QBrush(grad))
                else:
                    painter.setBrush(QBrush(QColor(255, 255, 255, 45)))

                painter.drawRoundedRect(QRectF(bx, by, bw, bar_h), bar_h / 2.0, bar_h / 2.0)
            painter.restore()

        else:
            # ── Idle Mode: Vertical Stacked Clock & Battery Indicator ──
            hh, mm = self._get_24h_time_parts()

            col_hr, col_min = self._get_time_colors()
            painter.save()
            t_font = get_display_font(12.0)
            painter.setFont(t_font)
            painter.setPen(col_hr)
            painter.drawText(QRectF(0, r_ear + 6.0, w, 15.0), Qt.AlignmentFlag.AlignCenter, hh)
            painter.setPen(col_min)
            painter.drawText(QRectF(0, r_ear + 21.0, w, 15.0), Qt.AlignmentFlag.AlignCenter, mm)

            # Minimal ambient dot ladder in center
            center_x = w / 2.0
            mid_y = h / 2.0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
            for d in range(-3, 4):
                painter.drawEllipse(QPointF(center_x, mid_y + d * 8.0), 1.5, 1.5)

            # Battery indicator at bottom (safely above bottom ear)
            pct = self._battery_info.get("percent", 100)
            b_font = get_microlabel_font()
            painter.setFont(b_font)
            dot_col = QColor("#34C759") if pct > 20 else QColor("#FF3B30")
            painter.setPen(dot_col)
            painter.drawText(QRectF(0, h - 38.0, w, 12.0), Qt.AlignmentFlag.AlignCenter, f"{pct}%")
            painter.restore()

    def _paint_compact_notch(self, painter: QPainter, w: float, h: float):
        """
        Renders the compact curvy notch with smooth subpixel text.
        """
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        if is_corner:
            self._paint_compact_corner(painter, w, h)
            return

        if is_side:
            self._paint_compact_side(painter, w, h)
            return

        is_playing = self._media_info.get("is_playing", False)
        morph = getattr(self, "_dock_morph", 1.0)

        if edge in ("top", "bottom"):
            r_top = NOTCH_RADIUS_TOP * morph
            content_left = r_top + 12.0
            content_right = w - r_top - 12.0
        elif edge == "left":
            content_left = 12.0
            content_right = w - 18.0
        elif edge == "right":
            content_left = 18.0
            content_right = w - 12.0
        else:  # floating
            content_left = 14.0
            content_right = w - 14.0

        # ── Left: Time (24-hour) ─────────────────────────────────
        hh, mm = self._get_24h_time_parts()
        col_hr, col_min = self._get_time_colors()

        time_font = get_display_font(11.0)
        painter.setFont(time_font)
        fm_time = QFontMetrics(time_font)
        text_h = fm_time.height()
        y_text = (h - text_h) / 2.0

        hh_w = fm_time.horizontalAdvance(hh)
        painter.setPen(col_hr)
        painter.drawText(QRectF(content_left, y_text, hh_w + 1.0, text_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, hh)

        cur_x = content_left + hh_w
        if mm:
            colon_w = fm_time.horizontalAdvance(":")
            painter.setPen(QColor(255, 255, 255, 140))
            painter.drawText(QRectF(cur_x, y_text, colon_w + 1.0, text_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, ":")
            cur_x += colon_w

            mm_w = fm_time.horizontalAdvance(mm)
            painter.setPen(col_min)
            painter.drawText(QRectF(cur_x, y_text, mm_w + 1.0, text_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, mm)
            cur_x += mm_w

        tw = cur_x - content_left

        has_media = bool(self._media_info.get("has_media", False))
        if not has_media:
            # ── Idle Mode: Minimalist Battery Status ────────
            right_offset = content_right
            pct = self._battery_info.get("percent", 100)
            plugged = self._battery_info.get("is_plugged", False)
            batt_text = f"{pct}% ⚡" if plugged else f"{pct}%"

            batt_font = get_microlabel_font()
            painter.setFont(batt_font)
            painter.setPen(QColor(255, 255, 255, 180))
            fm_b = QFontMetrics(batt_font)
            bw = fm_b.horizontalAdvance(batt_text)
            batt_rect = QRectF(right_offset - bw, (h - fm_b.height()) / 2.0, bw + 2.0, fm_b.height())
            painter.drawText(batt_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, batt_text)
            return

        # ── Album Art Squircle (20×20 for music, 28×16 for video) ───
        is_video = bool(self._media_info.get("is_video", False))
        if is_video:
            art_w = 28.0
            art_h = 16.0
            art_rad = 3.5
        else:
            art_w = 20.0
            art_h = 20.0
            art_rad = 5.0

        art_x = content_left + tw + 10.0
        art_y = (h - art_h) / 2.0
        art_rect = QRectF(art_x, art_y, art_w, art_h)

        painter.save()
        art_path = QPainterPath()
        art_path.addRoundedRect(art_rect, art_rad, art_rad)
        painter.setClipPath(art_path)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._album_art_pixmap and not self._album_art_pixmap.isNull():
            painter.drawPixmap(art_rect.toRect(), self._album_art_pixmap.scaled(
                int(art_w), int(art_h),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            painter.fillRect(art_rect, QColor(25, 27, 36))

        painter.restore()

        painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(art_rect, art_rad, art_rad)

        # ── Mini 4-Bar Equalizer (Far Right in Pure White - ONLY for Music) ────────
        if not is_video:
            eq_w = 16.0
            eq_x = content_right - eq_w
            eq_cy = h / 2.0
            bar_w = 2.0
            bar_gap = 2.0
            for idx in range(4):
                bx = eq_x + idx * (bar_w + bar_gap)
                bh = max(2.5, self._mini_eq_heights[idx] * 12.0) if is_playing else 2.5
                by = eq_cy - bh / 2.0
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 220) if is_playing else QColor(255, 255, 255, 45))
                painter.drawRoundedRect(QRectF(bx, by, bar_w, bh), 1.0, 1.0)
            right_limit = eq_x - 8.0
        else:
            right_limit = content_right

        # ── Center: Track title + artist (smooth scrolling) ──────
        text_x = art_x + art_w + 8.0
        text_avail_w = max(10.0, right_limit - text_x)
        clip_rect = QRectF(text_x, 0.0, text_avail_w, h)

        painter.save()
        painter.setClipRect(clip_rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        title = self._media_info.get("title", "")
        artist = self._media_info.get("artist", "")
        title_text = f"{title}   •   {artist}" if artist else title

        track_font = get_display_font(10)
        painter.setFont(track_font)
        fm_title = QFontMetrics(track_font)
        tw = fm_title.horizontalAdvance(title_text)
        track_h = fm_title.height()

        # Vertically centered row for track text
        text_top = (h - track_h) / 2.0

        if tw > text_avail_w:
            scroll_cycle = tw + 48.0
            if self._ticker_offset >= scroll_cycle:
                self._ticker_offset = 0.0
                self._ticker_pause = 60  # 1.0s pause when loop restarts

            x1 = text_x - self._ticker_offset
            x2 = x1 + scroll_cycle
            painter.setPen(COLOR_TEXT_PRIMARY)
            r1 = QRectF(x1, text_top, tw + 4.0, track_h)
            r2 = QRectF(x2, text_top, tw + 4.0, track_h)
            painter.drawText(r1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title_text)
            painter.drawText(r2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title_text)
        else:
            painter.setPen(COLOR_TEXT_PRIMARY)
            r = QRectF(text_x, text_top, text_avail_w, track_h)
            painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title_text)

        painter.restore()

        # ── Subtle Edge Fading Masks (Smooth feather on borders, no harsh letter slicing) ──
        if tw > text_avail_w:
            fade_w = 9.0
            bg_fade_col = getattr(self, "_solid_color", QColor(10, 10, 14)) if getattr(self, "_bg_style", "ambient") == "solid" else QColor(10, 10, 14)
            # Left edge fade-in
            l_grad = QLinearGradient(text_x, 0, text_x + fade_w, 0)
            l_grad.setColorAt(0.0, QColor(bg_fade_col.red(), bg_fade_col.green(), bg_fade_col.blue(), 255))
            l_grad.setColorAt(1.0, QColor(bg_fade_col.red(), bg_fade_col.green(), bg_fade_col.blue(), 0))
            painter.fillRect(QRectF(text_x, 0.0, fade_w, h), l_grad)

            # Right edge fade-out
            r_grad = QLinearGradient(right_limit - fade_w, 0, right_limit, 0)
            r_grad.setColorAt(0.0, QColor(bg_fade_col.red(), bg_fade_col.green(), bg_fade_col.blue(), 0))
            r_grad.setColorAt(1.0, QColor(bg_fade_col.red(), bg_fade_col.green(), bg_fade_col.blue(), 255))
            painter.fillRect(QRectF(right_limit - fade_w, 0.0, fade_w, h), r_grad)

    def _paint_toast_icon(self, painter: QPainter, icon_type: str, cx: float, cy: float, accent_col: QColor, tile_grad_bot: QColor):
        """Draws clean, solid, optically balanced Apple-grade iconography for notification tiles."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        icon_fill = QColor(255, 255, 255, 245)

        if icon_type == "camera":
            # 1. Solid camera body
            body_path = QPainterPath()
            body_path.addRoundedRect(QRectF(cx - 9.0, cy - 4.5, 18.0, 12.0), 2.8, 2.8)
            # Top viewfinder prism
            prism_path = QPainterPath()
            prism_path.addRoundedRect(QRectF(cx - 3.8, cy - 7.4, 7.6, 3.2), 1.2, 1.2)
            combined_cam = body_path.united(prism_path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(icon_fill))
            painter.drawPath(combined_cam)

            # 2. Cutout aperture lens hole
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(tile_grad_bot))
            painter.drawEllipse(QPointF(cx, cy + 1.5), 3.8, 3.8)

            # 3. Concentric glass reflex aperture ring in accent color
            painter.setPen(QPen(accent_col, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy + 1.5), 2.2, 2.2)

            # 4. Tiny top-right flash / sensor dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(tile_grad_bot))
            painter.drawEllipse(QPointF(cx + 4.8, cy - 1.8), 1.0, 1.0)

        elif icon_type == "chat":
            # 1. Solid speech bubble body
            path = QPainterPath()
            path.addRoundedRect(QRectF(cx - 9.5, cy - 7.0, 19.0, 13.0), 3.6, 3.6)
            tail = QPainterPath()
            tail.moveTo(cx - 5.0, cy + 5.5)
            tail.lineTo(cx - 8.5, cy + 9.5)
            tail.lineTo(cx - 2.0, cy + 5.5)
            tail.closeSubpath()
            combined_chat = path.united(tail)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(icon_fill))
            painter.drawPath(combined_chat)

            # 2. Message dots cutout inside
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(tile_grad_bot))
            for dx in (-3.8, 0.0, 3.8):
                painter.drawEllipse(QPointF(cx + dx, cy - 0.5), 1.3, 1.3)

        elif icon_type == "mail":
            # 1. Solid envelope body
            env_rect = QRectF(cx - 9.0, cy - 5.5, 18.0, 12.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(icon_fill))
            painter.drawRoundedRect(env_rect, 2.2, 2.2)

            # 2. Envelope flap crease line
            flap = QPainterPath()
            flap.moveTo(cx - 8.5, cy - 4.5)
            flap.lineTo(cx, cy + 1.2)
            flap.lineTo(cx + 8.5, cy - 4.5)
            painter.setPen(QPen(tile_grad_bot, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(flap)

        elif icon_type == "calendar":
            # 1. Calendar card body
            cal_rect = QRectF(cx - 8.5, cy - 5.5, 17.0, 13.5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(icon_fill))
            painter.drawRoundedRect(cal_rect, 2.5, 2.5)

            # 2. Top header ribbon
            ribbon_path = QPainterPath()
            ribbon_path.addRoundedRect(QRectF(cx - 8.5, cy - 5.5, 17.0, 4.5), 2.5, 2.5)
            painter.setBrush(QBrush(accent_col))
            painter.drawPath(ribbon_path)

            # 3. Top binder loops
            painter.setPen(QPen(icon_fill, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx - 4.0, cy - 7.8), QPointF(cx - 4.0, cy - 4.5))
            painter.drawLine(QPointF(cx + 4.0, cy - 7.8), QPointF(cx + 4.0, cy - 4.5))

            # 4. Subtle date grid dots
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(tile_grad_bot))
            for row in (1.5, 4.5):
                for col in (-4.0, 0.0, 4.0):
                    painter.drawEllipse(QPointF(cx + col, cy + row), 1.0, 1.0)

        elif icon_type == "music":
            # Beamed double eighth notes
            p = QPainterPath()
            p.addEllipse(QPointF(cx - 4.0, cy + 3.5), 2.6, 2.0)
            p.addEllipse(QPointF(cx + 3.5, cy + 1.5), 2.6, 2.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(icon_fill))
            painter.drawPath(p)

            # Stems & beam
            painter.setPen(QPen(icon_fill, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx - 2.0, cy + 3.5), QPointF(cx - 2.0, cy - 5.5))
            painter.drawLine(QPointF(cx + 5.5, cy + 1.5), QPointF(cx + 5.5, cy - 7.5))
            painter.setPen(QPen(icon_fill, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx - 2.0, cy - 5.5), QPointF(cx + 5.5, cy - 7.5))

        else:  # Bell (default / system)
            bell = QPainterPath()
            bell.addEllipse(QPointF(cx, cy - 7.2), 1.5, 1.5)
            bell.moveTo(cx - 3.2, cy - 5.0)
            bell.quadTo(cx - 4.0, cy + 0.5, cx - 7.5, cy + 4.2)
            bell.lineTo(cx + 7.5, cy + 4.2)
            bell.quadTo(cx + 4.0, cy + 0.5, cx + 3.2, cy - 5.0)
            bell.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(icon_fill))
            painter.drawPath(bell)

            painter.drawEllipse(QPointF(cx, cy + 5.8), 1.6, 1.6)

        painter.restore()

    # -------------------------------------------------------------
    # 1:1 Square & Vertical Notification Toast Handlers
    # -------------------------------------------------------------
    def _paint_toast_corner(self, painter: QPainter, w: float, h: float):
        """1:1 Square Notification Toast for Corners ("Edges")."""
        raw_app = (self._toast_info.get("app") or "Notification").strip()
        if raw_app.lower().endswith(".exe"):
            raw_app = raw_app[:-4]
        app_name = "WindowLand" if raw_app.lower() in ("dynamicisland", "main", "windowland") else raw_app.title()
        title = self._toast_info.get("title") or "Notification"
        message = (self._toast_info.get("message") or "").strip()

        # Dynamic icon
        app_lower = raw_app.lower()
        if any(k in app_lower for k in ("snip", "screen", "capture", "screenshot", "camera")):
            icon_type = "camera"
            accent_col = QColor("#00F2FE")
        elif any(k in app_lower for k in ("message", "chat", "teams", "whatsapp", "slack")):
            icon_type = "chat"
            accent_col = QColor("#29B6F6")
        elif any(k in app_lower for k in ("mail", "gmail", "outlook")):
            icon_type = "mail"
            accent_col = QColor("#5B86E5")
        elif any(k in app_lower for k in ("calendar", "meeting", "clock")):
            icon_type = "calendar"
            accent_col = QColor("#FFA726")
        else:
            icon_type = "bell"
            accent_col = QColor("#00D2FF")

        # 1. Top row: Icon Badge + App Name + Close Cross
        badge_size = 32.0
        badge_x = 18.0
        badge_y = 18.0
        tile_grad_bot = QColor(10, 18, 30, 250)
        self._paint_toast_icon(painter, icon_type, badge_x + badge_size / 2.0, badge_y + badge_size / 2.0, accent_col, tile_grad_bot)

        # App name
        painter.setFont(get_subtext_font(10.0))
        painter.setPen(accent_col)
        painter.drawText(QRectF(badge_x + badge_size + 8.0, badge_y + 8.0, w - badge_x - badge_size - 40.0, 16.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, app_name)

        # Dismiss button (close cross)
        cx_x = w - 24.0
        cx_y = 22.0
        self._toast_close_rect = QRectF(cx_x - 10.0, cx_y - 10.0, 20.0, 20.0)
        painter.save()
        close_pen = QPen(QColor(255, 255, 255, 240 if getattr(self, "_toast_close_hovered", False) else 130), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(close_pen)
        painter.drawLine(QPointF(cx_x - 4.0, cx_y - 4.0), QPointF(cx_x + 4.0, cx_y + 4.0))
        painter.drawLine(QPointF(cx_x + 4.0, cx_y - 4.0), QPointF(cx_x - 4.0, cx_y + 4.0))
        painter.restore()

        # 2. Middle: Title & Message
        title_font = get_display_font(11.5)
        painter.setFont(title_font)
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(18.0, 60.0, w - 36.0, 38.0), Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, title)

        if message:
            msg_font = get_subtext_font(10.0)
            painter.setFont(msg_font)
            painter.setPen(COLOR_TEXT_SECONDARY)
            painter.drawText(QRectF(18.0, 104.0, w - 36.0, 72.0), Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, message)

        # 3. Bottom: "now" badge
        painter.setFont(get_microlabel_font())
        painter.setPen(COLOR_TEXT_MUTED)
        painter.drawText(QRectF(18.0, h - 26.0, w - 36.0, 14.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "now • tap to dismiss")

    def _paint_toast_side(self, painter: QPainter, w: float, h: float):
        """Vertical Notification Toast for Left / Right Bezels."""
        raw_app = (self._toast_info.get("app") or "Notification").strip()
        if raw_app.lower().endswith(".exe"):
            raw_app = raw_app[:-4]
        app_name = "WindowLand" if raw_app.lower() in ("dynamicisland", "main", "windowland") else raw_app.title()
        title = self._toast_info.get("title") or "Notification"
        message = (self._toast_info.get("message") or "").strip()

        # Category icon
        app_lower = raw_app.lower()
        if any(k in app_lower for k in ("snip", "screen", "capture", "screenshot", "camera")):
            icon_type = "camera"
            accent_col = QColor("#00F2FE")
        elif any(k in app_lower for k in ("message", "chat", "teams", "whatsapp", "slack")):
            icon_type = "chat"
            accent_col = QColor("#29B6F6")
        elif any(k in app_lower for k in ("mail", "gmail", "outlook")):
            icon_type = "mail"
            accent_col = QColor("#5B86E5")
        elif any(k in app_lower for k in ("calendar", "meeting", "clock")):
            icon_type = "calendar"
            accent_col = QColor("#FFA726")
        else:
            icon_type = "bell"
            accent_col = QColor("#00D2FF")

        # 1. Top: Centered Icon Badge + Dismiss Cross
        badge_size = 36.0
        badge_x = (w - badge_size) / 2.0
        badge_y = 20.0
        tile_grad_bot = QColor(10, 18, 30, 250)
        self._paint_toast_icon(painter, icon_type, badge_x + badge_size / 2.0, badge_y + badge_size / 2.0, accent_col, tile_grad_bot)

        # Close button (away from bezel)
        edge = getattr(self, "_dock_edge", "left")
        cx_x = 18.0 if edge == "right" else (w - 18.0)
        cx_y = 18.0
        self._toast_close_rect = QRectF(cx_x - 10.0, cx_y - 10.0, 20.0, 20.0)
        painter.save()
        close_pen = QPen(QColor(255, 255, 255, 240 if getattr(self, "_toast_close_hovered", False) else 130), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(close_pen)
        painter.drawLine(QPointF(cx_x - 4.0, cx_y - 4.0), QPointF(cx_x + 4.0, cx_y + 4.0))
        painter.drawLine(QPointF(cx_x + 4.0, cx_y - 4.0), QPointF(cx_x - 4.0, cx_y + 4.0))
        painter.restore()

        # App name
        painter.setFont(get_subtext_font(10.0))
        painter.setPen(accent_col)
        painter.drawText(QRectF(10.0, 62.0, w - 20.0, 16.0), Qt.AlignmentFlag.AlignCenter, app_name)

        # Title
        painter.setFont(get_display_font(11.0))
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(14.0, 84.0, w - 28.0, 48.0), Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, title)

        # Message
        if message:
            painter.setFont(get_subtext_font(9.5))
            painter.setPen(COLOR_TEXT_SECONDARY)
            painter.drawText(QRectF(12.0, 138.0, w - 24.0, 80.0), Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, message)

        # Bottom: "now"
        painter.setFont(get_microlabel_font())
        painter.setPen(COLOR_TEXT_MUTED)
        painter.drawText(QRectF(0, h - 22.0, w, 14.0), Qt.AlignmentFlag.AlignCenter, "now")

    def _paint_toast_notch(self, painter: QPainter, w: float, h: float):
        """
        Apple-grade notification toast with frosted glass squircle badge,
        crisp vector iconography, proper typography hierarchy, and interactive dismiss button.
        """
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        if is_corner:
            self._paint_toast_corner(painter, w, h)
            return

        if is_side:
            self._paint_toast_side(painter, w, h)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        r_top = TOAST_R_TOP
        raw_app = (self._toast_info.get("app") or "Notification").strip()
        if raw_app.lower().endswith(".exe"):
            raw_app = raw_app[:-4]
        if raw_app.lower() in ("dynamicisland", "main", "windowland"):
            app_name = "WindowLand"
        else:
            app_name = raw_app.title() if raw_app.isupper() else raw_app
        title = self._toast_info.get("title") or "Incoming Alert"
        message = (self._toast_info.get("message") or "").strip()

        # Dynamic category iconography & palette
        app_lower = raw_app.lower()
        if any(k in app_lower for k in ("snip", "screen", "capture", "screenshot", "camera", "photo")):
            icon_type = "camera"
            accent_col = QColor("#00F2FE")     # Apple Mint Cyan
            tile_grad_top = QColor(14, 42, 58, 235)
            tile_grad_bot = QColor(8, 24, 34, 250)
            tile_border = QColor(0, 242, 254, 75)
        elif any(k in app_lower for k in ("message", "chat", "slack", "teams", "whatsapp", "telegram", "discord", "sms")):
            icon_type = "chat"
            accent_col = QColor("#29B6F6")     # iMessage Blue
            tile_grad_top = QColor(14, 38, 70, 235)
            tile_grad_bot = QColor(8, 22, 44, 250)
            tile_border = QColor(41, 182, 246, 75)
        elif any(k in app_lower for k in ("mail", "outlook", "gmail", "thunderbird", "email")):
            icon_type = "mail"
            accent_col = QColor("#5B86E5")     # Apple Mail Blue
            tile_grad_top = QColor(20, 34, 72, 235)
            tile_grad_bot = QColor(10, 20, 46, 250)
            tile_border = QColor(91, 134, 229, 75)
        elif any(k in app_lower for k in ("calendar", "meeting", "reminder", "alarm", "clock", "schedule")):
            icon_type = "calendar"
            accent_col = QColor("#FFA726")     # Warm Amber
            tile_grad_top = QColor(50, 32, 14, 235)
            tile_grad_bot = QColor(30, 18, 8, 250)
            tile_border = QColor(255, 167, 38, 75)
        elif any(k in app_lower for k in ("music", "spotify", "apple music", "ytmusic", "audio", "sound")):
            icon_type = "music"
            accent_col = QColor("#1DB954")     # Spotify Green
            tile_grad_top = QColor(12, 42, 26, 235)
            tile_grad_bot = QColor(6, 26, 16, 250)
            tile_border = QColor(29, 185, 84, 75)
        else:
            icon_type = "bell"
            accent_col = QColor("#00D2FF")     # Ice Cyan
            tile_grad_top = QColor(18, 30, 48, 235)
            tile_grad_bot = QColor(10, 18, 30, 250)
            tile_border = QColor(0, 210, 255, 75)

        # ── 1. Liquid Aurora Plasma Underglow & Top Meniscus ────────
        badge_size = 46.0
        badge_x = r_top + 14.0
        badge_y = (h - badge_size) / 2.0

        aurora = QRadialGradient(QPointF(badge_x + badge_size * 0.7, h * 0.5), w * 0.45)
        aurora.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 26))
        aurora.setColorAt(0.55, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 6))
        aurora.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aurora))
        painter.drawRect(QRectF(0, 0, w, h))

        # Diagonal liquid glass sheen across the whole toast
        sheen = QLinearGradient(0, 0, w * 0.6, h)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 18))
        sheen.setColorAt(0.4, QColor(255, 255, 255, 6))
        sheen.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(0, 0, w, h), sheen)

        # Top Specular Meniscus Line across curved notch ears
        meniscus = QLinearGradient(0, 0, w, 0)
        meniscus.setColorAt(0.0, QColor(255, 255, 255, 0))
        meniscus.setColorAt(r_top / w, QColor(255, 255, 255, 45))
        meniscus.setColorAt(0.5, QColor(255, 255, 255, 95))
        meniscus.setColorAt((w - r_top) / w, QColor(255, 255, 255, 45))
        meniscus.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(meniscus), 1.0))
        painter.drawLine(QPointF(0, 0.75), QPointF(w, 0.75))

        # ── 2. Apple App Tile / Icon Badge ──────────────────────────
        badge_rect = QRectF(badge_x, badge_y, badge_size, badge_size)

        # Ambient soft aura behind badge
        badge_glow = QRadialGradient(QPointF(badge_x + badge_size * 0.5, badge_y + badge_size * 0.5), badge_size * 0.8)
        glow_c = QColor(accent_col)
        glow_c.setAlpha(42)
        badge_glow.setColorAt(0.0, glow_c)
        badge_glow.setColorAt(0.55, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 10))
        badge_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(badge_glow))
        painter.drawEllipse(QRectF(badge_x - 8.0, badge_y - 8.0, badge_size + 16.0, badge_size + 16.0))

        # Rich Apple App Tile Gradient
        tile_grad = QLinearGradient(badge_x, badge_y, badge_x, badge_y + badge_size)
        tile_grad.setColorAt(0.0, tile_grad_top)
        tile_grad.setColorAt(1.0, tile_grad_bot)
        painter.setPen(QPen(tile_border, 1.0))
        painter.setBrush(QBrush(tile_grad))
        painter.drawRoundedRect(badge_rect, 13.0, 13.0)

        # Top Specular Sheen on App Tile
        tile_sheen = QLinearGradient(badge_x, badge_y, badge_x, badge_y + 20.0)
        tile_sheen.setColorAt(0.0, QColor(255, 255, 255, 55))
        tile_sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(tile_sheen))
        painter.drawRoundedRect(QRectF(badge_x + 1.0, badge_y + 1.0, badge_size - 2.0, 18.0), 12.0, 12.0)

        # Solid Apple SF-Style Vector Icon
        self._paint_toast_icon(painter, icon_type, badge_x + badge_size / 2.0, badge_y + badge_size / 2.0, accent_col, tile_grad_bot)

        # ── 3. Information Column ───────────────────────────────────
        text_x = badge_x + badge_size + 14.0
        close_size = 24.0
        close_x = w - r_top - 26.0
        close_y = (h - close_size) / 2.0
        text_w = max(40.0, close_x - text_x - 14.0)

        if message:
            row1_y = badge_y + 1.5
            row2_y = badge_y + 17.5
            row3_y = badge_y + 37.0

            # Row 1: Category indicator dot + App Name + subtle timestamp
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent_col))
            painter.drawEllipse(QRectF(text_x, row1_y + 4.5, 5.0, 5.0))

            label_font = get_microlabel_font()
            painter.setFont(label_font)
            fm_label = painter.fontMetrics()
            app_w = fm_label.horizontalAdvance(app_name)
            app_x = text_x + 9.5
            painter.setPen(QColor(255, 255, 255, 185))
            painter.drawText(QRectF(app_x, row1_y, app_w, 14.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, app_name)

            painter.setPen(QColor(255, 255, 255, 115))
            painter.drawText(QRectF(app_x + app_w + 5.0, row1_y, text_w - (app_x + app_w + 5.0 - text_x), 14.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "• now")

            # Row 2: Title (The Hero: Bold pure white)
            title_font = get_display_font(11.5)
            title_font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(title_font)
            painter.setPen(QColor(255, 255, 255, 255))
            fm_title = painter.fontMetrics()
            elided_title = fm_title.elidedText(title, Qt.TextElideMode.ElideRight, int(text_w))
            painter.drawText(QRectF(text_x, row2_y, text_w, 18.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_title)

            # Row 3: Message Body (Platinum slate — crisp contrast)
            body_font = get_subtext_font(10)
            painter.setFont(body_font)
            painter.setPen(QColor(203, 213, 225, 225))
            fm_body = painter.fontMetrics()
            elided_body = fm_body.elidedText(message, Qt.TextElideMode.ElideRight, int(text_w))
            painter.drawText(QRectF(text_x, row3_y, text_w, 16.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_body)
        else:
            # Vertically centered 2-row layout when no subtitle
            row1_y = badge_y + 7.0
            row2_y = badge_y + 24.0

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent_col))
            painter.drawEllipse(QRectF(text_x, row1_y + 4.5, 5.0, 5.0))

            label_font = get_microlabel_font()
            painter.setFont(label_font)
            fm_label = painter.fontMetrics()
            app_w = fm_label.horizontalAdvance(app_name)
            app_x = text_x + 9.5
            painter.setPen(QColor(255, 255, 255, 185))
            painter.drawText(QRectF(app_x, row1_y, app_w, 14.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, app_name)

            painter.setPen(QColor(255, 255, 255, 115))
            painter.drawText(QRectF(app_x + app_w + 5.0, row1_y, text_w - (app_x + app_w + 5.0 - text_x), 14.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "• now")

            title_font = get_display_font(11.5)
            title_font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(title_font)
            painter.setPen(QColor(255, 255, 255, 255))
            fm_title = painter.fontMetrics()
            elided_title = fm_title.elidedText(title, Qt.TextElideMode.ElideRight, int(text_w))
            painter.drawText(QRectF(text_x, row2_y, text_w, 18.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_title)

        # ── 4. Dismiss Button '✕' (No background, pure sleek vector cross) ───
        close_rect = QRectF(close_x, close_y, close_size, close_size)
        self._toast_close_rect = close_rect

        is_close_hov = getattr(self, "_toast_close_hovered", False)

        # Sleek fine vector cross (clean float, zero background circle)
        cross_path = QPainterPath()
        arm = 4.2
        ccx = close_x + close_size / 2.0
        ccy = close_y + close_size / 2.0
        cross_path.moveTo(ccx - arm, ccy - arm)
        cross_path.lineTo(ccx + arm, ccy + arm)
        cross_path.moveTo(ccx + arm, ccy - arm)
        cross_path.lineTo(ccx - arm, ccy + arm)

        cross_alpha = 255 if is_close_hov else 140
        cross_width = 1.8 if is_close_hov else 1.4
        painter.setPen(QPen(QColor(255, 255, 255, cross_alpha), cross_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(cross_path)

    def _paint_device_popup_corner(self, painter: QPainter, w: float, h: float):
        """1:1 Square Dynamic Accessory Modal for Screen Corners (280x280)."""
        cat = self._device_info.get("category", "airpods")
        title = self._device_info.get("display_title") or self._device_info.get("name") or "Audio Device"
        subtitle = self._device_info.get("display_subtitle") or "Connected • Audio Ready"
        dev_batt = self._device_info.get("battery", 86)

        accent_col = QColor("#38EF7D") if cat == "airpods" else (QColor("#56CCF2") if cat == "headphones" else QColor("#00D2FF"))

        # Canvas gradient
        canvas_grad = QLinearGradient(0, 0, 0, h)
        canvas_grad.setColorAt(0.0, QColor(22, 24, 34, 252))
        canvas_grad.setColorAt(1.0, QColor(8, 9, 14, 255))
        painter.fillRect(QRectF(0, 0, w, h), canvas_grad)

        # Aurora glow behind device
        aurora = QRadialGradient(QPointF(w * 0.5, h * 0.42), w * 0.5)
        aurora.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 55))
        aurora.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aurora))
        painter.drawRect(QRectF(0, 0, w, h))

        # Close button in top corner
        close_x = w - 30.0
        close_y = 16.0
        close_size = 20.0
        self._device_close_rect = QRectF(close_x, close_y, close_size, close_size)
        is_close_hov = getattr(self, "_device_close_hovered", False)
        painter.save()
        painter.setPen(QPen(QColor(255, 255, 255, 240 if is_close_hov else 130), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(close_x + 3.0, close_y + 3.0), QPointF(close_x + close_size - 3.0, close_y + close_size - 3.0))
        painter.drawLine(QPointF(close_x + close_size - 3.0, close_y + 3.0), QPointF(close_x + 3.0, close_y + close_size - 3.0))
        painter.restore()

        # Header: Device Title & Category
        f_title = get_display_font(13.0)
        f_title.setBold(True)
        painter.setFont(f_title)
        painter.setPen(COLOR_TEXT_PRIMARY)
        fm_t = painter.fontMetrics()
        elided_title = fm_t.elidedText(title, Qt.TextElideMode.ElideRight, int(w - 60.0))
        painter.drawText(QRectF(18.0, 16.0, w - 60.0, 22.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_title)

        # Hero 3D device model
        art_size = 88.0
        art_cx = w * 0.5
        art_cy = 105.0
        pix = self._device_pixmaps.get(cat)
        if pix and not pix.isNull():
            scaled_dev = pix.scaled(int(art_size), int(art_size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ix = art_cx - scaled_dev.width() / 2.0
            iy = art_cy - scaled_dev.height() / 2.0
            painter.drawPixmap(int(ix), int(iy), scaled_dev)

        # Contact shadow
        shadow = QRadialGradient(QPointF(art_cx, art_cy + 42.0), 38.0)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 120))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shadow))
        painter.drawEllipse(QRectF(art_cx - 40.0, art_cy + 38.0, 80.0, 10.0))

        # Battery & Status pill
        badge_w = 130.0
        badge_h = 24.0
        badge_x = (w - badge_w) / 2.0
        badge_y = 168.0
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1.0))
        painter.setBrush(QBrush(QColor(20, 22, 32, 200)))
        painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 12.0, 12.0)

        f_batt = get_microlabel_font()
        painter.setFont(f_batt)
        painter.setPen(COLOR_TEXT_PRIMARY)
        batt_str = f"⚡ {dev_batt}% • Ready"
        painter.drawText(QRectF(badge_x, badge_y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, batt_str)

        # Audio routing pill at bottom
        route_w = w - 36.0
        route_h = 34.0
        route_x = 18.0
        route_y = 208.0
        self._device_route_rect = QRectF(route_x, route_y, route_w, route_h)
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
        btn_grad = QLinearGradient(route_x, route_y, route_x, route_y + route_h)
        btn_grad.setColorAt(0.0, QColor("#0071E3"))
        btn_grad.setColorAt(1.0, QColor("#005BB5"))
        painter.setBrush(QBrush(btn_grad))
        painter.drawRoundedRect(self._device_route_rect, 17.0, 17.0)

        f_btn = get_subtext_font(10.5)
        f_btn.setBold(True)
        painter.setFont(f_btn)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(self._device_route_rect, Qt.AlignmentFlag.AlignCenter, "Connected • Tap to Route")

    def _paint_device_popup_side(self, painter: QPainter, w: float, h: float):
        """Vertical Accessory Showcase Modal for Left / Right Bezels (230x370)."""
        cat = self._device_info.get("category", "airpods")
        title = self._device_info.get("display_title") or self._device_info.get("name") or "Audio Device"
        subtitle = self._device_info.get("display_subtitle") or "Connected to Windows"
        dev_batt = self._device_info.get("battery", 86)

        accent_col = QColor("#38EF7D") if cat == "airpods" else (QColor("#56CCF2") if cat == "headphones" else QColor("#00D2FF"))

        # Obsidian gradient canvas
        canvas_grad = QLinearGradient(0, 0, 0, h)
        canvas_grad.setColorAt(0.0, QColor(22, 24, 34, 252))
        canvas_grad.setColorAt(0.5, QColor(14, 15, 23, 255))
        canvas_grad.setColorAt(1.0, QColor(8, 9, 14, 255))
        painter.fillRect(QRectF(0, 0, w, h), canvas_grad)

        # Fluid aurora glow
        aurora = QRadialGradient(QPointF(w * 0.5, 140.0), w * 0.55)
        aurora.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 60))
        aurora.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aurora))
        painter.drawRect(QRectF(0, 0, w, h))

        # Close button in top-right
        close_x = w - 30.0
        close_y = 16.0
        close_size = 20.0
        self._device_close_rect = QRectF(close_x, close_y, close_size, close_size)
        is_close_hov = getattr(self, "_device_close_hovered", False)
        painter.save()
        painter.setPen(QPen(QColor(255, 255, 255, 240 if is_close_hov else 130), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(close_x + 3.0, close_y + 3.0), QPointF(close_x + close_size - 3.0, close_y + close_size - 3.0))
        painter.drawLine(QPointF(close_x + close_size - 3.0, close_y + 3.0), QPointF(close_x + 3.0, close_y + close_size - 3.0))
        painter.restore()

        # Header Title (Centered)
        f_title = get_display_font(13.5)
        f_title.setBold(True)
        painter.setFont(f_title)
        painter.setPen(COLOR_TEXT_PRIMARY)
        fm_t = painter.fontMetrics()
        elided_title = fm_t.elidedText(title, Qt.TextElideMode.ElideRight, int(w - 40.0))
        painter.drawText(QRectF(20.0, 18.0, w - 40.0, 22.0), Qt.AlignmentFlag.AlignCenter, elided_title)

        f_sub = get_subtext_font(9.5)
        painter.setFont(f_sub)
        painter.setPen(QColor(255, 255, 255, 150))
        painter.drawText(QRectF(20.0, 40.0, w - 40.0, 16.0), Qt.AlignmentFlag.AlignCenter, subtitle)

        # Hero 3D device model (centered)
        art_size = 110.0
        art_cx = w * 0.5
        art_cy = 135.0
        pix = self._device_pixmaps.get(cat)
        if pix and not pix.isNull():
            scaled_dev = pix.scaled(int(art_size), int(art_size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ix = art_cx - scaled_dev.width() / 2.0
            iy = art_cy - scaled_dev.height() / 2.0
            painter.drawPixmap(int(ix), int(iy), scaled_dev)

        # Contact shadow
        shadow = QRadialGradient(QPointF(art_cx, art_cy + 54.0), 45.0)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 130))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shadow))
        painter.drawEllipse(QRectF(art_cx - 45.0, art_cy + 50.0, 90.0, 12.0))

        # Battery gauge pill
        badge_w = 140.0
        badge_h = 26.0
        badge_x = (w - badge_w) / 2.0
        badge_y = 222.0
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1.0))
        painter.setBrush(QBrush(QColor(20, 22, 32, 200)))
        painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 13.0, 13.0)

        f_batt = get_microlabel_font()
        f_batt.setBold(True)
        painter.setFont(f_batt)
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(badge_x, badge_y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, f"Battery • {dev_batt}%")

        # Action button at bottom
        route_w = w - 36.0
        route_h = 38.0
        route_x = 18.0
        route_y = 296.0
        self._device_route_rect = QRectF(route_x, route_y, route_w, route_h)
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
        btn_grad = QLinearGradient(route_x, route_y, route_x, route_y + route_h)
        btn_grad.setColorAt(0.0, QColor("#0071E3"))
        btn_grad.setColorAt(1.0, QColor("#005BB5"))
        painter.setBrush(QBrush(btn_grad))
        painter.drawRoundedRect(self._device_route_rect, 19.0, 19.0)

        f_btn = get_subtext_font(11.0)
        f_btn.setBold(True)
        painter.setFont(f_btn)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(self._device_route_rect, Qt.AlignmentFlag.AlignCenter, "Connected • Audio Ready")

    def _paint_device_popup_notch(self, painter: QPainter, w: float, h: float):
        """
        Draws the flagship Apple accessory showcase modal inside the Dynamic Island.
        Combines the iconic vertical Apple card hierarchy (large 3D hero model,
        crystal typography, full-width Apple action button) with true liquid obsidian
        glass morphism, fluid aurora plasma, and top screen bezel notch ears.
        """
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        if is_corner:
            self._paint_device_popup_corner(painter, w, h)
            return
        if is_side:
            self._paint_device_popup_side(painter, w, h)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        cat = self._device_info.get("category", "airpods")
        title = self._device_info.get("display_title") or self._device_info.get("name") or "Audio Device"
        subtitle = self._device_info.get("display_subtitle") or "Connected to Windows • Audio Ready"

        r_top = NOTCH_RADIUS_TOP

        # Theme accent & button palette based on device category
        if cat == "airpods":
            cat_label = "● AIRPODS PRO"
            accent_col = QColor("#38EF7D")       # Apple Green LED
            btn_grad_top = QColor("#0071E3")     # Apple Signature Blue
            btn_grad_bot = QColor("#005BB5")
        elif cat == "headphones":
            cat_label = "● OVER-EAR HEADPHONES"
            accent_col = QColor("#56CCF2")       # Cyan rim light
            btn_grad_top = QColor("#2F80ED")
            btn_grad_bot = QColor("#1B5DBB")
        elif cat == "speaker":
            cat_label = "● BLUETOOTH SPEAKER"
            accent_col = QColor("#00D2FF")       # Electric Aqua LED ring
            btn_grad_top = QColor("#00A8FF")
            btn_grad_bot = QColor("#0077B6")
        elif cat == "iem":
            cat_label = "● HI-FI IN-EAR MONITORS"
            accent_col = QColor("#B388FF")       # Smoked Sapphire / Amethyst resin
            btn_grad_top = QColor("#7C4DFF")
            btn_grad_bot = QColor("#5322D4")
        else:
            cat_label = "● AUDIO ACCESSORY"
            accent_col = QColor("#38EF7D")
            btn_grad_top = QColor("#0071E3")
            btn_grad_bot = QColor("#005BB5")

        # ── 1. Base Obsidian Liquid Glass Canvas Fill ────────────────
        canvas_grad = QLinearGradient(0, 0, 0, h)
        canvas_grad.setColorAt(0.0, QColor(22, 24, 34, 252))
        canvas_grad.setColorAt(0.4, QColor(14, 15, 23, 255))
        canvas_grad.setColorAt(1.0, QColor(7, 8, 12, 255))
        painter.fillRect(QRectF(0, 0, w, h), canvas_grad)

        # ── 2. Fluid Dynamic Aurora Plasma (Liquid Color Glow) ───────
        t = getattr(self, "_gradient_shift", 0.0)
        cx = w * 0.5 + math.cos(t * 0.8) * 20.0
        cy = h * 0.48 + math.sin(t * 0.6) * 15.0
        aurora = QRadialGradient(QPointF(cx, cy), w * 0.58)
        aurora.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 65))
        aurora.setColorAt(0.52, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 18))
        aurora.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aurora))
        painter.drawRect(QRectF(0, 0, w, h))

        # ── 3. Diagonal Liquid Glass Sheen & Top Meniscus ────────────
        sheen = QLinearGradient(0, 0, w * 0.6, h * 0.7)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 30))
        sheen.setColorAt(0.35, QColor(255, 255, 255, 10))
        sheen.setColorAt(0.7, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, h), sheen)

        # Top Specular Meniscus Line across curved notch ears
        meniscus = QLinearGradient(0, 0, w, 0)
        meniscus.setColorAt(0.0, QColor(255, 255, 255, 0))
        meniscus.setColorAt(r_top / w, QColor(255, 255, 255, 50))
        meniscus.setColorAt(0.5, QColor(255, 255, 255, 120))
        meniscus.setColorAt((w - r_top) / w, QColor(255, 255, 255, 50))
        meniscus.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(meniscus), 1.5))
        painter.drawLine(QPointF(0, 0.75), QPointF(w, 0.75))

        # ── 4. Header: Floating Sleek Vector Close Cross '✕' ─────────
        close_size = 24.0
        close_x = w - r_top - 28.0
        close_y = 20.0
        self._device_close_rect = QRectF(close_x, close_y, close_size, close_size)

        is_close_hov = getattr(self, "_device_close_hovered", False)
        cross_path = QPainterPath()
        arm = 4.4
        ccx = close_x + close_size / 2.0
        ccy = close_y + close_size / 2.0
        cross_path.moveTo(ccx - arm, ccy - arm)
        cross_path.lineTo(ccx + arm, ccy + arm)
        cross_path.moveTo(ccx + arm, ccy - arm)
        cross_path.lineTo(ccx - arm, ccy + arm)

        cross_alpha = 255 if is_close_hov else 140
        cross_width = 1.8 if is_close_hov else 1.4
        painter.setPen(QPen(QColor(255, 255, 255, cross_alpha), cross_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(cross_path)

        # ── 5. Header: Clean Title & Connection Status ───────────────
        header_x = r_top + 18.0
        header_w = close_x - header_x - 12.0

        # Device Title (Bold Crisp White, 16pt)
        f_title = get_display_font(16)
        f_title.setBold(True)
        painter.setFont(f_title)
        painter.setPen(QColor("#FFFFFF"))
        fm_t = painter.fontMetrics()
        elided_title = fm_t.elidedText(title, Qt.TextElideMode.ElideRight, int(header_w))
        painter.drawText(QRectF(header_x, 32.0, header_w, 28.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_title)

        # Subtitle (Muted Secondary)
        f_sub = get_subtext_font(10)
        painter.setFont(f_sub)
        painter.setPen(QColor(255, 255, 255, 160))
        fm_s = painter.fontMetrics()
        elided_sub = fm_s.elidedText(subtitle, Qt.TextElideMode.ElideRight, int(header_w))
        painter.drawText(QRectF(header_x, 60.0, header_w, 18.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_sub)

        # ── 6. Center Stage: Hero Device Model (Static, Crisp, No Jitter) ────────
        art_size = 125.0
        art_cx = w * 0.5
        art_cy = 145.0
        dev_cy = art_cy

        # Soft 3D Contact Shadow
        shadow = QRadialGradient(QPointF(art_cx, dev_cy + 58.0), 50.0)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 140))
        shadow.setColorAt(0.55, QColor(0, 0, 0, 45))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shadow))
        painter.drawEllipse(QRectF(art_cx - 52.0, dev_cy + 52.0, 104.0, 14.0))

        # Render 3D Device Art
        pix = self._device_pixmaps.get(cat)
        if pix and not pix.isNull():
            scaled_dev = pix.scaled(
                int(art_size), int(art_size),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            ix = art_cx - scaled_dev.width() / 2.0
            iy = dev_cy - scaled_dev.height() / 2.0
            painter.drawPixmap(int(ix), int(iy), scaled_dev)

        # ── 7. Segmented Battery Ring & Percentage Badge ──
        badge_w = 142.0
        badge_h = 26.0
        badge_x = (w - badge_w) / 2.0
        badge_y = 224.0
        badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)

        painter.setPen(QPen(QColor(255, 255, 255, 24), 1.0))
        painter.setBrush(QBrush(QColor(20, 22, 32, 200)))
        painter.drawRoundedRect(badge_rect, 13.0, 13.0)

        dev_batt = self._device_info.get("battery", 86)
        arc_cx = badge_x + 16.0
        arc_cy = badge_y + 13.0
        arc_r = 6.0
        arc_rect = QRectF(arc_cx - arc_r, arc_cy - arc_r, arc_r * 2.0, arc_r * 2.0)

        # Battery track
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(arc_rect)

        # Active battery arc
        arc_col = QColor("#38EF7D") if dev_batt >= 20 else QColor("#FF453A")
        painter.setPen(QPen(arc_col, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span_angle = int(-dev_batt * 360 * 16 / 100)
        painter.drawArc(arc_rect, 90 * 16, span_angle)

        f_batt_txt = get_microlabel_font()
        f_batt_txt.setBold(True)
        painter.setFont(f_batt_txt)
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(arc_cx + 10.0, badge_y, badge_w - 32.0, badge_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"Battery • {dev_batt}%")

        # Battery track
        painter.setPen(QPen(QColor(255, 255, 255, 30), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(arc_rect)

        # Active battery arc
        arc_col = QColor("#38EF7D") if dev_batt >= 20 else QColor("#FF453A")
        painter.setPen(QPen(arc_col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span_angle = int(-dev_batt * 360 * 16 / 100)
        painter.drawArc(arc_rect, 90 * 16, span_angle)

        f_batt_txt = get_microlabel_font()
        f_batt_txt.setBold(True)
        painter.setFont(f_batt_txt)
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(arc_cx + 10.0, badge_y, badge_w - 32.0, badge_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"Battery • {dev_batt}%")

        # ── 9. Inline Audio Routing Pill (Spec 4.2) ──────────────────
        btn_w = w - (r_top * 2 + 28.0)
        btn_h = 42.0
        btn_x = (w - btn_w) / 2.0
        btn_y = 302.0

        route_w = btn_w
        route_h = 34.0
        route_x = btn_x
        route_y = 260.0
        self._device_route_rect = QRectF(route_x, route_y, route_w, route_h)

        # Base capsule
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        painter.setBrush(QBrush(QColor(16, 18, 26, 230)))
        painter.drawRoundedRect(self._device_route_rect, 17.0, 17.0)

        # Slide indicator
        seg_w = (route_w - 4.0) / 2.0
        slide_x = route_x + 2.0 + getattr(self, "_device_route_pos", 0.0) * seg_w
        ind_rect = QRectF(slide_x, route_y + 2.0, seg_w, route_h - 4.0)
        painter.setPen(QPen(QColor(255, 255, 255, 42), 1.0))
        painter.setBrush(QBrush(QColor(255, 255, 255, 32)))
        painter.drawRoundedRect(ind_rect, 15.0, 15.0)

        is_dev = (getattr(self, "_device_route", "device") == "device")

        # Seg 1: Device (Vector Headphone + Title)
        hx = route_x + 18.0
        hy = route_y + route_h / 2.0
        painter.setPen(QPen(COLOR_TEXT_PRIMARY if is_dev else COLOR_TEXT_MUTED, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(hx - 5.0, hy - 6.0, 10.0, 9.0), 0, 180 * 16)
        painter.setBrush(QBrush(COLOR_TEXT_PRIMARY if is_dev else COLOR_TEXT_MUTED))
        painter.drawRoundedRect(QRectF(hx - 6.0, hy - 2.0, 2.5, 6.0), 1.0, 1.0)
        painter.drawRoundedRect(QRectF(hx + 3.5, hy - 2.0, 2.5, 6.0), 1.0, 1.0)

        f_r = get_microlabel_font()
        f_r.setBold(True)
        painter.setFont(f_r)
        painter.setPen(COLOR_TEXT_PRIMARY if is_dev else COLOR_TEXT_MUTED)
        fm_seg1 = painter.fontMetrics()
        short_t = fm_seg1.elidedText(title, Qt.TextElideMode.ElideRight, int(seg_w - 38.0))
        painter.drawText(QRectF(route_x + 28.0, route_y, seg_w - 32.0, route_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, short_t)

        # Seg 2: PC Speakers (Vector PC + "PC Speakers")
        sx = route_x + 2.0 + seg_w + 18.0
        sy = route_y + route_h / 2.0
        painter.setPen(QPen(COLOR_TEXT_PRIMARY if not is_dev else COLOR_TEXT_MUTED, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(sx - 6.0, sy - 5.0, 12.0, 8.0), 1.0, 1.0)
        painter.drawLine(QPointF(sx - 8.0, sy + 4.5), QPointF(sx + 8.0, sy + 4.5))

        painter.setPen(COLOR_TEXT_PRIMARY if not is_dev else COLOR_TEXT_MUTED)
        painter.drawText(QRectF(route_x + 2.0 + seg_w + 28.0, route_y, seg_w - 32.0, route_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "PC Speakers")

        # ── 10. Bottom Action Button: Hero Wide Pill ('Done') ────────
        self._device_done_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        is_done_hov = getattr(self, "_device_done_hovered", False)
        top_col = btn_grad_top.lighter(118) if is_done_hov else btn_grad_top
        bot_col = btn_grad_bot.lighter(118) if is_done_hov else btn_grad_bot

        btn_grad = QLinearGradient(btn_x, btn_y, btn_x, btn_y + btn_h)
        btn_grad.setColorAt(0.0, top_col)
        btn_grad.setColorAt(1.0, bot_col)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(btn_grad))
        painter.drawRoundedRect(self._device_done_rect, 21.0, 21.0)

        # Button Top Specular Rim Highlight Line
        btn_rim = QLinearGradient(btn_x, btn_y, btn_x + btn_w, btn_y)
        btn_rim.setColorAt(0.0, QColor(255, 255, 255, 25))
        btn_rim.setColorAt(0.5, QColor(255, 255, 255, 125 if is_done_hov else 85))
        btn_rim.setColorAt(1.0, QColor(255, 255, 255, 25))
        painter.setPen(QPen(QBrush(btn_rim), 1.2))
        painter.drawLine(QPointF(btn_x + 18.0, btn_y + 0.8), QPointF(btn_x + btn_w - 18.0, btn_y + 0.8))

        # Button Text
        f_btn = get_display_font(12)
        f_btn.setBold(True)
        painter.setFont(f_btn)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(self._device_done_rect, Qt.AlignmentFlag.AlignCenter, "Done")

    # -------------------------------------------------------------
    # New UI States QPainter Rendering Engines (Spec Section 3)
    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # 1:1 Square & Vertical Volume / Brightness HUD Handlers
    # -------------------------------------------------------------
    def _paint_osd_hud_corner(self, painter: QPainter, w: float, h: float):
        """1:1 Square Volume / Brightness HUD for Screen Corners."""
        val = max(0.0, min(1.0, float(self._osd_info.get("value", 0.5))))
        label = self._osd_info.get("label", f"{int(val * 100)}%")

        # 1. Circular Arc Gauge
        cx = w / 2.0
        cy = h / 2.0 - 8.0
        arc_radius = 30.0
        arc_rect = QRectF(cx - arc_radius, cy - arc_radius, arc_radius * 2.0, arc_radius * 2.0)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Track background
        bg_pen = QPen(QColor(255, 255, 255, 30), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(arc_rect, int(225 * 16), int(-270 * 16))

        # Active fill arc
        if val > 0.01:
            active_pen = QPen(QColor(255, 255, 255, 240), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(active_pen)
            painter.drawArc(arc_rect, int(225 * 16), int(-270 * val * 16))

        # Center vector speaker
        spk = QPainterPath()
        spk.addRoundedRect(QRectF(cx - 7.0, cy - 3.0, 3.5, 6.0), 0.8, 0.8)
        cone = QPainterPath()
        cone.moveTo(cx - 4.5, cy - 3.0)
        cone.lineTo(cx - 1.0, cy - 6.5)
        cone.lineTo(cx - 1.0, cy + 6.5)
        cone.lineTo(cx - 4.5, cy + 3.0)
        cone.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
        painter.drawPath(spk.united(cone))
        painter.restore()

        # Bottom tabular percentage
        painter.setFont(get_display_font(10.5))
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(0, h - 24.0, w, 16.0), Qt.AlignmentFlag.AlignCenter, label)

    def _paint_osd_hud_side(self, painter: QPainter, w: float, h: float):
        """Vertical Volume / Brightness HUD for Screen Sides."""
        val = max(0.0, min(1.0, float(self._osd_info.get("value", 0.5))))
        label = self._osd_info.get("label", f"{int(val * 100)}%")

        # 1. Top vector speaker
        cx = w / 2.0
        cy = 24.0
        painter.save()
        spk = QPainterPath()
        spk.addRoundedRect(QRectF(cx - 6.0, cy - 2.5, 3.0, 5.0), 0.8, 0.8)
        cone = QPainterPath()
        cone.moveTo(cx - 3.5, cy - 2.5)
        cone.lineTo(cx - 0.5, cy - 5.5)
        cone.lineTo(cx - 0.5, cy + 5.5)
        cone.lineTo(cx - 3.5, cy + 2.5)
        cone.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
        painter.drawPath(spk.united(cone))
        painter.restore()

        # 2. Vertical specular slider track
        track_w = 6.0
        track_h = max(60.0, h - 68.0)
        track_x = (w - track_w) / 2.0
        track_y = 40.0
        track_rect = QRectF(track_x, track_y, track_w, track_h)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 35)))
        painter.drawRoundedRect(track_rect, 3.0, 3.0)

        # Active fill from bottom to top
        if val > 0.01:
            fill_h = track_h * val
            fill_y = track_y + track_h - fill_h
            fill_rect = QRectF(track_x, fill_y, track_w, fill_h)

            grad = QLinearGradient(track_x, fill_y, track_x, fill_y + fill_h)
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(1.0, QColor(230, 235, 245, 220))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(fill_rect, 3.0, 3.0)
        painter.restore()

        # 3. Bottom percentage
        painter.setFont(get_microlabel_font())
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(0, h - 22.0, w, 14.0), Qt.AlignmentFlag.AlignCenter, label)

    def _paint_osd_hud(self, painter: QPainter, w: float, h: float):
        """
        Renders compact 260x38 liquid-glass OSD HUD for volume, brightness, caps.
        Features vector speaker/brightness iconography, specular sheen, and smooth continuous fill slider.
        """
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        if is_corner:
            self._paint_osd_hud_corner(painter, w, h)
            return

        if is_side:
            self._paint_osd_hud_side(painter, w, h)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        osd_type = self._osd_info.get("osd_type", "volume")
        val = max(0.0, min(1.0, float(self._osd_info.get("value", 0.5))))
        label = self._osd_info.get("label", f"{int(val * 100)}%")

        # 1. Left clean vector icon
        icon_cx = 28.0
        icon_cy = h / 2.0

        painter.save()
        if osd_type == "volume":
            # Clean vector speaker
            spk = QPainterPath()
            spk.addRoundedRect(QRectF(icon_cx - 9.0, icon_cy - 3.5, 4.5, 7.0), 1.0, 1.0)
            cone = QPainterPath()
            cone.moveTo(icon_cx - 5.5, icon_cy - 3.5)
            cone.lineTo(icon_cx - 1.0, icon_cy - 7.5)
            cone.lineTo(icon_cx - 1.0, icon_cy + 7.5)
            cone.lineTo(icon_cx - 5.5, icon_cy + 3.5)
            cone.closeSubpath()
            speaker_body = spk.united(cone)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
            painter.drawPath(speaker_body)

            # Sound wave arcs if volume > 0
            if val > 0.01:
                painter.setPen(QPen(QColor(255, 255, 255, 230), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                arc1 = QPainterPath()
                arc1.arcMoveTo(QRectF(icon_cx - 4.0, icon_cy - 6.0, 12.0, 12.0), -45)
                arc1.arcTo(QRectF(icon_cx - 4.0, icon_cy - 6.0, 12.0, 12.0), -45, 90)
                painter.drawPath(arc1)

                if val > 0.40:
                    arc2 = QPainterPath()
                    arc2.arcMoveTo(QRectF(icon_cx - 6.0, icon_cy - 9.5, 19.0, 19.0), -40)
                    arc2.arcTo(QRectF(icon_cx - 6.0, icon_cy - 9.5, 19.0, 19.0), -40, 80)
                    painter.drawPath(arc2)
            else:
                # Mute cross
                painter.setPen(QPen(QColor(255, 59, 48, 240), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(QPointF(icon_cx + 2.0, icon_cy - 3.5), QPointF(icon_cx + 8.0, icon_cy + 3.5))
                painter.drawLine(QPointF(icon_cx + 8.0, icon_cy - 3.5), QPointF(icon_cx + 2.0, icon_cy + 3.5))
        else:
            # Brightness sun icon
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
            painter.drawEllipse(QPointF(icon_cx, icon_cy), 3.5, 3.5)
            painter.setPen(QPen(QColor(255, 255, 255, 245), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for ang in range(0, 360, 45):
                rad = math.radians(ang)
                x1 = icon_cx + math.cos(rad) * 5.2
                y1 = icon_cy + math.sin(rad) * 5.2
                x2 = icon_cx + math.cos(rad) * 8.0
                y2 = icon_cy + math.sin(rad) * 8.0
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        painter.restore()

        # 2. Continuous pill slider track with specular sheen
        bar_x = 46.0
        bar_w = w - bar_x - 56.0
        bar_h = 7.0
        bar_y = (h - bar_h) / 2.0

        bar_bg = QRectF(bar_x, bar_y, bar_w, bar_h)
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        painter.setBrush(QColor(255, 255, 255, 24))
        painter.drawRoundedRect(bar_bg, 3.5, 3.5)

        fill_w = bar_w * val
        if fill_w > 0:
            fill_r = QRectF(bar_x, bar_y, fill_w, bar_h)
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(1.0, QColor(220, 230, 245, 240))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(fill_r, 3.5, 3.5)

        # 3. Tabular readout
        f_val = get_display_font(10.5)
        painter.setFont(f_val)
        painter.setPen(QColor(255, 255, 255, 225))
        painter.drawText(QRectF(w - 52.0, 0.0, 42.0, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)

    # -------------------------------------------------------------
    # 1:1 Square & Vertical Incoming Call Handlers
    # -------------------------------------------------------------
    def _paint_call_live_corner(self, painter: QPainter, w: float, h: float):
        """1:1 Square Incoming Call Modal for Screen Corners."""
        title = self._call_info.get("name", "Mom")
        subtitle = self._call_info.get("status", "Incoming Audio Call")

        # 1. Monogram Avatar with Pulsing Green Aura
        cx = w / 2.0
        cy = 50.0
        av_r = 24.0

        painter.save()
        aura = QRadialGradient(QPointF(cx, cy), av_r + 14.0)
        aura.setColorAt(0.0, QColor(52, 199, 89, 80))
        aura.setColorAt(0.6, QColor(52, 199, 89, 25))
        aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aura))
        painter.drawEllipse(QPointF(cx, cy), av_r + 14.0, av_r + 14.0)

        painter.setBrush(QBrush(QColor(28, 30, 38)))
        painter.setPen(QPen(QColor(52, 199, 89, 180), 1.5))
        painter.drawEllipse(QPointF(cx, cy), av_r, av_r)

        letter = title[0].upper() if title else "C"
        painter.setFont(get_display_font(13.0))
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(cx - av_r, cy - av_r, av_r * 2, av_r * 2), Qt.AlignmentFlag.AlignCenter, letter)
        painter.restore()

        # 2. Caller Name & Subtitle
        painter.setFont(get_display_font(12.0))
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(12.0, 88.0, w - 24.0, 20.0), Qt.AlignmentFlag.AlignCenter, title)

        painter.setFont(get_subtext_font(10.0))
        painter.setPen(QColor(52, 199, 89, 230))
        painter.drawText(QRectF(12.0, 108.0, w - 24.0, 16.0), Qt.AlignmentFlag.AlignCenter, subtitle)

        # 3. Action Buttons (Decline Left, Answer Right)
        btn_r = 18.0
        dec_cx = 58.0
        ans_cx = w - 58.0
        btn_cy = 168.0

        self._call_decline_rect = QRectF(dec_cx - btn_r, btn_cy - btn_r, btn_r * 2, btn_r * 2)
        self._call_answer_rect = QRectF(ans_cx - btn_r, btn_cy - btn_r, btn_r * 2, btn_r * 2)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 59, 48)))
        painter.drawEllipse(QPointF(dec_cx, btn_cy), btn_r, btn_r)
        painter.setPen(QPen(Qt.GlobalColor.white, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(dec_cx - 5.0, btn_cy - 5.0), QPointF(dec_cx + 5.0, btn_cy + 5.0))
        painter.drawLine(QPointF(dec_cx + 5.0, btn_cy - 5.0), QPointF(dec_cx - 5.0, btn_cy + 5.0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(52, 199, 89)))
        painter.drawEllipse(QPointF(ans_cx, btn_cy), btn_r, btn_r)
        painter.setFont(get_display_font(13.0))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(self._call_answer_rect, Qt.AlignmentFlag.AlignCenter, "✆")
        painter.restore()

    def _paint_call_live_side(self, painter: QPainter, w: float, h: float):
        """Vertical Incoming Call Modal for Screen Sides."""
        title = self._call_info.get("name", "Mom")
        subtitle = self._call_info.get("status", "Incoming Call")

        cx = w / 2.0
        cy = 44.0
        av_r = 22.0

        painter.save()
        aura = QRadialGradient(QPointF(cx, cy), av_r + 12.0)
        aura.setColorAt(0.0, QColor(52, 199, 89, 75))
        aura.setColorAt(0.6, QColor(52, 199, 89, 20))
        aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aura))
        painter.drawEllipse(QPointF(cx, cy), av_r + 12.0, av_r + 12.0)

        painter.setBrush(QBrush(QColor(28, 30, 38)))
        painter.setPen(QPen(QColor(52, 199, 89, 180), 1.5))
        painter.drawEllipse(QPointF(cx, cy), av_r, av_r)

        letter = title[0].upper() if title else "C"
        painter.setFont(get_display_font(12.0))
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(cx - av_r, cy - av_r, av_r * 2, av_r * 2), Qt.AlignmentFlag.AlignCenter, letter)
        painter.restore()

        painter.setFont(get_display_font(11.5))
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(8.0, 80.0, w - 16.0, 18.0), Qt.AlignmentFlag.AlignCenter, title)

        painter.setFont(get_subtext_font(9.5))
        painter.setPen(QColor(52, 199, 89, 230))
        painter.drawText(QRectF(8.0, 98.0, w - 16.0, 16.0), Qt.AlignmentFlag.AlignCenter, subtitle)

        btn_r = 17.0
        dec_cx = 44.0
        ans_cx = w - 44.0
        btn_cy = 190.0

        self._call_decline_rect = QRectF(dec_cx - btn_r, btn_cy - btn_r, btn_r * 2, btn_r * 2)
        self._call_answer_rect = QRectF(ans_cx - btn_r, btn_cy - btn_r, btn_r * 2, btn_r * 2)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 59, 48)))
        painter.drawEllipse(QPointF(dec_cx, btn_cy), btn_r, btn_r)
        painter.setPen(QPen(Qt.GlobalColor.white, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(dec_cx - 4.5, btn_cy - 4.5), QPointF(dec_cx + 4.5, btn_cy + 4.5))
        painter.drawLine(QPointF(dec_cx + 4.5, btn_cy - 4.5), QPointF(dec_cx - 4.5, btn_cy + 4.5))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(52, 199, 89)))
        painter.drawEllipse(QPointF(ans_cx, btn_cy), btn_r, btn_r)
        painter.setFont(get_display_font(12.0))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(self._call_answer_rect, Qt.AlignmentFlag.AlignCenter, "✆")
        painter.restore()

    def _paint_call_live(self, painter: QPainter, w: float, h: float):
        """
        Renders live phone call card (440x74) with pulsing avatar and vector Answer/Decline buttons.
        """
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        if is_corner:
            self._paint_call_live_corner(painter, w, h)
            return

        if is_side:
            self._paint_call_live_side(painter, w, h)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        name = self._call_info.get("name", "Incoming Call")
        subtitle = self._call_info.get("status", "iPhone • Incoming Call")

        # 1. Left circular avatar with pulsing green ring
        av_x = 22.0
        av_y = (h - 44.0) / 2.0
        av_size = 44.0
        av_cx = av_x + av_size / 2.0
        av_cy = av_y + av_size / 2.0

        # Pulsing green ring
        pulse = (math.sin(getattr(self, "_call_pulse", 0.0) * 2.0) + 1.0) / 2.0
        ring_r = av_size / 2.0 + 3.0 + pulse * 6.0
        ring_alpha = int(140 * (1.0 - pulse * 0.7))
        painter.setPen(QPen(QColor(52, 199, 89, ring_alpha), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(av_cx, av_cy), ring_r, ring_r)

        # Avatar circle with monogram initial
        painter.setPen(Qt.PenStyle.NoPen)
        av_grad = QLinearGradient(av_x, av_y, av_x, av_y + av_size)
        av_grad.setColorAt(0.0, QColor(48, 54, 78, 255))
        av_grad.setColorAt(1.0, QColor(26, 30, 46, 255))
        painter.setBrush(QBrush(av_grad))
        painter.drawEllipse(QRectF(av_x, av_y, av_size, av_size))

        # Initial letter (bold white)
        initial = (name[0] if name else "C").upper()
        f_init = get_display_font(17)
        f_init.setBold(True)
        painter.setFont(f_init)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(av_x, av_y, av_size, av_size), Qt.AlignmentFlag.AlignCenter, initial)

        # 2. Center caller name + subtitle + animated voice wave
        text_x = av_x + av_size + 14.0
        text_w = w - text_x - 110.0

        f_name = get_display_font(13.5)
        f_name.setBold(True)
        painter.setFont(f_name)
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(text_x, av_y + 3.0, text_w, 20.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

        f_sub = get_subtext_font(10)
        painter.setFont(f_sub)
        painter.setPen(QColor(52, 199, 89))
        painter.drawText(QRectF(text_x, av_y + 24.0, 10.0, 16.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "●")
        painter.setPen(COLOR_TEXT_SECONDARY)
        painter.drawText(QRectF(text_x + 10.0, av_y + 24.0, text_w - 10.0, 16.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, subtitle)

        # 3. Right vector buttons: Decline (#FF3B30) and Answer (#34C759)
        btn_r = 18.0
        btn_y = (h - btn_r * 2.0) / 2.0

        dec_x = w - 95.0
        ans_x = w - 48.0
        self._call_decline_rect = QRectF(dec_x, btn_y, btn_r * 2.0, btn_r * 2.0)
        self._call_answer_rect = QRectF(ans_x, btn_y, btn_r * 2.0, btn_r * 2.0)

        # Decline Button (#FF3B30) with vector cross
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FF3B30"))
        painter.drawEllipse(self._call_decline_rect)
        dec_cross = QPainterPath()
        arm = 4.2
        dcx = dec_x + btn_r
        dcy = btn_y + btn_r
        dec_cross.moveTo(dcx - arm, dcy - arm)
        dec_cross.lineTo(dcx + arm, dcy + arm)
        dec_cross.moveTo(dcx + arm, dcy - arm)
        dec_cross.lineTo(dcx - arm, dcy + arm)
        painter.setPen(QPen(QColor(255, 255, 255, 250), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(dec_cross)

        # Answer Button (#34C759) with vector phone receiver
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#34C759"))
        painter.drawEllipse(self._call_answer_rect)
        acx = ans_x + btn_r
        acy = btn_y + btn_r
        # Crisp phone receiver glyph
        f_ans = get_display_font(13)
        painter.setFont(f_ans)
        painter.setPen(QColor(255, 255, 255, 250))
        painter.drawText(self._call_answer_rect, Qt.AlignmentFlag.AlignCenter, "✆")

    # -------------------------------------------------------------
    # 1:1 Square & Vertical OTP Handlers
    # -------------------------------------------------------------
    def _paint_otp_pill_corner(self, painter: QPainter, w: float, h: float):
        """1:1 Square Two-Factor OTP Modal for Screen Corners."""
        code = self._otp_info.get("code", "482 910")
        copied = self._otp_info.get("copied", False)

        # 1. Top Badge
        cx = w / 2.0
        painter.save()
        badge_rect = QRectF(cx - 16.0, 18.0, 32.0, 22.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 122, 255, 230)))
        painter.drawRoundedRect(badge_rect, 6.0, 6.0)

        painter.setBrush(QBrush(Qt.GlobalColor.white))
        for dx in (-5.0, 0.0, 5.0):
            painter.drawEllipse(QPointF(cx + dx, 29.0), 1.4, 1.4)
        painter.restore()

        painter.setFont(get_subtext_font(9.0))
        painter.setPen(QColor(255, 255, 255, 160))
        painter.drawText(QRectF(10.0, 46.0, w - 20.0, 14.0), Qt.AlignmentFlag.AlignCenter, "TWO-FACTOR CODE")

        # 2. Big Monospace OTP Code
        painter.setFont(get_monospaced_font(15.0))
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(10.0, 72.0, w - 20.0, 32.0), Qt.AlignmentFlag.AlignCenter, code)

        # 3. Interactive Copy Button
        btn_w = 140.0
        btn_h = 32.0
        btn_x = (w - btn_w) / 2.0
        btn_y = 126.0
        self._otp_copy_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(52, 199, 89, 230) if copied else QColor(255, 255, 255, 30)))
        painter.drawRoundedRect(self._otp_copy_rect, 16.0, 16.0)

        painter.setFont(get_display_font(10.5))
        painter.setPen(COLOR_TEXT_PRIMARY)
        btn_txt = "Copied ✓" if copied else "Copy Code"
        painter.drawText(self._otp_copy_rect, Qt.AlignmentFlag.AlignCenter, btn_txt)
        painter.restore()

    def _paint_otp_pill_side(self, painter: QPainter, w: float, h: float):
        """Vertical Two-Factor OTP Modal for Screen Sides."""
        code = self._otp_info.get("code", "482 910")
        copied = self._otp_info.get("copied", False)

        cx = w / 2.0
        painter.save()
        badge_rect = QRectF(cx - 15.0, 18.0, 30.0, 20.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 122, 255, 230)))
        painter.drawRoundedRect(badge_rect, 5.0, 5.0)

        painter.setBrush(QBrush(Qt.GlobalColor.white))
        for dx in (-4.5, 0.0, 4.5):
            painter.drawEllipse(QPointF(cx + dx, 28.0), 1.3, 1.3)
        painter.restore()

        painter.setFont(get_subtext_font(8.5))
        painter.setPen(QColor(255, 255, 255, 160))
        painter.drawText(QRectF(6.0, 44.0, w - 12.0, 14.0), Qt.AlignmentFlag.AlignCenter, "2FA CODE")

        parts = code.split(" ")
        c1 = parts[0] if len(parts) > 0 else code
        c2 = parts[1] if len(parts) > 1 else ""

        painter.setFont(get_monospaced_font(13.5))
        painter.setPen(COLOR_TEXT_PRIMARY)
        if c2:
            painter.drawText(QRectF(6.0, 68.0, w - 12.0, 18.0), Qt.AlignmentFlag.AlignCenter, c1)
            painter.drawText(QRectF(6.0, 88.0, w - 12.0, 18.0), Qt.AlignmentFlag.AlignCenter, c2)
        else:
            painter.drawText(QRectF(6.0, 78.0, w - 12.0, 22.0), Qt.AlignmentFlag.AlignCenter, c1)

        btn_w = 110.0
        btn_h = 28.0
        btn_x = (w - btn_w) / 2.0
        btn_y = 140.0
        self._otp_copy_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(52, 199, 89, 230) if copied else QColor(255, 255, 255, 30)))
        painter.drawRoundedRect(self._otp_copy_rect, 14.0, 14.0)

        painter.setFont(get_display_font(9.5))
        painter.setPen(COLOR_TEXT_PRIMARY)
        btn_txt = "Copied ✓" if copied else "Copy"
        painter.drawText(self._otp_copy_rect, Qt.AlignmentFlag.AlignCenter, btn_txt)
        painter.restore()

    def _paint_otp_pill(self, painter: QPainter, w: float, h: float):
        """
        Renders 2FA verification code pill (380x56) with monospaced tabular numerals and copy button.
        """
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        if is_corner:
            self._paint_otp_pill_corner(painter, w, h)
            return

        if is_side:
            self._paint_otp_pill_side(painter, w, h)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        code = self._otp_info.get("code", "482 910")
        app_name = self._otp_info.get("app", "Messages")
        is_copied = self._otp_info.get("copied", False)

        # Left app badge with gradient & vector key/chat
        badge_size = 36.0
        badge_x = 16.0
        badge_y = (h - badge_size) / 2.0
        badge_rect = QRectF(badge_x, badge_y, badge_size, badge_size)

        badge_grad = QLinearGradient(badge_x, badge_y, badge_x, badge_y + badge_size)
        badge_grad.setColorAt(0.0, QColor(10, 132, 255, 220))
        badge_grad.setColorAt(1.0, QColor(0, 113, 227, 240))
        painter.setPen(QPen(QColor(10, 132, 255, 80), 1.0))
        painter.setBrush(QBrush(badge_grad))
        painter.drawRoundedRect(badge_rect, 10.0, 10.0)

        # Vector key / speech bubble in white
        k_cx = badge_x + badge_size / 2.0
        k_cy = badge_y + badge_size / 2.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(k_cx - 7.0, k_cy - 5.5, 14.0, 10.0), 2.5, 2.5)
        tail = QPainterPath()
        tail.moveTo(k_cx - 3.5, k_cy + 4.5)
        tail.lineTo(k_cx - 6.0, k_cy + 7.5)
        tail.lineTo(k_cx - 1.0, k_cy + 4.5)
        tail.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
        painter.drawPath(path.united(tail))

        # Center: Title + Code in Monospaced Tabular Numerals
        text_x = badge_x + badge_size + 14.0
        text_w = w - text_x - 110.0

        f_lbl = get_microlabel_font()
        painter.setFont(f_lbl)
        painter.setPen(QColor(255, 255, 255, 160))
        painter.drawText(QRectF(text_x, 9.0, text_w, 14.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{app_name.upper()} • VERIFICATION CODE")

        f_code = get_monospaced_font(14)
        f_code.setBold(True)
        painter.setFont(f_code)
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(QRectF(text_x, 26.0, text_w, 22.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, code)

        # Right Action Button: "Copy Code" -> "Copied ✓"
        btn_w = 92.0
        btn_h = 28.0
        btn_x = w - btn_w - 16.0
        btn_y = (h - btn_h) / 2.0
        self._otp_copy_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        if is_copied:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#34C759"))
            painter.drawRoundedRect(self._otp_copy_rect, 14.0, 14.0)
            f_btn = get_display_font(10.5)
            f_btn.setBold(True)
            painter.setFont(f_btn)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(self._otp_copy_rect, Qt.AlignmentFlag.AlignCenter, "Copied ✓")
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.drawRoundedRect(self._otp_copy_rect, 14.0, 14.0)
            f_btn = get_display_font(10.5)
            painter.setFont(f_btn)
            painter.setPen(COLOR_TEXT_PRIMARY)
            painter.drawText(self._otp_copy_rect, Qt.AlignmentFlag.AlignCenter, "Copy Code")

    # -------------------------------------------------------------
    # 1:1 Square & Vertical File Shelf Handlers
    # -------------------------------------------------------------
    def _paint_file_shelf_corner(self, painter: QPainter, w: float, h: float):
        """1:1 Square File Shelf for Screen Corners."""
        stashed_count = len(self._shelf_files)

        # Header
        painter.setFont(get_subtext_font(9.5))
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawText(QRectF(14.0, 16.0, w - 28.0, 16.0), Qt.AlignmentFlag.AlignCenter, "AIRDROP FILE SHELF")

        # Square dashed drop zone
        drop_rect = QRectF(18.0, 38.0, w - 36.0, h - 86.0)
        painter.save()
        dash_pen = QPen(QColor(0, 198, 255, 120), 1.5, Qt.PenStyle.DashLine)
        dash_pen.setDashPattern([4, 3])
        painter.setPen(dash_pen)
        painter.setBrush(QBrush(QColor(0, 198, 255, 10)))
        painter.drawRoundedRect(drop_rect, 12.0, 12.0)

        # Upload arrow & label
        cx = w / 2.0
        cy = drop_rect.center().y()
        painter.setPen(QPen(QColor(0, 198, 255, 220), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(cx, cy + 6.0), QPointF(cx, cy - 6.0))
        painter.drawLine(QPointF(cx - 5.0, cy - 1.0), QPointF(cx, cy - 6.0))
        painter.drawLine(QPointF(cx + 5.0, cy - 1.0), QPointF(cx, cy - 6.0))

        painter.setFont(get_microlabel_font())
        painter.setPen(QColor(255, 255, 255, 160))
        painter.drawText(QRectF(18.0, cy + 12.0, w - 36.0, 16.0), Qt.AlignmentFlag.AlignCenter, f"{stashed_count} files stashed" if stashed_count else "Drop files to stash")
        painter.restore()

        # Bottom clear button
        btn_w = 80.0
        btn_h = 24.0
        btn_x = (w - btn_w) / 2.0
        btn_y = h - 34.0
        self._shelf_clear_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 35)))
        painter.drawRoundedRect(self._shelf_clear_rect, 12.0, 12.0)
        painter.setFont(get_microlabel_font())
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(self._shelf_clear_rect, Qt.AlignmentFlag.AlignCenter, "Clear All")
        painter.restore()

    def _paint_file_shelf_side(self, painter: QPainter, w: float, h: float):
        """Vertical File Shelf for Screen Sides."""
        stashed_count = len(self._shelf_files)

        painter.setFont(get_subtext_font(8.5))
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawText(QRectF(8.0, 18.0, w - 16.0, 16.0), Qt.AlignmentFlag.AlignCenter, "FILE SHELF")

        drop_rect = QRectF(14.0, 42.0, w - 28.0, h - 90.0)
        painter.save()
        dash_pen = QPen(QColor(0, 198, 255, 120), 1.5, Qt.PenStyle.DashLine)
        dash_pen.setDashPattern([4, 3])
        painter.setPen(dash_pen)
        painter.setBrush(QBrush(QColor(0, 198, 255, 10)))
        painter.drawRoundedRect(drop_rect, 12.0, 12.0)

        cx = w / 2.0
        cy = drop_rect.center().y()
        painter.setPen(QPen(QColor(0, 198, 255, 220), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(cx, cy + 8.0), QPointF(cx, cy - 8.0))
        painter.drawLine(QPointF(cx - 6.0, cy - 2.0), QPointF(cx, cy - 8.0))
        painter.drawLine(QPointF(cx + 6.0, cy - 2.0), QPointF(cx, cy - 8.0))

        painter.setFont(get_microlabel_font())
        painter.setPen(QColor(255, 255, 255, 160))
        painter.drawText(QRectF(14.0, cy + 16.0, w - 28.0, 16.0), Qt.AlignmentFlag.AlignCenter, f"{stashed_count} stashed" if stashed_count else "Drop files")
        painter.restore()

        btn_w = 76.0
        btn_h = 24.0
        btn_x = (w - btn_w) / 2.0
        btn_y = h - 34.0
        self._shelf_clear_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 35)))
        painter.drawRoundedRect(self._shelf_clear_rect, 12.0, 12.0)
        painter.setFont(get_microlabel_font())
        painter.setPen(COLOR_TEXT_PRIMARY)
        painter.drawText(self._shelf_clear_rect, Qt.AlignmentFlag.AlignCenter, "Clear")
        painter.restore()

    def _paint_file_shelf(self, painter: QPainter, w: float, h: float):
        """
        Renders drag-and-drop file shelf tray (440x130) with dashed drop zone and stashed file cards.
        """
        edge = getattr(self, "_dock_edge", "top")
        is_corner = edge in ("top-left", "top-right", "bottom-left", "bottom-right", "corner-tl", "corner-tr", "corner-bl", "corner-br")
        is_side = edge in ("left", "right")

        if is_corner:
            self._paint_file_shelf_corner(painter, w, h)
            return

        if is_side:
            self._paint_file_shelf_side(painter, w, h)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        r_top = NOTCH_RADIUS_TOP
        f_head = get_microlabel_font()
        f_head.setBold(True)
        painter.setFont(f_head)
        painter.setPen(QColor("#56CCF2"))
        painter.drawText(QRectF(r_top + 14.0, 8.0, 200.0, 16.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "AIRDROP & FILE SHELF")

        # Clear Button
        clear_w = 52.0
        clear_h = 20.0
        clear_x = w - r_top - clear_w - 14.0
        clear_y = 6.0
        self._shelf_clear_rect = QRectF(clear_x, clear_y, clear_w, clear_h)
        is_clear_hov = getattr(self, "_shelf_hover_clear", False)
        painter.setPen(QPen(QColor(255, 255, 255, 55 if is_clear_hov else 28), 1.0))
        painter.setBrush(QBrush(QColor(255, 255, 255, 40 if is_clear_hov else 16)))
        painter.drawRoundedRect(self._shelf_clear_rect, 10.0, 10.0)
        painter.setFont(get_microlabel_font())
        painter.setPen(QColor("#FFFFFF" if is_clear_hov else "#A0A0AB"))
        painter.drawText(self._shelf_clear_rect, Qt.AlignmentFlag.AlignCenter, "Clear")

        # Dashed Luminous Drop Zone
        zone_rect = QRectF(16.0, 30.0, w - 32.0, h - 42.0)
        dash_pen = QPen(QColor(255, 255, 255, 45), 1.2, Qt.PenStyle.DashLine)
        dash_pen.setDashPattern([5, 5])
        painter.setPen(dash_pen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 8)))
        painter.drawRoundedRect(zone_rect, 14.0, 14.0)

        if not self._shelf_files:
            # Clean vector upload arrow
            ucx = zone_rect.center().x()
            ucy = zone_rect.center().y() - 10.0
            u_path = QPainterPath()
            u_path.moveTo(ucx, ucy - 6.0)
            u_path.lineTo(ucx - 5.0, ucy - 1.0)
            u_path.moveTo(ucx, ucy - 6.0)
            u_path.lineTo(ucx + 5.0, ucy - 1.0)
            u_path.moveTo(ucx, ucy - 6.0)
            u_path.lineTo(ucx, ucy + 6.0)
            painter.setPen(QPen(QColor("#56CCF2"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(u_path)

            painter.setFont(get_subtext_font(11))
            painter.setPen(QColor(255, 255, 255, 210))
            painter.drawText(QRectF(zone_rect.left(), ucy + 10.0, zone_rect.width(), 18.0), Qt.AlignmentFlag.AlignCenter, "Drop files here to stash or share")
        else:
            card_w = 88.0
            card_h = 72.0
            gap = 8.0
            start_x = zone_rect.left() + 10.0
            for idx, f in enumerate(self._shelf_files[:4]):
                cx = start_x + idx * (card_w + gap)
                cy = zone_rect.top() + (zone_rect.height() - card_h) / 2.0
                card_r = QRectF(cx, cy, card_w, card_h)

                painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
                painter.setBrush(QBrush(QColor(30, 32, 45, 200)))
                painter.drawRoundedRect(card_r, 10.0, 10.0)

                painter.setFont(get_display_font(14))
                painter.setPen(QColor("#56CCF2"))
                painter.drawText(QRectF(cx, cy + 4.0, card_w, 24.0), Qt.AlignmentFlag.AlignCenter, "📄")

                painter.setFont(get_microlabel_font())
                painter.setPen(COLOR_TEXT_PRIMARY)
                fm = painter.fontMetrics()
                short_name = fm.elidedText(f["name"], Qt.TextElideMode.ElideMiddle, int(card_w - 8.0))
                painter.drawText(QRectF(cx + 4.0, cy + 30.0, card_w - 8.0, 16.0), Qt.AlignmentFlag.AlignCenter, short_name)

                sz_str = f"{f['size'] // 1024} KB" if f['size'] > 1024 else f"{f['size']} B"
                painter.setFont(get_microlabel_font())
                painter.setPen(COLOR_TEXT_MUTED)
                painter.drawText(QRectF(cx + 4.0, cy + 48.0, card_w - 8.0, 14.0), Qt.AlignmentFlag.AlignCenter, sz_str)

    # -------------------------------------------------------------
    # State Trigger Methods for External Events & Telemetry
    # -------------------------------------------------------------
    def trigger_osd(self, glyph: str = "🔊", value: float = 0.68, label: str = "68%", osd_type: str = "volume"):
        if self._is_fullscreen_suppressed:
            return
        self._osd_info = {
            "glyph": glyph,
            "value": max(0.0, min(1.0, value)),
            "label": label,
            "type": osd_type
        }
        self.set_glow_state("notification", duration_sec=1.8)
        if not self.isVisible():
            self.show()
            self.raise_()
        self.set_island_state("osd_hud")
        self._osd_dismiss_timer.start(1800)

    def _on_osd_timeout(self):
        if self._island_state == "osd_hud":
            self.collapse_to_compact()

    def trigger_call(self, name: str = "Mom", number: str = "", status: str = "iPhone • Incoming Call", avatar: str = "👤"):
        if self._is_fullscreen_suppressed:
            return
        self._call_info = {
            "name": name,
            "number": number,
            "status": status,
            "avatar": avatar
        }
        self.set_glow_state("success", duration_sec=10.0)
        if not self.isVisible():
            self.show()
            self.raise_()
        self.set_island_state("call_live")

    def trigger_otp(self, code: str = "482 910", app: str = "Messages"):
        if self._is_fullscreen_suppressed:
            return
        self._otp_info = {
            "code": code,
            "app": app,
            "copied": False
        }
        self.set_glow_state("notification", duration_sec=6.0)
        if not self.isVisible():
            self.show()
            self.raise_()
        self.set_island_state("otp_pill")
        self._otp_dismiss_timer.start(5500)

    def _on_otp_timeout(self):
        if self._island_state == "otp_pill":
            self.collapse_to_compact()

    def trigger_file_shelf(self):
        if not self.isVisible():
            self.show()
            self.raise_()
        self.set_glow_state("notification", duration_sec=6.0)
        self.set_island_state("file_shelf")

    def set_download_progress(self, progress: float):
        self._download_progress = max(0.0, min(1.0, progress))
        self.update()

    def simulate_download(self):
        """Simulates an active download smoothly progressing from 5% to 100% with completion alert."""
        self._sim_download_active = True
        self._download_progress = 0.05
        self.set_glow_state("notification", duration_sec=4.0)
        if not self.isVisible():
            self.show()
            self.raise_()
        self.update()

        if not hasattr(self, "_sim_dl_timer"):
            self._sim_dl_timer = QTimer(self)
            def _step_dl():
                self._download_progress += 0.035
                if self._download_progress >= 1.0:
                    self._download_progress = 1.0
                    self._sim_dl_timer.stop()
                    self._sim_download_active = False
                    self.set_glow_state("success", duration_sec=2.5)
                    self.trigger_toast("Downloads", "Download Complete", "DynamicIsland-v2.6.zip ready in Downloads")
                self.update()
            self._sim_dl_timer.timeout.connect(_step_dl)
        self._sim_dl_timer.start(80)

    def toggle_auto_hide(self, enabled: Optional[bool] = None):
        if enabled is None:
            self._auto_hide_enabled = not getattr(self, "_auto_hide_enabled", False)
        else:
            self._auto_hide_enabled = bool(enabled)
        self._apply_geometry_for_state(self._island_state, animate=True)
        self.save_current_settings()
        self.update()

    def set_phone_battery(self, pct: int):
        self._phone_battery = pct
        self._phone_connected = True
        if hasattr(self, "lbl_exp_phone_battery"):
            self.lbl_exp_phone_battery.setText(f"📱 {pct}%")
            self.lbl_exp_phone_battery.setVisible(True)
        self.update()

    def set_privacy_leds(self, mic: Optional[bool] = None, cam: Optional[bool] = None):
        if mic is not None:
            self._privacy_mic = mic
            if hasattr(self, "led_mic"):
                self.led_mic.setVisible(mic)
        if cam is not None:
            self._privacy_cam = cam
            if hasattr(self, "led_cam"):
                self.led_cam.setVisible(cam)
        self.update()
