"""
WinDin-Link QR Code Pairing Modal Sheet.
Displays an Apple/Obsidian-grade dark pairing card with a high-contrast lime QR code,
live network pairing URL, clipboard copy helper, and active connection status indicator.
Strictly adheres to DESIGN.md and AGENTS.md (zero system emojis, vector iconography only).
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QApplication
)
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtSignal, pyqtSlot
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush,
    QPixmap, QPainterPath, QLinearGradient, QCursor
)

from ui.styles import get_display_font, get_subtext_font, get_microlabel_font


class QRPairingModal(QWidget):
    """
    Expandable QR Pairing View & Modal Sheet.
    Shows the one-time pairing QR code for zero-install mobile PWA connection.
    """

    closed = pyqtSignal()
    paired = pyqtSignal(str)  # Emits device_name

    CARD_WIDTH = 340
    CARD_HEIGHT = 440
    CORNER_RADIUS = 24.0

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMouseTracking(True)

        self._bridge = None
        self._connected = False
        self._device_name = ""
        self._pairing_url = ""

        self._close_rect = QRectF(self.CARD_WIDTH - 38, 14, 24, 24)
        self._close_hovered = False

        self._setup_ui()
        self.resize(self.CARD_WIDTH, self.CARD_HEIGHT)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        # 1. Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.lbl_title = QLabel("WinDin-Link", self)
        self.lbl_title.setFont(get_display_font(13.0))
        self.lbl_title.setStyleSheet("color: #FFFFFF; font-weight: 700; border: none; background: transparent;")

        self.lbl_subtitle = QLabel("Scan with Phone Camera", self)
        self.lbl_subtitle.setFont(get_subtext_font(10.0))
        self.lbl_subtitle.setStyleSheet("color: #A1A1AA; border: none; background: transparent;")

        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # 2. QR Code Display Container
        self.qr_label = QLabel(self)
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setStyleSheet("""
            QLabel {
                background-color: #0A0A0A;
                border: 1px solid rgba(163, 230, 53, 0.40);
                border-radius: 18px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 3. Connection URL Pill & Copy Button
        url_box = QHBoxLayout()
        url_box.setContentsMargins(4, 0, 4, 0)
        url_box.setSpacing(8)

        self.lbl_url = QLabel("http://...", self)
        self.lbl_url.setFont(get_microlabel_font())
        self.lbl_url.setStyleSheet("""
            QLabel {
                color: #A1A1AA;
                background-color: #141416;
                border: 1px solid #242429;
                border-radius: 10px;
                padding: 6px 10px;
            }
        """)
        self.lbl_url.setFixedHeight(28)
        url_box.addWidget(self.lbl_url, 1)

        self.btn_copy = QPushButton("Copy", self)
        self.btn_copy.setFixedSize(60, 28)
        self.btn_copy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_copy.setFont(get_microlabel_font())
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #1B1B1F;
                color: #A3E635;
                border: 1px solid rgba(163, 230, 53, 0.50);
                border-radius: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #A3E635;
                color: #0A0A0A;
            }
            QPushButton:pressed {
                background-color: #84CC16;
            }
        """)
        self.btn_copy.clicked.connect(self._copy_url)
        url_box.addWidget(self.btn_copy)

        layout.addLayout(url_box)

        # 4. Status Pill
        self.status_box = QHBoxLayout()
        self.status_box.setContentsMargins(4, 4, 4, 0)
        self.status_box.setSpacing(8)
        self.status_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_dot = QLabel(self)
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setStyleSheet("background-color: #EF4444; border-radius: 4px;")

        self.lbl_status = QLabel("Waiting for phone scan...", self)
        self.lbl_status.setFont(get_subtext_font(10.0))
        self.lbl_status.setStyleSheet("color: #A1A1AA; border: none; background: transparent;")

        self.status_box.addWidget(self.status_dot)
        self.status_box.addWidget(self.lbl_status)
        layout.addLayout(self.status_box)

        # Auto-dismiss timer after pairing
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.setInterval(2200)
        self._auto_close_timer.timeout.connect(self.close_modal)

    def set_bridge(self, bridge):
        self._bridge = bridge

    def show_pairing(self, bridge=None, anchor_rect=None):
        """Generates a fresh one-time QR code and displays the pairing modal near the island."""
        if bridge:
            self._bridge = bridge
        if not self._bridge:
            return

        self._connected = False
        self._device_name = ""
        self._auto_close_timer.stop()

        self.status_dot.setStyleSheet("background-color: #EF4444; border-radius: 4px;")
        self.lbl_status.setText("Waiting for phone scan...")

        try:
            png_bytes = self._bridge.generate_pairing_qr_png()
            pixmap = QPixmap()
            pixmap.loadFromData(png_bytes)
            # Scale smoothly to 200x200
            scaled = pixmap.scaled(
                200, 200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.qr_label.setPixmap(scaled)

            self._pairing_url = self._bridge.get_pairing_url()
            disp_url = self._pairing_url
            if len(disp_url) > 34:
                disp_url = disp_url[:31] + "..."
            self.lbl_url.setText(disp_url)
            self.lbl_url.setToolTip(self._pairing_url)
        except Exception as e:
            self.lbl_status.setText(f"QR Error: {e}")

        # Position cleanly near the Dynamic Island or screen center
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            if anchor_rect:
                x = anchor_rect.center().x() - (self.CARD_WIDTH // 2)
                y = anchor_rect.bottom() + 16
            else:
                x = geom.center().x() - (self.CARD_WIDTH // 2)
                y = 80

            # Screen bounds clamping
            x = max(10, min(x, geom.width() - self.CARD_WIDTH - 10))
            y = max(10, min(y, geom.height() - self.CARD_HEIGHT - 10))
            self.move(int(x), int(y))

        self.show()
        self.raise_()
        self.activateWindow()

    def set_connected(self, connected: bool, device_name: str = ""):
        self._connected = connected
        self._device_name = device_name
        if connected:
            self.status_dot.setStyleSheet("background-color: #34C759; border-radius: 4px; box-shadow: 0 0 8px #34C759;")
            self.lbl_status.setText(f"Connected • {device_name or 'Phone'}")
            self.lbl_status.setStyleSheet("color: #34C759; font-weight: 600; border: none; background: transparent;")
            self.paired.emit(device_name)
            self._auto_close_timer.start()
        else:
            self.status_dot.setStyleSheet("background-color: #EF4444; border-radius: 4px;")
            self.lbl_status.setText("Waiting for phone scan...")
            self.lbl_status.setStyleSheet("color: #A1A1AA; border: none; background: transparent;")

    def _copy_url(self):
        if self._pairing_url:
            QApplication.clipboard().setText(self._pairing_url)
            self.btn_copy.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy"))

    def close_modal(self):
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_modal()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position()
                if self._close_rect.contains(pos):
                    self.close_modal()
                    return
        except Exception:
            pass
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        try:
            pos = event.position()
            was_hov = self._close_hovered
            self._close_hovered = self._close_rect.contains(pos)
            if was_hov != self._close_hovered:
                self.update()
        except Exception:
            pass
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        try:
            self._do_paint_event(event)
        except Exception:
            pass

    def _do_paint_event(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        r = self.CORNER_RADIUS

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)

        # 1. Obsidian Liquid Glass Base Surface (DESIGN.md Section 1.1)
        base_grad = QLinearGradient(0, 0, 0, h)
        base_grad.setColorAt(0.0, QColor(14, 14, 20, 252))
        base_grad.setColorAt(0.4, QColor(8, 8, 12, 255))
        base_grad.setColorAt(1.0, QColor(2, 2, 4, 255))
        painter.fillPath(path, base_grad)

        # 2. Outer Milled Bezel Stroke (1.5px per DESIGN.md)
        bezel_pen = QPen(QColor(0, 0, 0, 240), 1.5)
        painter.strokePath(path, bezel_pen)

        # 3. Inner Specular Highlight Rim
        inner_col = QColor(52, 199, 89, 90) if self._connected else QColor(255, 255, 255, 30)
        inner_pen = QPen(inner_col, 1.0)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(QRectF(1.0, 1.0, w - 2.0, h - 2.0), r - 1.0, r - 1.0)
        painter.strokePath(inner_path, inner_pen)

        # 4. Top Specular Meniscus Line across top bezel
        meniscus = QLinearGradient(0, 0, w, 0)
        meniscus.setColorAt(0.0, QColor(255, 255, 255, 0))
        meniscus.setColorAt(0.2, QColor(255, 255, 255, 40))
        meniscus.setColorAt(0.5, QColor(255, 255, 255, 85))
        meniscus.setColorAt(0.8, QColor(255, 255, 255, 40))
        meniscus.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(meniscus), 1.0))
        painter.drawLine(QPointF(r, 1.0), QPointF(w - r, 1.0))

        # 5. Clean Vector Close Cross (Rule 1: Zero unicode emojis)
        cx = self._close_rect.center().x()
        cy = self._close_rect.center().y()
        c_pen = QPen(
            QColor(255, 255, 255, 240 if self._close_hovered else 140),
            1.6,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap
        )
        painter.setPen(c_pen)
        s = 4.5
        painter.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
        painter.drawLine(QPointF(cx + s, cy - s), QPointF(cx - s, cy + s))
