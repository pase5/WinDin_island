"""
WindowLand Dynamic Island - Dedicated Settings & Control Center Application Entry Point.
Can be launched independently from desktop shortcut, terminal, or start menu:
    python settings_app.py
"""

import sys
import os
import subprocess
import urllib.request
import json
import ctypes

MUTEX_NAME = "Global\\WinDinDynamicIsland_SingleInstanceMutex"


def is_island_running() -> bool:
    """Checks if WindowLand Dynamic Island is already active."""
    # 1. Check HTTP status endpoint
    try:
        req = urllib.request.Request("http://127.0.0.1:54321/api/status")
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    # 2. Check Named Mutex
    try:
        kernel32 = ctypes.windll.kernel32
        h_mutex = kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)
        if h_mutex:
            kernel32.CloseHandle(h_mutex)
            return True
    except Exception:
        pass

    return False


def notify_running_instance_to_open_settings() -> bool:
    """Notifies active background instance to bring Settings window to front."""
    try:
        req = urllib.request.Request("http://127.0.0.1:54321/api/open_settings")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    # If the main Dynamic Island process is already running, tell it to open the Settings window
    if is_island_running():
        if notify_running_instance_to_open_settings():
            print("Opened Settings in running WindowLand instance.")
            sys.exit(0)

    # Otherwise, run standalone Settings application
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont, QIcon
    from services.settings_service import settings
    from ui.settings_window import SettingsWindow

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("WindowLand Settings & Control Center")

    default_font = QFont("Segoe UI", 10)
    default_font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias |
        QFont.StyleStrategy.PreferQuality
    )
    app.setFont(default_font)

    # Set icon if exists
    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.ico")
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))

    window = SettingsWindow()
    window.show()
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
