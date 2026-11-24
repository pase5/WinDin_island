"""
Shared Wire Protocol Constants & Timeouts for WinDin-Link Web v1.
"""

SERVICE_TYPE = "_windin._tcp.local."
DEFAULT_PORT = 8765
CHUNK_SIZE = 64 * 1024  # 64 KB binary frames
AUTH_TIMEOUT_SEC = 10.0
ACK_TIMEOUT_SEC = 30.0
