"""
Hardware Notch Desktop Overlay for Windows 11/10
Main Entry Point, System Tray Icon, and Application Lifecycle.
"""

import sys
import os
import time
import json
import subprocess
import tempfile
import shutil
import ctypes
from ctypes import wintypes
import traceback

from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu,
    QColorDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QRectF, QAbstractNativeEventFilter, QUrl
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPen,
    QBrush, QAction, QActionGroup, QGuiApplication,
    QDesktopServices
)

# -------------------------------------------------------------
# Single Instance Lock & Wakeup via Windows Named Mutex & IPC
# If the app is already running, notify the active instance to
# reveal & expand the Dynamic Island immediately, then exit.
# -------------------------------------------------------------
MUTEX_NAME = "Global\\WinDinDynamicIsland_SingleInstanceMutex"
_kernel32 = ctypes.windll.kernel32
_user32 = ctypes.windll.user32
WM_SHOW_DYNAMIC_ISLAND = _user32.RegisterWindowMessageW("WinDin_ShowDynamicIsland")

_mutex_handle = _kernel32.CreateMutexW(None, True, MUTEX_NAME)
ERROR_ALREADY_EXISTS = 183
if _kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
    # Another instance is already running!
    if "--settings" in sys.argv or "-s" in sys.argv:
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:54321/api/open_settings")
            urllib.request.urlopen(req, timeout=1.5)
        except Exception:
            pass
        sys.exit(0)

    # 1. Wake up running instance via local phone bridge HTTP endpoint (<10ms)
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:54321/api/wake")
        urllib.request.urlopen(req, timeout=1.0)
    except Exception:
        pass
    # 2. Also broadcast native Windows message
    HWND_BROADCAST = 0xFFFF
    _user32.PostMessageW(HWND_BROADCAST, WM_SHOW_DYNAMIC_ISLAND, 0, 0)
    sys.exit(0)

# -------------------------------------------------------------
# Clean Residue & Temp Cache Pruner
# -------------------------------------------------------------
def _cleanup_temp_residue():
    """
    Cleans up stale PyInstaller temporary folders (_MEI*) left by previous
    crashes or terminations, preventing decompression error code -1,
    and prunes old cached covers.
    """
    try:
        temp_dir = tempfile.gettempdir()
        current_mei = getattr(sys, "_MEIPASS", "")
        for item in os.listdir(temp_dir):
            if item.startswith("_MEI"):
                full_path = os.path.join(temp_dir, item)
                if current_mei and os.path.abspath(full_path) == os.path.abspath(current_mei):
                    continue
                try:
                    # Clean folders older than 30 minutes
                    if time.time() - os.path.getmtime(full_path) > 1800:
                        shutil.rmtree(full_path, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass

    try:
        covers_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "covers")
        if os.path.exists(covers_dir):
            now = time.time()
            for f in os.listdir(covers_dir):
                if f.startswith("art_") or f.startswith("cover_"):
                    fp = os.path.join(covers_dir, f)
                    if now - os.path.getmtime(fp) > 7 * 86400:
                        try:
                            os.remove(fp)
                        except Exception:
                            pass
    except Exception:
        pass


# -------------------------------------------------------------
# Self-Healing Crash Guard & Auto-Recovery Engine
# -------------------------------------------------------------
CRASH_GUARD_FILE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WindowLand", "crash_guard.json")


def _record_crash_and_check_recovery() -> bool:
    """Limits auto-recovery to at most 3 restarts within 60s to prevent rapid crash loops."""
    now = time.time()
    crashes = []
    try:
        if os.path.exists(CRASH_GUARD_FILE):
            with open(CRASH_GUARD_FILE, "r", encoding="utf-8") as f:
                crashes = json.load(f)
    except Exception:
        crashes = []

    crashes = [t for t in crashes if now - t < 60.0]
    crashes.append(now)

    try:
        os.makedirs(os.path.dirname(CRASH_GUARD_FILE), exist_ok=True)
        with open(CRASH_GUARD_FILE, "w", encoding="utf-8") as f:
            json.dump(crashes, f)
    except Exception:
        pass

    return len(crashes) <= 3


def _respawn_self():
    """Spawns a clean new instance of the application detached from the dying process."""
    global _mutex_handle
    if _mutex_handle:
        try:
            _kernel32.ReleaseMutex(_mutex_handle)
            _kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
        except Exception:
            pass

    try:
        if getattr(sys, "frozen", False):
            target = [sys.executable]
        else:
            target = [sys.executable, os.path.abspath(__file__)]

        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        env = os.environ.copy()
        env.pop('_MEIPASS2', None)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        subprocess.Popen(target, env=env, creationflags=flags, close_fds=True)
    except Exception as e:
        log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"Failed to auto-recover/respawn: {e}\n")
        except Exception:
            pass


def _exception_hook(exctype, value, tb):
    err_str = "".join(traceback.format_exception(exctype, value, tb))
    log_file = os.path.join(os.path.expanduser("~"), "DynamicIsland_crash.log")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- CRASH {time.ctime()} ---\n{err_str}\n")
    except Exception:
        pass

    # Self-healing auto-recovery
    if _record_crash_and_check_recovery():
        _respawn_self()

    os._exit(1)


sys.excepthook = _exception_hook


class AppNativeEventFilter(QAbstractNativeEventFilter):
    """
    Handles native Windows broadcasts:
    1. TaskbarCreated: Restores system tray icon if Windows Explorer restarts.
    2. WinDin_ShowDynamicIsland: Reveals/expands island when user launches the app.
    """
    def __init__(self, island, tray_icon: QSystemTrayIcon):
        super().__init__()
        self.island = island
        self.tray_icon = tray_icon
        self.wm_taskbar_created = _user32.RegisterWindowMessageW("TaskbarCreated")
        self.wm_show_island = WM_SHOW_DYNAMIC_ISLAND

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == self.wm_taskbar_created:
                    self.tray_icon.hide()
                    self.tray_icon.show()
                elif msg.message == self.wm_show_island:
                    # User clicked app or launched again: reveal Dynamic Island!
                    self.island.wake_up()
            except Exception:
                pass
        return False, 0

from services.media_service import MediaService
from services.system_service import SystemService
from services.device_listener import DeviceService
from services.autostart_service import is_autostart_enabled, set_autostart
from services.phone_bridge import PhoneBridgeService
from ui.island_widget import DynamicIslandWidget
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def create_tray_icon() -> QIcon:
    ico_path = resource_path(os.path.join("assets", "app_icon.ico"))
    if os.path.exists(ico_path):
        return QIcon(ico_path)

    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    notch_rect = QRectF(12, 16, 40, 20)
    painter.setPen(QPen(QColor("#0A0A0C"), 1.5))
    painter.setBrush(QBrush(QColor("#0E0E14")))
    painter.drawRoundedRect(notch_rect, 6, 6)

    glow_rect = QRectF(34, 22, 8, 8)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("#0071E3")))
    painter.drawEllipse(glow_rect)

    painter.end()
    return QIcon(pix)


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    app = QApplication(sys.argv)
    app.setApplicationName("Hardware Notch Overlay")
    app.setQuitOnLastWindowClosed(False)

    # Global smooth font rendering
    from PyQt6.QtGui import QFont
    default_font = QFont("Segoe UI", 10)
    default_font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias |
        QFont.StyleStrategy.PreferQuality
    )
    app.setFont(default_font)

    # Clean stale temp residue from previous sessions to prevent decompression conflicts
    _cleanup_temp_residue()

    media_service = MediaService()
    system_service = SystemService()
    device_service = DeviceService()
    phone_service = PhoneBridgeService(port=54321)

    island = DynamicIslandWidget(media_service, system_service, device_service)

    # Restore user settings (position, screen, dock edge, theme, auto-hide)
    from services.settings_service import settings
    saved_cfg = settings.load()
    island.apply_saved_settings(saved_cfg)

    island.show()
    island.raise_()
    island.set_island_state("compact")
    island.set_glow_state("notification", duration_sec=3.5)

    media_service.start()
    system_service.start()
    device_service.start()

    # Wire phone notifications and remote wakeups to Dynamic Island with smart state routing
    import re

    def on_phone_notification(data: dict):
        app = data.get("app", "")
        title = data.get("title", "")
        msg = data.get("message", "")
        phone_type = data.get("phone", "iPhone")

        # 1. Incoming Call Detection -> call_live state (Spec 3.2)
        if "call" in app.lower() or "call" in title.lower() or "incoming" in msg.lower():
            caller = title if title and "call" not in title.lower() else (msg.split(" ")[0] if msg else "Mom")
            island.trigger_call(name=caller, number="", status=f"{phone_type} • Incoming Call")
            return

        # 2. 2FA Verification Code Detection -> otp_pill state (Spec 3.3)
        code_match = re.search(r'\b\d{3}[ -]\d{3}\b', msg) or re.search(r'\b\d{4,8}\b', msg)
        if ("otp" in msg.lower() or "code" in msg.lower() or "verification" in msg.lower() or "2fa" in msg.lower() or "code" in title.lower()) and code_match:
            clean_app = app.replace("📱", "").strip() or "Messages"
            island.trigger_otp(code=code_match.group(0), app=clean_app)
            return

        # 3. Default Notification Toast
        island.trigger_toast(app, title, msg)

    phone_service.notification_received.connect(on_phone_notification)
    phone_service.wake_requested.connect(island.wake_up)
    phone_service.device_paired.connect(
        lambda d: island.set_glow_state("success", duration_sec=2.5)
    )

    # ── Settings & Control Center Application Setup ───────────────
    settings_win_holder = [None]
    def show_settings():
        if settings_win_holder[0] is None:
            from ui.settings_window import SettingsWindow
            settings_win_holder[0] = SettingsWindow(
                island=island,
                media_service=media_service,
                system_service=system_service,
                device_service=device_service,
                phone_service=phone_service
            )
        settings_win_holder[0].show()
        settings_win_holder[0].raise_()
        settings_win_holder[0].activateWindow()

    phone_service.open_settings_requested.connect(show_settings)
    phone_service.dock_requested.connect(lambda edge: island.set_dock_edge(edge))

    def on_phone_simulate(kind: str):
        if kind == "osd":
            island.trigger_osd("Volume", 0.72, "72%", "volume")
        elif kind == "call":
            island.trigger_call("Mom", "+1 (555) 234-5678", "iPhone • Incoming Call")
        elif kind == "otp":
            island.trigger_otp("482 910", "Messages")
        elif kind == "shelf":
            island.trigger_file_shelf()
        elif kind == "download":
            island.set_download_progress(0.75)
        elif kind == "snip_toast":
            system_service.trigger_test_notification("Snipping Tool", "Screenshot copied to clipboard", "Saved to screenshots folder.")
        elif kind == "cal_toast":
            system_service.trigger_test_notification("Calendar", "12:30 PM Standup", "Sprint Architecture Review in 5 min.")
        elif kind == "demo_music":
            media_service.toggle_mock_mode()
        elif kind == "airpods":
            device_service.trigger_simulated_device("airpods", "Manu's AirPods Pro")
        elif kind == "headphones":
            device_service.trigger_simulated_device("headphones", "Sony WH-1000XM5")

    phone_service.simulate_requested.connect(on_phone_simulate)
    island.show_settings_requested.connect(show_settings)
    phone_service.start()

    # ── System Tray ──────────────────────────────────────────────
    tray_icon = QSystemTrayIcon(create_tray_icon(), app)
    app.setWindowIcon(create_tray_icon())
    tray_icon.setToolTip("Hardware Notch Overlay")

    # Native event filter: Restores tray icon on Explorer restart & reveals island on launch
    event_filter = AppNativeEventFilter(island, tray_icon)
    app.installNativeEventFilter(event_filter)

    # Ensure autostart is enabled permanently across Windows boot
    set_autostart(True)

    tray_menu = QMenu()
    tray_menu.setStyleSheet("""
        QMenu {
            background-color: #14151D;
            color: #EEEEF2;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 9px;
            padding: 5px;
            font-family: 'Segoe UI', -apple-system, sans-serif;
            font-size: 11.5px;
        }
        QMenu::item {
            padding: 5px 22px 5px 12px;
            border-radius: 5px;
            margin: 1px 0px;
        }
        QMenu::item:selected {
            background-color: #0A84FF;
            color: #FFFFFF;
        }
        QMenu::item:disabled {
            color: #585A66;
        }
        QMenu::separator {
            height: 1px;
            background-color: rgba(255, 255, 255, 0.08);
            margin: 4px 4px;
        }
    """)

    # ── Minimal Clean Taskbar Tray Menu (Settings & Quit Only) ───
    act_settings = QAction("⚙️  Settings", tray_menu)
    from PyQt6.QtGui import QFont
    act_settings_font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
    act_settings.setFont(act_settings_font)
    act_settings.triggered.connect(show_settings)
    tray_menu.addAction(act_settings)
    tray_menu.addSeparator()

    # Right-click directly on Dynamic Island opens this clean context menu
    island._on_right_click_callback = lambda pos: tray_menu.exec(pos)



    act_quit = QAction("Quit WindowLand", tray_menu)
    def on_quit():
        try:
            island.save_current_settings()
        except Exception:
            pass
        try:
            media_service.stop()
        except Exception:
            pass
        try:
            system_service.stop()
        except Exception:
            pass
        try:
            device_service.stop()
        except Exception:
            pass
        try:
            phone_service.stop()
        except Exception:
            pass

        global _mutex_handle
        if _mutex_handle:
            try:
                _kernel32.ReleaseMutex(_mutex_handle)
                _kernel32.CloseHandle(_mutex_handle)
                _mutex_handle = None
            except Exception:
                pass

        try:
            _cleanup_temp_residue()
        except Exception:
            pass

        try:
            app.quit()
        except Exception:
            pass

        os._exit(0)

    act_quit.triggered.connect(on_quit)
    tray_menu.addAction(act_quit)

    tray_icon.setContextMenu(tray_menu)
    # Tray activation: Single-click toggles island, Double-click opens Settings
    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            show_settings()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            island.toggle_expanded()

    tray_icon.activated.connect(on_tray_activated)
    tray_icon.show()
    tray_icon.showMessage(
        "Dynamic Island Active",
        "Running in background at top of screen. Press Alt+Space to expand.",
        QSystemTrayIcon.MessageIcon.Information,
        3000
    )

    if "--settings" in sys.argv or "-s" in sys.argv:
        show_settings()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
