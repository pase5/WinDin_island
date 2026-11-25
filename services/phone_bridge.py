"""
Phone Notification Bridge Service.
Runs an embedded, lightweight local HTTP and REST API server on the local Wi-Fi network.
Allows iOS (iPhone Shortcuts) and Android (MacroDroid / Tasker / Webhooks) on the same
network to sync and forward phone notifications directly to the Windows Dynamic Island.
Also provides a pairing web companion accessible at http://<local_ip>:54321.
Strictly adheres to DESIGN.md and AGENTS.md.
"""

import json
import socket
import threading
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from services.web_companion import WEB_COMPANION_HTML

MOBILE_COMPANION_HTML = WEB_COMPANION_HTML


def get_local_ip() -> str:
    """Detects primary local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class PhoneBridgeHandler(BaseHTTPRequestHandler):
    """Handles incoming mobile HTTP requests for pairing, notifications, and wakeups."""

    server_ref = None  # Reference to PhoneBridgeService

    def log_message(self, format, *args):
        # Suppress noisy console logs
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path in ("", "/index.html", "/pair"):
            # Serve the modern Ambient Glass web companion
            host = self.headers.get("Host") or f"{get_local_ip()}:54321"
            html = MOBILE_COMPANION_HTML.replace("{HOST}", host)
            body = html.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)

            if self.server_ref:
                ua = self.headers.get("User-Agent", "Mobile")
                self.server_ref.device_paired.emit({"ua": ua, "ip": self.client_address[0]})

        elif path in ("/api/status", "/status"):
            res = json.dumps({
                "status": "ok",
                "app": "WindowLand Dynamic Island",
                "version": "2.0.0",
                "ip": get_local_ip(),
                "port": 54321
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/wake", "/wake"):
            if self.server_ref:
                self.server_ref.wake_requested.emit()
            res = json.dumps({"status": "ok", "action": "woken"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/toggle", "/toggle"):
            if self.server_ref:
                self.server_ref.toggle_requested.emit()
            res = json.dumps({"status": "ok", "action": "toggled"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/open_settings", "/api/settings_window"):
            if self.server_ref:
                self.server_ref.open_settings_requested.emit()
            res = json.dumps({"status": "ok", "action": "open_settings"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/quit", "/quit"):
            if self.server_ref:
                self.server_ref.quit_requested.emit()
            res = json.dumps({"status": "ok", "action": "quit"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path.startswith("/api/dock"):
            query = parse_qs(urlparse(self.path).query)
            edge = query.get("edge", ["top"])[0]
            if self.server_ref:
                self.server_ref.dock_requested.emit(edge)
            res = json.dumps({"status": "ok", "dock": edge}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path.startswith("/api/simulate"):
            query = parse_qs(urlparse(self.path).query)
            kind = query.get("kind", ["osd"])[0]
            if self.server_ref:
                self.server_ref.simulate_requested.emit(kind)
            res = json.dumps({"status": "ok", "simulated": kind}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path.startswith("/api/theme"):
            query = parse_qs(urlparse(self.path).query)
            theme_data = {
                "mode": query.get("mode", ["ambient"])[0],
                "color": query.get("color", ["#08080C"])[0],
                "opacity": query.get("opacity", ["0.25"])[0]
            }
            if self.server_ref:
                self.server_ref.theme_requested.emit(theme_data)
            res = json.dumps({"status": "ok", "theme": theme_data}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")

        if path in ("/api/wake", "/wake"):
            if self.server_ref:
                self.server_ref.wake_requested.emit()
            res = json.dumps({"status": "ok", "action": "woken"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/toggle", "/toggle"):
            if self.server_ref:
                self.server_ref.toggle_requested.emit()
            res = json.dumps({"status": "ok", "action": "toggled"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/open_settings", "/api/settings_window"):
            if self.server_ref:
                self.server_ref.open_settings_requested.emit()
            res = json.dumps({"status": "ok", "action": "open_settings"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/quit", "/quit"):
            if self.server_ref:
                self.server_ref.quit_requested.emit()
            res = json.dumps({"status": "ok", "action": "quit"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path.startswith("/api/dock"):
            query = parse_qs(urlparse(self.path).query)
            edge = query.get("edge", ["top"])[0]
            if self.server_ref:
                self.server_ref.dock_requested.emit(edge)
            res = json.dumps({"status": "ok", "dock": edge}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path.startswith("/api/simulate"):
            query = parse_qs(urlparse(self.path).query)
            kind = query.get("kind", ["osd"])[0]
            if self.server_ref:
                self.server_ref.simulate_requested.emit(kind)
            res = json.dumps({"status": "ok", "simulated": kind}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path.startswith("/api/theme"):
            query = parse_qs(urlparse(self.path).query)
            content_length = int(self.headers.get("Content-Length", 0))
            body_data = {}
            if content_length > 0:
                try:
                    body_data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    pass

            theme_data = {
                "mode": query.get("mode", [body_data.get("mode", "ambient")])[0],
                "color": query.get("color", [body_data.get("color", "#08080C")])[0],
                "opacity": query.get("opacity", [body_data.get("opacity", "0.25")])[0]
            }
            if self.server_ref:
                self.server_ref.theme_requested.emit(theme_data)
            res = json.dumps({"status": "ok", "theme": theme_data}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        elif path in ("/api/notify", "/api/notification", "/notify", "/message"):
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            data = {}
            if post_data:
                try:
                    data = json.loads(post_data.decode("utf-8"))
                except Exception:
                    data = {"message": post_data.decode("utf-8", errors="ignore")}

            app_name = data.get("app") or data.get("source") or "Phone"
            title = data.get("title") or data.get("sender") or data.get("contact") or "Mobile Notification"
            message = data.get("message") or data.get("body") or data.get("text") or "Incoming alert"
            phone = data.get("phone") or "Mobile"

            # Clean notification payload (Rule 1 AGENTS.md: Zero system emojis)
            notif_payload = {
                "app": str(app_name).upper(),
                "title": title,
                "message": message,
                "is_phone": True,
                "phone": phone
            }

            if self.server_ref:
                self.server_ref.notification_received.emit(notif_payload)

            res = json.dumps({"status": "ok", "delivered": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(res)

        else:
            self.send_response(404)
            self.end_headers()


class PhoneBridgeService(QObject):
    """
    Background local network phone bridge service.
    Exposes signals when phone notifications are received or pairing events occur.
    """
    notification_received = pyqtSignal(dict)  # {"app": ..., "title": ..., "message": ..., "is_phone": True}
    device_paired = pyqtSignal(dict)          # {"ua": ..., "ip": ...}
    wake_requested = pyqtSignal()
    toggle_requested = pyqtSignal()
    open_settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    dock_requested = pyqtSignal(str)
    simulate_requested = pyqtSignal(str)
    theme_requested = pyqtSignal(dict)

    def __init__(self, port: int = 54321, parent=None):
        super().__init__(parent)
        self.port = port
        self.local_ip = get_local_ip()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def pairing_url(self) -> str:
        return f"http://{self.local_ip}:{self.port}"

    def start(self):
        """Starts the local phone bridge HTTP server on a background daemon thread."""
        if self._running:
            return

        PhoneBridgeHandler.server_ref = self

        # Try designated port, or fallback up to +5
        for p in range(self.port, self.port + 5):
            try:
                self._server = HTTPServer(("0.0.0.0", p), PhoneBridgeHandler)
                self.port = p
                break
            except OSError:
                continue

        if not self._server:
            return

        self._running = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="PhoneBridgeServer")
        self._thread.start()

    def stop(self):
        """Stops the phone bridge server."""
        self._running = False
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
