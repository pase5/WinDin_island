<div align="center">

# Dynamic Island for Windows
### An Organic, Curvy Hardware Notch Overlay for Windows 10 & 11

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows)](https://github.com/WindowLand)
[![FPS](https://img.shields.io/badge/Animation-60%20FPS-FFD600?style=for-the-badge)](#)
[![Build](https://img.shields.io/badge/Binary-Standalone%20EXE-FF8C00?style=for-the-badge)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](#)
[![UI Framework](https://img.shields.io/badge/UI-PyQt6-41CD52?style=for-the-badge&logo=qt)](#)

*A fluid, hardware-inspired desktop overlay with organic Bézier fillets, real-time WASAPI audio spectrum visualization, 3D tilt physics, and multi-edge screen docking.*

[Quick Start](#quick-start) • [Features](#features) • [Controls & Shortcuts](#controls--shortcuts) • [Technical Checklist & Roadmap](CHECKLIST.md)

</div>

---

## Overview

**Dynamic Island for Windows** brings a fluid, iOS/macOS-inspired interactive overlay to your Windows desktop. Designed with anti-aliased vector geometry, 60 FPS physics-driven animations, real-time audio analysis, and intelligent full-screen awareness, it remains completely unobtrusive until summoned.

Whether anchored flush to your monitor's top bezel, resting along the taskbar, tucked into screen corners as a dual-arm bracket, or docked to the screen edges, Dynamic Island adapts organically with smooth parametric vector morphing.

---

## Features

### Bespoke Vector Media Player
- **Zero System Emojis:** All UI controls are rendered using crisp, anti-aliased vector geometry.
- **Interactive Scrubber:** Precise timeline scrubbing with hover expansion, glowing playhead, and real-time seek synchronization.
- **3D Directional Tilt:** Realistic perspective shifts driven by cursor coordinates across the expanded dashboard card.
- **Color Extraction:** Dynamically extracts swatches from active album art to synchronize plasma backdrops, scrubber glows, and equalizer colors.

### Hardware-Accelerated Audio Spectrum
- **WASAPI Loopback Engine:** Real-time 2048-point Hann-windowed FFT capturing bit-exact audio directly from the default Windows playback device.
- **Top Notch Equalizer:** 26-bar center equalizer in the expanded card and 4-bar mini equalizer in compact mode.
- **Corner & Side Vertical Equalizers:** 10- and 12-band vertical frequency ladders on screen corners and side bezels that pulse horizontally with audio ballistics.

### Multi-Edge Docking & Morphing
- **Top Bezel Notch:** Anchors flush against `y = 0` with organic flared inverse fillets (`r = 14px`).
- **Corner Reverse-L (`⌈`):** Dual-arm bracket showcasing track progress on the horizontal arm, album art in the corner hub, and a vertical frequency ladder with digital clock on the vertical arm.
- **Side Bezel Pills:** Minimal vertical pills docked along left or right screen edges with unclipped stacked digital clocks.
- **Taskbar & Free-Floating:** Snap above the taskbar or float freely anywhere across multiple monitors.
- **Parametric Vector Morphing:** Smooth continuous Bézier path interpolation between compact anchors and expanded cards.

### Accessory Pairing & Showcase Modals
- **Automatic Recognition:** Real-time CoreAudio background detection for AirPods, over-ear headphones, Bluetooth speakers, and audiophile IEMs/DACs.
- **Interactive 3D Sheet:** Bobbing 3D models with ambient pedestal halos, segmented battery rings, and inline audio routing controls.

### Local Wi-Fi Companion & System Tools
- **Embedded Web Server:** Lightweight background service on port `54321` enabling triggers from iOS Shortcuts and Android automation (MacroDroid / Tasker).
- **Desktop HUDs & Utilities:** Native volume/brightness OSDs, 2FA OTP code copy pills, live call cards, drag-and-drop file shelves, and quick screen capture.
- **Full-Screen Suppression:** Automatically hides during full-screen games (DirectX/Vulkan) and video playback.

---

## Controls & Shortcuts

| Action | Input / Trigger |
| :--- | :--- |
| **Expand Dashboard** | Hover cursor over compact notch or press `Alt + Space` |
| **Collapse Dashboard** | Move cursor away (`450ms` delay) or press `Esc` |
| **Play / Pause** | Click golden capsule vector pill (`▶` / `❚❚`) |
| **Previous / Next Track** | Click frosted glass pills (`|◀` / `▶|`) |
| **Seek Playback** | Click or drag on the interactive timeline scrubber |
| **Stash Files** | Drag and drop files directly onto the notch |
| **Copy 2FA Code** | Click `"Copy Code"` inside the OTP alert pill |
| **Dock Positioning** | Drag the island to any edge/corner, or right-click Tray &rarr; *Dock Position* |
| **Settings & Exit** | Right-click the **Dynamic Island** icon in the Windows System Tray |

---

## Quick Start

### Pre-Compiled Standalone Binary (Recommended)
1. Download the latest release (`DynamicIsland.exe`).
2. Run `DynamicIsland.exe` — the notch will automatically anchor to the top center of your primary display.
3. Play audio in Spotify, YouTube, Apple Music, or any media player to see the island come alive.

### Running from Source
```bash
# Clone the repository
git clone https://github.com/WindowLand/DynamicIsland.git
cd DynamicIsland

# Create virtual environment & install dependencies
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Run application
python main.py
```

### Compiling Executable
```bash
pyinstaller DynamicIsland.spec --noconfirm
```
The standalone binary will be generated at `dist/DynamicIsland.exe` (~54 MB).

---

## Settings & Control Center Application

WindowLand now includes a dedicated modern desktop settings application for all adjustments:
- **General & Island Controls:** Expand/collapse, recenter to top bezel, auto-hide when idle toggle, autostart on Windows boot, 12h/24h clock format.
- **Appearance & Themes:** Live preview of Dynamic Island with dynamic ambient glow, OLED Obsidian, Frosted Titanium, custom color picker, gradient themes, and ambient intensity slider (0%–50%).
- **Interactive Docking Selector:** Visual monitor graphic to click and dock to Top Bezel, Bottom Taskbar, Left/Right edges, 4 Corners, or Free Floating, plus multi-monitor selector.
- **Tools & Companion:** Phone Companion connection dashboard with pairing URL, copy link, and quick desktop actions (Screenshot, Mute, Do Not Disturb).
- **Diagnostics Simulation Deck:** One-click live simulator for Volume HUD, Incoming Call, 2FA OTP Code, File Shelf, Download Hairline, Notifications, 3D AirPods, and Over-Ear Headphones connection sheets.

### Launching the Settings Application
- **Tray Menu:** Right-click the system tray icon and select **`⚙️ Settings & Control Center...`**
- **Tray Icon Double Click:** Double-click the tray icon to open Settings immediately.
- **Island Right Click:** Right-click directly on the Dynamic Island on your desktop.
- **Standalone Command:**
  ```bash
  python settings_app.py
  # or
  python main.py --settings
  ```

---

## Architecture & Implementation Details

For the complete technical breakdown, completed milestone checklist, and upcoming feature roadmap, see:

[Detailed Implementation Checklist & Roadmap](CHECKLIST.md)

---

## Author

Crafted with precision by **[pase](https://github.com/pase5)** in collaboration with **[MTCodes01](https://github.com/MTCodes01)**.
