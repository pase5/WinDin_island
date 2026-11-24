 WinDin-Link: Zero-Install Phone-to-PC Continuity (`implementation.md`)

## 1. System Architecture & Vision

**WinDin-Link** is a self-hosted, zero-dependency Phone-to-PC continuity platform built natively into the **WinDin** Windows Dynamic Island application (`DynamicIsland.exe` / Python).

By hosting a lightweight **Progressive Web App (PWA)** alongside the local WebSocket hub on a single unified port (`8765`), **no custom Android or iOS app installation is required**. Any phone on the same Wi-Fi network, mobile hotspot, or USB tether simply scans the QR code shown on the WinDin Dynamic Island with its native camera to pair, connect, and exchange files or clipboard text in real time.

### Core Capabilities Across All Phases

* **Phase 1 — Cryptographic Pairing & Token Engine:** Generates one-time `256-bit` pairing URLs rendered as high-contrast QR codes (`#0A0A0A` background / `#A3E635` lime modules) and stores verified device sessions in `config/paired_devices.json`.

* **Phase 2 — Unified HTTP PWA Server, mDNS & Binary WebSocket Hub:** Serves the mobile web interface over standard HTTP (`GET /`, `GET /pair`, `GET /manifest.json`) while upgrading `/ws` connections to raw binary WebSockets for `64 KB` chunked streaming and `SHA-256` integrity checks.

* **Phase 3 — Self-Hosted Mobile PWA (`receiver.html`):** Zero-dependency mobile browser client with automatic reconnection, `Web Crypto API` `SHA-256` verification, live image preview cards, automatic file downloads, native OS Share Sheet (`navigator.share`) integration, and instant text/link push to PC.

* **Phase 4 — Windows Dynamic Island UI & Drag-and-Drop Integration:** Native Qt/Python drag-and-drop hooks (`dragEnterEvent`, `dragLeaveEvent`, `dropEvent`) that morph the Dynamic Island pill into a glowing drop target and animate a circular transfer progress ring.

* **Phase 5 — Network Resilience, Firewall & Verification:** Automated Windows Firewall rule provisioning (supporting both Private Wi-Fi and Public mobile hotspot profiles) and end-to-end acceptance tests.

## 2. Target Repository Structure

```
WinDin/
├── implementation.md                 # Master implementation specification
├── requirements.txt                  # Python dependencies
├── config/
│   └── paired_devices.json           # Auto-generated local token store (add to .gitignore)
├── bridge/
│   ├── __init__.py
│   ├── protocol.py                   # Shared wire protocol constants & timeouts
│   ├── pairing_manager.py            # Token generation, validation & QR PNG builder
│   └── phone_bridge.py               # Unified HTTP PWA server + WebSocket hub + mDNS
├── web/
│   └── receiver.html                 # Self-contained mobile PWA (HTML + CSS + JS)
├── ui/
│   ├── dynamic_island.py             # Existing overlay (add drag/drop & progress ring)
│   └── qr_pairing_modal.py           # Expandable QR pairing view inside Dynamic Island
└── scripts/
    └── setup_firewall.ps1            # One-time Windows Firewall port 8765 rule script

```

## 3. Wire Protocol Specification (`WinDin-Link Web v1`)

All HTTP requests and WebSocket upgrades share TCP port `8765` via `websockets`' `process_request` hook. Control messages are UTF-8 JSON frames; file payloads travel as raw WebSocket Binary Frames (`bytes` / `ArrayBuffer`) to eliminate Base64 overhead.

### 3.1 QR Code Pairing URL

Encoded inside the QR code displayed on Windows:

```
http://192.168.1.42:8765/pair?token=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08

```

### 3.2 Authentication Handshake (`ws://<LAN_IP>:8765/ws`)

1. **Phone Browser → PC (must be sent within `5.0s` of socket open):**

   ```
   {
     "type": "auth",
     "token": "<64-char-hex-secret>",
     "device_id": "browser-uuid-v4",
     "device_name": "Android Phone"
   }
   
   ```

2. **PC → Phone Browser (Success):**

   ```
   {
     "type": "auth_ok",
     "host": "DESKTOP-WINDIN"
   }
   
   ```

3. **PC → Phone Browser (Failure — closes with code `4001`):**

   ```
   {
     "type": "auth_error",
     "reason": "invalid_token"
   }
   
   ```

### 3.3 Chunked Binary File Transfer (PC → Phone)

1. **PC → Phone (`file_offer` JSON):**

   ```
   {
     "type": "file_offer",
     "transfer_id": "tx_8f14e45f",
     "filename": "render_final.png",
     "mime": "image/png",
     "size": 2450120,
     "chunk_size": 65536
   }
   
   ```

2. **PC → Phone (Raw Binary Frames):** Sequential `65536`-byte binary frames until `size` bytes are transmitted.

3. **PC → Phone (`file_end` JSON):**

   ```
   {
     "type": "file_end",
     "transfer_id": "tx_8f14e45f",
     "sha256": "<64-char-lowercase-sha256-hex>"
   }
   
   ```

4. **Phone → PC (`file_ack` JSON):**

   ```
   {
     "type": "file_ack",
     "transfer_id": "tx_8f14e45f",
     "status": "saved"
   }
   
   ```

### 3.4 Keep-Alive Heartbeat & Clipboard Sync

* **Heartbeat:** Phone sends `{"type": "ping"}` every `15s` → PC replies `{"type": "pong"}`.

* **Clipboard Push:** `{"type": "clipboard_push", "text": "https://..."}` (bidirectional).

## 4. Phase 1: Dependencies, Constants & QR Pairing Engine

### 4.1 `requirements.txt`

```
websockets>=17.4
zeroconf>=0.132.0
qrcode[pil]>=7.4.2
Pillow>=10.4.0

```

### 4.2 `bridge/protocol.py`

```
SERVICE_TYPE = "_windin._tcp.local."
DEFAULT_PORT = 8765
CHUNK_SIZE = 64 * 1024  # 64 KB binary frames
AUTH_TIMEOUT_SEC = 5.0
ACK_TIMEOUT_SEC = 15.0

```

### 4.3 `bridge/pairing_manager.py`

Generates a cryptographically secure `32-byte` pairing secret (`secrets.token_hex(32)`), encodes the pairing URL into a dark/lime QR code PNG, and uses constant-time comparison (`secrets.compare_digest`) to validate connections.

```
import io
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import qrcode
from PIL import Image


class PairingManager:
    def __init__(self, config_path: str = "config/paired_devices.json") -> None:
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._paired_devices: dict[str, dict] = self._load()
        self._pending_token: Optional[str] = None

    def _load(self) -> dict[str, dict]:
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        self.config_path.write_text(
            json.dumps(self._paired_devices, indent=2), encoding="utf-8"
        )

    def create_pairing_qr_png(self, ip: str, port: int) -> bytes:
        """Generate a fresh pairing token and encode http://<ip>:<port>/pair?token=... as PNG bytes."""
        self._pending_token = secrets.token_hex(32)
        pair_url = f"http://{ip}:{port}/pair?token={self._pending_token}"

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(pair_url)
        qr.make(fit=True)

        img: Image.Image = qr.make_image(fill_color="#A3E635", back_color="#0A0A0A").convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def verify_and_register(self, token: str, device_id: str, device_name: str) -> bool:
        """Validate either a previously paired device token or the active QR pairing token."""
        if not token:
            return False

        for dev in self._paired_devices.values():
            if secrets.compare_digest(dev.get("token", ""), token):
                dev["last_seen"] = datetime.now(timezone.utc).isoformat()
                dev["device_name"] = device_name
                self._save()
                return True

        if self._pending_token and secrets.compare_digest(self._pending_token, token):
            self._paired_devices[device_id] = {
                "device_id": device_id,
                "device_name": device_name,
                "token": token,
                "paired_at": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
            self._pending_token = None
            self._save()
            return True

        return False

```

## 5. Phase 2: Unified HTTP PWA Server & WebSocket Hub (`bridge/phone_bridge.py`)

Combines mDNS discovery (`AsyncZeroconf`), static PWA serving (`_serve_http_request`), and chunked binary file streaming (`send_file_to_phone`) on a single asynchronous event loop.

```
import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import socket
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from bridge.pairing_manager import PairingManager
from bridge.protocol import (
    ACK_TIMEOUT_SEC,
    AUTH_TIMEOUT_SEC,
    CHUNK_SIZE,
    DEFAULT_PORT,
    SERVICE_TYPE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def get_local_ip() -> str:
    """Resolve active outbound LAN IPv4 without transmitting network packets."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


class PhoneBridge:
    def __init__(
        self,
        port: int = DEFAULT_PORT,
        on_connection_change: Optional[Callable[[bool, str], None]] = None,
        on_clipboard_received: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.port = port
        self.hostname = socket.gethostname()
        self.local_ip = get_local_ip()
        self.pairing = PairingManager()
        self.on_connection_change = on_connection_change
        self.on_clipboard_received = on_clipboard_received

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.active_phone: Optional[ServerConnection] = None
        self.active_device_name: str = ""
        self._pending_acks: dict[str, asyncio.Future] = {}
        self._aiozc: Optional[AsyncZeroconf] = None
        self._service_info: Optional[ServiceInfo] = None

    @property
    def is_connected(self) -> bool:
        return self.active_phone is not None

    def generate_pairing_qr_png(self) -> bytes:
        self.local_ip = get_local_ip()
        return self.pairing.create_pairing_qr_png(ip=self.local_ip, port=self.port)

    def _serve_http_request(self, connection: ServerConnection, request: Request) -> Optional[Response]:
        """Intercept normal HTTP GET requests to serve the self-hosted PWA receiver."""
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None

        parsed = urlparse(request.path)
        route = parsed.path

        if route in ("/", "/pair"):
            html_path = WEB_DIR / "receiver.html"
            if not html_path.exists():
                return Response(HTTPStatus.NOT_FOUND, "Not Found", Headers(), b"receiver.html missing")
            body = html_path.read_bytes()
            headers = Headers([
                ("Content-Type", "text/html; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ])
            return Response(HTTPStatus.OK, "OK", headers, body)

        if route == "/manifest.json":
            manifest = json.dumps({
                "name": "WinDin-Link",
                "short_name": "WinDin",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#0A0A0A",
                "theme_color": "#A3E635",
            }).encode("utf-8")
            headers = Headers([("Content-Type", "application/manifest+json")])
            return Response(HTTPStatus.OK, "OK", headers, manifest)

        return Response(HTTPStatus.NOT_FOUND, "Not Found", Headers(), b"404 Not Found")

    async def _start_mdns(self) -> None:
        service_name = f"WinDin-{self.hostname}.{SERVICE_TYPE}"
        self._service_info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=service_name,
            addresses=[socket.inet_aton(self.local_ip)],
            port=self.port,
            properties={"v": "1", "host": self.hostname},
            server=f"{self.hostname}.local.",
        )
        self._aiozc = AsyncZeroconf()
        await self._aiozc.async_register_service(self._service_info)
        logging.info(f"mDNS broadcasting {service_name} at http://{self.local_ip}:{self.port}")

    async def _stop_mdns(self) -> None:
        if self._aiozc and self._service_info:
            await self._aiozc.async_unregister_service(self._service_info)
            await self._aiozc.async_close()

    async def _handle_client(self, ws: ServerConnection) -> None:
        try:
            raw_auth = await asyncio.wait_for(ws.recv(), timeout=AUTH_TIMEOUT_SEC)
            auth_msg = json.loads(raw_auth)
            if auth_msg.get("type") != "auth":
                await ws.close(4001, "Expected auth frame")
                return

            token = auth_msg.get("token", "")
            device_id = auth_msg.get("device_id", "unknown")
            device_name = auth_msg.get("device_name", "Mobile Browser")

            if not self.pairing.verify_and_register(token, device_id, device_name):
                await ws.send(json.dumps({"type": "auth_error", "reason": "invalid_token"}))
                await ws.close(4001, "Invalid token")
                return

            if self.active_phone and self.active_phone != ws:
                await self.active_phone.close(1000, "Superseded by new session")

            self.active_phone = ws
            self.active_device_name = device_name
            await ws.send(json.dumps({"type": "auth_ok", "host": self.hostname}))
            logging.info(f"Paired mobile browser connected: {device_name} ({ws.remote_address})")
            if self.on_connection_change:
                self.on_connection_change(True, device_name)

            async for message in ws:
                if isinstance(message, str):
                    await self._handle_json_frame(ws, message)

        except Exception as exc:
            logging.warning(f"Client session ended: {exc}")
        finally:
            if self.active_phone == ws:
                self.active_phone = None
                self.active_device_name = ""
                if self.on_connection_change:
                    self.on_connection_change(False, "")

    async def _handle_json_frame(self, ws: ServerConnection, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")
        if msg_type == "ping":
            await ws.send(json.dumps({"type": "pong"}))
        elif msg_type == "file_ack":
            tx_id = data.get("transfer_id")
            fut = self._pending_acks.get(tx_id)
            if fut and not fut.done():
                fut.set_result(data.get("status", "saved"))
        elif msg_type == "clipboard_push" and self.on_clipboard_received:
            self.on_clipboard_received(data.get("text", ""))

    async def send_file_to_phone(
        self,
        file_path: str,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """Stream a dropped file over WebSocket binary frames and await browser save ACK."""
        ws = self.active_phone
        if not ws:
            raise RuntimeError("No phone connected")
        if not os.path.isfile(file_path):
            raise FileNotFoundError(file_path)

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        transfer_id = f"tx_{uuid.uuid4().hex[:8]}"
        sha256 = hashlib.sha256()

        ack_future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_acks[transfer_id] = ack_future

        try:
            await ws.send(json.dumps({
                "type": "file_offer",
                "transfer_id": transfer_id,
                "filename": filename,
                "mime": mime_type or "application/octet-stream",
                "size": file_size,
                "chunk_size": CHUNK_SIZE,
            }))

            sent = 0
            with open(file_path, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    sha256.update(chunk)
                    await ws.send(chunk)
                    sent += len(chunk)
                    if on_progress and file_size > 0:
                        on_progress(min(1.0, sent / file_size))

            await ws.send(json.dumps({
                "type": "file_end",
                "transfer_id": transfer_id,
                "sha256": sha256.hexdigest(),
            }))

            status = await asyncio.wait_for(ack_future, timeout=ACK_TIMEOUT_SEC)
            logging.info(f"Transfer {transfer_id} ({filename}) acknowledged: {status}")
            return status == "saved"
        finally:
            self._pending_acks.pop(transfer_id, None)

    async def run_forever(self) -> None:
        self.loop = asyncio.get_running_loop()
        await self._start_mdns()
        try:
            async with serve(
                self._handle_client,
                "0.0.0.0",
                self.port,
                process_request=self._serve_http_request,
                max_size=None,
            ):
                logging.info(f"WinDin HTTP/WebSocket bridge listening on http://{self.local_ip}:{self.port}")
                await asyncio.Future()
        finally:
            await self._stop_mdns()


if __name__ == "__main__":
    bridge = PhoneBridge()
    try:
        asyncio.run(bridge.run_forever())
    except KeyboardInterrupt:
        pass

```

## 6. Phase 3: Self-Hosted Mobile PWA (`web/receiver.html`)

A self-contained HTML5/CSS3/JS application served directly by Python. Supports Android Chrome and iOS Safari with automatic token persistence, `Web Crypto` `SHA-256` verification, automatic downloads, native Share Sheet export, and clipboard pushing.

```
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <meta name="theme-color" content="#0A0A0A" />
  <link rel="manifest" href="/manifest.json" />
  <title>WinDin-Link</title>
  <style>
    :root {
      --bg: #0A0A0A;
      --surface: #141416;
      --border: #242429;
      --accent: #A3E635;
      --text: #F4F4F5;
      --muted: #A1A1AA;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Inter", sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .pill {
      display: inline-flex; align-items: center; gap: 10px;
      background: #000; border: 1px solid var(--border);
      padding: 10px 18px; border-radius: 999px; margin-bottom: 24px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.6);
    }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: #EF4444; transition: background 0.3s; }
    .dot.connected { background: var(--accent); box-shadow: 0 0 10px var(--accent); }
    .container { width: 100%; max-width: 440px; display: flex; flex-direction: column; gap: 16px; }
    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 20px; padding: 18px;
    }
    h2 { font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
    .feed { display: flex; flex-direction: column; gap: 12px; }
    .item {
      background: #1B1B1F; border: 1px solid var(--border); border-radius: 14px;
      padding: 12px; display: flex; flex-direction: column; gap: 10px;
    }
    .item img { width: 100%; max-height: 280px; object-fit: contain; border-radius: 10px; background: #000; }
    .item-meta { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
    .btn {
      background: var(--accent); color: #0A0A0A; border: none; border-radius: 10px;
      padding: 8px 14px; font-weight: 600; font-size: 13px; cursor: pointer;
    }
    .clip-row { display: flex; gap: 8px; }
    input {
      flex: 1; background: #0A0A0A; border: 1px solid var(--border); color: var(--text);
      padding: 10px 12px; border-radius: 12px; font-size: 14px; outline: none;
    }
    input:focus { border-color: var(--accent); }
    .empty { color: var(--muted); font-size: 14px; text-align: center; padding: 24px 0; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="pill">
    <span class="dot" id="statusDot"></span>
    <span id="statusText" style="font-size: 14px; font-weight: 500;">Connecting to WinDin...</span>
  </div>

  <div class="container">
    <div class="card">
      <h2>Push Text / Link to PC</h2>
      <div class="clip-row">
        <input type="text" id="clipInput" placeholder="Paste link or note..." />
        <button class="btn" id="sendClipBtn">Push</button>
      </div>
    </div>

    <div class="card">
      <h2>Incoming Drops</h2>
      <div class="feed" id="feed">
        <div class="empty" id="emptyState">Drag any image or file onto your PC's Dynamic Island to receive it here instantly.</div>
      </div>
    </div>
  </div>

  <script>
    const params = new URLSearchParams(window.location.search);
    if (params.has("token")) {
      localStorage.setItem("windin_token", params.get("token"));
      window.history.replaceState({}, document.title, "/");
    }

    let deviceId = localStorage.getItem("windin_device_id");
    if (!deviceId) {
      deviceId = crypto.randomUUID ? crypto.randomUUID() : "dev-" + Math.random().toString(36).slice(2);
      localStorage.setItem("windin_device_id", deviceId);
    }

    const statusDot = document.getElementById("statusDot");
    const statusText = document.getElementById("statusText");
    const feed = document.getElementById("feed");
    const emptyState = document.getElementById("emptyState");

    let ws = null;
    let activeTransfer = null;

    function getDeviceName() {
      const ua = navigator.userAgent;
      if (/Android/i.test(ua)) return "Android Phone";
      if (/iPhone|iPad/i.test(ua)) return "iPhone";
      return "Mobile Browser";
    }

    async function sha256Hex(buffer) {
      const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
      return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, "0")).join("");
    }

    function connect() {
      const token = localStorage.getItem("windin_token");
      if (!token) {
        statusText.textContent = "Scan QR on PC to Pair";
        return;
      }

      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(`${proto}//${window.location.host}/ws`);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        ws.send(JSON.stringify({
          type: "auth",
          token,
          device_id: deviceId,
          device_name: getDeviceName()
        }));
      };

      ws.onmessage = async (event) => {
        if (typeof event.data === "string") {
          const msg = JSON.parse(event.data);
          if (msg.type === "auth_ok") {
            statusDot.classList.add("connected");
            statusText.textContent = `Connected • ${msg.host}`;
          } else if (msg.type === "auth_error") {
            statusDot.classList.remove("connected");
            statusText.textContent = "Pairing Expired — Rescan QR";
            localStorage.removeItem("windin_token");
          } else if (msg.type === "file_offer") {
            activeTransfer = { ...msg, chunks: [] };
            statusText.textContent = `Receiving ${msg.filename}...`;
          } else if (msg.type === "file_end" && activeTransfer) {
            const blob = new Blob(activeTransfer.chunks, { type: activeTransfer.mime });
            const arrayBuf = await blob.arrayBuffer();
            const digest = await sha256Hex(arrayBuf);
            const valid = digest.toLowerCase() === msg.sha256.toLowerCase();

            ws.send(JSON.stringify({
              type: "file_ack",
              transfer_id: activeTransfer.transfer_id,
              status: valid ? "saved" : "hash_mismatch"
            }));

            if (valid) renderReceivedFile(activeTransfer.filename, activeTransfer.mime, blob);
            statusText.textContent = "Connected";
            activeTransfer = null;
          }
        } else if (event.data instanceof ArrayBuffer && activeTransfer) {
          activeTransfer.chunks.push(event.data);
        }
      };

      ws.onclose = () => {
        statusDot.classList.remove("connected");
        statusText.textContent = "Reconnecting...";
        setTimeout(connect, 2000);
      };
    }

    function renderReceivedFile(filename, mime, blob) {
      if (emptyState) emptyState.remove();
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();

      const card = document.createElement("div");
      card.className = "item";

      if (mime.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = url;
        card.appendChild(img);
      }

      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.innerHTML = `<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:65%;">${filename}</span>`;

      const shareBtn = document.createElement("button");
      shareBtn.className = "btn";
      shareBtn.textContent = "Save / Share";
      shareBtn.onclick = async () => {
        const file = new File([blob], filename, { type: mime });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: filename });
        } else {
          const dl = document.createElement("a");
          dl.href = url;
          dl.download = filename;
          dl.click();
        }
      };

      meta.appendChild(shareBtn);
      card.appendChild(meta);
      feed.prepend(card);
    }

    document.getElementById("sendClipBtn").onclick = () => {
      const input = document.getElementById("clipInput");
      if (ws && ws.readyState === WebSocket.OPEN && input.value.trim()) {
        ws.send(JSON.stringify({ type: "clipboard_push", text: input.value.trim() }));
        input.value = "";
      }
    };

    setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 15000);

    connect();
  </script>
</body>
</html>

```

## 7. Phase 4: Dynamic Island Windows UI Hooks (`ui/`)

### 7.1 `ui/dynamic_island.py` Integration Blueprint

1. **Background Bridge Thread:**

   * Start `PhoneBridge.run_forever()` on a daemon `threading.Thread` running its own `asyncio` event loop at startup.

   * Connect `on_connection_change(connected: bool, device_name: str)` to a Qt `Signal` to update the pill's connection status dot (`#A3E635`).

   * Connect `on_clipboard_received(text: str)` to `QApplication.clipboard().setText(text)` and flash a `"Copied from Phone"` pill alert.

2. **Drag-and-Drop Overlay Target:**

   * Call `self.setAcceptDrops(True)` in the root Dynamic Island widget constructor.

   * `dragEnterEvent(event)`: Verify `event.mimeData().hasUrls()`, accept proposed action, and expand the pill smoothly into `"Drop to Send to Phone"` with an `#A3E635` border glow.

   * `dragLeaveEvent(event)`: Collapse back to idle/visualizer dimensions.

   * `dropEvent(event)`:

     * Extract local file paths (`url.toLocalFile()`).

     * If `not bridge.is_connected`: expand `qr_pairing_modal.py` automatically so the user can scan the QR code immediately.

     * If connected: schedule `bridge.send_file_to_phone(path, progress_callback)` onto `bridge.loop` via `asyncio.run_coroutine_threadsafe` and drive a `QPainter` circular progress arc (`0°` to `360°`) inside the pill until completion (`✓ Sent`).

3. **QR Pairing Modal (`ui/qr_pairing_modal.py`):**

   * Add a **"Pair Phone"** button in the hover-expanded dashboard.

   * Render the PNG bytes from `bridge.generate_pairing_qr_png()` into a `QLabel` (`QPixmap`) with the subtitle `"Scan with Phone Camera"`.

## 8. Phase 5: Firewall Provisioning & End-to-End Verification

### 8.1 Windows Firewall Rule (`scripts/setup_firewall.ps1`)

Windows classifies phone hotspots as **Public** networks by default. Run this once (or invoke via UAC during first launch) so inbound connections reach port `8765`:

```
New-NetFirewallRule -DisplayName "WinDin-Link Continuity Bridge" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 8765 `
  -Action Allow `
  -Profile Private,Public

```

### 8.2 Acceptance Checklist

1. **Single-Port HTTP + WebSocket Verification:** Run `python -m bridge.phone_bridge` and open `http://<LAN_IP>:8765/` on a phone on the same Wi-Fi or mobile hotspot; confirm the dark/lime `WinDin-Link` PWA renders immediately.

2. **Camera QR Pairing:** Click **"Pair Phone"** on the WinDin Dynamic Island, scan the QR code with the phone's built-in camera, and verify the pill updates to `"Connected • Android Phone"` (or `"Connected • iPhone"`) within `<500ms`.

3. **Drag-and-Drop Image Transfer:** Drag a `.png` or `.jpg` from Windows Explorer onto the Dynamic Island pill; verify the drop-zone expansion, live circular progress arc, `SHA-256` match, automatic file download on the phone, and working **Save / Share** button.

4. **Two-Way Clipboard Push:** Paste a URL into the phone PWA input and click **Push**; verify the Windows clipboard immediately contains the URL.