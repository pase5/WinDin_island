"""
Unified HTTP PWA Server & WebSocket Hub for WinDin-Link.
Hosts the self-contained receiver PWA on port 8765, broadcasts mDNS,
and facilitates binary chunked file transfer with SHA-256 verification.
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import socket
import sys
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

logger = logging.getLogger("windin.phone_bridge")

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    WEB_DIR = Path(sys._MEIPASS) / "web"
else:
    WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def get_local_ip() -> str:
    """Resolve active outbound LAN IPv4 without transmitting network packets."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


class PhoneBridge:
    """
    Unified Single-Port HTTP + WebSocket Hub on port 8765.
    Combines mDNS discovery, static PWA serving, and chunked binary streaming.
    """

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        on_connection_change: Optional[Callable[[bool, str], None]] = None,
        on_clipboard_received: Optional[Callable[[str], None]] = None,
        on_wake: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_remote_action: Optional[Callable[[str, str], None]] = None,
        on_battery_sync: Optional[Callable[[int, bool, str], None]] = None,
        on_notification_push: Optional[Callable[[str, str, str], None]] = None,
        on_incoming_file_start: Optional[Callable[[str, int], None]] = None,
        on_incoming_file_progress: Optional[Callable[[float], None]] = None,
        on_incoming_file_complete: Optional[Callable[[bool, str, str], None]] = None,
    ) -> None:
        self.port = port
        self.hostname = socket.gethostname()
        self.local_ip = get_local_ip()
        self.pairing = PairingManager()
        self.on_connection_change = on_connection_change
        self.on_clipboard_received = on_clipboard_received
        self.on_wake = on_wake
        self.on_open_settings = on_open_settings
        self.on_remote_action = on_remote_action
        self.on_battery_sync = on_battery_sync
        self.on_notification_push = on_notification_push
        self.on_incoming_file_start = on_incoming_file_start
        self.on_incoming_file_progress = on_incoming_file_progress
        self.on_incoming_file_complete = on_incoming_file_complete

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.active_phone: Optional[ServerConnection] = None
        self.active_device_name: str = ""
        self._pending_acks: dict[str, asyncio.Future] = {}
        self._incoming_tx: Optional[dict] = None
        self._aiozc: Optional[AsyncZeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self._server = None

    @property
    def is_connected(self) -> bool:
        return self.active_phone is not None

    def generate_pairing_qr_png(self) -> bytes:
        self.local_ip = get_local_ip()
        return self.pairing.create_pairing_qr_png(
            ip=self.local_ip,
            port=self.port,
            host=self.hostname,
            service=SERVICE_TYPE,
        )

    def get_pairing_url(self) -> str:
        self.local_ip = get_local_ip()
        return self.pairing.get_pending_url(ip=self.local_ip, port=self.port)

    def _serve_http_request(
        self, connection: ServerConnection, request: Request
    ) -> Optional[Response]:
        """Intercept normal HTTP GET requests to serve the self-hosted PWA receiver."""
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None

        parsed = urlparse(request.path)
        route = parsed.path

        if route in ("/", "/pair"):
            html_path = WEB_DIR / "receiver.html"
            if not html_path.exists():
                return Response(
                    HTTPStatus.NOT_FOUND,
                    "Not Found",
                    Headers([("Content-Type", "text/plain")]),
                    b"receiver.html missing",
                )
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
            headers = Headers([
                ("Content-Type", "application/manifest+json; charset=utf-8"),
                ("Cache-Control", "public, max-age=3600"),
            ])
            return Response(HTTPStatus.OK, "OK", headers, manifest)

        if route in ("/WinDin.apk", "/app-debug.apk", "/download", "/apk"):
            candidates = [
                Path(sys.executable).parent / "WinDin.apk",
                Path.cwd() / "dist" / "WinDin.apk",
                Path(__file__).resolve().parent.parent / "dist" / "WinDin.apk",
                WEB_DIR / "WinDin.apk",
            ]
            apk_path = next((p for p in candidates if p.exists()), None)
            if apk_path:
                body = apk_path.read_bytes()
                headers = Headers([
                    ("Content-Type", "application/vnd.android.package-archive"),
                    ("Content-Disposition", 'attachment; filename="WinDin.apk"'),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-cache"),
                ])
                return Response(HTTPStatus.OK, "OK", headers, body)

        if route in ("/wake", "/api/wake"):
            if self.on_wake:
                try:
                    self.on_wake()
                except Exception:
                    pass
            return Response(HTTPStatus.OK, "OK", Headers([("Content-Type", "text/plain")]), b"OK")

        if route in ("/open_settings", "/api/open_settings"):
            if self.on_open_settings:
                try:
                    self.on_open_settings()
                except Exception:
                    pass
            return Response(HTTPStatus.OK, "OK", Headers([("Content-Type", "text/plain")]), b"OK")

        return Response(
            HTTPStatus.NOT_FOUND,
            "Not Found",
            Headers([("Content-Type", "text/plain")]),
            b"404 Not Found",
        )

    async def _start_mdns(self) -> None:
        try:
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
            logger.info(
                f"mDNS broadcasting {service_name} at http://{self.local_ip}:{self.port}"
            )
        except Exception as e:
            logger.warning(f"mDNS broadcast initialization failed: {e}")

    async def _stop_mdns(self) -> None:
        try:
            if self._aiozc and self._service_info:
                await self._aiozc.async_unregister_service(self._service_info)
                await self._aiozc.async_close()
        except Exception as e:
            logger.warning(f"Error stopping mDNS: {e}")

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
                await ws.send(
                    json.dumps({"type": "auth_error", "reason": "invalid_token"})
                )
                await ws.close(4001, "Invalid token")
                return

            if self.active_phone and self.active_phone != ws:
                try:
                    await self.active_phone.close(1000, "Superseded by new session")
                except Exception:
                    pass

            self.active_phone = ws
            self.active_device_name = device_name
            await ws.send(json.dumps({"type": "auth_ok", "host": self.hostname}))
            logger.info(
                f"Paired mobile browser connected: {device_name} ({ws.remote_address})"
            )
            if self.on_connection_change:
                self.on_connection_change(True, device_name)

            async for message in ws:
                if isinstance(message, str):
                    await self._handle_json_frame(ws, message)
                elif isinstance(message, (bytes, bytearray)):
                    await self._handle_binary_frame(ws, bytes(message))

        except Exception as exc:
            logger.warning(f"Client session ended: {exc}")
        finally:
            if self._incoming_tx and self._incoming_tx.get("file"):
                try:
                    self._incoming_tx["file"].close()
                except Exception:
                    pass
                try:
                    self._incoming_tx["temp_path"].unlink(missing_ok=True)
                except Exception:
                    pass
                self._incoming_tx = None

            if self.active_phone == ws:
                self.active_phone = None
                self.active_device_name = ""
                if self.on_connection_change:
                    self.on_connection_change(False, "")

    async def _handle_binary_frame(self, ws: ServerConnection, data: bytes) -> None:
        if self._incoming_tx and self._incoming_tx.get("file"):
            try:
                self._incoming_tx["file"].write(data)
                self._incoming_tx["sha256"].update(data)
                self._incoming_tx["received"] += len(data)
                if self.on_incoming_file_progress and self._incoming_tx["size"] > 0:
                    prog = min(1.0, self._incoming_tx["received"] / self._incoming_tx["size"])
                    self.on_incoming_file_progress(prog)
            except Exception as e:
                logger.error(f"Error writing incoming binary chunk: {e}")

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

        elif msg_type == "phone_file_offer":
            # Incoming file stream from phone to PC
            tx_id = data.get("transfer_id", f"tx_{uuid.uuid4().hex[:8]}")
            filename = data.get("filename", "received_file")
            size = data.get("size", 0)
            drops_dir = Path.home() / "Downloads" / "WinDin_Drops"
            drops_dir.mkdir(parents=True, exist_ok=True)
            temp_path = drops_dir / f".part_{tx_id}"
            try:
                out_f = open(temp_path, "wb")
            except Exception as e:
                logger.error(f"Failed to open temp file for incoming upload: {e}")
                return

            self._incoming_tx = {
                "id": tx_id,
                "filename": filename,
                "size": size,
                "received": 0,
                "sha256": hashlib.sha256(),
                "file": out_f,
                "temp_path": temp_path,
                "final_path": drops_dir / filename,
            }
            if self.on_incoming_file_start:
                self.on_incoming_file_start(filename, size)

        elif msg_type == "phone_file_end":
            expected_hash = data.get("sha256", "")
            tx_id = data.get("transfer_id", "")
            if self._incoming_tx and self._incoming_tx["id"] == tx_id:
                try:
                    self._incoming_tx["file"].close()
                    actual_hash = self._incoming_tx["sha256"].hexdigest()
                    if not expected_hash or actual_hash.lower() == expected_hash.lower():
                        target = self._incoming_tx["final_path"]
                        if target.exists():
                            import time
                            target = target.parent / f"{target.stem}_{int(time.time())}{target.suffix}"
                        import shutil
                        shutil.move(str(self._incoming_tx["temp_path"]), str(target))
                        await ws.send(json.dumps({"type": "phone_file_ack", "transfer_id": tx_id, "status": "saved"}))
                        if self.on_incoming_file_complete:
                            self.on_incoming_file_complete(True, str(target), self._incoming_tx["filename"])
                    else:
                        self._incoming_tx["temp_path"].unlink(missing_ok=True)
                        await ws.send(json.dumps({"type": "phone_file_ack", "transfer_id": tx_id, "status": "hash_mismatch"}))
                        if self.on_incoming_file_complete:
                            self.on_incoming_file_complete(False, "", "Integrity mismatch")
                except Exception as e:
                    logger.error(f"Error finalizing incoming file: {e}")
                finally:
                    self._incoming_tx = None

        elif msg_type == "pc_action" and self.on_remote_action:
            action = data.get("action", "")
            param = data.get("param", "")
            self.on_remote_action(action, param)

        elif msg_type == "battery_sync" and self.on_battery_sync:
            level = int(data.get("level", 100))
            charging = bool(data.get("charging", False))
            device = str(data.get("device_name", self.active_device_name or "Phone"))
            self.on_battery_sync(level, charging, device)

        elif msg_type == "notification_push" and self.on_notification_push:
            app = data.get("app", "Phone")
            title = data.get("title", "")
            message = data.get("message", "")
            self.on_notification_push(app, title, message)

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

        loop = asyncio.get_running_loop()
        ack_future: asyncio.Future = loop.create_future()
        self._pending_acks[transfer_id] = ack_future

        try:
            await ws.send(
                json.dumps({
                    "type": "file_offer",
                    "transfer_id": transfer_id,
                    "filename": filename,
                    "mime": mime_type or "application/octet-stream",
                    "size": file_size,
                    "chunk_size": CHUNK_SIZE,
                })
            )

            sent = 0
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    sha256.update(chunk)
                    await ws.send(chunk)
                    sent += len(chunk)
                    if on_progress and file_size > 0:
                        on_progress(min(1.0, sent / file_size))

            await ws.send(
                json.dumps({
                    "type": "file_end",
                    "transfer_id": transfer_id,
                    "sha256": sha256.hexdigest(),
                })
            )

            status = await asyncio.wait_for(ack_future, timeout=ACK_TIMEOUT_SEC)
            logger.info(f"Transfer {transfer_id} ({filename}) acknowledged: {status}")
            return status == "saved"
        finally:
            self._pending_acks.pop(transfer_id, None)

    def send_file(
        self,
        file_path: str,
        on_progress: Optional[Callable[[float], None]] = None,
    ):
        """Thread-safe file sending helper for Qt GUI thread."""
        if not self.loop or not self.loop.is_running():
            raise RuntimeError("PhoneBridge event loop is not running")
        return asyncio.run_coroutine_threadsafe(
            self.send_file_to_phone(file_path, on_progress), self.loop
        )

    async def run_forever(self, ready_event: Optional[asyncio.Event] = None) -> None:
        self.loop = asyncio.get_running_loop()
        # Launch mDNS discovery in background so HTTP/WebSocket port binds instantly
        asyncio.create_task(self._start_mdns())
        try:
            async with serve(
                self._handle_client,
                "0.0.0.0",
                self.port,
                process_request=self._serve_http_request,
                max_size=None,
            ) as server:
                self._server = server
                if ready_event:
                    ready_event.set()
                logger.info(
                    f"WinDin HTTP/WebSocket bridge listening on http://{self.local_ip}:{self.port}"
                )
                await asyncio.Future()
        finally:
            await self._stop_mdns()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    bridge = PhoneBridge()
    try:
        asyncio.run(bridge.run_forever())
    except KeyboardInterrupt:
        pass
