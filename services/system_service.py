"""
System Service for Glass Notch Overlay.
Handles:
1. Real-time Clock & Battery Status (psutil)
2. Local JSON-backed Reminders & To-Do manager with timed alert checks
3. System Volume Mute/Unmute via pycaw
4. Screen capture & clipboard copy
5. Do Not Disturb (DND) mode
6. Windows Toast Notification listener & queue
"""

import os
import json
import time
import datetime
import threading
import asyncio
from typing import List, Dict, Any, Optional, Tuple

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication

# Audio Endpoint via pycaw
try:
    import comtypes
    from pycaw.pycaw import AudioUtilities
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False

# High-resolution WASAPI loopback spectrum engine
try:
    from services.audio_spectrum import AudioSpectrumEngine
    HAS_SPECTRUM_ENGINE = True
except Exception:
    HAS_SPECTRUM_ENGINE = False

# Battery via psutil
try:
    import psutil
    HAS_PSUTIL = True
except Exception:
    HAS_PSUTIL = False

# WinRT Notifications
HAS_WINRT_NOTIF = False
try:
    import winrt.windows.ui.notifications as un
    import winrt.windows.ui.notifications.management as unm
    import winrt.windows.applicationmodel
    HAS_WINRT_NOTIF = True
except Exception:
    pass


class SystemService(QObject):
    """
    Central system services provider.
    """
    time_tick = pyqtSignal(str, str)            # time_str ("01:27 PM"), date_str ("Thu, Nov 19")
    battery_tick = pyqtSignal(dict)             # {"percent": 99, "is_plugged": True}
    volume_changed = pyqtSignal(bool, float)    # is_muted, volume_level (0.0 to 1.0)
    screenshot_taken = pyqtSignal(str)          # filepath
    dnd_changed = pyqtSignal(bool)              # is_dnd
    reminder_alert = pyqtSignal(dict)           # reminder object that just fired
    reminders_updated = pyqtSignal(list)        # full list of reminders
    notification_received = pyqtSignal(dict)    # {"app": ..., "title": ..., "message": ...}
    status_alert = pyqtSignal(str, str)         # category, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dnd_enabled = False
        self._storage_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reminders.json")
        self._reminders: List[Dict[str, Any]] = []
        self._alerted_reminder_ids = set()
        self._seen_notification_ids = set()
        self._spectrum_engine = AudioSpectrumEngine(22) if HAS_SPECTRUM_ENGINE else None

        self._load_reminders()

        # 1-second clock timer
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._on_clock_tick)

        # 5-second reminder alert checker timer
        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(5000)
        self._reminder_timer.timeout.connect(self._check_reminder_due_times)

        # 10-second battery checker timer
        self._battery_timer = QTimer(self)
        self._battery_timer.setInterval(10000)
        self._battery_timer.timeout.connect(self._on_battery_check)

        self._listener_running = False
        self._listener_thread: Optional[threading.Thread] = None

    def start(self):
        self._on_clock_tick()
        self._on_battery_check()
        self._clock_timer.start()
        self._reminder_timer.start()
        self._battery_timer.start()
        self._start_notification_listener()
        if self._spectrum_engine:
            self._spectrum_engine.start()

    def stop(self):
        self._clock_timer.stop()
        self._reminder_timer.stop()
        self._battery_timer.stop()
        self._listener_running = False
        if self._spectrum_engine:
            self._spectrum_engine.stop()

    def _on_clock_tick(self):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%a, %b %d")
        self.time_tick.emit(time_str, date_str)

    def _on_battery_check(self):
        info = self.get_battery_info()
        self.battery_tick.emit(info)

    def get_battery_info(self) -> dict:
        if HAS_PSUTIL:
            try:
                b = psutil.sensors_battery()
                if b is not None:
                    return {
                        "has_battery": True,
                        "percent": int(b.percent),
                        "is_plugged": bool(b.power_plugged)
                    }
            except Exception:
                pass
        return {"has_battery": False, "percent": 100, "is_plugged": True}

    def _load_reminders(self):
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    self._reminders = json.load(f)
            except Exception:
                self._reminders = []
        
        if not self._reminders:
            self._reminders = [
                {
                    "id": "rem-1",
                    "text": "Review architecture & UI polish",
                    "completed": False,
                    "created_at": time.time(),
                    "due_time": None
                },
                {
                    "id": "rem-2",
                    "text": "Daily standup & team sync",
                    "completed": True,
                    "created_at": time.time() - 3600,
                    "due_time": None
                }
            ]
            self._save_reminders()

    def _save_reminders(self):
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(self._reminders, f, indent=2)
        except Exception:
            pass

    def get_reminders(self) -> List[Dict[str, Any]]:
        return list(self._reminders)

    def add_reminder(self, text: str, due_minutes: Optional[int] = None) -> Dict[str, Any]:
        text = text.strip()
        if not text:
            return {}
        
        due_timestamp = None
        if due_minutes and due_minutes > 0:
            due_timestamp = time.time() + (due_minutes * 60)

        item = {
            "id": f"rem-{int(time.time() * 1000)}",
            "text": text,
            "completed": False,
            "created_at": time.time(),
            "due_time": due_timestamp
        }
        self._reminders.append(item)
        self._save_reminders()
        self.reminders_updated.emit(self.get_reminders())
        return item

    def toggle_reminder(self, reminder_id: str):
        for item in self._reminders:
            if item["id"] == reminder_id:
                item["completed"] = not item["completed"]
                break
        self._save_reminders()
        self.reminders_updated.emit(self.get_reminders())

    def delete_reminder(self, reminder_id: str):
        self._reminders = [r for r in self._reminders if r["id"] != reminder_id]
        self._save_reminders()
        self.reminders_updated.emit(self.get_reminders())

    def _check_reminder_due_times(self):
        now = time.time()
        for item in self._reminders:
            if not item.get("completed", False):
                due = item.get("due_time")
                rid = item.get("id")
                if due and due <= now and rid not in self._alerted_reminder_ids:
                    self._alerted_reminder_ids.add(rid)
                    self.reminder_alert.emit(item)
                    if not self._dnd_enabled:
                        self.notification_received.emit({
                            "app": "Task Alert",
                            "title": "Reminder Due",
                            "message": item.get("text", "Upcoming reminder")
                        })

    def _get_volume_endpoint(self):
        if not HAS_PYCAW:
            return None
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            speakers = AudioUtilities.GetSpeakers()
            if not speakers:
                return None
            vol = getattr(speakers, "EndpointVolume", None)
            if vol is None:
                interface = speakers.Activate(AudioUtilities.IAudioEndpointVolume._iid_, 0, None)
                from ctypes import cast, POINTER
                from pycaw.pycaw import IAudioEndpointVolume
                vol = cast(interface, POINTER(IAudioEndpointVolume))
            return vol
        except Exception:
            return None

    def get_audio_spectrum(self) -> Tuple[List[float], List[float]]:
        """Returns (bands, peak_caps) from live 60 FPS WASAPI loopback FFT."""
        if getattr(self, "_spectrum_engine", None):
            return self._spectrum_engine.get_spectrum(), self._spectrum_engine.get_peak_caps()
        return [0.0] * 22, [0.0] * 22

    def get_bass_energy(self) -> float:
        """Returns live sub-bass / kick drum transient energy [0.0 .. 1.0]."""
        if getattr(self, "_spectrum_engine", None):
            return self._spectrum_engine.get_bass()
        return 0.0

    def get_audio_peak(self) -> float:
        """Returns live hardware master audio peak (0.0 to 1.0) with zero overhead."""
        if getattr(self, "_spectrum_engine", None):
            peak = self._spectrum_engine.get_peak()
            if peak > 0.001:
                return peak
        if not HAS_PYCAW:
            return 0.0
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            if not hasattr(self, "_cached_meter") or self._cached_meter is None:
                speakers = AudioUtilities.GetSpeakers()
                if speakers and hasattr(speakers, "_dev") and speakers._dev:
                    from pycaw.pycaw import IAudioMeterInformation
                    m = speakers._dev.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None)
                    self._cached_meter = m.QueryInterface(IAudioMeterInformation)
            if self._cached_meter:
                return float(self._cached_meter.GetPeakValue())
        except Exception:
            self._cached_meter = None
        return 0.0

    def get_mute_state(self) -> (bool, float):
        endpoint = self._get_volume_endpoint()
        if endpoint:
            try:
                muted = bool(endpoint.GetMute())
                level = float(endpoint.GetMasterVolumeLevelScalar())
                return muted, level
            except Exception:
                pass
        return False, 0.75

    def toggle_mute(self) -> bool:
        endpoint = self._get_volume_endpoint()
        if endpoint:
            try:
                curr_mute = bool(endpoint.GetMute())
                new_mute = not curr_mute
                endpoint.SetMute(new_mute, None)
                level = float(endpoint.GetMasterVolumeLevelScalar())
                self.volume_changed.emit(new_mute, level)
                msg = "Audio Muted" if new_mute else "Audio Unmuted"
                self.status_alert.emit("volume", msg)
                return new_mute
            except Exception:
                pass
        self.volume_changed.emit(True, 0.5)
        self.status_alert.emit("volume", "Mute Toggled")
        return True

    def take_screenshot(self) -> Optional[str]:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return None

        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            return None

        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
        if not os.path.exists(pictures_dir):
            try:
                os.makedirs(pictures_dir, exist_ok=True)
            except Exception:
                pictures_dir = os.path.join(os.path.expanduser("~"), "Desktop")

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Capture_{timestamp_str}.png"
        filepath = os.path.join(pictures_dir, filename)

        success = pixmap.save(filepath, "PNG")
        if success:
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setPixmap(pixmap)
            self.screenshot_taken.emit(filepath)
            self.status_alert.emit("success", f"Saved: {filename}")
            return filepath
        return None

    @property
    def is_dnd(self) -> bool:
        return self._dnd_enabled

    def toggle_dnd(self) -> bool:
        self._dnd_enabled = not self._dnd_enabled
        self.dnd_changed.emit(self._dnd_enabled)
        msg = "DND: ON" if self._dnd_enabled else "DND: OFF"
        self.status_alert.emit("dnd", msg)
        return self._dnd_enabled

    def trigger_test_notification(self, app="System Alert", title="Quick Alert", message="Compact notch expanded on alert!"):
        app_icon = None
        try:
            from services.icon_service import get_app_icon
            app_icon = get_app_icon(app)
        except Exception:
            pass
        notif = {
            "app": app,
            "title": title,
            "message": message,
            "app_icon": app_icon,
            "time": time.time()
        }
        self.notification_received.emit(notif)

    def _start_notification_listener(self):
        if not HAS_WINRT_NOTIF:
            return
        self._listener_running = True
        self._listener_thread = threading.Thread(target=self._run_notif_worker, daemon=True, name="NotifListener")
        self._listener_thread.start()

    def _run_notif_worker(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._notif_monitor_loop())
        finally:
            loop.close()

    async def _notif_monitor_loop(self):
        try:
            listener = unm.UserNotificationListener.current
            access = await listener.request_access_async()
            if int(access) != 1:
                return

            try:
                initial_notes = await listener.get_notifications_async(un.NotificationKinds.TOAST)
                for n in initial_notes:
                    self._seen_notification_ids.add(n.id)
            except Exception:
                pass

            while self._listener_running:
                await asyncio.sleep(1.0)
                if self._dnd_enabled:
                    continue

                try:
                    current_notes = await listener.get_notifications_async(un.NotificationKinds.TOAST)
                    for n in current_notes:
                        if n.id not in self._seen_notification_ids:
                            self._seen_notification_ids.add(n.id)
                            app_name = "Notification"
                            try:
                                if n.app_info and n.app_info.display_info:
                                    app_name = n.app_info.display_info.display_name or "Notification"
                            except Exception:
                                pass

                            binding = n.notification.visual.get_binding(un.KnownNotificationBindings.toast_generic)
                            title = "New Notification"
                            msg = ""
                            if binding:
                                texts = [t.text for t in binding.get_text_elements() if t and t.text]
                                if len(texts) > 0:
                                    title = texts[0]
                                if len(texts) > 1:
                                    msg = " ".join(texts[1:])
                                elif len(texts) == 1:
                                    msg = texts[0]

                            app_icon = None
                            try:
                                from services.icon_service import get_app_icon
                                app_icon = get_app_icon(app_name)
                            except Exception:
                                pass

                            self.notification_received.emit({
                                "app": app_name,
                                "title": title,
                                "message": msg or "Incoming alert",
                                "app_icon": app_icon,
                                "time": time.time()
                            })
                except Exception:
                    pass

        except Exception:
            pass
