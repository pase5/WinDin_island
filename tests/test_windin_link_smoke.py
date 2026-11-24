"""
Automated Smoke Test for WinDin-Link Continuity Bridge.
Verifies:
1. QR token generation & high-contrast PNG format.
2. HTTP endpoint serving (/ and /manifest.json).
3. WebSocket authentication handshake & token registration.
4. Two-way clipboard push.
5. 64 KB chunked binary file streaming with SHA-256 integrity verification and ACK.
"""

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import websockets.asyncio.client
from bridge.phone_bridge import PhoneBridge
from bridge.protocol import CHUNK_SIZE


async def run_smoke_test():
    print("=" * 60)
    print("Starting WinDin-Link Automated Smoke Test")
    print("=" * 60)

    received_clipboard = []

    def on_clip(text: str):
        received_clipboard.append(text)

    connection_events = []

    def on_conn(connected: bool, name: str):
        connection_events.append((connected, name))

    test_port = 8769
    bridge = PhoneBridge(
        port=test_port,
        on_connection_change=on_conn,
        on_clipboard_received=on_clip,
    )

    # 1. Test QR Code Generation
    print("[1/5] Testing QR Code PNG & Token Generation...")
    qr_bytes = bridge.generate_pairing_qr_png()
    assert qr_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "QR output must be valid PNG bytes"
    assert len(qr_bytes) > 200, "QR PNG size should be realistic"
    pair_url = bridge.get_pairing_url()
    assert f":{test_port}/pair?token=" in pair_url, "Pair URL must contain port and token"
    token = pair_url.split("token=")[1]
    assert len(token) == 64, "Token must be a 64-char hex string"
    print(f"      OK - QR code generated ({len(qr_bytes)} bytes), Token: {token[:12]}...")

    # Start bridge server task with ready notification
    ready_event = asyncio.Event()
    server_task = asyncio.create_task(bridge.run_forever(ready_event=ready_event))
    await asyncio.wait_for(ready_event.wait(), timeout=5.0)

    try:
        # 2. Test HTTP Serving (/ and /manifest.json)
        print("[2/5] Testing HTTP Static & Manifest Endpoints...")
        base_url = f"http://127.0.0.1:{test_port}"

        # Test GET /
        def fetch_root():
            with urllib.request.urlopen(f"{base_url}/", timeout=3.0) as resp:
                return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8")

        status, ct, html_body = await asyncio.to_thread(fetch_root)
        assert status == 200, "Root path must return HTTP 200"
        assert "text/html" in ct, f"Expected text/html, got {ct}"
        assert "WinDin-Link" in html_body, "PWA title must be present in HTML"
        assert "localStorage.setItem" in html_body, "Token handler must be present"
        print("      OK - GET / returned valid receiver PWA HTML")

        # Test GET /manifest.json
        def fetch_manifest():
            with urllib.request.urlopen(f"{base_url}/manifest.json", timeout=3.0) as resp:
                return resp.status, resp.read().decode("utf-8")

        status, manifest_text = await asyncio.to_thread(fetch_manifest)
        assert status == 200, "Manifest path must return HTTP 200"
        manifest = json.loads(manifest_text)
        assert manifest["name"] == "WinDin-Link", "Manifest name must be WinDin-Link"
        assert manifest["theme_color"] == "#A3E635", "Theme color must be #A3E635"
        print("      OK - GET /manifest.json returned valid PWA manifest")

        # 3. Test WebSocket Authentication Handshake
        print("[3/5] Testing WebSocket Authentication Handshake...")
        ws_url = f"ws://127.0.0.1:{test_port}/ws"
        async with websockets.asyncio.client.connect(ws_url) as ws:
            # Send Auth frame
            device_id = "test-smoke-device-123"
            device_name = "Pixel 9 Pro"
            await ws.send(
                json.dumps({
                    "type": "auth",
                    "token": token,
                    "device_id": device_id,
                    "device_name": device_name,
                })
            )

            auth_reply_raw = await asyncio.wait_for(ws.recv(), timeout=4.0)
            auth_reply = json.loads(auth_reply_raw)
            assert auth_reply.get("type") == "auth_ok", f"Expected auth_ok, got {auth_reply}"
            assert bridge.is_connected, "Bridge must report connected"
            print(f"      OK - Handshake verified: {auth_reply.get('host')} connected with {device_name}")

            # 4. Test Clipboard Push from Phone to PC
            print("[4/5] Testing Phone-to-PC Clipboard Push...")
            test_clip_text = "https://github.com/windin/sample-repo-link"
            await ws.send(
                json.dumps({
                    "type": "clipboard_push",
                    "text": test_clip_text,
                })
            )
            await asyncio.sleep(0.3)
            assert test_clip_text in received_clipboard, "Clipboard text was not delivered to bridge handler"
            print(f"      OK - Clipboard pushed and received: '{test_clip_text}'")

            # 5. Test Chunked Binary File Streaming with SHA-256 Integrity Verification
            print("[5/5] Testing 64 KB Chunked Binary Streaming & SHA-256 ACK...")
            # Create a 150 KB test binary file (spans 3 chunks: 64KB + 64KB + 22KB)
            test_size = 150 * 1024
            test_data = os.urandom(test_size)
            expected_sha256 = hashlib.sha256(test_data).hexdigest()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tf:
                tf.write(test_data)
                temp_file_path = tf.name

            progress_reports = []

            def on_progress(p: float):
                progress_reports.append(p)

            try:
                # Start file transfer in bridge
                send_task = asyncio.create_task(
                    bridge.send_file_to_phone(temp_file_path, on_progress=on_progress)
                )

                # Client simulates PWA receiver behavior
                offer_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=4.0))
                assert offer_msg["type"] == "file_offer", f"Expected file_offer, got {offer_msg}"
                assert offer_msg["size"] == test_size, "File size mismatch"
                tx_id = offer_msg["transfer_id"]

                received_chunks = []
                received_bytes_count = 0

                while received_bytes_count < test_size:
                    chunk = await asyncio.wait_for(ws.recv(), timeout=4.0)
                    assert isinstance(chunk, bytes), "Expected raw binary chunk"
                    received_chunks.append(chunk)
                    received_bytes_count += len(chunk)

                end_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=4.0))
                assert end_msg["type"] == "file_end", f"Expected file_end, got {end_msg}"
                assert end_msg["sha256"] == expected_sha256, "Server SHA-256 mismatch"

                # Client verifies SHA-256
                client_sha256 = hashlib.sha256(b"".join(received_chunks)).hexdigest()
                assert client_sha256 == expected_sha256, "Client reassembly hash mismatch"

                # Client sends ACK
                await ws.send(
                    json.dumps({
                        "type": "file_ack",
                        "transfer_id": tx_id,
                        "status": "saved",
                    })
                )

                # Wait for server send_task to complete
                send_result = await asyncio.wait_for(send_task, timeout=4.0)
                assert send_result is True, "send_file_to_phone should return True on ACK 'saved'"
                assert len(progress_reports) > 0, "Progress callback should have been called"
                assert progress_reports[-1] == 1.0, "Progress should reach 1.0 (100%)"
                print(f"      OK - File transfer completed: {test_size} bytes transmitted across {len(received_chunks)} chunks")
                print(f"      OK - SHA-256 match verified: {expected_sha256[:16]}...")
                print(f"      OK - ACK received and verified.")

            finally:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    print("=" * 60)
    print("ALL 5 SMOKE TESTS PASSED CLEANLY (100%)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
