"""
Persistent Settings Manager for WindowLand Dynamic Island.
Saves and loads user preferences to/from %APPDATA%/WindowLand/settings.json:
- Dock edge (top, left, right, bottom, corners, floating)
- Screen position & monitor index
- Theme mode (ambient reactive, obsidian, titanium, solid color)
- Auto-hide & autostart preferences
- 24-hour time format preference
"""

import os
import json
import logging
from typing import Dict, Any

SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "WindowLand")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "dock_edge": "top",
    "dock_ratio_x": 0.5,
    "dock_ratio_y": 0.5,
    "floating_x": -1,
    "floating_y": -1,
    "screen_index": 0,
    "theme_mode": "ambient",
    "theme_preset": "ambient",
    "ambient_opacity": 0.24,
    "solid_color": "#08080C",
    "gradient_c1": "#0A1628",
    "gradient_c2": "#050912",
    "clock_accent": "auto",
    "show_border": True,
    "hover_to_expand": True,
    "auto_hide": False,
    "time_format": "24h",
    "autostart": True,
}


class SettingsService:
    def __init__(self):
        self._settings = dict(DEFAULT_SETTINGS)
        self._ensure_dir()
        self.load()

    def _ensure_dir(self):
        try:
            os.makedirs(SETTINGS_DIR, exist_ok=True)
        except Exception:
            pass

    def load(self) -> Dict[str, Any]:
        """Loads settings from disk, applying default fallbacks for missing keys."""
        if not os.path.exists(SETTINGS_FILE):
            self._settings = dict(DEFAULT_SETTINGS)
            self.save()
            return self._settings

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Merge with defaults
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(data)
                    self._settings = merged
        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            self._settings = dict(DEFAULT_SETTINGS)

        return self._settings

    def save(self) -> bool:
        """Atomically saves current settings to disk."""
        self._ensure_dir()
        temp_file = SETTINGS_FILE + ".tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
            if os.path.exists(SETTINGS_FILE):
                os.replace(temp_file, SETTINGS_FILE)
            else:
                os.rename(temp_file, SETTINGS_FILE)
            return True
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True):
        self._settings[key] = value
        if auto_save:
            self.save()

    def update(self, updates: Dict[str, Any], auto_save: bool = True):
        self._settings.update(updates)
        if auto_save:
            self.save()

    @property
    def all(self) -> Dict[str, Any]:
        return dict(self._settings)


# Global singleton instance
settings = SettingsService()
