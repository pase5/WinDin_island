"""
Hardware Notch Overlay Visual Styling & Theme Constants.
Ultra-compact curvy hardware notch design sitting flush at the top bezel (y = 0).
Soft organic curvature with zero unwanted text clutter.
"""

from PyQt6.QtGui import QColor, QFont

# Geometry Constants for Compact Curvy Top Notch
COMPACT_IDLE_WIDTH = 180
COMPACT_MUSIC_WIDTH = 280
COMPACT_HEIGHT = 30

TOAST_WIDTH = 440
TOAST_HEIGHT = 74
TOAST_R_TOP = 16.0
TOAST_R_BOT = 24.0

EXPANDED_WIDTH = 440
EXPANDED_HEIGHT = 194

# Section 3 New UI States & Geometry Matrix
OSD_HUD_WIDTH = 260
OSD_HUD_HEIGHT = 38
OSD_HUD_R_TOP = 14.0
OSD_HUD_R_BOT = 19.0

CALL_LIVE_WIDTH = 440
CALL_LIVE_HEIGHT = 74
CALL_LIVE_R_TOP = 14.0
CALL_LIVE_R_BOT = 26.0

OTP_PILL_WIDTH = 380
OTP_PILL_HEIGHT = 56
OTP_PILL_R_TOP = 14.0
OTP_PILL_R_BOT = 22.0

FILE_SHELF_WIDTH = 440
FILE_SHELF_HEIGHT = 130
FILE_SHELF_R_TOP = 14.0
FILE_SHELF_R_BOT = 28.0

DEVICE_POPUP_WIDTH = 380
DEVICE_POPUP_HEIGHT = 370

# Side Dock Geometry Constants (Left / Right Bezels - Vertical Proportions)
SIDE_COMPACT_IDLE_W = 32
SIDE_COMPACT_IDLE_H = 180
SIDE_COMPACT_MUSIC_W = 32
SIDE_COMPACT_MUSIC_H = 260
SIDE_TOAST_W = 160
SIDE_TOAST_H = 260
SIDE_EXPANDED_W = 230
SIDE_EXPANDED_H = 370
SIDE_OSD_HUD_W = 38
SIDE_OSD_HUD_H = 240
SIDE_CALL_LIVE_W = 160
SIDE_CALL_LIVE_H = 260
SIDE_OTP_PILL_W = 160
SIDE_OTP_PILL_H = 220
SIDE_FILE_SHELF_W = 180
SIDE_FILE_SHELF_H = 300
SIDE_DEVICE_POPUP_W = 280
SIDE_DEVICE_POPUP_H = 440

# Corner Dock Geometry Constants (L-Bracket Architecture: Reverse-L)
CORNER_COMPACT_IDLE_W = 230
CORNER_COMPACT_IDLE_H = 180
CORNER_COMPACT_MUSIC_W = 230
CORNER_COMPACT_MUSIC_H = 180
CORNER_ARM_THICKNESS = 36.0
CORNER_INNER_RADIUS = 16.0
CORNER_COMPACT_IDLE_SIZE = 64
CORNER_COMPACT_MUSIC_SIZE = 72
CORNER_TOAST_SIZE = 220
CORNER_EXPANDED_SIZE = 280
CORNER_OSD_HUD_SIZE = 120
CORNER_CALL_LIVE_SIZE = 220
CORNER_OTP_PILL_SIZE = 190
CORNER_FILE_SHELF_SIZE = 220
CORNER_DEVICE_POPUP_SIZE = 340

NOTCH_RADIUS_TOP = 14.0   # Curvy flaring inverse fillets at top bezel
NOTCH_RADIUS_BOT = 20.0   # Curvy soft bottom corners
EXPANDED_RADIUS = 28.0    # Curvy bottom corners in expanded mode

# Base Theme Colors (Apple-Grade Deep Obsidian)
COLOR_BEZEL = QColor("#000000")
COLOR_CANVAS = QColor("#08080C")
COLOR_TEXT_PRIMARY = QColor("#FFFFFF")
COLOR_TEXT_SECONDARY = QColor("#8E8E93")
COLOR_TEXT_MUTED = QColor("#636366")
COLOR_ACCENT = QColor("#FFFFFF")
COLOR_ACCENT_YELLOW = QColor("#FFFFFF")

# Dynamic Glow Palettes (Subtle, Restrained Tints)
GLOW_STATES = {
    "idle": {
        "color1": QColor(255, 255, 255),
        "color2": QColor(200, 200, 210),
        "opacity": 0.06,
        "name": "Subtle White"
    },
    "music": {
        "color1": QColor(255, 255, 255),
        "color2": QColor(220, 220, 230),
        "opacity": 0.08,
        "name": "Soft Glass"
    },
    "notification": {
        "color1": QColor(86, 204, 242),
        "color2": QColor(47, 128, 237),
        "opacity": 0.12,
        "name": "Cyan"
    },
    "reminders": {
        "color1": QColor(142, 45, 226),
        "color2": QColor(74, 0, 224),
        "opacity": 0.10,
        "name": "Violet"
    },
    "success": {
        "color1": QColor(56, 239, 125),
        "color2": QColor(17, 153, 142),
        "opacity": 0.12,
        "name": "Emerald"
    }
}

# Typography – smooth, subpixel-rendered fonts
def _apply_smooth(font: QFont) -> QFont:
    """Apply maximum subpixel antialiasing and hinting to a font."""
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias |
        QFont.StyleStrategy.PreferQuality
    )
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font

def get_microlabel_font():
    font = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
    return _apply_smooth(font)

def get_display_font(size=12):
    font = QFont("Segoe UI")
    font.setPointSizeF(float(size))
    font.setWeight(QFont.Weight.Bold)
    return _apply_smooth(font)

def get_subtext_font(size=10):
    font = QFont("Segoe UI")
    font.setPointSizeF(float(size))
    font.setWeight(QFont.Weight.Normal)
    return _apply_smooth(font)

def get_monospaced_font(size=12):
    font = QFont("Consolas")
    font.setPointSizeF(float(size))
    font.setWeight(QFont.Weight.Bold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
    return _apply_smooth(font)

# Modern Curvy Dark Glass QSS Stylesheet
DASHBOARD_STYLESHEET = """
QToolTip {
    background-color: #14141A;
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 3px 6px;
    font-family: 'Segoe UI';
    font-size: 11px;
}

QPushButton.action-pill {
    background-color: rgba(25, 25, 34, 0.70);
    color: #D8D8DF;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 2px 6px;
    font-family: 'Segoe UI';
    font-size: 10px;
    font-weight: 600;
}

QPushButton.action-pill:hover {
    background-color: rgba(50, 50, 68, 0.85);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.25);
}

QPushButton.action-pill:checked {
    background-color: rgba(255, 214, 0, 0.20);
    color: #FFD600;
    border: 1px solid #FFD600;
}

/* Curvy Reference Playback Buttons */
QPushButton.media-control-primary {
    background-color: #FFD600;
    color: #0A0A0C;
    border: none;
    border-radius: 16px;
    font-size: 13px;
    font-weight: bold;
    padding: 0px;
}

QPushButton.media-control-primary:hover {
    background-color: #FFE24D;
}

QPushButton.media-control-primary:pressed {
    background-color: #E6C000;
}

QPushButton.media-control-secondary {
    background-color: rgba(255, 255, 255, 0.08);
    color: #E0E0E6;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 14px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton.media-control-secondary:hover {
    background-color: rgba(255, 255, 255, 0.18);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.25);
}

QPushButton.media-control-secondary:pressed {
    background-color: rgba(255, 255, 255, 0.26);
}
"""
