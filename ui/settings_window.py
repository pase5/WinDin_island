"""
WindowLand Dynamic Island — Minimal Obsidian Control Center.
Clean, fast, distraction-free settings UI matching the Dynamic Island aesthetic:
- Deep Obsidian canvas (#09090D) with subtle frosted surfaces (#121218 / #17171F)
- Crisp 1px hairlines (rgba(255, 255, 255, 0.08)) and Apple-grade accent tokens
- 4 focused sections: General, Appearance, Position, Phone & Tools
- Zero system emojis (Rule 1), defensive painting (Rule 3), live atomic sync
"""

import os
import sys
import urllib.request
from typing import Optional, Dict

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QScrollArea, QSlider, QComboBox,
    QColorDialog, QMessageBox, QGridLayout, QButtonGroup
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QFont, QDesktopServices, QGuiApplication, QIcon
)

from services.settings_service import settings
from services.autostart_service import is_autostart_enabled, set_autostart
from services.icon_service import render_vector_ui_icon, render_brand_logo


ACCENT_BLUE = "#0A84FF"
ACCENT_GREEN = "#34C759"
BG_ROOT = "#09090D"
BG_SIDEBAR = "#0E0E14"
BG_CARD = "#13131A"
BG_CONTROL = "#1B1B24"
BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"


class SwitchToggle(QWidget):
    """Minimal pill toggle switch matching macOS / iOS control aesthetics."""
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(42, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, emit: bool = False):
        checked = bool(checked)
        if self._checked != checked:
            self._checked = checked
            self.update()
            if emit:
                self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked, emit=True)

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = float(self.width()), float(self.height())
            if self._checked:
                painter.setBrush(QBrush(QColor(ACCENT_GREEN)))
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                painter.setBrush(QBrush(QColor(255, 255, 255, 28)))
                painter.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
            painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), (h - 1.0) / 2.0, (h - 1.0) / 2.0)

            thumb_d = h - 6.0
            thumb_x = (w - thumb_d - 3.0) if self._checked else 3.0
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(thumb_x, 3.0, thumb_d, thumb_d))
            painter.end()
        except Exception:
            pass


class SettingsWindow(QMainWindow):
    """Clean, simple Obsidian Control Center for WindowLand Dynamic Island."""

    def __init__(
        self,
        island=None,
        media_service=None,
        system_service=None,
        device_service=None,
        phone_service=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.island = island
        self.media_service = media_service
        self.system_service = system_service
        self.device_service = device_service
        self.phone_service = phone_service
        self.cfg = settings.load()

        self.setWindowTitle("WindowLand Settings")
        self.resize(820, 560)
        self.setMinimumSize(720, 500)

        ico_path = os.path.join(_PROJECT_ROOT, "assets", "app_icon.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        self._apply_global_styles()
        self._build_ui()
        self._sync_values_to_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.cfg = settings.load()
        self._sync_values_to_ui()

    def _apply_global_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {BG_ROOT};
                color: #F2F2F7;
                font-family: "Segoe UI", "Inter", sans-serif;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 0.14);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255, 255, 255, 0.25);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QComboBox {{
                background-color: {BG_CONTROL};
                color: #F2F2F7;
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
                padding: 5px 12px;
                font-size: 12px;
                min-width: 130px;
            }}
            QComboBox:hover {{
                border: 1px solid rgba(255, 255, 255, 0.20);
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {BG_CARD};
                color: #F2F2F7;
                border: 1px solid rgba(255, 255, 255, 0.14);
                selection-background-color: {ACCENT_BLUE};
                outline: none;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT_BLUE};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
        """)

    def _build_ui(self):
        root = QWidget(self)
        root.setStyleSheet(f"background-color: {BG_ROOT};")
        self.setCentralWidget(root)

        main_lay = QHBoxLayout(root)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────
        sidebar = QFrame(root)
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SIDEBAR};
                border-right: 1px solid {BORDER_SUBTLE};
            }}
        """)
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(14, 20, 14, 16)
        sb_lay.setSpacing(6)

        # Brand Header
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        logo_lbl = QLabel(sidebar)
        logo_lbl.setFixedSize(28, 28)
        logo_lbl.setStyleSheet("border: none; background: transparent;")
        try:
            logo_lbl.setPixmap(render_brand_logo(28))
        except Exception:
            pass
        brand_row.addWidget(logo_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        lbl_brand = QLabel("WindowLand", sidebar)
        lbl_brand.setStyleSheet("font-size: 14px; font-weight: 700; color: #FFFFFF; border: none; background: transparent;")
        lbl_sub = QLabel("Settings", sidebar)
        lbl_sub.setStyleSheet("font-size: 11px; color: #8E8E93; border: none; background: transparent;")
        title_col.addWidget(lbl_brand)
        title_col.addWidget(lbl_sub)
        brand_row.addLayout(title_col)
        brand_row.addStretch()
        sb_lay.addLayout(brand_row)
        sb_lay.addSpacing(14)

        self.nav_buttons = []
        nav_items = [
            ("General", "settings"),
            ("Appearance", "palette"),
            ("Position", "dock"),
            ("Phone & Tools", "phone"),
        ]
        for idx, (label, icon_name) in enumerate(nav_items):
            btn = QPushButton(f"  {label}", sidebar)
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            try:
                btn.setIcon(QIcon(render_vector_ui_icon(icon_name, 16, "#E5E5EA")))
            except Exception:
                pass
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    padding: 0 12px;
                    border-radius: 9px;
                    border: none;
                    background: transparent;
                    color: #A1A1AA;
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #FFFFFF;
                }}
                QPushButton:checked {{
                    background-color: rgba(255, 255, 255, 0.11);
                    color: #FFFFFF;
                    font-weight: 600;
                }}
            """)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            sb_lay.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_lay.addStretch()

        # Subtle version footer
        lbl_ver = QLabel("Dynamic Island v2.0", sidebar)
        lbl_ver.setStyleSheet("font-size: 11px; color: #636366; padding-left: 6px; border: none; background: transparent;")
        sb_lay.addWidget(lbl_ver)

        main_lay.addWidget(sidebar)

        # ── Content Stack ─────────────────────────────────────────
        self.stack = QStackedWidget(root)
        self.stack.addWidget(self._wrap_scroll(self._build_general_page()))
        self.stack.addWidget(self._wrap_scroll(self._build_appearance_page()))
        self.stack.addWidget(self._wrap_scroll(self._build_position_page()))
        self.stack.addWidget(self._wrap_scroll(self._build_tools_page()))
        main_lay.addWidget(self.stack, 1)

        self._switch_page(0)

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)
        if idx == 3:
            self._refresh_phone_status()

    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    # ── UI Helpers ────────────────────────────────────────────────
    def _make_page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setStyleSheet(f"background-color: {BG_ROOT};")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QVBoxLayout()
        hdr.setSpacing(3)
        lbl_t = QLabel(title, page)
        lbl_t.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF;")
        lbl_s = QLabel(subtitle, page)
        lbl_s.setStyleSheet("font-size: 12px; color: #8E8E93;")
        hdr.addWidget(lbl_t)
        hdr.addWidget(lbl_s)
        lay.addLayout(hdr)
        return page, lay

    def _make_card(self, section_title: Optional[str] = None) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        if section_title:
            lbl = QLabel(section_title.upper(), card)
            lbl.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.8px; color: #8E8E93; border: none; background: transparent;")
            lay.addWidget(lbl)
        return card, lay

    def _make_row(self, title: str, desc: str, control: QWidget) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent; border: none;")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(16)

        txt = QVBoxLayout()
        txt.setSpacing(2)
        lbl_t = QLabel(title, row)
        lbl_t.setStyleSheet("font-size: 13px; font-weight: 600; color: #F2F2F7; border: none;")
        lbl_d = QLabel(desc, row)
        lbl_d.setWordWrap(True)
        lbl_d.setStyleSheet("font-size: 11px; color: #8E8E93; border: none;")
        txt.addWidget(lbl_t)
        txt.addWidget(lbl_d)
        lay.addLayout(txt, 1)
        lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 0.06); border: none;")
        return line

    def _make_btn(self, text: str, primary: bool = False, danger: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(30)
        if primary:
            bg, fg, border, hover = ACCENT_BLUE, "#FFFFFF", "transparent", "#2594FF"
        elif danger:
            bg, fg, border, hover = "rgba(255, 69, 58, 0.14)", "#FF453A", "rgba(255, 69, 58, 0.35)", "rgba(255, 69, 58, 0.25)"
        else:
            bg, fg, border, hover = BG_CONTROL, "#F2F2F7", BORDER_SUBTLE, "#262632"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)
        return btn

    # ── Page 1: General ───────────────────────────────────────────
    def _build_general_page(self) -> QWidget:
        page, lay = self._make_page("General", "Control Dynamic Island behavior and system startup.")

        c1, c1_lay = self._make_card("Quick Controls")
        self.btn_toggle_expand = self._make_btn("Toggle Expand", primary=True)
        self.btn_toggle_expand.clicked.connect(self._on_toggle_expand)
        c1_lay.addWidget(self._make_row(
            "Expand / Collapse Island",
            "Morph between the compact notch and expanded dashboard.",
            self.btn_toggle_expand
        ))
        c1_lay.addWidget(self._make_divider())

        btn_recenter = self._make_btn("Recenter")
        btn_recenter.clicked.connect(lambda: self._set_dock("top"))
        c1_lay.addWidget(self._make_row(
            "Recenter to Top Bezel",
            "Snap the island back to the top center of your primary display.",
            btn_recenter
        ))
        lay.addWidget(c1)

        c2, c2_lay = self._make_card("Behavior & Startup")
        self.sw_hover_expand = SwitchToggle(bool(self.cfg.get("hover_to_expand", True)))
        self.sw_hover_expand.toggled.connect(self._on_hover_expand_toggled)
        c2_lay.addWidget(self._make_row(
            "Hover to Expand",
            "Automatically expand the island when your cursor rests on it.",
            self.sw_hover_expand
        ))
        c2_lay.addWidget(self._make_divider())

        self.sw_autohide = SwitchToggle(bool(self.cfg.get("auto_hide", False)))
        self.sw_autohide.toggled.connect(self._on_autohide_toggled)
        c2_lay.addWidget(self._make_row(
            "Auto-Hide When Idle",
            "Tucks the compact pill into a subtle edge handle until hovered.",
            self.sw_autohide
        ))
        c2_lay.addWidget(self._make_divider())

        self.sw_autostart = SwitchToggle(is_autostart_enabled())
        self.sw_autostart.toggled.connect(self._on_autostart_toggled)
        c2_lay.addWidget(self._make_row(
            "Launch at Windows Startup",
            "Automatically start WindowLand when you sign in to Windows.",
            self.sw_autostart
        ))
        c2_lay.addWidget(self._make_divider())

        self.cmb_time_format = QComboBox()
        self.cmb_time_format.addItems(["24-Hour (19:30)", "12-Hour (7:30 PM)"])
        self.cmb_time_format.currentIndexChanged.connect(self._on_time_format_changed)
        c2_lay.addWidget(self._make_row(
            "Clock Format",
            "Choose how time is displayed on the compact notch.",
            self.cmb_time_format
        ))
        lay.addWidget(c2)

        c3, c3_lay = self._make_card("Application")
        btn_quit = self._make_btn("Quit WindowLand", danger=True)
        btn_quit.clicked.connect(self._on_quit_app)
        c3_lay.addWidget(self._make_row(
            "Exit Application",
            "Cleanly stop background audio listeners and close WindowLand.",
            btn_quit
        ))
        lay.addWidget(c3)

        lay.addStretch()
        return page

    # ── Page 2: Appearance ────────────────────────────────────────
    THEME_PRESETS = [
        ("ambient", "Ambient Reactive", "ambient", "#08080C", "#08080C"),
        ("obsidian", "Pure Obsidian", "solid", "#08080C", "#08080C"),
        ("titanium", "Titanium", "solid", "#181A22", "#181A22"),
        ("midnight", "Midnight Ocean", "gradient", "#0A1628", "#050912"),
        ("emerald", "Emerald Forest", "gradient", "#081C15", "#040B09"),
        ("ember", "Sunset Ember", "gradient", "#231116", "#0B0709"),
        ("violet", "Violet Dusk", "gradient", "#1A102B", "#08060E"),
        ("slate", "Frosted Slate", "gradient", "#222530", "#101218"),
    ]

    def _build_appearance_page(self) -> QWidget:
        page, lay = self._make_page("Appearance", "Customize surface presets, custom colors, clock accent, and glow.")

        c1, c1_lay = self._make_card("Theme Presets")
        preset_grid = QGridLayout()
        preset_grid.setSpacing(8)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self.theme_buttons: Dict[str, QPushButton] = {}

        for idx, (key, label, mode, c1_hex, c2_hex) in enumerate(self.THEME_PRESETS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BG_CONTROL};
                    color: #A1A1AA;
                    border: 1px solid {BORDER_SUBTLE};
                    border-radius: 9px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    color: #FFFFFF;
                    border-color: rgba(255, 255, 255, 0.20);
                }}
                QPushButton:checked {{
                    background-color: {ACCENT_BLUE};
                    color: #FFFFFF;
                    border-color: {ACCENT_BLUE};
                }}
            """)
            btn.clicked.connect(lambda _, p=key: self._apply_theme_preset(p))
            self._theme_group.addButton(btn)
            self.theme_buttons[key] = btn
            preset_grid.addWidget(btn, idx // 4, idx % 4)
        c1_lay.addLayout(preset_grid)

        c1_lay.addWidget(self._make_divider())

        # Custom Solid Tint & Dual Gradient
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(8)
        lbl_sw = QLabel("Custom Finish", page)
        lbl_sw.setStyleSheet("font-size: 13px; font-weight: 600; color: #F2F2F7; border: none;")
        swatch_row.addWidget(lbl_sw)
        swatch_row.addStretch()

        for hex_col in ["#08080C", "#11131A", "#181A22", "#1A1423", "#0D1A18", "#1F1418"]:
            sw = QPushButton()
            sw.setFixedSize(22, 22)
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            sw.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_col};
                    border: 1px solid rgba(255, 255, 255, 0.22);
                    border-radius: 11px;
                }}
                QPushButton:hover {{
                    border: 2px solid #FFFFFF;
                }}
            """)
            sw.clicked.connect(lambda _, hx=hex_col: self._set_solid_color(hx))
            swatch_row.addWidget(sw)

        btn_pick = self._make_btn("Solid...")
        btn_pick.clicked.connect(self._pick_custom_color)
        swatch_row.addWidget(btn_pick)

        btn_grad = self._make_btn("Gradient...")
        btn_grad.clicked.connect(self._pick_custom_gradient)
        swatch_row.addWidget(btn_grad)
        c1_lay.addLayout(swatch_row)
        lay.addWidget(c1)

        # Clock Accent Color
        c_clk, c_clk_lay = self._make_card("Clock Accent")
        clk_row = QHBoxLayout()
        clk_row.setSpacing(8)
        lbl_clk = QLabel("Minute Accent Color", page)
        lbl_clk.setStyleSheet("font-size: 13px; font-weight: 600; color: #F2F2F7; border: none;")
        clk_row.addWidget(lbl_clk)
        clk_row.addStretch()

        self.clock_accent_buttons: Dict[str, QPushButton] = {}
        btn_auto_clk = self._make_btn("Auto")
        btn_auto_clk.setCheckable(True)
        btn_auto_clk.clicked.connect(lambda: self._set_clock_accent("auto"))
        self.clock_accent_buttons["auto"] = btn_auto_clk
        clk_row.addWidget(btn_auto_clk)

        for hx in ["#FF9F0A", "#34C759", "#0A84FF", "#BF5AF2", "#FF375F", "#FFFFFF"]:
            cb = QPushButton()
            cb.setCheckable(True)
            cb.setFixedSize(22, 22)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hx};
                    border: 1px solid rgba(255, 255, 255, 0.25);
                    border-radius: 11px;
                }}
                QPushButton:hover {{
                    border: 2px solid #FFFFFF;
                }}
                QPushButton:checked {{
                    border: 2px solid #FFFFFF;
                }}
            """)
            cb.clicked.connect(lambda _, c=hx: self._set_clock_accent(c))
            self.clock_accent_buttons[hx] = cb
            clk_row.addWidget(cb)
        c_clk_lay.addLayout(clk_row)
        lay.addWidget(c_clk)

        # Ambient Glow Intensity & Specular Rim
        c2, c2_lay = self._make_card("Glow & Edge Rim")
        slider_row = QHBoxLayout()
        slider_row.setSpacing(14)

        self.slider_glow = QSlider(Qt.Orientation.Horizontal)
        self.slider_glow.setRange(0, 100)
        self.slider_glow.valueChanged.connect(self._on_glow_slider_changed)

        self.lbl_glow_val = QLabel("24%")
        self.lbl_glow_val.setFixedWidth(38)
        self.lbl_glow_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_glow_val.setStyleSheet("font-size: 12px; font-weight: 600; color: #F2F2F7; border: none;")

        slider_row.addWidget(self.slider_glow, 1)
        slider_row.addWidget(self.lbl_glow_val)
        c2_lay.addWidget(self._make_row(
            "Reactive Album & Edge Glow",
            "Controls how strongly album art and status colors illuminate the island.",
            QWidget()
        ))
        c2_lay.addLayout(slider_row)
        c2_lay.addWidget(self._make_divider())

        self.sw_border = SwitchToggle(bool(self.cfg.get("show_border", True)))
        self.sw_border.toggled.connect(self._on_border_toggled)
        c2_lay.addWidget(self._make_row(
            "Specular Rim Highlight",
            "Displays a subtle luminous hairline along the screen bezel edge.",
            self.sw_border
        ))
        lay.addWidget(c2)

        lay.addStretch()
        return page

    # ── Page 3: Position ──────────────────────────────────────────
    def _build_position_page(self) -> QWidget:
        page, lay = self._make_page("Position & Docking", "Snap the Dynamic Island to any screen edge, corner, or float freely.")

        c1, c1_lay = self._make_card("Screen Bezel Map")
        grid_frame = QFrame()
        grid_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_ROOT};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 12px;
            }}
        """)
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(8)

        self.dock_buttons: Dict[str, QPushButton] = {}
        positions = [
            ("top-left", "Top Left", 0, 0),
            ("top", "Top Center", 0, 1),
            ("top-right", "Top Right", 0, 2),
            ("left", "Left Edge", 1, 0),
            ("floating", "Floating Pill", 1, 1),
            ("right", "Right Edge", 1, 2),
            ("bottom-left", "Bottom Left", 2, 0),
            ("bottom", "Bottom Center", 2, 1),
            ("bottom-right", "Bottom Right", 2, 2),
        ]
        for key, label, r, c in positions:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BG_CONTROL};
                    color: #A1A1AA;
                    border: 1px solid {BORDER_SUBTLE};
                    border-radius: 9px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    color: #FFFFFF;
                    border-color: rgba(255, 255, 255, 0.22);
                }}
                QPushButton:checked {{
                    background-color: {ACCENT_BLUE};
                    color: #FFFFFF;
                    border-color: {ACCENT_BLUE};
                }}
            """)
            btn.clicked.connect(lambda _, e=key: self._set_dock(e))
            grid.addWidget(btn, r, c)
            self.dock_buttons[key] = btn

        c1_lay.addWidget(grid_frame)
        lay.addWidget(c1)

        c2, c2_lay = self._make_card("Monitor Selection")
        self.cmb_screen = QComboBox()
        for i, scr in enumerate(QGuiApplication.screens()):
            g = scr.geometry()
            self.cmb_screen.addItem(f"Display {i + 1} ({g.width()}x{g.height()})")
        self.cmb_screen.currentIndexChanged.connect(self._on_screen_changed)
        c2_lay.addWidget(self._make_row(
            "Active Display",
            "Choose which monitor hosts the Dynamic Island.",
            self.cmb_screen
        ))
        lay.addWidget(c2)

        lay.addStretch()
        return page

    # ── Page 4: Phone & Tools ─────────────────────────────────────
    def _build_tools_page(self) -> QWidget:
        page, lay = self._make_page("Phone & Tools", "Pair your phone, trigger quick system actions, or test island states.")

        # Phone Bridge
        c1, c1_lay = self._make_card("WinDin-Link Phone Continuity")
        btn_pair = self._make_btn("Pair Phone (QR Code)", primary=True)
        btn_pair.clicked.connect(self._on_open_qr_pairing)
        self.lbl_phone_status = QLabel("Not paired", page)
        self.lbl_phone_status.setStyleSheet("font-size: 11px; color: #8E8E93; border: none;")

        c1_lay.addWidget(self._make_row(
            "Wireless Phone Bridge",
            "Send files, sync clipboard, and mirror notifications over local Wi-Fi.",
            btn_pair
        ))
        c1_lay.addWidget(self.lbl_phone_status)
        lay.addWidget(c1)

        # Quick System Actions
        c2, c2_lay = self._make_card("System Actions")
        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        for text, fn in [
            ("Take Screenshot", lambda: self.system_service and self.system_service.take_screenshot()),
            ("Toggle Mute", lambda: self.system_service and self.system_service.toggle_mute()),
            ("Toggle Do Not Disturb", lambda: self.system_service and self.system_service.toggle_dnd()),
        ]:
            b = self._make_btn(text)
            b.clicked.connect(fn)
            act_row.addWidget(b)
        c2_lay.addLayout(act_row)
        lay.addWidget(c2)

        # Live State Simulator
        c3, c3_lay = self._make_card("Test Island States")
        sim_grid = QGridLayout()
        sim_grid.setSpacing(8)
        sims = [
            ("Volume OSD", "osd", 0, 0),
            ("Toast Alert", "notif_toast", 0, 1),
            ("Incoming Call", "call", 0, 2),
            ("2FA OTP Pill", "otp", 1, 0),
            ("AirPods Popup", "airpods", 1, 1),
            ("Demo Music", "demo_music", 1, 2),
        ]
        for label, kind, r, c in sims:
            b = self._make_btn(label)
            b.clicked.connect(lambda _, k=kind: self._sim_call(k))
            sim_grid.addWidget(b, r, c)
        c3_lay.addLayout(sim_grid)
        lay.addWidget(c3)

        lay.addStretch()
        return page

    # ── Synchronization & Actions ─────────────────────────────────
    def _sync_values_to_ui(self):
        edge = self.cfg.get("dock_edge", "top")
        for k, btn in self.dock_buttons.items():
            btn.setChecked(k == edge)

        preset = self.cfg.get("theme_preset", "")
        if not preset:
            theme = self.cfg.get("theme_mode", "ambient")
            preset = "obsidian" if theme == "solid" else theme
        for k, btn in self.theme_buttons.items():
            btn.setChecked(k == preset)

        clk_acc = self.cfg.get("clock_accent", "auto")
        for k, btn in self.clock_accent_buttons.items():
            btn.setChecked(k.lower() == str(clk_acc).lower())

        op = float(self.cfg.get("ambient_opacity", 0.24))
        pct = max(0, min(100, int(round(op * 100))))
        self.slider_glow.blockSignals(True)
        self.slider_glow.setValue(pct)
        self.slider_glow.blockSignals(False)
        self.lbl_glow_val.setText(f"{pct}%")

        self.sw_hover_expand.setChecked(bool(self.cfg.get("hover_to_expand", True)), emit=False)
        self.sw_border.setChecked(bool(self.cfg.get("show_border", True)), emit=False)
        self.sw_autohide.setChecked(bool(self.cfg.get("auto_hide", False)), emit=False)
        self.sw_autostart.setChecked(is_autostart_enabled(), emit=False)

        tf = self.cfg.get("time_format", "24h")
        self.cmb_time_format.blockSignals(True)
        self.cmb_time_format.setCurrentIndex(0 if tf == "24h" else 1)
        self.cmb_time_format.blockSignals(False)

        scr_idx = int(self.cfg.get("screen_index", 0))
        if 0 <= scr_idx < self.cmb_screen.count():
            self.cmb_screen.blockSignals(True)
            self.cmb_screen.setCurrentIndex(scr_idx)
            self.cmb_screen.blockSignals(False)

        self._refresh_phone_status()

    def _refresh_phone_status(self):
        if not hasattr(self, "lbl_phone_status"):
            return
        if self.island and getattr(self.island, "_phone_bridge_connected", False):
            dev = getattr(self.island, "_phone_bridge_device", "Phone")
            self.lbl_phone_status.setText(f"Connected: {dev}")
            self.lbl_phone_status.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {ACCENT_GREEN}; border: none;")
        else:
            self.lbl_phone_status.setText("Status: Ready to pair")
            self.lbl_phone_status.setStyleSheet("font-size: 11px; color: #8E8E93; border: none;")

    def _on_toggle_expand(self):
        if self.island:
            self.island.toggle_expanded()
        else:
            self._send_http_cmd("/api/wake")

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
        if self.island:
            self.island._time_format = val
            self.island.update()

    def _on_hover_expand_toggled(self, checked: bool):
        self.cfg["hover_to_expand"] = checked
        settings.set("hover_to_expand", checked)
        if self.island:
            self.island._hover_to_expand = checked

    def _on_border_toggled(self, checked: bool):
        self.cfg["show_border"] = checked
        settings.set("show_border", checked)
        if self.island:
            self.island._show_border = checked
            self.island.update()

    def _set_clock_accent(self, accent: str):
        self.cfg["clock_accent"] = accent
        settings.set("clock_accent", accent)
        for k, btn in self.clock_accent_buttons.items():
            btn.setChecked(k.lower() == accent.lower())
        if self.island:
            self.island._clock_accent = accent
            self.island.update()

    def _apply_theme_preset(self, preset_key: str):
        for key, _lbl, mode, c1_hex, c2_hex in self.THEME_PRESETS:
            if key == preset_key:
                self.cfg["theme_preset"] = key
                self.cfg["theme_mode"] = mode
                for k, btn in self.theme_buttons.items():
                    btn.setChecked(k == key)
                if mode == "ambient":
                    op = float(self.cfg.get("ambient_opacity", 0.24))
                    settings.update({"theme_preset": key, "theme_mode": "ambient"})
                    if self.island:
                        self.island.set_theme_ambient(op)
                elif mode == "solid":
                    self.cfg["solid_color"] = c1_hex
                    settings.update({"theme_preset": key, "theme_mode": "solid", "solid_color": c1_hex})
                    if self.island:
                        self.island.set_theme_solid(QColor(c1_hex))
                elif mode == "gradient":
                    self.cfg["gradient_c1"] = c1_hex
                    self.cfg["gradient_c2"] = c2_hex
                    settings.update({"theme_preset": key, "theme_mode": "gradient", "gradient_c1": c1_hex, "gradient_c2": c2_hex})
                    if self.island:
                        self.island.set_theme_gradient(QColor(c1_hex), QColor(c2_hex))
                break

    def _set_solid_color(self, hex_code: str):
        self.cfg["solid_color"] = hex_code
        self.cfg["theme_mode"] = "solid"
        self.cfg["theme_preset"] = "custom_solid"
        settings.update({"solid_color": hex_code, "theme_mode": "solid", "theme_preset": "custom_solid"})
        for btn in self.theme_buttons.values():
            btn.setChecked(False)
        if self.island:
            self.island.set_theme_solid(QColor(hex_code))

    def _pick_custom_color(self):
        c = QColorDialog.getColor(QColor(self.cfg.get("solid_color", "#08080C")), self, "Select Island Solid Color")
        if c.isValid():
            self._set_solid_color(c.name())

    def _pick_custom_gradient(self):
        c1 = QColorDialog.getColor(QColor(self.cfg.get("gradient_c1", "#0A1628")), self, "Select Gradient Start Color")
        if not c1.isValid():
            return
        c2 = QColorDialog.getColor(QColor(self.cfg.get("gradient_c2", "#050912")), self, "Select Gradient End Color")
        if not c2.isValid():
            return
        self.cfg["gradient_c1"] = c1.name()
        self.cfg["gradient_c2"] = c2.name()
        self.cfg["theme_mode"] = "gradient"
        self.cfg["theme_preset"] = "custom_gradient"
        settings.update({
            "gradient_c1": c1.name(),
            "gradient_c2": c2.name(),
            "theme_mode": "gradient",
            "theme_preset": "custom_gradient",
        })
        for btn in self.theme_buttons.values():
            btn.setChecked(False)
        if self.island:
            self.island.set_theme_gradient(c1, c2)

    def _on_glow_slider_changed(self, val: int):
        self.lbl_glow_val.setText(f"{val}%")
        op = val / 100.0
        self.cfg["ambient_opacity"] = op
        settings.set("ambient_opacity", op)
        if self.island:
            self.island.set_ambient_opacity(op)

    def _set_dock(self, edge: str):
        self.cfg["dock_edge"] = edge
        settings.set("dock_edge", edge)
        for k, btn in self.dock_buttons.items():
            btn.setChecked(k == edge)
        if self.island:
            self.island.set_dock_edge(edge, animate=True)
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

    def _on_open_qr_pairing(self):
        if self.island and hasattr(self.island, "open_qr_pairing_modal"):
            self.island.open_qr_pairing_modal()
        else:
            QMessageBox.information(self, "WinDin-Link", "Start WindowLand Dynamic Island to pair a phone.")

    def _sim_call(self, kind: str):
        if kind == "osd" and self.island:
            self.island.trigger_osd("Volume", 0.72, "72%", "volume")
        elif kind == "call" and self.island:
            self.island.trigger_call("Mom", "+1 (555) 234-5678", "iPhone • Incoming Call")
        elif kind == "otp" and self.island:
            self.island.trigger_otp("482 910", "Messages")
        elif kind == "notif_toast" and self.system_service:
            self.system_service.trigger_test_notification("Notification", "System Alert", "WindowLand Dynamic Island is active.")
        elif kind == "demo_music" and self.media_service:
            self.media_service.toggle_mock_mode()
        elif kind == "airpods" and self.device_service:
            self.device_service.trigger_simulated_device("airpods", "AirPods Pro")
        elif not self.island:
            self._send_http_cmd(f"/api/simulate?kind={kind}")

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._send_http_cmd("/api/quit")
            except Exception:
                pass
            if self.island:
                try:
                    self.island.save_current_settings()
                except Exception:
                    pass
            app_inst = QApplication.instance()
            if app_inst:
                app_inst.quit()
