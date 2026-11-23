"""
WindowLand Dynamic Island - Ambient Glass Control Center Application.
Strictly implements DESIGN.md and the 6 screen designs from stitch_frosted_glass_web_ui:
- Frosted Glassmorphism with deep ambient dark canvas (#0e0e14 -> #131319)
- Soft ambient radial glow blobs (magenta #ff43a8, violet #7c03d3, mint #4edea3)
- Luminous glass surfaces (rgba(31, 31, 38, 0.65)) with crisp 1px borders
- Primary gradient accent (#ff43a8 -> #7c03d3) for active pills, buttons, and switches
- Interactive Live Island Preview widgets (Compact notch & Expanded states)
- Real-time live synchronization with DynamicIslandWidget and background services
"""

import os
import sys
import urllib.request
from typing import Optional, Dict, Tuple

# Ensure project root is on sys.path for direct module runs
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QScrollArea, QSlider, QComboBox, QColorDialog,
    QMessageBox, QGridLayout
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QLinearGradient, QRadialGradient,
    QFont, QDesktopServices, QGuiApplication, QPainterPath
)

from services.settings_service import settings
from services.autostart_service import is_autostart_enabled, set_autostart


class AmbientCanvasWidget(QWidget):
    """
    Root canvas widget that paints the deep ambient dark background
    with soft, low-opacity radial glow blobs (magenta, violet, and mint)
    behind the frosted glass cards as specified in DESIGN.md.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)  # type: ignore[arg-type]
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        # Base dark canvas: #0E0E14
        painter.fillRect(0, 0, int(w), int(h), QColor("#0E0E14"))

        # Ambient Glow Blob 1: Top-Left (Magenta #ff43a8 at 14% opacity)
        g1 = QRadialGradient(QPointF(w * 0.15, h * 0.15), w * 0.45)
        g1.setColorAt(0.0, QColor(255, 67, 168, 35))
        g1.setColorAt(0.6, QColor(255, 67, 168, 10))
        g1.setColorAt(1.0, QColor(14, 14, 20, 0))
        painter.setBrush(QBrush(g1))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, int(w), int(h))

        # Ambient Glow Blob 2: Center-Right (Violet #7c03d3 at 14% opacity)
        g2 = QRadialGradient(QPointF(w * 0.85, h * 0.45), w * 0.50)
        g2.setColorAt(0.0, QColor(124, 3, 211, 35))
        g2.setColorAt(0.6, QColor(124, 3, 211, 10))
        g2.setColorAt(1.0, QColor(14, 14, 20, 0))
        painter.setBrush(QBrush(g2))
        painter.drawRect(0, 0, int(w), int(h))

        # Ambient Glow Blob 3: Bottom-Center (Mint #4edea3 at 8% opacity)
        g3 = QRadialGradient(QPointF(w * 0.45, h * 0.90), w * 0.40)
        g3.setColorAt(0.0, QColor(78, 222, 163, 22))
        g3.setColorAt(0.7, QColor(78, 222, 163, 5))
        g3.setColorAt(1.0, QColor(14, 14, 20, 0))
        painter.setBrush(QBrush(g3))
        painter.drawRect(0, 0, int(w), int(h))

        painter.end()


class SwitchToggle(QWidget):
    """
    Pill-shaped toggle switch implementing DESIGN.md:
    Off: #35343B / rgba(255, 255, 255, 0.12)
    On: Linear gradient (#FF43A8 -> #7C03D3) with glowing shadow
    """
    toggled = pyqtSignal(bool)  # type: ignore

    def __init__(self, checked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)  # type: ignore[arg-type]
        self._checked = checked
        self.setFixedSize(48, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        # Track
        if self._checked:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor("#FF43A8"))
            grad.setColorAt(1.0, QColor("#7C03D3"))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(255, 67, 168, 120), 1.0))
        else:
            painter.setBrush(QBrush(QColor("#35343B")))
            painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))

        painter.drawRoundedRect(0, 0, int(w), int(h), int(h / 2.0), int(h / 2.0))

        # Thumb
        thumb_d = int(h - 6)
        thumb_x = int(w - thumb_d - 3 if self._checked else 3)
        painter.setBrush(QBrush(QColor("#E4E1EA")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(thumb_x, 3, thumb_d, thumb_d)
        painter.end()


class GeneralNotchPreview(QWidget):
    """
    Live Island Preview Card for Page 1 (General Island).
    Displays the compact notch pill with live clock and green indicator dot
    over an inner dark well with background ambient glow.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)  # type: ignore[arg-type]
        self.setFixedHeight(96)
        self._is_expanded = False
        self._time_str = "19:30"

    def set_expanded(self, expanded: bool):
        self._is_expanded = expanded
        self.update()

    def set_time_str(self, time_str: str):
        self._time_str = time_str
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        # Inner well
        well_path = QPainterPath()
        well_path.addRoundedRect(QRectF(0, 0, w, h), 12.0, 12.0)
        painter.fillPath(well_path, QColor("#0E0E14"))
        painter.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        painter.drawPath(well_path)

        # Ambient Glow behind pill
        glow_rad = QRadialGradient(w / 2.0, 32.0, 100.0)
        glow_rad.setColorAt(0.0, QColor(255, 67, 168, 45))
        glow_rad.setColorAt(1.0, QColor(14, 14, 20, 0))
        painter.setBrush(QBrush(glow_rad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(w / 2.0 - 90), 8, 180, 50)

        # Island Pill
        pill_w = 260.0 if self._is_expanded else 115.0
        pill_h = 32.0
        pill_x = (w - pill_w) / 2.0
        pill_y = 16.0
        pill_rect = QRectF(pill_x, pill_y, pill_w, pill_h)

        painter.setBrush(QBrush(QColor("#1F1F26")))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        painter.drawRoundedRect(pill_rect, 16.0, 16.0)

        # Green indicator dot
        painter.setBrush(QBrush(QColor("#4EDEA3")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(pill_x + 14), int(pill_y + 12), 8, 8)

        # Clock Text
        painter.setPen(QColor("#E4E1EA"))
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(int(pill_x + 30), int(pill_y + 21), self._time_str)

        if self._is_expanded:
            # Expanded media badge text
            painter.setPen(QColor("#FF43A8"))
            f2 = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
            painter.setFont(f2)
            painter.drawText(int(pill_x + 92), int(pill_y + 20), "• Now Playing")

            # Mini visualizer
            painter.setBrush(QBrush(QColor("#4EDEA3")))
            painter.drawRoundedRect(int(pill_x + pill_w - 30), int(pill_y + 11), 3, 10, 1.5, 1.5)
            painter.setBrush(QBrush(QColor("#FF43A8")))
            painter.drawRoundedRect(int(pill_x + pill_w - 24), int(pill_y + 8), 3, 16, 1.5, 1.5)
            painter.setBrush(QBrush(QColor("#DDB8FF")))
            painter.drawRoundedRect(int(pill_x + pill_w - 18), int(pill_y + 12), 3, 8, 1.5, 1.5)

        painter.end()


class AppearanceNotchPreview(QWidget):
    """
    Live Island Preview Card for Page 2 (Appearance & Theme).
    Displays the notch pill with cover art / surface reactive glow,
    hardware indicator, title text, and multi-colored equalizer bars.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)  # type: ignore[arg-type]
        self.setFixedHeight(140)
        self._theme_mode = "ambient"
        self._ambient_opacity = 0.25
        self._solid_color = QColor("#08080C")
        self._grad_color1 = QColor(24, 25, 32)
        self._grad_color2 = QColor(4, 4, 6)

    def update_theme(self, mode: str, opacity: float = 0.25, solid_col: Optional[QColor] = None,
                      grad_c1: Optional[QColor] = None, grad_c2: Optional[QColor] = None):
        self._theme_mode = mode
        self._ambient_opacity = opacity
        if solid_col:
            self._solid_color = solid_col
        if grad_c1 and grad_c2:
            self._grad_color1 = grad_c1
            self._grad_color2 = grad_c2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        # Inner well
        well_path = QPainterPath()
        well_path.addRoundedRect(QRectF(0, 0, w, h), 12.0, 12.0)
        painter.fillPath(well_path, QColor("#0E0E14"))
        painter.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        painter.drawPath(well_path)

        # Center notch dimensions
        notch_w = min(320.0, w - 80.0)
        notch_h = 38.0
        notch_x = (w - notch_w) / 2.0
        notch_y = (h - notch_h) / 2.0

        # Ambient Glow behind notch
        if self._ambient_opacity > 0:
            glow_rad = QRadialGradient(w / 2.0, h / 2.0, notch_w * 0.70)
            if self._theme_mode == "ambient":
                glow_col1 = QColor(255, 67, 168, int(220 * self._ambient_opacity))
                glow_col2 = QColor(124, 3, 211, 0)
            elif self._theme_mode == "gradient":
                glow_col1 = QColor(self._grad_color1.red(), self._grad_color1.green(), self._grad_color1.blue(), int(220 * self._ambient_opacity))
                glow_col2 = QColor(0, 0, 0, 0)
            else:
                glow_col1 = QColor(self._solid_color.red(), self._solid_color.green(), self._solid_color.blue(), int(200 * self._ambient_opacity))
                glow_col2 = QColor(0, 0, 0, 0)
            glow_rad.setColorAt(0.0, glow_col1)
            glow_rad.setColorAt(1.0, glow_col2)
            painter.setBrush(QBrush(glow_rad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(notch_x - 40), int(notch_y - 20), int(notch_w + 80), 78)

        # Notch pill body
        notch_rect = QRectF(notch_x, notch_y, notch_w, notch_h)
        if self._theme_mode == "ambient":
            grad = QLinearGradient(notch_x, notch_y, notch_x + notch_w, notch_y + notch_h)
            grad.setColorAt(0.0, QColor(25, 20, 32))
            grad.setColorAt(0.5, QColor(14, 14, 20))
            grad.setColorAt(1.0, QColor(8, 8, 12))
            painter.setBrush(QBrush(grad))
        elif self._theme_mode == "gradient":
            grad = QLinearGradient(notch_x, notch_y, notch_x + notch_w, notch_y)
            grad.setColorAt(0.0, self._grad_color1)
            grad.setColorAt(1.0, self._grad_color2)
            painter.setBrush(QBrush(grad))
        else:
            painter.setBrush(QBrush(self._solid_color))

        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        painter.drawRoundedRect(notch_rect, 19.0, 19.0)

        # Miniature content:
        # Left: glowing mint dot
        painter.setBrush(QBrush(QColor("#4EDEA3")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(notch_x + 16), int(notch_y + 14), 10, 10)

        # Center: title
        painter.setPen(QColor("#E4E1EA"))
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(QRectF(notch_x + 36, notch_y, notch_w - 90, notch_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "WindowLand Dynamic Island")

        # Right: 4 colored equalizer bars (pink, purple, mint, pink)
        bar_colors = [QColor("#FF43A8"), QColor("#DDB8FF"), QColor("#4EDEA3"), QColor("#FF43A8")]
        bar_heights = [10, 18, 12, 16]
        for i, (col, bh) in enumerate(zip(bar_colors, bar_heights)):
            painter.setBrush(QBrush(col))
            painter.drawRoundedRect(int(notch_x + notch_w - 42 + (i * 7)), int(notch_y + (notch_h - bh) / 2), 3, bh, 1.5, 1.5)

        painter.end()


class SettingsWindow(QMainWindow):
    """
    Ambient Glass Control Center Application for WindowLand Dynamic Island.
    Faithfully implements the DESIGN.md specifications and screen wireframes.
    """

    def __init__(self, island=None, media_service=None, system_service=None,
                 device_service=None, phone_service=None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.island = island
        self.media_service = media_service
        self.system_service = system_service
        self.device_service = device_service
        self.phone_service = phone_service

        self.cfg = settings.load()

        self.setWindowTitle("WindowLand • Control Center")
        self.setMinimumSize(960, 680)
        self.resize(1020, 720)

        # Center on primary screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            self.move(
                screen_geo.x() + (screen_geo.width() - self.width()) // 2,
                screen_geo.y() + (screen_geo.height() - self.height()) // 2
            )

        self._init_ui()
        self._apply_styles()
        self._sync_values_to_ui()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def _init_ui(self):
        root = AmbientCanvasWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Left Sidebar Navigation (DESIGN.md: w-[260px]) ──────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 24)
        sidebar_layout.setSpacing(10)

        # App Brand Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Rounded-xl gradient badge with tree symbol
        logo_frame = QFrame()
        logo_frame.setFixedSize(40, 40)
        logo_frame.setObjectName("brandLogoBadge")
        lf_layout = QVBoxLayout(logo_frame)
        lf_layout.setContentsMargins(0, 0, 0, 0)
        lbl_logo_icon = QLabel("🌲")
        lbl_logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_logo_icon.setStyleSheet("font-size: 20px; background: transparent;")
        lf_layout.addWidget(lbl_logo_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        lbl_title = QLabel("WindowLand")
        lbl_title.setStyleSheet("color: #E4E1EA; font-size: 16px; font-weight: 700; letter-spacing: -0.3px;")
        lbl_sub = QLabel("CONTROL CENTER")
        lbl_sub.setStyleSheet("color: #FFB0CF; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)

        header_layout.addWidget(logo_frame)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        sidebar_layout.addLayout(header_layout)

        sidebar_layout.addSpacing(22)

        # Nav Buttons
        self.nav_buttons = []
        nav_items = [
            ("tune", "⚙️", "General Island", 0),
            ("palette", "🎨", "Appearance Glow", 1),
            ("dock", "🗖", "Position Docking", 2),
            ("extension", "🧩", "Tools Companion", 3),
            ("monitoring", "📊", "Diagnostics Simulator", 4),
            ("info", "ℹ️", "About WindowLand", 5),
        ]

        for _, emoji_icon, label, idx in nav_items:
            btn = QPushButton(f"{emoji_icon}   {label}")
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_page(i))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # Dynamic Island Active Status Pill at bottom of sidebar
        status_box = QFrame()
        status_box.setObjectName("statusPill")
        sbox_layout = QHBoxLayout(status_box)
        sbox_layout.setContentsMargins(14, 8, 14, 8)
        sbox_layout.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet("color: #4EDEA3; font-size: 11px;")
        lbl_live = QLabel("Dynamic Island Active")
        lbl_live.setStyleSheet("color: #4EDEA3; font-size: 11.5px; font-weight: 700;")
        sbox_layout.addWidget(dot)
        sbox_layout.addWidget(lbl_live)
        sbox_layout.addStretch()
        sidebar_layout.addWidget(status_box)

        root_layout.addWidget(sidebar)

        # ── Main Content Container with Top Header Bar ───────────
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Header Bar (Avatar on right, live simulation indicator in diagnostics)
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(56)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(32, 8, 32, 8)

        # Top Header Live Status Pill (shown on Diagnostics page)
        self.top_status_pill = QFrame()
        self.top_status_pill.setObjectName("topStatusPill")
        tsp_layout = QHBoxLayout(self.top_status_pill)
        tsp_layout.setContentsMargins(14, 6, 14, 6)
        tsp_layout.setSpacing(8)

        tsp_icon = QLabel("📊")
        tsp_icon.setStyleSheet("font-size: 13px; color: #4EDEA3;")
        tsp_text_box = QVBoxLayout()
        tsp_text_box.setSpacing(0)
        self.tsp_title = QLabel("Dynamic Island Idle")
        self.tsp_title.setStyleSheet("color: #E4E1EA; font-size: 11.5px; font-weight: 600;")
        self.tsp_sub = QLabel("READY FOR SIMULATION")
        self.tsp_sub.setStyleSheet("color: #E0BEC9; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;")
        tsp_text_box.addWidget(self.tsp_title)
        tsp_text_box.addWidget(self.tsp_sub)

        tsp_dot = QLabel("●")
        tsp_dot.setStyleSheet("color: #4EDEA3; font-size: 10px;")

        tsp_layout.addWidget(tsp_icon)
        tsp_layout.addLayout(tsp_text_box)
        tsp_layout.addWidget(tsp_dot)
        self.top_status_pill.hide()

        tb_layout.addWidget(self.top_status_pill)
        tb_layout.addStretch()

        # User Avatar profile button
        avatar_btn = QLabel("👤")
        avatar_btn.setObjectName("avatarPill")
        avatar_btn.setFixedSize(32, 32)
        avatar_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_btn.setStyleSheet("""
            background: #FFB0CF;
            color: #63003C;
            border-radius: 16px;
            font-size: 14px;
        """)
        tb_layout.addWidget(avatar_btn)

        right_layout.addWidget(top_bar)

        # Main Pages Stack
        content_frame = QFrame()
        content_frame.setObjectName("contentArea")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(24, 16, 24, 20)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._create_general_page())
        self.pages.addWidget(self._create_appearance_page())
        self.pages.addWidget(self._create_docking_page())
        self.pages.addWidget(self._create_tools_page())
        self.pages.addWidget(self._create_diagnostics_page())
        self.pages.addWidget(self._create_about_page())

        content_layout.addWidget(self.pages)
        right_layout.addWidget(content_frame)

        root_layout.addWidget(right_container)

        self._switch_page(0)

    def _switch_page(self, index: int):
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if hasattr(self, "top_status_pill"):
            self.top_status_pill.setVisible(index == 4)

    # -------------------------------------------------------------
    # 1. Page: General Island Controls
    # -------------------------------------------------------------
    def _create_general_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(18)

        layout.addWidget(self._make_header(
            "General & Island Controls",
            "Manage island behavior, startup preferences, and primary triggers."
        ))

        # Card 1: Live Island Preview
        card_preview, cp_layout = self._make_card("Live Island Preview", right_badge="COMPACT NOTCH")
        self.gen_notch_preview = GeneralNotchPreview()
        cp_layout.addWidget(self.gen_notch_preview)
        layout.addWidget(card_preview)

        # Card 2: Quick Actions
        card_quick, cq_layout = self._make_card("Quick Actions")
        row_exp, self.btn_toggle_expand = self._make_control_row(
            "Expand / Collapse Island",
            "Instantly morph between compact notch and expanded music/multitasking view.",
            "Toggle Now"
        )
        self.btn_toggle_expand.clicked.connect(self._on_toggle_expand)
        cq_layout.addWidget(row_exp)

        row_rec, btn_recenter = self._make_control_row(
            "Recenter to Top Bezel",
            "Instantly snap the island back to the center of your primary top screen bezel.",
            "Recenter"
        )
        btn_recenter.clicked.connect(self._on_recenter)
        cq_layout.addWidget(row_rec)
        layout.addWidget(card_quick)

        # Card 3: Island Behavior
        card_beh, cb_layout = self._make_card("Island Behavior")

        # Auto-Hide
        row_auto, ra_lay = self._make_row_container()
        ra_text = QVBoxLayout()
        ra_text.setSpacing(2)
        ra_t = QLabel("Auto-Hide when Idle")
        ra_t.setStyleSheet("color: #E4E1EA; font-size: 14px; font-weight: 600;")
        ra_d = QLabel("Collapses the island into an ultra-thin hidden tab when idle. Expands smoothly on cursor hover.")
        ra_d.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        ra_text.addWidget(ra_t)
        ra_text.addWidget(ra_d)
        ra_lay.addLayout(ra_text, 1)

        self.switch_autohide = SwitchToggle(self.cfg.get("auto_hide", False))
        self.switch_autohide.toggled.connect(self._on_autohide_toggled)
        ra_lay.addWidget(self.switch_autohide, 0, Qt.AlignmentFlag.AlignVCenter)
        cb_layout.addWidget(row_auto)

        # Start with Windows
        row_start, rs_lay = self._make_row_container()
        rs_text = QVBoxLayout()
        rs_text.setSpacing(2)
        rs_t = QLabel("Start with Windows")
        rs_t.setStyleSheet("color: #E4E1EA; font-size: 14px; font-weight: 600;")
        rs_d = QLabel("Automatically launch WindowLand Dynamic Island when your PC starts.")
        rs_d.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        rs_text.addWidget(rs_t)
        rs_text.addWidget(rs_d)
        rs_lay.addLayout(rs_text, 1)

        self.switch_autostart = SwitchToggle(is_autostart_enabled())
        self.switch_autostart.toggled.connect(self._on_autostart_toggled)
        rs_lay.addWidget(self.switch_autostart, 0, Qt.AlignmentFlag.AlignVCenter)
        cb_layout.addWidget(row_start)

        # Clock Time Format
        row_clock, rc_lay = self._make_row_container()
        rc_text = QVBoxLayout()
        rc_text.setSpacing(2)
        rc_t = QLabel("Clock Time Format")
        rc_t.setStyleSheet("color: #E4E1EA; font-size: 14px; font-weight: 600;")
        rc_d = QLabel("Format used for the compact notch clock and schedule notifications.")
        rc_d.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        rc_text.addWidget(rc_t)
        rc_text.addWidget(rc_d)
        rc_lay.addLayout(rc_text, 1)

        self.combo_time = QComboBox()
        self.combo_time.addItems(["24-Hour (19:30)", "12-Hour (7:30 PM)"])
        cur_fmt = self.cfg.get("time_format", "24h")
        self.combo_time.setCurrentIndex(0 if cur_fmt == "24h" else 1)
        self.combo_time.currentIndexChanged.connect(self._on_time_format_changed)
        rc_lay.addWidget(self.combo_time, 0, Qt.AlignmentFlag.AlignVCenter)
        cb_layout.addWidget(row_clock)

        layout.addWidget(card_beh)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------
    # 2. Page: Appearance & Glow
    # -------------------------------------------------------------
    def _create_appearance_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(18)

        layout.addWidget(self._make_header(
            "Appearance & Theme",
            "Personalize surface materials, accent gradients, and ambient backlight glow."
        ))

        # Card 1: Live Preview
        card_prev, cp_layout = self._make_card("LIVE PREVIEW")
        self.app_notch_preview = AppearanceNotchPreview()
        cp_layout.addWidget(self.app_notch_preview)
        layout.addWidget(card_prev)

        # Card 2: Surface Material & Mode
        card_mat, cm_layout = self._make_card("SURFACE MATERIAL & MODE")
        mat_grid = QGridLayout()
        mat_grid.setSpacing(12)

        self.btn_ambient = self._make_material_tile("wb_sunny", "☀️", "Ambient Reactive", "(Dynamic Cover Art Glow)", "ambient")
        self.btn_obsidian = self._make_material_tile("contrast", "◐", "OLED Obsidian", "(Deep Black Glass)", "obsidian")
        self.btn_titanium = self._make_material_tile("blur_on", "▦", "Frosted Titanium", "(Dark Translucent Glass)", "titanium")

        mat_grid.addWidget(self.btn_ambient, 0, 0)
        mat_grid.addWidget(self.btn_obsidian, 0, 1)
        mat_grid.addWidget(self.btn_titanium, 0, 2)
        cm_layout.addLayout(mat_grid)
        layout.addWidget(card_mat)

        # Card 3: Solid Colors Palette
        card_sol, cs_layout = self._make_card("SOLID COLORS PALETTE")
        sol_grid = QGridLayout()
        sol_grid.setSpacing(10)

        swatch_items = [
            ("Obsidian Black", "#0E0E14"),
            ("Midnight Blue", "#2C0051"),
            ("Space Gray", "#35343B"),
            ("Deep Emerald", "#002113"),
            ("Royal Amethyst", "#490080"),
            ("Slate Titanium", "#393840"),
        ]

        self.swatch_buttons = []
        for i, (name, hex_code) in enumerate(swatch_items):
            btn = QPushButton(name)
            btn.setObjectName("swatchTile")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                background-color: {hex_code};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
                color: #E4E1EA;
                font-size: 13.5px;
                font-weight: 600;
                padding: 16px 12px;
            """)
            btn.clicked.connect(lambda checked=False, h=hex_code: self._set_solid_color(h))
            sol_grid.addWidget(btn, i // 3, i % 3)
            self.swatch_buttons.append(btn)

        cs_layout.addLayout(sol_grid)

        btn_custom = QPushButton("🎨  Pick Custom Color...")
        btn_custom.setObjectName("customColorBtn")
        btn_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_custom.clicked.connect(self._pick_custom_color)
        cs_layout.addWidget(btn_custom)
        layout.addWidget(card_sol)

        # Card 4: Ambient Glow Intensity Slider
        card_glow, cgl_layout = self._make_card("AMBIENT GLOW INTENSITY")
        gh = QHBoxLayout()
        gh_lbl = QLabel("Backlight Glow Opacity")
        gh_lbl.setStyleSheet("color: #E4E1EA; font-size: 13.5px; font-weight: 600;")
        self.lbl_glow_val = QLabel("25%")
        self.lbl_glow_val.setStyleSheet("color: #FF43A8; font-size: 14px; font-weight: 700;")
        gh.addWidget(gh_lbl)
        gh.addStretch()
        gh.addWidget(self.lbl_glow_val)
        cgl_layout.addLayout(gh)

        self.slider_glow = QSlider(Qt.Orientation.Horizontal)
        self.slider_glow.setRange(0, 50)
        cur_op = int(float(self.cfg.get("ambient_opacity", 0.25)) * 100)
        self.slider_glow.setValue(cur_op)
        self.lbl_glow_val.setText(f"{cur_op}%")
        self.slider_glow.valueChanged.connect(self._on_glow_slider_changed)
        cgl_layout.addWidget(self.slider_glow)

        quick_glows = QHBoxLayout()
        quick_glows.setSpacing(8)
        glow_presets = [("Disabled (0%)", 0), ("Subtle (15%)", 15), ("Balanced (25%)", 25), ("Vibrant (40%)", 40)]
        for label, val in glow_presets:
            btn = QPushButton(label)
            btn.setObjectName("secondaryActionBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=val: self.slider_glow.setValue(v))
            quick_glows.addWidget(btn)
        cgl_layout.addLayout(quick_glows)

        layout.addWidget(card_glow)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _make_material_tile(self, icon_id: str, emoji: str, title: str, subtitle: str, mode_key: str) -> QPushButton:
        btn = QPushButton(f"{emoji}  {title}\n{subtitle}")
        btn.setObjectName("materialTile")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._set_theme_mode(mode_key))
        return btn

    # -------------------------------------------------------------
    # 3. Page: Position & Docking
    # -------------------------------------------------------------
    def _create_docking_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(18)

        layout.addWidget(self._make_header(
            "Position & Docking",
            "Choose how the Dynamic Island anchors to your screen bezels, corners, or taskbar."
        ))

        # Card 1: Screen Docking Selector
        card_dock, cd_layout = self._make_card("SCREEN DOCKING SELECTOR")

        lbl_hint = QLabel("Select an anchor position on your desktop (the island will animate live to that edge):")
        lbl_hint.setStyleSheet("color: #94A3B8; font-size: 13px; margin-bottom: 4px;")
        cd_layout.addWidget(lbl_hint)

        well = QFrame()
        well.setObjectName("dockWell")
        w_layout = QGridLayout(well)
        w_layout.setContentsMargins(16, 16, 16, 16)
        w_layout.setSpacing(12)

        self.dock_buttons: Dict[str, QPushButton] = {}

        # 3x3 Grid
        btn_tl = self._make_dock_btn("Top-Left Corner", "↖", "top-left")
        btn_top = self._make_dock_btn("Top Bezel (Default)", "↑", "top")
        btn_tr = self._make_dock_btn("Top-Right Corner", "↗", "top-right")

        btn_left = self._make_dock_btn("Left Screen Edge", "←", "left")
        btn_float = self._make_dock_btn("Free Floating Anywhere", "✛", "floating")
        btn_right = self._make_dock_btn("Right Screen Edge", "→", "right")

        btn_bl = self._make_dock_btn("Bottom-Left Corner", "↙", "bottom-left")
        btn_bot = self._make_dock_btn("Bottom Taskbar Edge", "↓", "bottom")
        btn_br = self._make_dock_btn("Bottom-Right Corner", "↘", "bottom-right")

        w_layout.addWidget(btn_tl, 0, 0)
        w_layout.addWidget(btn_top, 0, 1)
        w_layout.addWidget(btn_tr, 0, 2)

        w_layout.addWidget(btn_left, 1, 0)
        w_layout.addWidget(btn_float, 1, 1)
        w_layout.addWidget(btn_right, 1, 2)

        w_layout.addWidget(btn_bl, 2, 0)
        w_layout.addWidget(btn_bot, 2, 1)
        w_layout.addWidget(btn_br, 2, 2)

        cd_layout.addWidget(well)

        btn_snap = QPushButton("🎯  Snap to Screen Center / Default Top")
        btn_snap.setObjectName("snapDefaultBtn")
        btn_snap.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_snap.clicked.connect(lambda: self._set_dock("top"))
        cd_layout.addWidget(btn_snap)

        layout.addWidget(card_dock)

        # Card 2: Display / Monitor
        card_mon, cm_layout = self._make_card("DISPLAY / MONITOR")
        row_mon, rm_lay = self._make_row_container()
        rm_left = QHBoxLayout()
        rm_left.setSpacing(10)
        rm_icon = QLabel("🖥️")
        rm_icon.setStyleSheet("font-size: 18px;")
        rm_lbl = QLabel("Target Display")
        rm_lbl.setStyleSheet("color: #E4E1EA; font-size: 14px; font-weight: 600;")
        rm_left.addWidget(rm_icon)
        rm_left.addWidget(rm_lbl)
        rm_lay.addLayout(rm_left)
        rm_lay.addStretch()

        self.combo_mon = QComboBox()
        screens = QGuiApplication.screens()
        for idx, s in enumerate(screens):
            geo = s.geometry()
            is_prim = " (Primary)" if s == QGuiApplication.primaryScreen() else ""
            self.combo_mon.addItem(f"Display {idx + 1}: {geo.width()}x{geo.height()}{is_prim}")

        cur_idx = min(int(self.cfg.get("screen_index", 0)), max(0, len(screens) - 1))
        self.combo_mon.setCurrentIndex(cur_idx)
        self.combo_mon.currentIndexChanged.connect(self._on_screen_changed)
        rm_lay.addWidget(self.combo_mon)
        cm_layout.addWidget(row_mon)

        layout.addWidget(card_mon)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _make_dock_btn(self, title: str, arrow: str, edge_key: str) -> QPushButton:
        btn = QPushButton(f"{arrow}  {title}")
        btn.setObjectName("dockBtn")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, e=edge_key: self._set_dock(e))
        self.dock_buttons[edge_key] = btn
        return btn

    # -------------------------------------------------------------
    # 4. Page: Tools Companion
    # -------------------------------------------------------------
    def _create_tools_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(18)

        layout.addWidget(self._make_header(
            "Tools & Phone Companion",
            "Access mobile notifications pairing, wireless companion dashboard, and quick desktop shortcuts."
        ))

        # Card 1: Phone Companion Dashboard
        card_phone, cp_layout = self._make_card("PHONE COMPANION DASHBOARD")
        p_desc = QLabel("Connect your iPhone (iOS Shortcuts) or Android device to mirror live phone notifications, calls, and 2FA codes directly onto your Windows Dynamic Island.")
        p_desc.setWordWrap(True)
        p_desc.setStyleSheet("color: #94A3B8; font-size: 13px; margin-bottom: 8px;")
        cp_layout.addWidget(p_desc)

        url_well = QFrame()
        url_well.setObjectName("urlWell")
        uw_layout = QHBoxLayout(url_well)
        uw_layout.setContentsMargins(16, 12, 16, 12)
        uw_layout.setSpacing(12)

        dot = QLabel("●")
        dot.setStyleSheet("color: #4EDEA3; font-size: 12px;")
        uw_layout.addWidget(dot)

        pairing_url = self.phone_service.pairing_url if self.phone_service else "http://192.168.1.2:54321"
        self.lbl_url = QLabel(pairing_url)
        self.lbl_url.setStyleSheet("color: #4EDEA3; font-family: 'Consolas', monospace; font-size: 14px; font-weight: 700;")
        uw_layout.addWidget(self.lbl_url)
        uw_layout.addStretch()

        btn_copy = QPushButton("📋  Copy Link")
        btn_copy.setObjectName("secondaryActionBtn")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_companion_url)
        uw_layout.addWidget(btn_copy)

        btn_open = QPushButton("↗  Open in Browser")
        btn_open.setObjectName("primaryGradientBtn")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(self._open_companion_url)
        uw_layout.addWidget(btn_open)

        cp_layout.addWidget(url_well)
        layout.addWidget(card_phone)

        # Card 2: Desktop Quick Actions
        card_quick, cq_layout = self._make_card("DESKTOP QUICK ACTIONS")

        row_snip = self._make_tile_row(
            icon_char="⛶", icon_color="#FFB0CF",
            title="Take Screenshot",
            desc="Capture region or screen and copy to clipboard immediately.",
            btn_text="Capture",
            callback=self._on_take_screenshot
        )
        cq_layout.addWidget(row_snip)

        row_mute = self._make_tile_row(
            icon_char="🔇", icon_color="#DDB8FF",
            title="Toggle Audio Mute",
            desc="Mute or unmute system audio master channel.",
            btn_text="Toggle Mute",
            callback=self._on_toggle_mute
        )
        cq_layout.addWidget(row_mute)

        row_dnd = self._make_tile_row(
            icon_char="⛔", icon_color="#4EDEA3",
            title="Toggle Do Not Disturb",
            desc="Silence non-critical notification toasts and incoming popups.",
            btn_text="Toggle DND",
            callback=self._on_toggle_dnd
        )
        cq_layout.addWidget(row_dnd)

        layout.addWidget(card_quick)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _make_tile_row(self, icon_char: str, icon_color: str, title: str, desc: str,
                       btn_text: str, callback) -> QFrame:
        row, layout = self._make_row_container()

        ibox = QFrame()
        ibox.setFixedSize(40, 40)
        ibox.setStyleSheet("background-color: #2A2930; border-radius: 10px; border: 1px solid rgba(255,255,255,0.06);")
        ib_lay = QVBoxLayout(ibox)
        ib_lay.setContentsMargins(0, 0, 0, 0)
        lbl_i = QLabel()
        lbl_i.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            from services.icon_service import get_app_icon
            pix = get_app_icon(title, target_size=24)
            if pix and not pix.isNull():
                lbl_i.setPixmap(pix)
            else:
                lbl_i.setText(icon_char)
                lbl_i.setStyleSheet(f"font-size: 18px; color: {icon_color};")
        except Exception:
            lbl_i.setText(icon_char)
            lbl_i.setStyleSheet(f"font-size: 18px; color: {icon_color};")
        ib_lay.addWidget(lbl_i)
        layout.addWidget(ibox)

        tb = QVBoxLayout()
        tb.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("color: #E4E1EA; font-size: 14px; font-weight: 600;")
        d = QLabel(desc)
        d.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        tb.addWidget(t)
        tb.addWidget(d)
        layout.addLayout(tb, 1)

        btn = QPushButton(btn_text)
        btn.setObjectName("secondaryActionBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(callback)
        layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return row

    # -------------------------------------------------------------
    # 5. Page: Diagnostics & Simulator
    # -------------------------------------------------------------
    def _create_diagnostics_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(18)

        layout.addWidget(self._make_header(
            "Diagnostics & Live Simulator",
            "Test all Dynamic Island morph states, HUD overlays, accessory connection popups, and alerts."
        ))

        card_sim, cs_layout = self._make_card("INTERACTIVE STATE SIMULATION DECK", right_badge="7 MORPH STATES")

        sim_items = [
            ("🔊", "#FFB0CF", "Volume OSD HUD", "Simulate liquid-glass volume slider overlay (72%)", lambda: self._sim_call("osd")),
            ("📞", "#FF43A8", "Incoming Phone Call", "Simulate live incoming call card with Accept / Decline controls", lambda: self._sim_call("call")),
            ("🔑", "#4EDEA3", "Two-Factor OTP Code", "Simulate 2FA verification code card with one-click copy button", lambda: self._sim_call("otp")),
            ("📁", "#DDB8FF", "File Shelf Drag Tray", "Simulate liquid drag-and-drop file stash tray", lambda: self._sim_call("shelf")),
            ("⬇️", "#FFB0CF", "Download Hairline Progress", "Simulate animated sub-2px progress line along bottom curve", lambda: self._sim_call("download")),
            ("📸", "#DDB8FF", "Snipping Tool Toast", "Simulate screenshot notification toast", lambda: self._sim_call("snip_toast")),
            ("📅", "#4EDEA3", "Calendar Event Toast", "Simulate calendar reminder alert toast", lambda: self._sim_call("cal_toast")),
            ("🎵", "#FF43A8", "Demo Music Track", "Toggle demo audio track to test cover art & visualizer", lambda: self._sim_call("demo_music")),
            ("🎧", "#4EDEA3", "AirPods Pro Connected", "Simulate AirPods device connected notification alert", lambda: self._sim_call("airpods")),
            ("🎧", "#DDB8FF", "Sony Headphones Connected", "Simulate Bluetooth headphones connected alert", lambda: self._sim_call("headphones")),
        ]

        for emoji, col, title, desc, action in sim_items:
            row = self._make_tile_row(emoji, col, title, desc, "Simulate", action)
            cs_layout.addWidget(row)

        layout.addWidget(card_sim)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------
    # 6. Page: About WindowLand
    # -------------------------------------------------------------
    def _create_about_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(18)

        layout.addWidget(self._make_header(
            "About WindowLand",
            "Product information, keyboard shortcuts, and application lifecycle controls."
        ))

        # Card 1: Application Details
        card_info, ci_layout = self._make_card("APPLICATION DETAILS")
        ih = QHBoxLayout()
        ih.setSpacing(16)

        ibox = QFrame()
        ibox.setFixedSize(64, 64)
        ibox.setObjectName("aboutLogoBadge")
        ib_layout = QVBoxLayout(ibox)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        lbl_ai = QLabel("🌲")
        lbl_ai.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ai.setStyleSheet("font-size: 32px; background: transparent;")
        ib_layout.addWidget(lbl_ai)
        ih.addWidget(ibox)

        it_box = QVBoxLayout()
        it_box.setSpacing(2)
        it_title = QLabel("WindowLand Dynamic Island")
        it_title.setStyleSheet("color: #E4E1EA; font-size: 18px; font-weight: 700;")
        it_desc = QLabel("Apple-grade hardware notch & liquid multitasking overlay for Windows 11 / 10.")
        it_desc.setStyleSheet("color: #94A3B8; font-size: 13px;")
        it_ver = QLabel("Version 2.0.0 • Windows 15 Fluent Architecture")
        it_ver.setStyleSheet("color: #FF43A8; font-size: 12px; font-weight: 700; margin-top: 4px;")
        it_box.addWidget(it_title)
        it_box.addWidget(it_desc)
        it_box.addWidget(it_ver)
        ih.addLayout(it_box)
        ih.addStretch()
        ci_layout.addLayout(ih)
        layout.addWidget(card_info)

        # Card 2: Keyboard Shortcuts & Gestures
        card_keys, ck_layout = self._make_card("KEYBOARD SHORTCUTS & GESTURES")
        shortcuts = [
            ("Alt + Space", "Expand or Collapse Dynamic Island from any application"),
            ("Right Click on Island", "Open this Settings & Control Center application"),
            ("Left Click & Drag", "Drag island to reposition or snap to any screen edge"),
            ("Mouse Hover (Auto-Hide)", "Peek & reveal hidden notch when cursor reaches bezel edge"),
            ("Click Album Art", "Cycle audio play / pause in expanded mode"),
        ]

        for k, d in shortcuts:
            row, r_lay = self._make_row_container()
            lbl_k = QLabel(k)
            lbl_k.setObjectName("kbdPill")
            lbl_k.setStyleSheet("background: #35343B; color: #DDB8FF; font-family: 'Consolas', monospace; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 8px;")
            lbl_d = QLabel(d)
            lbl_d.setStyleSheet("color: #E4E1EA; font-size: 13px;")
            r_lay.addWidget(lbl_k)
            r_lay.addSpacing(12)
            r_lay.addWidget(lbl_d)
            r_lay.addStretch()
            ck_layout.addWidget(row)

        layout.addWidget(card_keys)

        # Card 3: Session & Lifecycle
        card_exit, ce_layout = self._make_card("SESSION & LIFECYCLE")
        row_quit, rq_lay = self._make_row_container()
        rq_box = QVBoxLayout()
        rq_box.setSpacing(2)
        rq_t = QLabel("Quit WindowLand")
        rq_t.setStyleSheet("color: #E4E1EA; font-size: 14px; font-weight: 600;")
        rq_d = QLabel("Fully exit Dynamic Island background processes and system tray.")
        rq_d.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        rq_box.addWidget(rq_t)
        rq_box.addWidget(rq_d)
        rq_lay.addLayout(rq_box, 1)

        btn_quit = QPushButton("⏻  Quit Application")
        btn_quit.setObjectName("dangerBtn")
        btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_quit.clicked.connect(self._on_quit_app)
        rq_lay.addWidget(btn_quit, 0, Qt.AlignmentFlag.AlignVCenter)
        ce_layout.addWidget(row_quit)

        layout.addWidget(card_exit)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------
    # UI Building Blocks
    # -------------------------------------------------------------
    def _make_header(self, title: str, subtitle: str) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet("color: #E4E1EA; font-size: 26px; font-weight: 700; letter-spacing: -0.4px;")
        s = QLabel(subtitle)
        s.setStyleSheet("color: #94A3B8; font-size: 13.5px;")
        lay.addWidget(t)
        lay.addWidget(s)
        return box

    def _make_card(self, title: str, right_badge: Optional[str] = None) -> Tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        if title or right_badge:
            h = QHBoxLayout()
            h.setContentsMargins(0, 0, 0, 4)
            if title:
                t = QLabel(title.upper())
                t.setStyleSheet("color: #FF43A8; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
                h.addWidget(t)
            h.addStretch()
            if right_badge:
                b = QLabel(right_badge.upper())
                b.setStyleSheet("color: #4EDEA3; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
                h.addWidget(b)
            layout.addLayout(h)

        return card, layout

    def _make_row_container(self) -> Tuple[QFrame, QHBoxLayout]:
        row = QFrame()
        row.setObjectName("settingRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)
        return row, lay

    def _make_control_row(self, title: str, desc: str, action_text: str) -> Tuple[QFrame, QPushButton]:
        row, lay = self._make_row_container()

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #E4E1EA; font-size: 14px; font-weight: 600;")
        lbl_d = QLabel(desc)
        lbl_d.setStyleSheet("color: #94A3B8; font-size: 12.5px;")
        lbl_d.setWordWrap(True)
        text_layout.addWidget(lbl_t)
        text_layout.addWidget(lbl_d)

        lay.addLayout(text_layout, 1)

        btn = QPushButton(action_text)
        btn.setObjectName("secondaryActionBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return row, btn

    # -------------------------------------------------------------
    # Synchronization & Event Handlers (Live Dynamic Island Updates)
    # -------------------------------------------------------------
    def _sync_values_to_ui(self):
        edge = self.cfg.get("dock_edge", "top")
        for k, btn in self.dock_buttons.items():
            btn.setChecked(k == edge)

        theme = self.cfg.get("theme_mode", "ambient")
        self.btn_ambient.setChecked(theme == "ambient")
        self.btn_obsidian.setChecked(theme in ("obsidian", "solid"))
        self.btn_titanium.setChecked(theme == "titanium")

        op = float(self.cfg.get("ambient_opacity", 0.25))
        sol = QColor(str(self.cfg.get("solid_color", "#08080C")))
        self.app_notch_preview.update_theme(theme, op, sol)

    def _on_toggle_expand(self):
        if self.island:
            self.island.toggle_expanded()
            is_exp = getattr(self.island, "_island_state", "") == "expanded"
            self.btn_toggle_expand.setText("Collapse Now" if is_exp else "Toggle Now")
            self.gen_notch_preview.set_expanded(is_exp)
        else:
            self._send_http_cmd("/api/wake")

    def _on_recenter(self):
        self._set_dock("top")

    def _on_autohide_toggled(self, checked: bool):
        self.cfg["auto_hide"] = checked
        settings.set("auto_hide", checked)
        if self.island:
            self.island.toggle_auto_hide(checked)

    def _on_autostart_toggled(self, checked: bool):
        self.cfg["autostart"] = checked
        settings.set("autostart", checked)
        set_autostart(checked)

    def _on_time_format_changed(self, idx: int):
        val = "24h" if idx == 0 else "12h"
        self.cfg["time_format"] = val
        settings.set("time_format", val)
        self.gen_notch_preview.set_time_str("19:30" if idx == 0 else "7:30 PM")

    def _set_theme_mode(self, mode: str):
        self.cfg["theme_mode"] = mode
        settings.set("theme_mode", mode)
        self.btn_ambient.setChecked(mode == "ambient")
        self.btn_obsidian.setChecked(mode == "obsidian")
        self.btn_titanium.setChecked(mode == "titanium")

        if mode == "ambient":
            op = float(self.cfg.get("ambient_opacity", 0.25))
            if self.island:
                self.island.set_theme_ambient(op)
            self.app_notch_preview.update_theme("ambient", op)
        elif mode == "obsidian":
            c = QColor("#08080C")
            if self.island:
                self.island.set_theme_solid(c)
            self.app_notch_preview.update_theme("solid", 0.0, c)
        elif mode == "titanium":
            c = QColor("#181A22")
            if self.island:
                self.island.set_theme_solid(c)
            self.app_notch_preview.update_theme("solid", 0.15, c)

    def _set_solid_color(self, hex_code: str):
        c = QColor(hex_code)
        self.cfg["solid_color"] = hex_code
        self.cfg["theme_mode"] = "solid"
        settings.update({"solid_color": hex_code, "theme_mode": "solid"})
        if self.island:
            self.island.set_theme_solid(c)
        self.app_notch_preview.update_theme("solid", 0.0, c)
        self.btn_obsidian.setChecked(True)

    def _pick_custom_color(self):
        c = QColorDialog.getColor(QColor("#08080C"), self, "Select Custom Island Color")
        if c.isValid():
            self._set_solid_color(c.name())

    def _on_glow_slider_changed(self, val: int):
        self.lbl_glow_val.setText(f"{val}%")
        op = val / 100.0
        self.cfg["ambient_opacity"] = op
        settings.set("ambient_opacity", op)
        if self.island:
            self.island.set_ambient_opacity(op)
        mode = self.cfg.get("theme_mode", "ambient")
        self.app_notch_preview.update_theme(mode, op)

    def _set_dock(self, edge: str):
        self.cfg["dock_edge"] = edge
        settings.set("dock_edge", edge)

        for k, btn in self.dock_buttons.items():
            btn.setChecked(k == edge)

        if self.island:
            self.island._dock_edge = edge
            self.island._target_morph = 1.0 if edge != "floating" else 0.0
            self.island._dock_ratio_x = 0.5
            self.island._dock_ratio_y = 0.5
            self.island._apply_geometry_for_state(self.island._island_state, animate=True)
            self.island.save_current_settings()
            self.island.update()
        else:
            self._send_http_cmd(f"/api/dock?edge={edge}")

    def _on_screen_changed(self, idx: int):
        self.cfg["screen_index"] = idx
        settings.set("screen_index", idx)
        if self.island:
            screens = QGuiApplication.screens()
            if 0 <= idx < len(screens):
                s_geo = screens[idx].geometry()
                self.island.move(s_geo.center())
                self.island._apply_geometry_for_state(self.island._island_state, animate=True)
                self.island.save_current_settings()

    def _copy_companion_url(self):
        url = self.lbl_url.text()
        clip = QGuiApplication.clipboard()
        if clip:
            clip.setText(url)
        QMessageBox.information(self, "Copied", f"Copied pairing link to clipboard:\n{url}")

    def _open_companion_url(self):
        QDesktopServices.openUrl(QUrl(self.lbl_url.text()))

    def _on_take_screenshot(self):
        if self.system_service:
            self.system_service.take_screenshot()

    def _on_toggle_mute(self):
        if self.system_service:
            self.system_service.toggle_mute()

    def _on_toggle_dnd(self):
        if self.system_service:
            self.system_service.toggle_dnd()

    def _sim_call(self, kind: str):
        if hasattr(self, "tsp_title"):
            self.tsp_title.setText(f"Simulating: {kind.upper()}")
            QTimer.singleShot(2500, lambda: self.tsp_title.setText("Dynamic Island Idle"))

        if kind == "osd":
            if self.island:
                self.island.trigger_osd("Volume", 0.72, "72%", "volume")
            else:
                self._send_http_cmd("/api/simulate?kind=osd")
        elif kind == "call":
            if self.island:
                self.island.trigger_call("Mom", "+1 (555) 234-5678", "iPhone • Incoming Call")
            else:
                self._send_http_cmd("/api/simulate?kind=call")
        elif kind == "otp":
            if self.island:
                self.island.trigger_otp("482 910", "Messages")
            else:
                self._send_http_cmd("/api/simulate?kind=otp")
        elif kind == "shelf":
            if self.island:
                self.island.trigger_file_shelf()
            else:
                self._send_http_cmd("/api/simulate?kind=shelf")
        elif kind == "download":
            if self.island:
                self.island.set_download_progress(0.75)
            else:
                self._send_http_cmd("/api/simulate?kind=download")
        elif kind == "snip_toast":
            if self.system_service:
                self.system_service.trigger_test_notification("Snipping Tool", "Screenshot copied to clipboard", "Saved to screenshots folder.")
        elif kind == "cal_toast":
            if self.system_service:
                self.system_service.trigger_test_notification("Calendar", "12:30 PM Architecture Review", "Starts in 5 minutes.")
        elif kind == "demo_music":
            if self.media_service:
                self.media_service.toggle_mock_mode()
        elif kind == "airpods":
            if self.device_service:
                self.device_service.trigger_simulated_device("airpods", "Manu's AirPods Pro")
        elif kind == "headphones":
            if self.device_service:
                self.device_service.trigger_simulated_device("headphones", "Sony WH-1000XM5")

    def _send_http_cmd(self, path: str):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:54321{path}")
            urllib.request.urlopen(req, timeout=1.0)
        except Exception:
            pass

    def _on_quit_app(self):
        reply = QMessageBox.question(
            self,
            "Quit WindowLand",
            "Are you sure you want to quit WindowLand Dynamic Island?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            app_inst = QApplication.instance()
            if app_inst:
                app_inst.quit()
            os._exit(0)

    # -------------------------------------------------------------
    # Visual Stylesheet: DESIGN.md Ambient Glass Specification
    # -------------------------------------------------------------
    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0E0E14;
            }
            #sidebar {
                background-color: rgba(31, 31, 38, 0.70);
                border-right: 1px solid rgba(89, 64, 73, 0.35);
            }
            #topBar {
                background-color: rgba(19, 19, 25, 0.60);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
            #contentArea {
                background-color: transparent;
            }
            #brandLogoBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF43A8, stop:1 #7C03D3);
                border-radius: 12px;
            }
            #aboutLogoBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255, 67, 168, 0.3), stop:0.5 rgba(124, 3, 211, 0.3), stop:1 rgba(78, 222, 163, 0.25));
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }
            #settingsCard {
                background-color: rgba(31, 31, 38, 0.65);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
            }
            #settingRow {
                background-color: rgba(42, 41, 48, 0.40);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
            }
            #settingRow:hover {
                background-color: rgba(42, 41, 48, 0.75);
                border-color: rgba(255, 67, 168, 0.20);
            }
            #dockWell, #urlWell {
                background-color: #0E0E14;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            #statusPill {
                background-color: rgba(0, 165, 114, 0.15);
                border: 1px solid rgba(78, 222, 163, 0.30);
                border-radius: 14px;
            }
            #topStatusPill {
                background-color: rgba(14, 14, 20, 0.90);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 18px;
            }
            #navBtn {
                text-align: left;
                padding: 10px 14px;
                border-radius: 10px;
                color: #E0BEC9;
                font-size: 13px;
                font-weight: 500;
                border: none;
                background-color: transparent;
            }
            #navBtn:hover {
                background-color: #2A2930;
                color: #E4E1EA;
            }
            #navBtn:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF43A8, stop:1 #7C03D3);
                color: #FFFFFF;
                font-weight: 700;
            }
            #secondaryActionBtn {
                background-color: rgba(53, 52, 59, 0.70);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
                color: #E4E1EA;
                font-size: 13px;
                font-weight: 600;
                padding: 7px 16px;
            }
            #secondaryActionBtn:hover {
                background-color: #393840;
                border-color: rgba(255, 67, 168, 0.40);
                color: #FFFFFF;
            }
            #secondaryActionBtn:pressed {
                background-color: #2A2930;
            }
            #primaryGradientBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF43A8, stop:1 #7C03D3);
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
                padding: 7px 18px;
            }
            #primaryGradientBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF5DAF, stop:1 #8F1EE6);
            }
            #materialTile {
                background-color: rgba(42, 41, 48, 0.50);
                border: 1.5px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                color: #E4E1EA;
                font-size: 13.5px;
                font-weight: 600;
                padding: 16px 12px;
                text-align: center;
            }
            #materialTile:hover {
                background-color: rgba(42, 41, 48, 0.80);
                border-color: rgba(255, 67, 168, 0.40);
            }
            #materialTile:checked {
                background-color: rgba(42, 41, 48, 0.85);
                border: 1.5px solid #FF43A8;
                color: #FFFFFF;
            }
            #swatchTile:hover {
                border: 2px solid #FF43A8 !important;
            }
            #customColorBtn {
                background-color: rgba(42, 41, 48, 0.50);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                color: #E4E1EA;
                font-size: 13.5px;
                font-weight: 600;
                padding: 14px 16px;
            }
            #customColorBtn:hover {
                background-color: rgba(42, 41, 48, 0.80);
                border-color: #FF43A8;
            }
            #dockBtn {
                background-color: rgba(42, 41, 48, 0.60);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                color: #E0BEC9;
                font-size: 13px;
                font-weight: 600;
                padding: 14px 10px;
            }
            #dockBtn:hover {
                background-color: rgba(53, 52, 59, 0.80);
                color: #E4E1EA;
                border-color: rgba(255, 67, 168, 0.30);
            }
            #dockBtn:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255, 67, 168, 0.25), stop:1 rgba(124, 3, 211, 0.25));
                border: 1.5px solid #FF43A8;
                color: #FFFFFF;
                font-weight: 700;
            }
            #snapDefaultBtn {
                background-color: rgba(42, 41, 48, 0.70);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 10px;
                color: #E4E1EA;
                font-size: 13.5px;
                font-weight: 600;
                padding: 12px 16px;
            }
            #snapDefaultBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255, 67, 168, 0.20), stop:1 rgba(124, 3, 211, 0.20));
                border-color: #FF43A8;
                color: #FFFFFF;
            }
            #dangerBtn {
                background-color: rgba(147, 0, 10, 0.40);
                border: 1px solid rgba(255, 180, 171, 0.30);
                border-radius: 8px;
                color: #FFB4AB;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 20px;
            }
            #dangerBtn:hover {
                background-color: rgba(147, 0, 10, 0.75);
                color: #FFFFFF;
            }
            QComboBox {
                background-color: rgba(53, 52, 59, 0.70);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: #E4E1EA;
                padding: 6px 14px;
                font-size: 13px;
                min-width: 190px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1F1F26;
                border: 1px solid #FF43A8;
                selection-background-color: #FF43A8;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 6px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2A2930;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF43A8, stop:1 #7C03D3);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 18px;
                margin-top: -6px;
                margin-bottom: -6px;
                border-radius: 9px;
                border: 2px solid #FF43A8;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                min-height: 25px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #FF43A8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())
