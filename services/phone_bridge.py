"""
Phone Notification Bridge Service.
Runs an embedded, lightweight local HTTP & REST API server on the local Wi-Fi network.
Allows iOS (iPhone Shortcuts) and Android (MacroDroid / Tasker / Webhooks) on the same
network to sync and forward phone notifications directly to the Windows Dynamic Island.
Also provides a pairing web companion accessible at http://<local_ip>:54321.
"""

import os
import sys
import json
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal


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


# Modern Apple-inspired dark liquid glass mobile web companion HTML
MOBILE_COMPANION_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Dynamic Island • Phone Bridge</title>
<style>
  :root {
    --bg: #090A10;
    --card: rgba(22, 24, 38, 0.75);
    --border: rgba(255, 255, 255, 0.12);
    --accent: #56CCF2;
    --accent-glow: rgba(86, 204, 242, 0.35);
    --emerald: #38EF7D;
    --text: #FFFFFF;
    --text-muted: #8E8E9E;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body {
    background: radial-gradient(circle at 50% 0%, #171A29, var(--bg));
    color: var(--text);
    min-height: 100vh;
    padding: 24px 16px 48px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .container { width: 100%; max-width: 480px; }
  .header { text-align: center; margin-bottom: 24px; }
  .pill-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(56, 239, 125, 0.12);
    border: 1px solid rgba(56, 239, 125, 0.35);
    color: var(--emerald);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 12px;
  }
  .dot { width: 8px; height: 8px; background: var(--emerald); border-radius: 50%; box-shadow: 0 0 8px var(--emerald); }
  h1 { font-size: 24px; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 4px; }
  p.subtitle { color: var(--text-muted); font-size: 14px; }
  .card {
    background: var(--card);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 20px;
    margin-bottom: 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  }
  .card-title { font-size: 16px; font-weight: 700; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
  .presets { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
  .btn-preset {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: var(--text);
    padding: 12px;
    border-radius: 14px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s;
  }
  .btn-preset:active { transform: scale(0.97); background: rgba(86, 204, 242, 0.2); border-color: var(--accent); }
  .form-group { margin-bottom: 12px; }
  label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
  input, textarea {
    width: 100%;
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    padding: 12px 14px;
    color: var(--text);
    font-size: 14px;
    outline: none;
    transition: border 0.2s;
  }
  input:focus, textarea:focus { border-color: var(--accent); }
  .btn-send {
    width: 100%;
    background: linear-gradient(135deg, #56CCF2, #2F80ED);
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 14px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 15px var(--accent-glow);
    transition: transform 0.15s, opacity 0.2s;
  }
  .btn-send:active { transform: scale(0.98); opacity: 0.9; }
  .code-box {
    background: rgba(0, 0, 0, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 12px;
    font-family: monospace;
    font-size: 12px;
    color: #38EF7D;
    word-break: break-all;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
  }
  .btn-copy {
    background: rgba(255, 255, 255, 0.12);
    border: none;
    color: #FFF;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    margin-left: 8px;
    white-space: nowrap;
  }
  .step-list { margin-left: 18px; color: var(--text-muted); font-size: 13px; line-height: 1.6; }
  .step-list li { margin-bottom: 6px; }
  .step-list strong { color: var(--text); }
  .toast-feedback {
    position: fixed;
    bottom: 24px;
    background: #10121C;
    border: 1px solid var(--emerald);
    color: #FFF;
    padding: 12px 20px;
    border-radius: 25px;
    font-size: 14px;
    font-weight: 600;
    display: none;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    z-index: 1000;
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="pill-status"><div class="dot"></div> Connected to Windows PC</div>
    <h1>Dynamic Island</h1>
    <p class="subtitle">Mobile Notification Bridge</p>
  </div>

  <div class="card">
    <div class="card-title">⚡ Quick Notification Send</div>
    <div class="presets">
      <button class="btn-preset" onclick="sendPreset('WhatsApp', 'Alex Johnson', 'Hey! Let me know when you arrive.')">💬 WhatsApp</button>
      <button class="btn-preset" onclick="sendPreset('Instagram', 'Sarah', 'liked your recent photo.')">📷 Instagram</button>
      <button class="btn-preset" onclick="sendPreset('Phone Call', 'Incoming Call', 'Mom (Mobile) is calling...')">📞 Phone Call</button>
      <button class="btn-preset" onclick="sendPreset('iMessage', 'David Miller', 'See you at the office tomorrow!')">💬 iMessage</button>
    </div>

    <form onsubmit="handleCustomSend(event)">
      <div class="form-group">
        <label>App Name</label>
        <input type="text" id="app_name" value="WhatsApp" required placeholder="e.g. WhatsApp, Slack, Teams">
      </div>
      <div class="form-group">
        <label>Title / Contact</label>
        <input type="text" id="notif_title" value="Sarah Jenkins" required placeholder="e.g. John Doe, Meeting Alert">
      </div>
      <div class="form-group">
        <label>Message</label>
        <input type="text" id="notif_msg" value="Hey! Are you joining the call now?" required placeholder="Notification body text">
      </div>
      <button type="submit" class="btn-send">Send to Dynamic Island</button>
    </form>
  </div>

  <div class="card">
    <div class="card-title">🔗 Webhook Endpoint</div>
    <p style="font-size: 13px; color: var(--text-muted);">Send POST requests with JSON <code>{"app":"...","title":"...","message":"..."}</code> to:</p>
    <div class="code-box">
      <span id="endpoint_url">http://{HOST}/api/notify</span>
      <button class="btn-copy" onclick="copyEndpoint()">Copy</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">📱 Automatic Setup Guide</div>
    <div style="margin-bottom: 14px;">
      <div style="font-size: 14px; font-weight: 700; margin-bottom: 6px; color: var(--accent);">🍎 For iPhone (iOS Shortcuts):</div>
      <ol class="step-list">
        <li>Open Apple's built-in <strong>Shortcuts</strong> app.</li>
        <li>Tap the <strong>Automation</strong> tab at the bottom &rarr; tap <strong>New Automation</strong>.</li>
        <li>Choose <strong>Message</strong> or <strong>App</strong> (when an app like WhatsApp or Messages is opened).</li>
        <li>Add Action: search for <strong>Get Contents of URL</strong>.</li>
        <li>Set Method to <strong>POST</strong>, URL to the Webhook URL above.</li>
        <li>Add JSON fields: <code>app</code>, <code>title</code>, <code>message</code>.</li>
        <li>Turn off <em>Ask Before Running</em> &rarr; Tap Done!</li>
      </ol>
    </div>
    <div>
      <div style="font-size: 14px; font-weight: 700; margin-bottom: 6px; color: var(--emerald);">🤖 For Android:</div>
      <ol class="step-list">
        <li>Install free <strong>MacroDroid</strong> or <strong>Tasker</strong> from Google Play.</li>
        <li>Add Trigger: <strong>Notification Received</strong> (select apps).</li>
        <li>Add Action: <strong>HTTP Request</strong> &rarr; Method: POST.</li>
        <li>Set URL to the Webhook URL above, Content Type: <code>application/json</code>.</li>
        <li>Set Body to: <code>{"app":"{notif_app_name}","title":"{notif_title}","message":"{notif_body}"}</code>.</li>
      </ol>
    </div>
  </div>
</div>

<div class="toast-feedback" id="toast">✓ Sent to Dynamic Island!</div>

<script>
  const endpoint = `${window.location.origin}/api/notify`;
  document.getElementById('endpoint_url').innerText = endpoint;

  function showToast(msg) {
    const t = document.getElementById('toast');
    t.innerText = msg || '✓ Sent to Dynamic Island!';
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 2200);
  }

  function copyEndpoint() {
    navigator.clipboard.writeText(endpoint);
    showToast('✓ URL copied to clipboard');
  }

  function sendNotification(app, title, message) {
    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app, title, message, phone: navigator.userAgent.includes('iPhone') ? 'iPhone' : 'Android' })
    })
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') showToast(`✓ Sent ${app} alert!`);
      else showToast('⚠️ Delivery error');
    })
    .catch(e => showToast('⚠️ Connection error'));
  }

  function sendPreset(app, title, msg) {
    sendNotification(app, title, msg);
  }

  function handleCustomSend(e) {
    e.preventDefault();
    const app = document.getElementById('app_name').value;
    const title = document.getElementById('notif_title').value;
    const msg = document.getElementById('notif_msg').value;
    sendNotification(app, title, msg);
  }
</script>
</body>
</html>
"""


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
            # Serve the mobile web companion
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
                "app": "WinDin Dynamic Island",
                "version": "2.0",
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

        elif path.startswith("/api/dock"):
            from urllib.parse import urlparse, parse_qs
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
            from urllib.parse import urlparse, parse_qs
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

        elif path in ("/api/notify", "/api/notification", "/notify", "/message"):
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            data = {}
            if post_data:
                try:
                    data = json.loads(post_data.decode("utf-8"))
                except Exception:
                    # Might be raw URL-encoded or plain text
                    data = {"message": post_data.decode("utf-8", errors="ignore")}

            app_name = data.get("app") or data.get("source") or "Phone"
            title = data.get("title") or data.get("sender") or data.get("contact") or "Mobile Notification"
            message = data.get("message") or data.get("body") or data.get("text") or "Incoming alert"
            phone = data.get("phone") or "Mobile"

            notif_payload = {
                "app": f"📱 {app_name.upper()}",
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

        elif path.startswith("/api/dock"):
            from urllib.parse import urlparse, parse_qs
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
            from urllib.parse import urlparse, parse_qs
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
    open_settings_requested = pyqtSignal()
    dock_requested = pyqtSignal(str)
    simulate_requested = pyqtSignal(str)

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
