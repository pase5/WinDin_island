"""
Cryptographic Pairing & Token Engine for WinDin-Link.
Generates one-time 256-bit pairing URLs, encodes dark/lime QR codes,
and validates sessions using constant-time comparisons.
"""

import io
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import qrcode
from PIL import Image

APPDATA_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "WindowLand"
DEFAULT_CONFIG_PATH = APPDATA_DIR / "paired_devices.json"


class PairingManager:
    """Manages pairing tokens, QR code generation, and persistent paired device storage."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        # Migrate old local config if present and APPDATA doesn't exist
        legacy_path = Path("config/paired_devices.json")
        if legacy_path.exists() and not self.config_path.exists():
            try:
                self.config_path.write_bytes(legacy_path.read_bytes())
            except Exception:
                pass

        self._paired_devices: dict[str, dict] = self._load()
        self._pending_tokens: dict[str, float] = {}  # token -> timestamp
        self._pending_token: Optional[str] = None

    def _load(self) -> dict[str, dict]:
        if not self.config_path.exists():
            # Check legacy fallback
            legacy = Path("config/paired_devices.json")
            if legacy.exists():
                try:
                    return json.loads(legacy.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(self._paired_devices, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def create_pairing_qr_png(
        self,
        ip: str,
        port: int,
        host: Optional[str] = None,
        service: str = "_windin._tcp.local.",
    ) -> bytes:
        """
        Generate a fresh pairing token and encode structured JSON connection metadata
        as high-contrast QR code PNG bytes (#0A0A0A background / #A3E635 lime modules).
        Also supports fallback pairing URL generation.
        """
        import socket
        self._pending_token = secrets.token_hex(32)
        self._pending_tokens[self._pending_token] = time.time()
        resolved_host = host or socket.gethostname()

        payload = json.dumps({
            "app": "WinDin",
            "v": 1,
            "host": resolved_host,
            "ip": ip,
            "port": port,
            "service": service,
            "token": self._pending_token,
        }, separators=(",", ":"))

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img: Image.Image = qr.make_image(
            fill_color="#A3E635", back_color="#0A0A0A"
        ).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def get_pending_url(self, ip: str, port: int) -> str:
        """Returns the active pairing URL, or creates a new token if none is pending."""
        if not self._pending_token:
            self._pending_token = secrets.token_hex(32)
            self._pending_tokens[self._pending_token] = time.time()
        return f"http://{ip}:{port}/pair?token={self._pending_token}"

    def verify_and_register(self, token: str, device_id: str, device_name: str) -> bool:
        """Validate either a previously paired device token or an active QR pairing token."""
        if not token:
            return False

        # 1. Check existing paired devices (Permanent Remembered Devices)
        for dev_key, dev in list(self._paired_devices.items()):
            if secrets.compare_digest(dev.get("token", ""), token):
                dev["last_seen"] = datetime.now(timezone.utc).isoformat()
                dev["device_name"] = device_name
                self._save()
                return True

        # 2. Check pending QR tokens (valid for 15 minutes)
        now = time.time()
        self._pending_tokens = {t: exp for t, exp in self._pending_tokens.items() if now - exp < 900}

        is_pending = False
        if self._pending_token and secrets.compare_digest(self._pending_token, token):
            is_pending = True
        elif any(secrets.compare_digest(t, token) for t in self._pending_tokens):
            is_pending = True

        if is_pending:
            self._paired_devices[device_id] = {
                "device_id": device_id,
                "device_name": device_name,
                "token": token,
                "paired_at": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
            # Remove consumed token from pending
            self._pending_tokens = {t: exp for t, exp in self._pending_tokens.items() if not secrets.compare_digest(t, token)}
            if self._pending_token and secrets.compare_digest(self._pending_token, token):
                self._pending_token = None
            self._save()
            return True

        return False
