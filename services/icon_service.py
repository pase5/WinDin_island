"""
Application Icon & Logo Extraction Service.
Extracts native, high-resolution application icons on Windows:
1. Resolves running process executables via psutil
2. Resolves Windows Start Menu shortcuts (.lnk files) in User & System directories
3. Resolves well-known system applications (Explorer, Snipping Tool, Notepad, etc.)
4. Extracts native HICON via Win32 Shell API (SHGetFileInfoW) and converts to 32-bit QPixmap
5. Renders pixel-perfect, anti-aliased vector brand icons for phone/web notifications (WhatsApp, Slack, Discord, Instagram, Spotify, etc.)
6. Caches all extracted QPixmaps in memory for instant (<0.1ms) reuse
Strictly adheres to AGENTS.md (Rule 1: Zero System Emojis) and DESIGN.md.
"""

import os
import glob
import ctypes
from ctypes import wintypes
from typing import Optional, Dict

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QRadialGradient
)

# In-memory cache: app_name_normalized -> QPixmap
_APP_ICON_CACHE: Dict[str, QPixmap] = {}

# ── 64-bit Windows GDI & Shell32 Ctypes Binding ─────────────
gdi32 = ctypes.windll.gdi32
user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
user32.DestroyIcon.argtypes = [ctypes.c_void_p]
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
gdi32.GetDIBits.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
]


class _ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", ctypes.c_void_p),
        ("hbmColor", ctypes.c_void_p)
    ]


user32.GetIconInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


class _BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG),
        ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG),
        ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", ctypes.c_void_p)
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD)
    ]


class _SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", ctypes.c_void_p),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80)
    ]


def _hicon_to_qpixmap(hicon: int) -> Optional[QPixmap]:
    """Converts a native Win32 HICON to a high-quality 32-bit ARGB QPixmap."""
    try:
        info = _ICONINFO()
        if not user32.GetIconInfo(hicon, ctypes.byref(info)):
            return None

        bm = _BITMAP()
        gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(bm), ctypes.byref(bm))
        w = bm.bmWidth
        h = bm.bmHeight

        if w <= 0 or h <= 0:
            if info.hbmColor:
                gdi32.DeleteObject(info.hbmColor)
            if info.hbmMask:
                gdi32.DeleteObject(info.hbmMask)
            return None

        hdc = user32.GetDC(None)
        memdc = gdi32.CreateCompatibleDC(hdc)

        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down DIB
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = (ctypes.c_ubyte * (w * h * 4))()
        gdi32.GetDIBits(memdc, info.hbmColor, 0, h, buf, ctypes.byref(bmi), 0)

        user32.ReleaseDC(None, hdc)
        gdi32.DeleteDC(memdc)
        if info.hbmColor:
            gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            gdi32.DeleteObject(info.hbmMask)

        img = QImage(buf, w, h, w * 4, QImage.Format.Format_ARGB32_Premultiplied)
        return QPixmap.fromImage(img.copy())
    except Exception:
        return None


def _extract_icon_from_file(file_path: str) -> Optional[QPixmap]:
    """Extracts the native Windows icon from an executable or shortcut (.lnk)."""
    if not os.path.exists(file_path):
        return None
    try:
        sfi = _SHFILEINFOW()
        SHGFI_ICON = 0x000000100
        SHGFI_LARGEICON = 0x000000000
        res = shell32.SHGetFileInfoW(
            file_path,
            0,
            ctypes.byref(sfi),
            ctypes.sizeof(sfi),
            SHGFI_ICON | SHGFI_LARGEICON
        )
        if res and sfi.hIcon:
            pix = _hicon_to_qpixmap(sfi.hIcon)
            user32.DestroyIcon(sfi.hIcon)
            return pix
    except Exception:
        pass
    return None


def _find_installed_app_path(app_name: str) -> Optional[str]:
    """Locates an installed application executable or Start Menu shortcut."""
    app_lower = app_name.lower().strip()
    if app_lower.endswith(".exe"):
        app_lower = app_lower[:-4]

    # 1. Search currently running processes (<5ms)
    try:
        import psutil
        for p in psutil.process_iter(["name", "exe"]):
            try:
                name = (p.info["name"] or "").lower()
                exe = p.info["exe"]
                if exe and os.path.exists(exe):
                    if app_lower in name or name.startswith(app_lower) or app_lower in exe.lower():
                        return exe
            except Exception:
                continue
    except Exception:
        pass

    # 2. Search Windows Start Menu shortcuts (.lnk files)
    shortcut_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs")
    ]
    for base_dir in shortcut_dirs:
        if not os.path.exists(base_dir):
            continue
        try:
            for lnk in glob.glob(os.path.join(base_dir, "**", "*.lnk"), recursive=True):
                fname = os.path.splitext(os.path.basename(lnk))[0].lower()
                if app_lower == fname or app_lower in fname or fname in app_lower:
                    return lnk
        except Exception:
            continue

    # 3. Well-known system applications
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    system_paths = {
        "explorer": os.path.join(win_dir, "explorer.exe"),
        "file explorer": os.path.join(win_dir, "explorer.exe"),
        "notepad": os.path.join(win_dir, "System32", "notepad.exe"),
        "cmd": os.path.join(win_dir, "System32", "cmd.exe"),
        "command prompt": os.path.join(win_dir, "System32", "cmd.exe"),
        "terminal": os.path.join(win_dir, "System32", "cmd.exe"),
        "snipping tool": os.path.join(win_dir, "System32", "SnippingTool.exe"),
        "screen capture": os.path.join(win_dir, "System32", "SnippingTool.exe"),
        "calculator": os.path.join(win_dir, "System32", "calc.exe"),
        "task manager": os.path.join(win_dir, "System32", "Taskmgr.exe")
    }
    if app_lower in system_paths and os.path.exists(system_paths[app_lower]):
        return system_paths[app_lower]

    return None


def paint_uniform_notification_symbol(
    painter: QPainter,
    cx: float,
    cy: float,
    s: float,
    accent_col: Optional[QColor] = None,
    icon_fill: Optional[QColor] = None,
    with_beacon: bool = True
):
    """
    Renders the canonical WindowLand uniform notification chime symbol.
    Strictly adheres to AGENTS.md (Rule 1: Zero System Emojis) and DESIGN.md (continuous Bézier fillets).
    Optically centered with subpixel antialiasing at (cx, cy) over span s.
    """
    if accent_col is None:
        accent_col = QColor("#00F2FE")
    if icon_fill is None:
        icon_fill = QColor(255, 255, 255, 248)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # 1. Top Suspension Finial Loop / Crown
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(icon_fill))
    painter.drawEllipse(QPointF(cx, cy - 0.22 * s), 0.045 * s, 0.045 * s)

    # 2. Bell Flared Mantle Path (C1 continuous Béziers)
    bell = QPainterPath()
    bell.moveTo(cx - 0.075 * s, cy - 0.17 * s)
    bell.cubicTo(
        cx - 0.09 * s, cy - 0.04 * s,
        cx - 0.14 * s, cy + 0.08 * s,
        cx - 0.24 * s, cy + 0.15 * s
    )
    # Bottom curved lip connecting left to right
    bell.quadTo(cx, cy + 0.175 * s, cx + 0.24 * s, cy + 0.15 * s)
    # Right flank
    bell.cubicTo(
        cx + 0.14 * s, cy + 0.08 * s,
        cx + 0.09 * s, cy - 0.04 * s,
        cx + 0.075 * s, cy - 0.17 * s
    )
    bell.closeSubpath()
    painter.drawPath(bell)

    # 3. Horizontal Lip Rim Bead
    lip_path = QPainterPath()
    lip_path.addRoundedRect(QRectF(cx - 0.25 * s, cy + 0.125 * s, 0.50 * s, 0.055 * s), 0.025 * s, 0.025 * s)
    painter.drawPath(lip_path)

    # 4. Centered Clapper Drop Bead
    painter.drawEllipse(QPointF(cx, cy + 0.22 * s), 0.052 * s, 0.052 * s)

    # 5. Active Notification Signal Ping / Beacon
    if with_beacon:
        ping_cx = cx + 0.21 * s
        ping_cy = cy - 0.19 * s
        ping_r = 0.065 * s

        # Outer soft aura halo
        ping_aura = QRadialGradient(QPointF(ping_cx, ping_cy), ping_r * 2.2)
        ping_aura.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 120))
        ping_aura.setColorAt(0.5, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 30))
        ping_aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(ping_aura))
        painter.drawEllipse(QPointF(ping_cx, ping_cy), ping_r * 2.2, ping_r * 2.2)

        # Inner solid beacon
        painter.setBrush(QBrush(accent_col))
        painter.drawEllipse(QPointF(ping_cx, ping_cy), ping_r, ping_r)

        # Micro white specular glint on beacon
        painter.setBrush(QColor(255, 255, 255, 210))
        painter.drawEllipse(QPointF(ping_cx - ping_r * 0.25, ping_cy - ping_r * 0.25), ping_r * 0.35, ping_r * 0.35)

    painter.restore()


def render_uniform_notification_icon(
    size: int = 48,
    accent_col: Optional[QColor] = None,
    solid_col: Optional[QColor] = None
) -> QPixmap:
    """
    Renders the complete high-resolution uniform notification tile icon.
    Follows DESIGN.md Section 4.3 (Corner Squircle Superellipse r = 0.25 * size,
    diagonal 2.5D specular highlight sheen, and atmospheric underglow).
    """
    if accent_col is None:
        accent_col = QColor("#00F2FE")

    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    s = float(size)
    rect = QRectF(0, 0, s, s)
    cx = s / 2.0
    cy = s / 2.0

    r_corner = s * 0.25

    # Background tile gradient
    if solid_col:
        tile_grad = QLinearGradient(0, 0, 0, s)
        tile_grad.setColorAt(0.0, solid_col.lighter(130))
        tile_grad.setColorAt(1.0, solid_col.darker(110))
        border_col = solid_col.lighter(160)
        border_col.setAlpha(120)
    else:
        tile_grad = QLinearGradient(0, 0, 0, s)
        tile_grad.setColorAt(0.0, QColor(24, 28, 42, 245))
        tile_grad.setColorAt(1.0, QColor(10, 12, 20, 252))
        border_col = QColor(255, 255, 255, 38)

    p.setPen(QPen(border_col, 1.0))
    p.setBrush(QBrush(tile_grad))
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r_corner, r_corner)

    # Specular 2.5D diagonal glass sheen
    sheen = QLinearGradient(0, 0, s * 0.8, s * 0.8)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 45))
    sheen.setColorAt(0.4, QColor(255, 255, 255, 12))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(sheen))
    p.drawRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), r_corner, r_corner)

    # Ambient radial backlight aura
    aura = QRadialGradient(QPointF(cx, cy * 0.9), s * 0.45)
    aura.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 35))
    aura.setColorAt(0.6, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 8))
    aura.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(aura))
    p.drawRect(rect)

    # Uniform notification symbol
    paint_uniform_notification_symbol(p, cx, cy, s, accent_col=accent_col, with_beacon=True)

    p.end()
    return pix


def _render_vector_brand_logo(app_name: str, size: int = 48, accent_col: Optional[QColor] = None) -> Optional[QPixmap]:
    """
    Renders an anti-aliased vector brand logo for common apps
    when native .exe is not locally installed (e.g., phone bridge notifications).
    Strictly follows AGENTS.md Rule 1 (Zero emojis, 100% clean vector paths).
    """
    app_lower = app_name.lower().strip()
    if any(k in app_lower for k in ("notification", "notifications", "alert", "alerts", "system alert", "system", "bell")):
        return render_uniform_notification_icon(size=size, accent_col=accent_col)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    s = float(size)
    rect = QRectF(0, 0, s, s)

    if "whatsapp" in app_lower:
        # WhatsApp Green Squircle
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#25D366"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        # White speech bubble + phone symbol
        p.setPen(QPen(QColor(255, 255, 255), s * 0.075, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * 0.22, s * 0.20, s * 0.56, s * 0.56))
        # Tail
        tail = QPainterPath()
        tail.moveTo(s * 0.30, s * 0.65)
        tail.lineTo(s * 0.22, s * 0.78)
        tail.lineTo(s * 0.38, s * 0.72)
        p.strokePath(tail, p.pen())

    elif "discord" in app_lower:
        # Discord Blurple
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#5865F2"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        # White game controller / Clyde
        p.setBrush(QColor(255, 255, 255))
        clyde = QPainterPath()
        clyde.addRoundedRect(QRectF(s * 0.24, s * 0.30, s * 0.52, s * 0.38), s * 0.12, s * 0.12)
        p.drawPath(clyde)
        p.setBrush(QColor("#5865F2"))
        p.drawEllipse(QRectF(s * 0.35, s * 0.42, s * 0.09, s * 0.09))
        p.drawEllipse(QRectF(s * 0.56, s * 0.42, s * 0.09, s * 0.09))

    elif "slack" in app_lower:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#4A154B"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        # Multi-colored slack hashtag pills
        pen = QPen(QColor("#E01E5A"), s * 0.08, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(s * 0.38, s * 0.28), QPointF(s * 0.38, s * 0.72))
        p.setPen(QPen(QColor("#2EB67D"), s * 0.08, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(s * 0.62, s * 0.28), QPointF(s * 0.62, s * 0.72))
        p.setPen(QPen(QColor("#ECB22E"), s * 0.08, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(s * 0.28, s * 0.42), QPointF(s * 0.72, s * 0.42))
        p.setPen(QPen(QColor("#36C5F0"), s * 0.08, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(s * 0.28, s * 0.58), QPointF(s * 0.72, s * 0.58))

    elif "spotify" in app_lower:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1ED760"))
        p.drawEllipse(rect)
        p.setPen(QPen(QColor("#121212"), s * 0.075, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        # 3 Curved waves
        w1 = QPainterPath()
        w1.arcMoveTo(QRectF(s * 0.25, s * 0.26, s * 0.50, s * 0.44), 30)
        w1.arcTo(QRectF(s * 0.25, s * 0.26, s * 0.50, s * 0.44), 30, 115)
        p.strokePath(w1, p.pen())
        w2 = QPainterPath()
        w2.arcMoveTo(QRectF(s * 0.28, s * 0.38, s * 0.44, s * 0.38), 30)
        w2.arcTo(QRectF(s * 0.28, s * 0.38, s * 0.44, s * 0.38), 30, 115)
        p.strokePath(w2, p.pen())
        w3 = QPainterPath()
        w3.arcMoveTo(QRectF(s * 0.32, s * 0.50, s * 0.36, s * 0.32), 30)
        w3.arcTo(QRectF(s * 0.32, s * 0.50, s * 0.36, s * 0.32), 30, 115)
        p.strokePath(w3, p.pen())

    elif "instagram" in app_lower:
        grad = QLinearGradient(0, s, s, 0)
        grad.setColorAt(0.0, QColor("#FEE411"))
        grad.setColorAt(0.4, QColor("#FEDB1E"))
        grad.setColorAt(0.6, QColor("#E1306C"))
        grad.setColorAt(1.0, QColor("#833AB4"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        p.setPen(QPen(QColor(255, 255, 255), s * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.26, s * 0.26, s * 0.48, s * 0.48), s * 0.12, s * 0.12)
        p.drawEllipse(QRectF(s * 0.38, s * 0.38, s * 0.24, s * 0.24))
        p.setBrush(QColor(255, 255, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(s * 0.60, s * 0.32, s * 0.05, s * 0.05))

    elif any(k in app_lower for k in ("message", "imessage", "sms")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#34C759"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        p.setBrush(QColor(255, 255, 255))
        bubble = QPainterPath()
        bubble.addRoundedRect(QRectF(s * 0.22, s * 0.24, s * 0.56, s * 0.44), s * 0.14, s * 0.14)
        bubble.moveTo(s * 0.32, s * 0.64)
        bubble.lineTo(s * 0.22, s * 0.76)
        bubble.lineTo(s * 0.42, s * 0.68)
        p.drawPath(bubble)

    elif any(k in app_lower for k in ("mail", "outlook", "gmail")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0078D4"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        p.setPen(QPen(QColor(255, 255, 255), s * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.28, s * 0.56, s * 0.44), s * 0.06, s * 0.06)
        env = QPainterPath()
        env.moveTo(s * 0.22, s * 0.32)
        env.lineTo(s * 0.50, s * 0.52)
        env.lineTo(s * 0.78, s * 0.32)
        p.strokePath(env, p.pen())

    elif "telegram" in app_lower:
        # Telegram Blue circle with paper plane
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#24A1DE"))
        p.drawEllipse(rect)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255))
        plane = QPainterPath()
        plane.moveTo(s * 0.22, s * 0.50)
        plane.lineTo(s * 0.78, s * 0.26)
        plane.lineTo(s * 0.62, s * 0.74)
        plane.lineTo(s * 0.46, s * 0.58)
        plane.closeSubpath()
        p.drawPath(plane)

    elif any(k in app_lower for k in ("calendar", "meeting", "schedule")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FF9500"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255))
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.24, s * 0.56, s * 0.52), s * 0.10, s * 0.10)
        p.setBrush(QColor("#FF3B30"))
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.24, s * 0.56, s * 0.16), s * 0.08, s * 0.08)

    elif any(k in app_lower for k in ("snip", "camera", "screenshot", "capture")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#00F2FE"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        p.setBrush(QColor(255, 255, 255))
        cam = QPainterPath()
        cam.addRoundedRect(QRectF(s * 0.22, s * 0.32, s * 0.56, s * 0.40), s * 0.08, s * 0.08)
        cam.addRoundedRect(QRectF(s * 0.38, s * 0.24, s * 0.24, s * 0.10), s * 0.04, s * 0.04)
        p.drawPath(cam)
        p.setBrush(QColor("#00F2FE"))
        p.drawEllipse(QRectF(s * 0.40, s * 0.42, s * 0.20, s * 0.20))

    elif any(k in app_lower for k in ("audio", "headphone", "earphone", "airpods", "sony", "bluetooth", "sound", "speaker", "device", "iem")):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#6366F1"))
        p.drawRoundedRect(rect, s * 0.26, s * 0.26)
        p.setPen(QPen(QColor(255, 255, 255), s * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Headphone arch
        arch = QPainterPath()
        arch.arcMoveTo(QRectF(s * 0.25, s * 0.26, s * 0.50, s * 0.46), 0)
        arch.arcTo(QRectF(s * 0.25, s * 0.26, s * 0.50, s * 0.46), 0, 180)
        p.strokePath(arch, p.pen())
        # Ear cushions
        p.setBrush(QColor(255, 255, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.46, s * 0.11, s * 0.26), s * 0.05, s * 0.05)
        p.drawRoundedRect(QRectF(s * 0.67, s * 0.46, s * 0.11, s * 0.26), s * 0.05, s * 0.05)

    else:
        # Default fallback: Canonical Uniform Clean Notification Icon
        return render_uniform_notification_icon(size=int(s), accent_col=accent_col)

    p.end()
    return pix


def render_brand_logo(size: int = 48) -> QPixmap:
    """
    Renders or loads the canonical WindowLand Dynamic Island brand logo
    generated from gemini-svg.svg (hardware notch cutout with emerald beacon and audio spectrum bars).
    Follows AGENTS.md Rule 1 (Zero emojis) and Rule 3 (Defensive rendering).
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        svg_path = os.path.join(base_dir, "assets", "app_logo.svg")
        if not os.path.exists(svg_path):
            svg_path = os.path.join(base_dir, "gemini-svg.svg")
        
        if os.path.exists(svg_path):
            from PyQt6.QtSvg import QSvgRenderer
            renderer = QSvgRenderer(svg_path)
            pix = QPixmap(size, size)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(p, QRectF(0, 0, size, size))
            p.end()
            return pix
    except Exception:
        pass

    try:
        png_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "app_logo.png")
        if os.path.exists(png_path):
            pix = QPixmap(png_path)
            if not pix.isNull():
                return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    except Exception:
        pass

    # Direct defensive fallback rendering using QPainter
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = float(size)
    r = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
    p.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
    p.setBrush(QBrush(QColor("#08080C")))
    p.drawRoundedRect(r, s * 0.22, s * 0.22)
    # Notch pill
    notch = QRectF(s * 0.21, s * 0.38, s * 0.58, s * 0.24)
    p.setPen(QPen(QColor("#262630"), 1.0))
    p.setBrush(QBrush(QColor("#000000")))
    p.drawRoundedRect(notch, s * 0.12, s * 0.12)
    # Emerald circle
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#34C759")))
    p.drawEllipse(QRectF(s * 0.31, s * 0.46, s * 0.08, s * 0.08))
    # Bars
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.drawRoundedRect(QRectF(s * 0.48, s * 0.44, s * 0.03, s * 0.12), s * 0.015, s * 0.015)
    p.setBrush(QBrush(QColor("#34C759")))
    p.drawRoundedRect(QRectF(s * 0.54, s * 0.40, s * 0.03, s * 0.18), s * 0.015, s * 0.015)
    p.setBrush(QBrush(QColor(255, 255, 255, 180)))
    p.drawRoundedRect(QRectF(s * 0.60, s * 0.42, s * 0.03, s * 0.14), s * 0.015, s * 0.015)
    p.end()
    return pix


def get_app_icon(
    app_name: str,
    target_size: int = 48,
    accent_color: Optional[QColor] = None,
    solid_color: Optional[QColor] = None
) -> QPixmap:
    """
    Main entry point for extracting and retrieving the official application logo.
    1. Checks in-memory cache
    2. Directly returns canonical uniform notification icon for system alerts / notifications
    3. Searches for native Windows process / .lnk / .exe file
    4. Extracts high-resolution Win32 HICON if found
    5. Renders crisp vector brand glyph fallback if native file is not present
    6. Returns smoothed QPixmap
    """
    clean_name = (app_name or "Notification").strip()
    cache_key = f"{clean_name.lower()}_{target_size}"

    # Return brand logo for WindowLand / DynamicIsland / WinDin
    if clean_name.lower() in ("windowland", "dynamicisland", "windin", "island", "control center"):
        brand_icon = render_brand_logo(size=target_size)
        _APP_ICON_CACHE[cache_key] = brand_icon
        return brand_icon

    # Return canonical uniform notification icon for generic/system notification alerts
    if clean_name.lower() in ("notification", "notifications", "alert", "alerts", "system alert", "system", "quick alert", "toast", ""):
        uniform_icon = render_uniform_notification_icon(size=target_size, accent_col=accent_color, solid_col=solid_color)
        _APP_ICON_CACHE[cache_key] = uniform_icon
        return uniform_icon

    if cache_key in _APP_ICON_CACHE:
        cached = _APP_ICON_CACHE[cache_key]
        if not cached.isNull():
            return cached

    # 1. Try finding installed app executable or shortcut
    path = _find_installed_app_path(clean_name)
    if path:
        pix = _extract_icon_from_file(path)
        if pix and not pix.isNull():
            # Smooth scale to target size
            scaled = pix.scaled(
                target_size, target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            _APP_ICON_CACHE[cache_key] = scaled
            return scaled

    # 2. Render vector brand logo
    vec_pix = _render_vector_brand_logo(clean_name, size=target_size, accent_col=accent_color)
    if vec_pix and not vec_pix.isNull():
        _APP_ICON_CACHE[cache_key] = vec_pix
        return vec_pix

    # 3. Fallback canonical uniform notification icon
    fallback = render_uniform_notification_icon(size=target_size, accent_col=accent_color, solid_col=solid_color)
    _APP_ICON_CACHE[cache_key] = fallback
    return fallback


# ── Vector UI Icon Rendering Engine (AGENTS.md Rule 1 & DESIGN.md) ──
_UI_ICON_CACHE: Dict[str, QPixmap] = {}


def render_vector_ui_icon(
    name: str,
    size: int = 24,
    color: Optional[QColor] = None,
    stroke_width: float = 1.6
) -> QPixmap:
    """
    Renders pure mathematical vector UI icons with subpixel antialiasing.
    Strictly follows AGENTS.md (Rule 1: Zero System Emojis) and DESIGN.md (precision geometry).
    Results are cached in memory for zero-latency UI rendering.
    """
    if color is None:
        color = QColor("#E4E1EA")

    key = f"{name.lower()}_{size}_{color.name()}_{color.alpha()}_{stroke_width}"
    if key in _UI_ICON_CACHE:
        return _UI_ICON_CACHE[key]

    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    s = float(size)
    cx = s / 2.0
    cy = s / 2.0
    pen = QPen(color, stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    n = name.lower().strip()

    try:
        if n in ("tune", "general"):
            # Horizontal slider rails with knurled indicator beads
            p.drawLine(QPointF(s * 0.18, s * 0.35), QPointF(s * 0.82, s * 0.35))
            p.drawLine(QPointF(s * 0.18, s * 0.65), QPointF(s * 0.82, s * 0.65))
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(s * 0.32, s * 0.23, s * 0.16, s * 0.24), s * 0.04, s * 0.04)
            p.drawRoundedRect(QRectF(s * 0.52, s * 0.53, s * 0.16, s * 0.24), s * 0.04, s * 0.04)

        elif n in ("palette", "appearance"):
            # Artist palette squircle outline with thumb opening and pigment wells
            path = QPainterPath()
            path.moveTo(s * 0.5, s * 0.15)
            path.cubicTo(s * 0.85, s * 0.15, s * 0.88, s * 0.50, s * 0.80, s * 0.70)
            path.cubicTo(s * 0.75, s * 0.82, s * 0.60, s * 0.85, s * 0.50, s * 0.85)
            path.cubicTo(s * 0.38, s * 0.85, s * 0.35, s * 0.75, s * 0.30, s * 0.75)
            path.cubicTo(s * 0.25, s * 0.75, s * 0.20, s * 0.82, s * 0.15, s * 0.70)
            path.cubicTo(s * 0.10, s * 0.50, s * 0.15, s * 0.15, s * 0.5, s * 0.15)
            p.drawPath(path)
            # Pigment dab dots
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(s * 0.40, s * 0.32), s * 0.05, s * 0.05)
            p.drawEllipse(QPointF(s * 0.60, s * 0.34), s * 0.05, s * 0.05)
            p.drawEllipse(QPointF(s * 0.70, s * 0.52), s * 0.05, s * 0.05)

        elif n in ("dock", "position"):
            # Display frame with top dock pill highlight
            p.drawRoundedRect(QRectF(s * 0.16, s * 0.20, s * 0.68, s * 0.54), s * 0.10, s * 0.10)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(s * 0.36, s * 0.20, s * 0.28, s * 0.09), s * 0.04, s * 0.04)

        elif n in ("tools", "companion", "extension"):
            # Smartphone with screen and dynamic notch
            p.drawRoundedRect(QRectF(s * 0.26, s * 0.14, s * 0.48, s * 0.72), s * 0.10, s * 0.10)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(s * 0.40, s * 0.20, s * 0.20, s * 0.05), s * 0.025, s * 0.025)
            p.drawLine(QPointF(s * 0.42, s * 0.78), QPointF(s * 0.58, s * 0.78))

        elif n in ("diagnostics", "monitoring"):
            # EKG pulse line with monitor bezel
            p.drawRoundedRect(QRectF(s * 0.14, s * 0.16, s * 0.72, s * 0.68), s * 0.12, s * 0.12)
            path = QPainterPath()
            path.moveTo(s * 0.20, s * 0.52)
            path.lineTo(s * 0.36, s * 0.52)
            path.lineTo(s * 0.44, s * 0.30)
            path.lineTo(s * 0.54, s * 0.72)
            path.lineTo(s * 0.64, s * 0.44)
            path.lineTo(s * 0.70, s * 0.52)
            path.lineTo(s * 0.80, s * 0.52)
            p.drawPath(path)

        elif n in ("info", "about"):
            # Precision circular "i" information glyph
            p.drawEllipse(QRectF(s * 0.15, s * 0.15, s * 0.70, s * 0.70))
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, s * 0.34), s * 0.045, s * 0.045)
            p.drawLine(QPointF(cx, s * 0.46), QPointF(cx, s * 0.66))

        elif n in ("user", "avatar"):
            # Head and curved shoulders silhouette
            p.drawEllipse(QPointF(cx, s * 0.34), s * 0.18, s * 0.18)
            body = QPainterPath()
            body.moveTo(s * 0.18, s * 0.78)
            body.cubicTo(s * 0.22, s * 0.58, s * 0.78, s * 0.58, s * 0.82, s * 0.78)
            p.drawPath(body)

        elif n in ("ambient", "sun"):
            # Center sun orb with radiating orbital rays
            p.drawEllipse(QPointF(cx, cy), s * 0.18, s * 0.18)
            for angle in (0, 45, 90, 135, 180, 225, 270, 315):
                p.save()
                p.translate(cx, cy)
                p.rotate(angle)
                p.drawLine(QPointF(s * 0.28, 0), QPointF(s * 0.40, 0))
                p.restore()

        elif n in ("obsidian", "oled"):
            # OLED contrast circle: left half filled solid, right half rim
            p.drawEllipse(QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68))
            half = QPainterPath()
            half.moveTo(cx, s * 0.16)
            half.arcTo(QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68), 90, 180)
            half.closeSubpath()
            p.setBrush(QBrush(color))
            p.drawPath(half)

        elif n in ("titanium", "frosted"):
            # Frosted glass quadrant matrix
            r = QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64)
            p.drawRoundedRect(r, s * 0.12, s * 0.12)
            p.drawLine(QPointF(cx, s * 0.18), QPointF(cx, s * 0.82))
            p.drawLine(QPointF(s * 0.18, cy), QPointF(s * 0.82, cy))

        elif n in ("color_picker", "palette_picker"):
            # Color droplet / selector
            p.drawEllipse(QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68))
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, cy), s * 0.12, s * 0.12)

        elif n in ("arrow_tl",):
            p.drawLine(QPointF(s * 0.72, s * 0.72), QPointF(s * 0.28, s * 0.28))
            p.drawLine(QPointF(s * 0.28, s * 0.54), QPointF(s * 0.28, s * 0.28))
            p.drawLine(QPointF(s * 0.54, s * 0.28), QPointF(s * 0.28, s * 0.28))

        elif n in ("arrow_top",):
            p.drawLine(QPointF(cx, s * 0.76), QPointF(cx, s * 0.24))
            p.drawLine(QPointF(cx - s * 0.20, s * 0.44), QPointF(cx, s * 0.24))
            p.drawLine(QPointF(cx + s * 0.20, s * 0.44), QPointF(cx, s * 0.24))

        elif n in ("arrow_tr",):
            p.drawLine(QPointF(s * 0.28, s * 0.72), QPointF(s * 0.72, s * 0.28))
            p.drawLine(QPointF(s * 0.46, s * 0.28), QPointF(s * 0.72, s * 0.28))
            p.drawLine(QPointF(s * 0.72, s * 0.54), QPointF(s * 0.72, s * 0.28))

        elif n in ("arrow_left",):
            p.drawLine(QPointF(s * 0.76, cy), QPointF(s * 0.24, cy))
            p.drawLine(QPointF(s * 0.44, cy - s * 0.20), QPointF(s * 0.24, cy))
            p.drawLine(QPointF(s * 0.44, cy + s * 0.20), QPointF(s * 0.24, cy))

        elif n in ("float", "cross"):
            # 4-way move crosshair
            p.drawLine(QPointF(cx, s * 0.20), QPointF(cx, s * 0.80))
            p.drawLine(QPointF(s * 0.20, cy), QPointF(s * 0.80, cy))
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, cy), s * 0.08, s * 0.08)

        elif n in ("arrow_right",):
            p.drawLine(QPointF(s * 0.24, cy), QPointF(s * 0.76, cy))
            p.drawLine(QPointF(s * 0.56, cy - s * 0.20), QPointF(s * 0.76, cy))
            p.drawLine(QPointF(s * 0.56, cy + s * 0.20), QPointF(s * 0.76, cy))

        elif n in ("arrow_bl",):
            p.drawLine(QPointF(s * 0.72, s * 0.28), QPointF(s * 0.28, s * 0.72))
            p.drawLine(QPointF(s * 0.28, s * 0.46), QPointF(s * 0.28, s * 0.72))
            p.drawLine(QPointF(s * 0.54, s * 0.72), QPointF(s * 0.28, s * 0.72))

        elif n in ("arrow_bottom",):
            p.drawLine(QPointF(cx, s * 0.24), QPointF(cx, s * 0.76))
            p.drawLine(QPointF(cx - s * 0.20, s * 0.56), QPointF(cx, s * 0.76))
            p.drawLine(QPointF(cx + s * 0.20, s * 0.56), QPointF(cx, s * 0.76))

        elif n in ("arrow_br",):
            p.drawLine(QPointF(s * 0.28, s * 0.28), QPointF(s * 0.72, s * 0.72))
            p.drawLine(QPointF(s * 0.72, s * 0.46), QPointF(s * 0.72, s * 0.72))
            p.drawLine(QPointF(s * 0.46, s * 0.72), QPointF(s * 0.72, s * 0.72))

        elif n in ("target", "recenter"):
            p.drawEllipse(QRectF(s * 0.22, s * 0.22, s * 0.56, s * 0.56))
            p.drawLine(QPointF(cx, s * 0.12), QPointF(cx, s * 0.24))
            p.drawLine(QPointF(cx, s * 0.76), QPointF(cx, s * 0.88))
            p.drawLine(QPointF(s * 0.12, cy), QPointF(s * 0.24, cy))
            p.drawLine(QPointF(s * 0.76, cy), QPointF(s * 0.88, cy))
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, cy), s * 0.07, s * 0.07)

        elif n in ("monitor", "display"):
            p.drawRoundedRect(QRectF(s * 0.15, s * 0.20, s * 0.70, s * 0.46), s * 0.08, s * 0.08)
            p.drawLine(QPointF(cx, s * 0.66), QPointF(cx, s * 0.78))
            p.drawLine(QPointF(s * 0.34, s * 0.78), QPointF(s * 0.66, s * 0.78))

        elif n in ("copy",):
            p.drawRoundedRect(QRectF(s * 0.18, s * 0.28, s * 0.48, s * 0.52), s * 0.08, s * 0.08)
            bg_doc = QPainterPath()
            bg_doc.moveTo(s * 0.34, s * 0.28)
            bg_doc.lineTo(s * 0.34, s * 0.18)
            bg_doc.lineTo(s * 0.78, s * 0.18)
            bg_doc.lineTo(s * 0.78, s * 0.62)
            bg_doc.lineTo(s * 0.66, s * 0.62)
            p.drawPath(bg_doc)

        elif n in ("external_link",):
            path = QPainterPath()
            path.moveTo(s * 0.48, s * 0.22)
            path.lineTo(s * 0.22, s * 0.22)
            path.lineTo(s * 0.22, s * 0.78)
            path.lineTo(s * 0.78, s * 0.78)
            path.lineTo(s * 0.78, s * 0.52)
            p.drawPath(path)
            p.drawLine(QPointF(s * 0.45, s * 0.55), QPointF(s * 0.78, s * 0.22))
            p.drawLine(QPointF(s * 0.58, s * 0.22), QPointF(s * 0.78, s * 0.22))
            p.drawLine(QPointF(s * 0.78, s * 0.42), QPointF(s * 0.78, s * 0.22))

        elif n in ("screenshot",):
            p.drawRoundedRect(QRectF(s * 0.16, s * 0.26, s * 0.68, s * 0.50), s * 0.08, s * 0.08)
            p.drawRoundedRect(QRectF(s * 0.36, s * 0.18, s * 0.28, s * 0.10), s * 0.04, s * 0.04)
            p.drawEllipse(QRectF(s * 0.38, s * 0.38, s * 0.24, s * 0.24))

        elif n in ("volume",):
            # Speaker horn
            horn = QPainterPath()
            horn.moveTo(s * 0.20, s * 0.38)
            horn.lineTo(s * 0.34, s * 0.38)
            horn.lineTo(s * 0.50, s * 0.24)
            horn.lineTo(s * 0.50, s * 0.76)
            horn.lineTo(s * 0.34, s * 0.62)
            horn.lineTo(s * 0.20, s * 0.62)
            horn.closeSubpath()
            p.drawPath(horn)
            # Sound waves
            w1 = QPainterPath()
            w1.arcMoveTo(QRectF(s * 0.44, s * 0.34, s * 0.24, s * 0.32), -45)
            w1.arcTo(QRectF(s * 0.44, s * 0.34, s * 0.24, s * 0.32), -45, 90)
            p.drawPath(w1)
            w2 = QPainterPath()
            w2.arcMoveTo(QRectF(s * 0.48, s * 0.24, s * 0.36, s * 0.52), -45)
            w2.arcTo(QRectF(s * 0.48, s * 0.24, s * 0.36, s * 0.52), -45, 90)
            p.drawPath(w2)

        elif n in ("mute",):
            horn = QPainterPath()
            horn.moveTo(s * 0.20, s * 0.38)
            horn.lineTo(s * 0.34, s * 0.38)
            horn.lineTo(s * 0.50, s * 0.24)
            horn.lineTo(s * 0.50, s * 0.76)
            horn.lineTo(s * 0.34, s * 0.62)
            horn.lineTo(s * 0.20, s * 0.62)
            horn.closeSubpath()
            p.drawPath(horn)
            p.drawLine(QPointF(s * 0.60, s * 0.36), QPointF(s * 0.80, s * 0.64))
            p.drawLine(QPointF(s * 0.80, s * 0.36), QPointF(s * 0.60, s * 0.64))

        elif n in ("dnd",):
            p.drawEllipse(QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68))
            p.drawLine(QPointF(s * 0.30, cy), QPointF(s * 0.70, cy))

        elif n in ("phone", "call"):
            # Clean telephone handset angled at 45 degrees
            p.save()
            p.translate(cx, cy)
            p.rotate(-45)
            phone = QPainterPath()
            phone.moveTo(-s * 0.20, -s * 0.30)
            phone.lineTo(-s * 0.06, -s * 0.30)
            phone.lineTo(-s * 0.02, -s * 0.16)
            phone.lineTo(-s * 0.10, -s * 0.08)
            phone.quadTo(0, 0, s * 0.08, s * 0.10)
            phone.lineTo(s * 0.16, s * 0.02)
            phone.lineTo(s * 0.30, s * 0.06)
            phone.lineTo(s * 0.30, s * 0.20)
            phone.quadTo(s * 0.25, s * 0.30, s * 0.15, s * 0.30)
            phone.cubicTo(-s * 0.10, s * 0.30, -s * 0.30, s * 0.10, -s * 0.30, -s * 0.15)
            phone.quadTo(-s * 0.30, -s * 0.25, -s * 0.20, -s * 0.30)
            p.drawPath(phone)
            p.restore()

        elif n in ("otp", "key"):
            p.drawEllipse(QRectF(s * 0.20, s * 0.22, s * 0.32, s * 0.32))
            p.drawLine(QPointF(s * 0.44, s * 0.44), QPointF(s * 0.78, s * 0.78))
            p.drawLine(QPointF(s * 0.78, s * 0.78), QPointF(s * 0.78, s * 0.68))
            p.drawLine(QPointF(s * 0.66, s * 0.66), QPointF(s * 0.66, s * 0.56))

        elif n in ("folder", "shelf"):
            f = QPainterPath()
            f.moveTo(s * 0.18, s * 0.28)
            f.lineTo(s * 0.40, s * 0.28)
            f.lineTo(s * 0.48, s * 0.36)
            f.lineTo(s * 0.82, s * 0.36)
            f.lineTo(s * 0.82, s * 0.74)
            f.lineTo(s * 0.18, s * 0.74)
            f.closeSubpath()
            p.drawPath(f)

        elif n in ("download",):
            p.drawLine(QPointF(cx, s * 0.22), QPointF(cx, s * 0.62))
            p.drawLine(QPointF(cx - s * 0.18, s * 0.46), QPointF(cx, s * 0.62))
            p.drawLine(QPointF(cx + s * 0.18, s * 0.46), QPointF(cx, s * 0.62))
            tray = QPainterPath()
            tray.moveTo(s * 0.20, s * 0.66)
            tray.lineTo(s * 0.20, s * 0.78)
            tray.lineTo(s * 0.80, s * 0.78)
            tray.lineTo(s * 0.80, s * 0.66)
            p.drawPath(tray)

        elif n in ("bell", "notification", "toast"):
            paint_uniform_notification_symbol(p, cx, cy, s, accent_col=color, icon_fill=color, with_beacon=False)

        elif n in ("calendar",):
            p.drawRoundedRect(QRectF(s * 0.18, s * 0.22, s * 0.64, s * 0.60), s * 0.10, s * 0.10)
            p.drawLine(QPointF(s * 0.18, s * 0.40), QPointF(s * 0.82, s * 0.40))
            p.drawLine(QPointF(s * 0.34, s * 0.14), QPointF(s * 0.34, s * 0.26))
            p.drawLine(QPointF(s * 0.66, s * 0.14), QPointF(s * 0.66, s * 0.26))
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(s * 0.36, s * 0.54), s * 0.04, s * 0.04)
            p.drawEllipse(QPointF(s * 0.50, s * 0.54), s * 0.04, s * 0.04)
            p.drawEllipse(QPointF(s * 0.64, s * 0.54), s * 0.04, s * 0.04)
            p.drawEllipse(QPointF(s * 0.36, s * 0.68), s * 0.04, s * 0.04)
            p.drawEllipse(QPointF(s * 0.50, s * 0.68), s * 0.04, s * 0.04)

        elif n in ("music", "demo_music"):
            m = QPainterPath()
            m.moveTo(s * 0.36, s * 0.66)
            m.lineTo(s * 0.36, s * 0.26)
            m.lineTo(s * 0.74, s * 0.18)
            m.lineTo(s * 0.74, s * 0.58)
            p.drawPath(m)
            p.setBrush(QBrush(color))
            p.drawEllipse(QRectF(s * 0.22, s * 0.60, s * 0.20, s * 0.16))
            p.drawEllipse(QRectF(s * 0.60, s * 0.52, s * 0.20, s * 0.16))

        elif n in ("headphones", "airpods"):
            arch = QPainterPath()
            arch.arcMoveTo(QRectF(s * 0.24, s * 0.22, s * 0.52, s * 0.50), 0)
            arch.arcTo(QRectF(s * 0.24, s * 0.22, s * 0.52, s * 0.50), 0, 180)
            p.drawPath(arch)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(s * 0.20, s * 0.48, s * 0.12, s * 0.28), s * 0.06, s * 0.06)
            p.drawRoundedRect(QRectF(s * 0.68, s * 0.48, s * 0.12, s * 0.28), s * 0.06, s * 0.06)

        elif n in ("power", "quit"):
            circle = QPainterPath()
            circle.arcMoveTo(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), 60)
            circle.arcTo(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), 60, 240)
            p.drawPath(circle)
            p.drawLine(QPointF(cx, s * 0.14), QPointF(cx, s * 0.48))

        elif n in ("dot",):
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), s * 0.40, s * 0.40)

        else:
            # Fallback neat concentric squircle marker
            p.drawRoundedRect(QRectF(s * 0.20, s * 0.20, s * 0.60, s * 0.60), s * 0.16, s * 0.16)
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, cy), s * 0.10, s * 0.10)

    except Exception:
        pass
    finally:
        p.end()

    _UI_ICON_CACHE[key] = pix
    return pix

