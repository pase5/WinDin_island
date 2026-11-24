"""
WinDin-Link Bridge Package.
Unified HTTP PWA server + WebSocket Hub + mDNS discovery for zero-install phone continuity.
"""

from bridge.protocol import (
    SERVICE_TYPE,
    DEFAULT_PORT,
    CHUNK_SIZE,
    AUTH_TIMEOUT_SEC,
    ACK_TIMEOUT_SEC,
)
from bridge.pairing_manager import PairingManager
from bridge.phone_bridge import PhoneBridge

__all__ = [
    "SERVICE_TYPE",
    "DEFAULT_PORT",
    "CHUNK_SIZE",
    "AUTH_TIMEOUT_SEC",
    "ACK_TIMEOUT_SEC",
    "PairingManager",
    "PhoneBridge",
]
