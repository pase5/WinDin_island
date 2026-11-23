# WindowLand Dynamic Island — AI Agent Guidelines & Repository Architecture

Welcome, agent. This document serves as the operational guide and technical standard for any AI assistant or developer working on the **WindowLand Dynamic Island** codebase. Follow these rules and architectural invariants strictly to maintain system stability, performance, and aesthetic fidelity.

---

## 1. Core Directives & Hard Constraints

### Rule 1: Zero System Emojis
- **NEVER** use unicode emojis (`▶`, `⏸`, `⏮`, `⏭`, `⚡`, `📱`, `🔔`, etc.) for user-facing UI controls, buttons, or status displays.
- All iconography and media controls **must** be rendered as clean, anti-aliased vector paths (`QPainterPath`, `drawPolygon`, `drawRoundedRect`, `drawLine`, `drawEllipse`) with subpixel antialiasing enabled.
- System notifications or titles received externally from third-party apps may contain emojis; handle them gracefully with text elision.

### Rule 2: Standalone Executable Size Bound (< 60 MB)
- The compiled standalone executable `dist/DynamicIsland.exe` **must remain under 60 MB**.
- In `DynamicIsland.spec`, heavy frameworks are strictly excluded (`torch`, `tensorflow`, `jax`, `scipy`, `pandas`, `cv2`, `matplotlib`, `tkinter`).
- Do not introduce heavy dependencies without verifying their impact on the PyInstaller output size.

### Rule 3: Defensive Rendering (No Paint Crashes)
- Every widget `paintEvent` (`DynamicIslandWidget`, `CoverArtWidget`, `TimelineScrubber`, `VectorMediaButton`, `AudioVisualizerWidget`) **must** be wrapped in defensive try/except blocks.
- If a paint error occurs (missing GDI object, null pixmap, division by zero during window resize), log the error and fall back to rendering a safe obsidian surface. A paint glitch must **never** crash the application.

### Rule 4: Windows Taskbar Z-Order Layering
- The island uses `Qt.WindowType.WindowStaysOnTopHint` to float above standard desktop applications.
- However, it **must always sit behind the Windows Taskbar** (`Shell_TrayWnd` and `Shell_SecondaryTrayWnd`) in Win32 Z-order via `_ensure_behind_taskbar()`.
- Never allow the island to cover Windows Taskbar icons, pinned apps, or the Start button when the taskbar is visible or auto-unhides.

### Rule 5: Zero Process Residue on Exit
- In `on_quit()`, the application must flush settings, terminate background threads (`AudioSpectrumEngine`, `DeviceListener`), release the single-instance mutex (`WindowLand_DynamicIsland_SingleInstance_Mutex`), purge temporary PyInstaller `_MEI*` folders older than 30 minutes, and call `os._exit(0)` to guarantee zero zombie processes remain.

---

## 2. Repository Layout & Module Ownership

```
WindowLand/
├── main.py                     # App entrypoint, tray menu, single-instance mutex, crash recovery
├── DynamicIsland.spec          # PyInstaller packaging configuration (< 60 MB budget)
├── README.md                   # User-facing overview, features, and quickstart guide
├── DESIGN.md                   # Design system, typography, motion physics, and color tokens
├── AGENTS.md                   # This agent guideline document
├── requirements.txt            # Python dependencies (PyQt6, pycaw, comtypes, psutil, Pillow, numpy, winrt)
├── assets/                     # App icon, 3D device renders, mock covers
│   ├── app_icon.ico
│   ├── covers/
│   └── devices/
├── services/                   # Background system, media, and hardware listeners
│   ├── audio_spectrum.py       # WASAPI loopback audio stream & NumPy FFT analysis
│   ├── media_service.py        # Windows SMTC integration, track metadata, album art
│   ├── system_service.py       # Battery status, volume/brightness OSD, fullscreen app suppression
│   ├── settings_service.py     # Atomic configuration persistence (%APPDATA%\WindowLand\settings.json)
│   ├── device_listener.py      # CoreAudio device connection watcher (AirPods, headphones, IEMs)
│   ├── autostart_service.py    # Windows Registry Run key startup registration
│   └── phone_bridge.py         # HTTP bridge for iOS Shortcuts & MacroDroid webhooks
└── ui/                         # PyQt6 presentation layer
    ├── island_widget.py        # Core Dynamic Island widget, Bézier notch paths, docking engine
    ├── styles.py               # Canonical dimensional constants, layout palettes, font loaders
    ├── device_popup.py         # 3D accessory pairing modal sheet
    └── components/             # Reusable UI widgets
        ├── visualizer.py       # Real-time audio spectrum widgets
        ├── quick_actions.py    # Quick action controls
        └── reminder_widget.py  # Minimalist reminder pills
```

---

## 3. Critical Architectural Contracts

### 3.1 Docking & Geometry Calculations
When calculating window target rectangles in `ui/island_widget.py::_get_target_rect(state)`:
- Support all 9 docking targets: `top`, `bottom`, `left`, `right`, `top-left`, `top-right`, `bottom-left`, `bottom-right`, and `floating`.
- **Top / Bottom**: Dimensions driven by `COMPACT_HEIGHT` ($30\text{ px}$), `COMPACT_MUSIC_WIDTH` ($280\text{ px}$), and `EXPANDED_WIDTH`/`EXPANDED_HEIGHT` ($460 \times 200\text{ px}$).
- **Sides (`left`, `right`)**: Vertical pill geometry driven by `SIDE_COMPACT_IDLE_W` / `SIDE_COMPACT_MUSIC_W` ($32\text{ px}$) and `SIDE_EXPANDED_W`/`SIDE_EXPANDED_H` ($230 \times 370\text{ px}$).
- **Corners**: Reverse-L dual-arm bracket driven by `CORNER_COMPACT_IDLE_W` / `CORNER_COMPACT_MUSIC_W` ($230\text{ px}$) and `CORNER_COMPACT_IDLE_H` / `CORNER_COMPACT_MUSIC_H` ($180\text{ px}$).
- **Non-Inverting Ear Scaling**: Always clamp $r_{\text{ear}} + r_{\text{bot}}$ to $\min(w, h) - 2.0$ in `_create_notch_path` so Bézier curves never reverse or loop over themselves.

### 3.2 State Morphing & Opacity Staging
- Do **not** show child expanded containers (`dashboard_container`, `dashboard_container_side`, `dashboard_container_corner`) when expansion progress $p < 0.25$.
- Compact elements must fade out within $p \in [0.0, 0.28]$:
  $$\alpha_{\text{compact}}(p) = \max\left(0.0, \min\left(1.0, \frac{0.28 - p}{0.28}\right)\right)$$
- Expanded containers fade in from $p \in [0.25, 1.0]$:
  $$\alpha_{\text{expanded}}(p) = \max\left(0.0, \min\left(1.0, \frac{p - 0.25}{0.75}\right)\right)$$
- Always disconnect previous `finished` signal handlers on `self._geo_animation` before starting a new transition to prevent listener accumulation.

### 3.3 Settings Persistence Contract
- Settings are persisted atomically in `%APPDATA%\WindowLand\settings.json`.
- Access settings exclusively through `services.settings_service.settings`:
  ```python
  from services.settings_service import settings
  cfg = settings.load()
  settings.update(dock_edge="top-left", theme_mode="ambient")
  ```
- Saved properties: `dock_edge`, `dock_ratio_x`, `dock_ratio_y`, `screen_index`, `theme_mode`, `solid_color`, `ambient_opacity`, `auto_hide`, `time_format`, `autostart`.

### 3.4 Self-Healing Crash Recovery
- `main.py` installs a custom `sys.excepthook` via `_exception_hook`.
- If an unhandled exception occurs in the Qt event loop, the error is written to `%APPDATA%\WindowLand\crash.log` and the application respawns itself via `_respawn_self()`.
- Enforce crash-loop protection: Maximum 3 restarts within any 60-second window.

---

## 4. Build, Verification, & Testing Protocols

When modifying or verifying code in this repository:

### Step 1: Pre-Execution Syntax Check
Always verify syntax across affected files before running or building:
```powershell
.\venv\Scripts\python.exe -m py_compile main.py ui/island_widget.py services/settings_service.py
```

### Step 2: Terminate Existing Instances
Before rebuilding the binary or running single-instance tests, terminate any running instances to release file locks:
```powershell
Stop-Process -Name DynamicIsland -Force -ErrorAction SilentlyContinue
```

### Step 3: Standalone Executable Build
Build using PyInstaller with the spec file:
```powershell
.\venv\Scripts\pyinstaller.exe DynamicIsland.spec --noconfirm
```
Verify the output size and file timestamp:
```powershell
Get-Item dist/DynamicIsland.exe | Select-Object Length, LastWriteTime
```
Confirm `Length < 62914560` ($60\text{ MB}$).

### Step 4: Verification of Launch & Clean Exit
Launch the executable and verify running state, settings file creation, and clean exit:
```powershell
$proc = Start-Process -FilePath "dist/DynamicIsland.exe" -PassThru
Start-Sleep -Seconds 3
Get-Process -Id $proc.Id
Stop-Process -Id $proc.Id -Force
```

---

## 5. Anti-Patterns to Avoid

| Anti-Pattern | Why It Breaks the System | What to Do Instead |
| :--- | :--- | :--- |
| **Using emojis for buttons** | Looks inconsistent, breaks dark theme styling, renders blurry on high-DPI displays. | Render vector paths with `QPainterPath` inside squircle capsules. |
| **Hardcoding screen dimensions (`1920x1080`)** | Breaks on multi-monitor setups, ultrawide displays, and high-DPI laptops. | Query `QGuiApplication.screenAt(center)` and use dynamic screen bounds. |
| **Directly calling `app.quit()` without cleanup** | Leaves WASAPI audio threads running, blocks named mutex, and creates zombie processes. | Call `on_quit()` in `main.py` which releases mutex and calls `os._exit(0)`. |
| **Showing child containers at $p \approx 0.0$** | Causes Qt layouts to compress $160\text{ px}$ controls into $20\text{ px}$ pill bounds, thrashing CPU. | Keep child containers hidden until $p \ge 0.25$. |
| **Omitting ear constraint scaling** | $r_{\text{ear}} + r_{\text{bot}} > h$ causes Bézier curves to self-intersect, creating black knots and visual glitches. | Bound both radii dynamically by $\min(w, h) - 2.0$. |
| **Overriding `WindowStaysOnTopHint` without taskbar awareness** | Dynamic Island draws on top of the Windows Taskbar, blocking Start menu and pinned taskbar apps. | Always call `_ensure_behind_taskbar()` to place the island behind `Shell_TrayWnd`. |
