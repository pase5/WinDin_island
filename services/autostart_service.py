"""
Autostart Manager for Windows 10 & 11.
Manages automatic silent background startup on user login via:
1. Windows Registry (HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
2. Windows Startup Folder (%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\DynamicIsland.lnk)

Provides dual-layer persistence so the app always starts on Windows boot
without requiring administrator privileges or showing UAC prompts.
"""

import sys
import os
import winreg
import tempfile
import subprocess

APP_REG_NAME = "DynamicIslandOverlay"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
SHORTCUT_NAME = "DynamicIsland.lnk"


def get_startup_folder() -> str:
    """Returns the user's Windows Startup folder path."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
    return os.path.join(os.path.expanduser("~"), r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup")


def get_shortcut_path() -> str:
    """Returns the full path to the DynamicIsland shortcut in the Startup folder."""
    return os.path.join(get_startup_folder(), SHORTCUT_NAME)


def get_target_exe_and_workdir() -> tuple[str, str]:
    """
    Returns (exe_path, working_dir) for the current installation.
    Works whether running as frozen PyInstaller executable or Python script.
    """
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
        work_dir = os.path.dirname(os.path.dirname(os.path.abspath(exe_path)))
        if not os.path.exists(os.path.join(work_dir, "assets")):
            work_dir = os.path.dirname(os.path.abspath(exe_path))
        return os.path.abspath(exe_path), os.path.abspath(work_dir)
    else:
        python_exe = sys.executable
        dirname = os.path.dirname(python_exe)
        pythonw_candidate = os.path.join(dirname, "pythonw.exe")
        runner = pythonw_candidate if os.path.exists(pythonw_candidate) else python_exe
        main_script = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"))
        work_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # For python scripts, we can target the dist exe if built, otherwise pythonw + script
        dist_exe = os.path.join(work_dir, "dist", "DynamicIsland.exe")
        if os.path.exists(dist_exe):
            return dist_exe, work_dir
        return f'"{runner}" "{main_script}"', work_dir


def create_startup_shortcut() -> bool:
    """Creates a Windows shortcut (.lnk) in the Startup folder."""
    try:
        exe_path, work_dir = get_target_exe_and_workdir()
        lnk_path = get_shortcut_path()

        os.makedirs(os.path.dirname(lnk_path), exist_ok=True)

        vbs_content = f'''Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{lnk_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{exe_path}"
oLink.WorkingDirectory = "{work_dir}"
oLink.Description = "WinDin Island Hardware Notch Desktop Overlay"
oLink.Save
'''
        temp_vbs = os.path.join(tempfile.gettempdir(), "create_dynamic_island_sc.vbs")
        with open(temp_vbs, "w", encoding="utf-8") as f:
            f.write(vbs_content)

        subprocess.run(["cscript", "//nologo", temp_vbs], check=True, creationflags=0x08000000)
        try:
            os.remove(temp_vbs)
        except Exception:
            pass

        return os.path.exists(lnk_path)
    except Exception:
        return False


def remove_startup_shortcut() -> bool:
    """Removes the Windows shortcut (.lnk) from the Startup folder."""
    try:
        lnk_path = get_shortcut_path()
        if os.path.exists(lnk_path):
            os.remove(lnk_path)
        return True
    except Exception:
        return False


def is_autostart_enabled() -> bool:
    """
    Checks whether automatic startup is configured.
    Returns True if either the Registry Run key or the Startup shortcut exists.
    """
    # 1. Check Startup Folder shortcut
    if os.path.exists(get_shortcut_path()):
        return True

    # 2. Check Registry Run key
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return bool(val)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return False


def set_autostart(enable: bool, custom_exe_path: str = None) -> bool:
    """
    Enables or disables automatic startup with Windows.
    Applies both Registry Run key and Startup folder shortcut for bulletproof autostart.
    """
    success = True

    if enable:
        exe_path, work_dir = get_target_exe_and_workdir()
        target = f'"{custom_exe_path}"' if custom_exe_path else f'"{exe_path}"'

        # 1. Update Registry Run Key
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, target)
        except Exception:
            success = False

        # 2. Update Startup Folder Shortcut
        if not create_startup_shortcut():
            success = False

    else:
        # 1. Remove Registry Key
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
        except Exception:
            success = False

        # 2. Remove Startup Shortcut
        if not remove_startup_shortcut():
            success = False

    return success
