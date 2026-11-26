<div align="center">

# WinDin — Dynamic Island & Win Drop for Windows
### Liquid Hardware Notch, 26-Band WASAPI Spectrum & Zero-Cloud Mobile Continuity

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20%26%20Android%208.0%2B-0078D6?style=for-the-badge&logo=windows)](https://github.com/pase5/WinDin)
[![License](https://img.shields.io/badge/License-MIT-34C759?style=for-the-badge)](#)
[![Animation](https://img.shields.io/badge/Physics-60%20FPS%20B%C3%A9zier-FF9500?style=for-the-badge)](#)
[![Binary Windows](https://img.shields.io/badge/Binary%20Windows-50.2%20MB%20Standalone-0078D6?style=for-the-badge)](#)
[![Binary Android](https://img.shields.io/badge/Binary%20Android-39.5%20MB%20APK-3DDC84?style=for-the-badge&logo=android)](#)
[![UI Framework](https://img.shields.io/badge/UI-PyQt6%20Vector%20%7C%20Jetpack%20Compose-41CD52?style=for-the-badge&logo=qt)](#)

*An organic, hardware-inspired desktop notch overlay with subpixel vector geometry, 26-band WASAPI loopback audio visualization, 9-edge magnetic docking, and instant zero-cloud Win Drop file beaming to your Android phone.*

[Direct Downloads](#quick-start--downloads) • [Win Drop Continuity](#win-drop-zero-cloud-continuity) • [Key Features](#key-features) • [Mobile Companion](#android-companion-app) • [Controls & Shortcuts](#controls--shortcuts) • [Building from Source](#building-from-source)

</div>

---

## Overview

**WinDin** brings an Apple-grade Dynamic Island hardware notch and seamless proximity file continuity to Windows 10 & 11. Designed with anti-aliased vector geometry, 60 FPS physics-driven Bézier transitions, real-time WASAPI audio analysis, and intelligent fullscreen suppression, it remains completely unobtrusive until summoned.

Whether anchored flush to your monitor's top bezel, resting along the taskbar, tucked into screen corners as a dual-arm bracket, or docked to the screen edges, WinDin adapts organically with smooth parametric vector morphing.

With **Win Drop**, dragging any file near the top bezel summons a radiant iridescent light corona, smoothly morphs the island into an active transfer card, and beams files directly to your Android companion app over your local Wi-Fi network—saving photos straight into your phone's gallery with zero cloud dependency.

---

## Win Drop (Zero-Cloud Continuity)

Win Drop replicates the fluid proximity and file transfer experience on Windows and Android with subpixel vector precision:

- **Top-Edge Luminous Light Corona (60 FPS Tracking):** Dragging a file within 140 px of the top screen edge summons a soft, diffused white/iridescent radial light bloom (`rgba(255, 255, 255, 0.38)` fading to transparent at `y = 0`) that actively tracks cursor coordinates in real time.
- **Frosted Card Morphing (320 ms OutBack):** The compact notch smoothly expands into an obsidian glass transfer card (`340 x 64 px`, `#08080C` base, frosted rim, specular meniscus highlight).
- **Clean 3-Column Card Layout (Zero Overlap):**
  - **Left (`36 x 36 px` squircle, `r = 10 px`):** Frosted device badge with crisp white vector smartphone glyph (zero system emojis per Rule 1).
  - **Center:** Two-line clean stack—`"Win Drop"` (or connected device name) in 11 pt Bold over live progress / elided filename in 9 pt Segoe UI Variable.
  - **Right (`26 x 26 px` circular progress ring):** Circular track with sweeping pure white (`#FFFFFF`) progress arc synchronized to live WebSocket binary transmission.
- **Ring-to-Checkmark Completion & Retraction:** Upon transfer acknowledgement (`100%`), the white ring closes completely, animates a pure white vector checkmark (1.0s hold), fades out the top light corona, and smoothly retracts back to the compact notch.
- **Silent MediaStore Gallery Drops:** Incoming photos and screenshots on Android are immediately registered into `MediaStore.Images.Media.EXTERNAL_CONTENT_URI` (`/Pictures/WinDin`), appearing instantly inside Google Photos or your gallery app without confirmation prompts.

---

## Key Features

### 1. Bespoke Vector Media Player
- **Zero System Emojis (Rule 1):** All playback controls, icons, and badges are mathematically drawn vector paths (`QPainterPath`) with anti-aliasing.
- **Interactive Scrubber:** Click-to-seek timeline scrubbing with glowing playhead, hover expansion, and real-time SMTC seek synchronization.
- **3D Directional Tilt:** Perspective shifts driven by cursor coordinates across the expanded dashboard card.
- **Aurora Color Extraction:** Dynamically samples active album art to synchronize background plasma glows, scrubber progress, and equalizer bar highlights.

### 2. 26-Band WASAPI Loopback Audio Visualizer
- **Bit-Exact Engine:** Real-time 2048-point Hann-windowed FFT capturing bit-exact audio directly from the default Windows playback device with sub-millisecond latency.
- **Center Equalizer:** 26-bar center equalizer in expanded mode; 5-bar responsive mini-equalizer in compact mode.
- **Corner & Side Vertical Ladders:** 10- and 12-band vertical frequency ladders on screen corners and side bezels that pulse horizontally with audio ballistics.

### 3. 9-Edge Magnetic Docking Engine
- **Top Bezel Notch:** Anchors flush against `y = 0` with organic flared inverse fillets (`r = 14 px`).
- **Corner Reverse-L (`⌈`):** Dual-arm bracket showcasing track progress on the horizontal arm, album art in the corner hub, and a vertical frequency ladder with digital clock on the vertical arm.
- **Side Bezel Pills:** Minimal vertical pills docked along left or right screen edges with unclipped stacked digital clocks.
- **Taskbar & Free-Floating:** Snap above the Windows taskbar or float freely anywhere across multiple monitors.
- **Non-Inverting Ear Scaling:** Bézier ear radii dynamically bound by geometry so curves never reverse or create visual knots.

### 4. Windows Taskbar Z-Order Layering
- Utilizes `Qt.WindowType.WindowStaysOnTopHint` to float above normal desktop windows.
- Dynamically sits behind the Windows Taskbar (`Shell_TrayWnd` and `Shell_SecondaryTrayWnd`) in Win32 Z-order via `_ensure_behind_taskbar()`, ensuring taskbar icons, pinned apps, and the Start button remain completely accessible.

### 5. Hardware Accessory Detection & Modals
- **Automatic Recognition:** Real-time CoreAudio watcher detecting AirPods, over-ear headphones, Bluetooth speakers, and audiophile DACs.
- **Interactive 3D Sheet:** Animated 3D device renders with ambient pedestal halos, segmented battery rings, and inline audio routing controls.

### 6. Desktop HUDs & System Suppression
- Native volume and brightness OSD overlays with smooth numerical readouts.
- 2FA OTP code copy pills, incoming call alerts, and quick screen capture.
- **Fullscreen App Suppression:** Automatically hides during full-screen games (DirectX, Vulkan) and video playback.
- **Self-Healing Crash Recovery:** Protected paint loops with obsidian fallback; crash-loop protected respawn mechanism.

---

## Android Companion App

The repository includes a companion mobile application built with **Kotlin & Jetpack Compose**:

- **Location:** `android_companion/` (Pre-compiled: `dist/WinDin.apk`)
- **Zero-Cloud Local Wi-Fi Bridge:** Connects to the desktop's embedded WebSocket server (`ws://<PC_IP>:54321`) with mDNS auto-discovery and one-tap QR token pairing.
- **Silent MediaStore Photo Drops:** Received images bypass download folders and save straight into Android's native MediaStore gallery.
- **Bidirectional Sync:** Streams live phone battery levels to the desktop island and allows quick remote clipboard beaming.

---

## Controls & Shortcuts

| Action | Input / Trigger |
| :--- | :--- |
| **Expand Dashboard** | Hover cursor over compact notch or press `Alt + Space` |
| **Collapse Dashboard** | Move cursor away (`450 ms` delay) or press `Esc` |
| **Play / Pause** | Click center vector pill control |
| **Previous / Next Track** | Click left / right vector pill controls |
| **Seek Playback** | Click or drag on the interactive timeline scrubber |
| **Win Drop File Beam** | Drag any file within 140 px of the top screen edge |
| **Copy 2FA Code** | Click `"Copy Code"` inside the OTP alert pill |
| **Dock Positioning** | Drag island to any screen edge/corner, or right-click Tray &rarr; *Dock Position* |
| **Settings & Control Center** | Double-click System Tray icon or right-click the island |

---

## Quick Start & Downloads

### Pre-Compiled Standalone Binaries (Recommended)

1. **Windows 11 / 10:**
   - Download [`DynamicIsland.exe`](https://github.com/pase5/WinDin/releases/latest) (~50.2 MB, strictly under 100 MB budget).
   - Run `DynamicIsland.exe` — the notch anchors automatically to the top center of your display.
   - *SmartScreen note:* If prompted with "Windows protected your PC", click **More info &rarr; Run anyway**. WinDin is standalone and open-source.
2. **Android Companion:**
   - Download [`WinDin.apk`](https://github.com/pase5/WinDin/releases/latest) (~39.5 MB).
   - Install the APK on your Android device (Android 8.0+, enable *Install unknown apps*).
   - Scan the pairing QR code displayed in the desktop island to connect instantly.

---

## Building from Source

### Prerequisites
- Python 3.10+ (64-bit)
- Windows 10 or 11
- Android Studio / JDK 17+ (for building mobile companion)

### 1. Running the Windows App from Source
```powershell
# Clone the repository
git clone https://github.com/pase5/WinDin.git
cd WinDin

# Create virtual environment & install dependencies
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Run application
python main.py
```

### 2. Compiling Windows Standalone Executable
```powershell
# Build standalone binary using PyInstaller spec (< 100 MB budget)
pyinstaller DynamicIsland.spec --noconfirm

# Verify binary output
Get-Item dist/DynamicIsland.exe | Select-Object Length, LastWriteTime
```

### 3. Building Android Companion APK
```powershell
cd android_companion
gradle assembleDebug
# Output binary: app/build/outputs/apk/debug/app-debug.apk
```

---

## Repository Architecture

```
WinDin/
├── main.py                     # Entrypoint, system tray, single-instance mutex, crash recovery
├── settings_app.py             # Dedicated Settings & Control Center launcher
├── DynamicIsland.spec          # PyInstaller packaging configuration (< 100 MB budget)
├── README.md                   # Project overview, features, and quickstart guide
├── DESIGN.md                   # Design tokens, color system, and motion physics
├── AGENTS.md                   # Operational standards (Zero emojis, < 100 MB, taskbar Z-order)
├── requirements.txt            # Python dependencies (PyQt6, pycaw, psutil, Pillow, numpy, winrt)
├── assets/                     # Vector icons, 3D device renders, mock covers
│   ├── app_icon.ico
│   ├── covers/
│   └── devices/
├── services/                   # Background system, media, and hardware listeners
│   ├── audio_spectrum.py       # WASAPI loopback audio stream & NumPy FFT analysis
│   ├── media_service.py        # Windows SMTC integration, track metadata, album art
│   ├── system_service.py       # Battery status, volume/brightness OSD, fullscreen suppression
│   ├── settings_service.py     # Atomic configuration persistence (%APPDATA%\WindowLand\settings.json)
│   ├── device_listener.py      # CoreAudio device connection watcher (AirPods, headphones)
│   ├── autostart_service.py    # Windows Registry Run key startup registration
│   ├── phone_bridge.py         # HTTP bridge for iOS Shortcuts & MacroDroid webhooks
│   └── web_companion.py        # Zero-cloud WebSocket server (ws://:54321) & mDNS pairing
├── ui/                         # PyQt6 presentation layer
│   ├── island_widget.py        # Core Dynamic Island widget, Bézier notch paths, Win Drop corona
│   ├── settings_window.py      # Control Center GUI (General, Appearance, Docking, Tools)
│   ├── styles.py               # Canonical dimensional constants, layout palettes, font loaders
│   ├── device_popup.py         # 3D accessory pairing modal sheet
│   └── components/             # Reusable UI widgets
│       ├── visualizer.py       # Real-time audio spectrum widgets
│       ├── quick_actions.py    # Quick action controls
│       └── reminder_widget.py  # Minimalist reminder pills
├── android_companion/          # Native Kotlin & Jetpack Compose Android companion
│   ├── app/src/main/           # MainActivity, WebSocket service, MediaStore gallery writer
│   └── build.gradle.kts
└── website/                    # Static showcase website (GitHub Pages)
    ├── index.html              # Single-page showcase & Web Simulator
    ├── css/style.css           # Obsidian + frosted glass styles & fluid spring physics
    ├── js/app.js               # Web Island simulator & GitHub Releases hub
    ├── js/neon-glyphs.js       # WebGL2 Holographic Matrix engine (Hero scoped)
    └── assets/logo.svg         # Vector notch brand logo
```

---

## Architectural Invariants (AGENTS.md)

1. **Rule 1: Zero System Emojis** — All user-facing UI controls, buttons, and status indicators are rendered as clean, anti-aliased vector paths (`QPainterPath`, `drawPolygon`, `drawRoundedRect`, `drawEllipse`).
2. **Rule 2: Executable Size Bound (< 100 MB)** — Standalone executable `dist/DynamicIsland.exe` must remain strictly under 100 MB (current: ~50.2 MB). Heavy libraries (`torch`, `tensorflow`, `cv2`, `pandas`) are excluded in `DynamicIsland.spec`.
3. **Rule 3: Defensive Rendering** — Every widget `paintEvent` is wrapped in defensive try/except blocks to prevent paint crashes.
4. **Rule 4: Windows Taskbar Z-Order Layering** — The island floats above standard windows but always sits behind `Shell_TrayWnd` and `Shell_SecondaryTrayWnd`.
5. **Rule 5: Zero Process Residue on Exit** — Background audio and device threads terminate cleanly on quit, releasing the named mutex and exiting with `os._exit(0)`.

---

## Authors & License

Crafted with precision by **[pase](https://github.com/pase5)** in collaboration with **[MTCodes01](https://github.com/MTCodes01)**.

Distributed under the **MIT License**. See `LICENSE` for details.
