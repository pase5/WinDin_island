import threading
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

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt, QRectF, QAbstractNativeEventFilter
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPen,
    QBrush, QAction
)

# -------------------------------------------------------------
# Single Instance Lock & Wakeup via Windows Named Mutex & IPC
# If the app is already running, notify the active instance to
# reveal & expand the Dynamic Island immediately, then exit.
# -------------------------------------------------------------
MUTEX_NAME = "Local\\WindowLand_DynamicIsland_SingleInstance_Mutex"
_kernel32 = ctypes.windll.kernel32
_user32 = ctypes.windll.user32
WM_SHOW_DYNAMIC_ISLAND = _user32.RegisterWindowMessageW("WinDin_ShowDynamicIsland")

_mutex_handle = _kernel32.CreateMutexW(None, True, MUTEX_NAME)
ERROR_ALREADY_EXISTS = 183
if _kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
    # Check if a live instance is ACTUALLY responding on the local bridge
    is_alive = False
    try:
        import urllib.request
        target_endpoint = "open_settings" if ("--settings" in sys.argv or "-s" in sys.argv) else "wake"
        req = urllib.request.Request(f"http://127.0.0.1:8765/{target_endpoint}")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            if resp.status == 200:
                is_alive = True
    except Exception:
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:54321/api/status")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                if resp.status == 200:
                    is_alive = True
        except Exception:
            is_alive = False

    if is_alive:
        # A live instance was contacted and woken up; safely exit launcher
        HWND_BROADCAST = 0xFFFF
        _user32.PostMessageW(HWND_BROADCAST, WM_SHOW_DYNAMIC_ISLAND, 0, 0)
        sys.exit(0)
    else:
        # Mutex was lingering from a killed/crashed instance with no active server; proceed to start!
        pass

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
        # Also clean MEIPASS2 from current process environment if it exists
        os.environ.pop("_MEIPASS2", None)
        for item in os.listdir(temp_dir):
            if item.startswith("_MEI"):
                full_path = os.path.join(temp_dir, item)
                if current_mei and os.path.abspath(full_path) == os.path.abspath(current_mei):
                    continue
                try:
                    # Clean folders older than 15 minutes.
                    # NEVER delete folders created within the last 5 minutes (300s) to avoid
                    # interrupting another instance or child process that is currently extracting.
                    age = time.time() - os.path.getmtime(full_path)
                    if age > 900 or (age > 300 and not os.path.exists(os.path.join(full_path, "base_library.zip"))):
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
        for k in list(env.keys()):
            if k.startswith("_MEI") or k in ("PYTHONPATH", "PYTHONHOME"):
                env.pop(k, None)
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
from services.autostart_service import set_autostart
from services.phone_bridge import PhoneBridgeService
try:
    from bridge.phone_bridge import PhoneBridge
except Exception as _e:
    PhoneBridge = None
    print(f"Warning: bridge.phone_bridge optional import skipped: {_e}")
from ui.island_widget import DynamicIslandWidget


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

    # Obsidian squircle background
    painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
    painter.setBrush(QBrush(QColor("#08080C")))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 14, 14)

    # Hardware notch pill cutout
    notch_rect = QRectF(13, 24, 38, 16)
    painter.setPen(QPen(QColor("#262630"), 1.0))
    painter.setBrush(QBrush(QColor("#000000")))
    painter.drawRoundedRect(notch_rect, 8, 8)

    # Emerald status circle
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("#34C759")))
    painter.drawEllipse(QRectF(20, 29, 5, 5))

    # Equalizer bars
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.drawRoundedRect(QRectF(30, 28, 2, 7), 1, 1)
    painter.setBrush(QBrush(QColor("#34C759")))
    painter.drawRoundedRect(QRectF(34, 26, 2, 11), 1, 1)
    painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
    painter.drawRoundedRect(QRectF(38, 27, 2, 9), 1, 1)

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
    phone_bridge = None
    if PhoneBridge is not None:
        try:
            phone_bridge = PhoneBridge(
                port=8765,
                on_wake=lambda: island.phone_signals.wake_requested.emit() if hasattr(island, "phone_signals") else None,
                on_open_settings=lambda: island.show_settings_requested.emit() if hasattr(island, "show_settings_requested") else None,
            )

            def _run_bridge_loop():
                try:
                    import asyncio
                    asyncio.run(phone_bridge.run_forever())
                except Exception as e:
                    print(f"WinDin-Link bridge server error: {e}")

            bridge_thread = threading.Thread(target=_run_bridge_loop, daemon=True, name="WinDinLinkBridge")
            bridge_thread.start()
        except Exception as e:
            print(f"WinDin-Link bridge init error: {e}")
            phone_bridge = None

    island = DynamicIslandWidget(media_service, system_service, device_service)
    if phone_bridge is not None:
        island.set_phone_bridge(phone_bridge)

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
    phone_service.toggle_requested.connect(island.toggle_expanded)

    PRESETS_MAP = {
        "ambient": ("ambient", "#08080C", "#08080C"),
        "obsidian": ("solid", "#08080C", "#08080C"),
        "titanium": ("solid", "#181A22", "#181A22"),
        "midnight": ("gradient", "#0A1628", "#050912"),
        "emerald": ("gradient", "#081C15", "#040B09"),
        "ember": ("gradient", "#231116", "#0B0709"),
        "sunset": ("gradient", "#231116", "#0B0709"),
        "violet": ("gradient", "#1A102B", "#08060E"),
        "slate": ("gradient", "#222530", "#101218"),
    }

    def on_phone_theme(data: dict):
        if not data:
            return
        preset = data.get("preset")
        if preset and preset in PRESETS_MAP:
            mode, c1, c2 = PRESETS_MAP[preset]
            data["theme_preset"] = preset
            data["theme_mode"] = mode
            if mode == "gradient":
                data["gradient_c1"] = c1
                data["gradient_c2"] = c2
            elif mode == "solid":
                data["solid_color"] = c1

        if "c1" in data and "gradient_c1" not in data:
            data["gradient_c1"] = data["c1"]
        if "c2" in data and "gradient_c2" not in data:
            data["gradient_c2"] = data["c2"]

        if "mode" in data and "theme_mode" not in data:
            data["theme_mode"] = data["mode"]

        mode = data.get("theme_mode", "ambient")
        if mode == "ambient":
            try:
                op = float(data.get("ambient_opacity", data.get("opacity", 0.24)))
                island.set_theme_ambient(op)
            except Exception:
                island.set_theme_ambient()
        elif mode == "gradient":
            c1 = QColor(data.get("gradient_c1", "#0A1628"))
            c2 = QColor(data.get("gradient_c2", "#050912"))
            island.set_theme_gradient(c1, c2)
        elif mode in ("obsidian", "solid"):
            col = data.get("solid_color", data.get("color", "#08080C"))
            island.set_theme_solid(QColor(col))
        elif mode in ("titanium", "frosted"):
            col = data.get("solid_color", data.get("color", "#181A22"))
            island.set_theme_solid(QColor(col))

        if "clock_accent" in data:
            island._clock_accent = str(data["clock_accent"])
            island.update()
        if "show_border" in data:
            val = str(data["show_border"]).lower() in ("true", "1", "yes")
            island._show_border = val
            island.update()
        if "hover_to_expand" in data:
            island._hover_to_expand = str(data["hover_to_expand"]).lower() in ("true", "1", "yes")
        if "auto_hide" in data:
            val = str(data["auto_hide"]).lower() in ("true", "1", "yes")
            island.set_auto_hide(val)
        if "time_format" in data:
            tf = str(data["time_format"]).lower()
            island.use_24h_format = (tf in ("24h", "true", "24-hour"))
            island.update()
        if "dock_edge" in data:
            island.set_dock_edge(str(data["dock_edge"]))

        # Persist changes
        try:
            settings.update(**data)
        except Exception:
            pass

    def on_phone_settings(data: dict):
        on_phone_theme(data)

    phone_service.theme_requested.connect(on_phone_theme)
    phone_service.settings_requested.connect(on_phone_settings)

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

    # ── Minimal Clean Taskbar Tray Menu (Settings, Pairing & Quit) ───
    from PyQt6.QtGui import QFont
    tray_item_font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)

    act_pair = QAction("Pair Phone (QR Code)...", tray_menu)
    act_pair.setFont(tray_item_font)
    act_pair.triggered.connect(island.open_qr_pairing_modal)
    tray_menu.addAction(act_pair)

    act_settings = QAction("Settings...", tray_menu)
    act_settings.setFont(tray_item_font)
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
    phone_service.quit_requested.connect(on_quit)
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
