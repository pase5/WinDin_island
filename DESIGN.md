# WindowLand Dynamic Island — Design System & Visual Specification

## 1. Executive Summary & Design Philosophy

**WindowLand Dynamic Island** is a hardware-integrated desktop overlay designed for Windows 10 and 11. It reimagines the fluid, tactile micro-interactions of modern mobile operating systems as a native, non-intrusive component of the desktop computing environment.

### Core Design Principles
1. **Physicality & Material Authenticity**: The interface avoids the appearance of a disconnected floating window. Instead, it behaves as an organic physical extrusion of the monitor’s bezel, utilizing continuous inverse Bézier fillets, specular surface reflections, and milled edge highlights.
2. **Mathematical Continuity**: Interface transitions never snap, jump, or invert. Radii, path tangents, control points, and opacities continuously morph using parametric mathematical curves ($60\text{ FPS}$).
3. **Clarity Without Embellishment**: Every pixel serves a communicative purpose. System emojis and generic iconography are replaced with mathematically precise, anti-aliased vector geometry.
4. **Contextual Awareness**: The UI adapts dynamically to user attention, media activity, connected hardware accessories, full-screen gaming, and taskbar visibility.

---

## 2. Visual Language & Color System

The visual architecture is anchored in deep, layered obsidian tones overlaid with dynamic ambient glow derived from active content.

### 2.1 Core Neutral Palette

| Token | Hex / RGBA | Role / Usage |
| :--- | :--- | :--- |
| `COLOR_OBSIDIAN_BASE` | `#08080C` / `rgba(8, 8, 12, 1.0)` | Primary background core for compact notch and cards. |
| `COLOR_OBSIDIAN_SURFACE` | `rgba(14, 14, 18, 0.99)` | Top surface gradient stop for subtle vertical depth. |
| `COLOR_OBSIDIAN_DEEP` | `rgba(2, 2, 4, 1.0)` | Bottom surface gradient stop providing grounded weight. |
| `COLOR_BEZEL_STROKE` | `rgba(26, 26, 34, 0.90)` | $1.5\text{ px}$ milled hardware border separating island from desktop. |
| `COLOR_SPECULAR_HIGH` | `rgba(255, 255, 255, 0.24)` | Meniscus specular highlight rim along top docked edge. |
| `COLOR_SPECULAR_SUBTLE` | `rgba(255, 255, 255, 0.08)` | Inner card border stroke creating frosted glass edge definition. |

### 2.2 Content-Adaptive Aurora Plasma
In **Ambient Mode**, the interface dynamically samples color swatches from the active album artwork thumbnail:
- **Atmospheric Reflection**: The artwork is heavily blurred ($\sigma = 40\text{ px}$) and blended across the rear layer at $24\%$ opacity (`rgba(..., 0.24)`).
- **Vibrant Accent**: Extracted primary color drives the timeline scrubber progress fill, active audio spectrum gradient tips, and primary vector buttons.
- **Luminance Floor**: Extracted colors are clamped to ensure a minimum perceived luminance ($L \ge 0.45$) against dark obsidian backgrounds, ensuring readability regardless of album cover darkness.

### 2.3 Semantic & Status Colors

| Role | Color | Hex | Usage |
| :--- | :--- | :--- | :--- |
| **Active / Success** | Emerald Green | `#34C759` | Battery $> 20\%$, Incoming call answer, 2FA copied checkmark. |
| **Warning / Minute** | Amber Gold | `#FF9500` | $24\text{h}$ clock minutes, hardware privacy microphone LED. |
| **Critical / Decline** | Ruby Red | `#FF3B30` | Battery $\le 20\%$, Call decline button, disconnect alert. |
| **Notification Glow** | Cyan / Violet | `#00C6FF` $\to$ `#0072FF` | Incoming toast border pulse and notification ping. |

---

## 3. Typography & Numerical Hierarchy

Typefaces utilize Windows system variable typefaces (`Segoe UI Variable Display`, `Segoe UI Variable Text`, `Segoe UI`, or native system sans-serif fallback) rendered with subpixel anti-aliasing.

### 3.1 Type Scale

| Role | Font Family | Size | Weight | Line Height | Tracking | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Display** | Segoe UI Variable Display | $12.5\text{ pt}$ | Bold ($700$) | $16\text{ px}$ | $-0.02\text{ em}$ | Expanded track title, OSD values. |
| **Clock Primary** | Segoe UI Variable Display | $11.0\text{ pt}$ | Bold ($700$) | $14\text{ px}$ | $0.0\text{ em}$ | $24\text{h}$ clock hour value (`hh`). |
| **Clock Accent** | Segoe UI Variable Display | $11.0\text{ pt}$ | Bold ($700$) | $14\text{ px}$ | $0.0\text{ em}$ | $24\text{h}$ clock minute value (`mm`). |
| **Body / Title** | Segoe UI Variable Text | $10.0\text{ pt}$ | SemiBold ($600$) | $14\text{ px}$ | $0.0\text{ em}$ | Compact track title, device model name. |
| **Subtitle** | Segoe UI Variable Text | $9.0\text{ pt}$ | Regular ($400$) | $12\text{ px}$ | $+0.01\text{ em}$ | Artist name, phone caller subtitle, date label. |
| **Microlabel** | Segoe UI Variable Text | $7.5\text{ pt}$ | Medium ($500$) | $10\text{ px}$ | $+0.03\text{ em}$ | Scrubber elapsed/duration timestamps, battery $\%$. |

### 3.2 Dual-Color $24\text{h}$ Clock Anatomy
To eliminate ambiguity in compact peripheral viewing:
- The clock is strictly zero-padded 24-hour time ($13:05$ or stacked $\begin{matrix} 13 \\ 05 \end{matrix}$).
- **Hours (`hh`)** render in pure white (`#FFFFFF`, $100\%$ opacity).
- **Minutes (`mm`)** render in amber (`#FF9500`, $100\%$ opacity).
- On vertical bezels and corner arms, hours and minutes stack vertically with a $0.5\text{ px}$ gap, centered inside the $36\text{ px}$ arm profile.

---

## 4. Hardware Geometry & Vector Mathematics

WindowLand uses custom `QPainterPath` algorithms to generate continuous hardware silhouettes without raster clipping or texture scaling artifacts.

```
       r_ear                                      r_ear
(0,0)───╭────╮                                  ╭────╮───(w,0)
        │    ╰──────────────────────────────────╯    │
        │                                            │
        ╰──────────╮                      ╭──────────╯
               r_bot                      r_bot
```

### 4.1 Inverse Ear Fillet Formula
The top flaring inverse fillets (the "ears") connect the flat screen border at $y = 0$ to the island body with curvature continuity.
- From $(0, 0)$ to $(r_{\text{ear}}, r_{\text{ear}})$, the curve is generated by a cubic Bézier:
  $$P_0 = (0, 0), \quad P_1 = (r_{\text{ear}} \cdot 0.4, 0), \quad P_2 = (r_{\text{ear}}, r_{\text{ear}} \cdot 0.4), \quad P_3 = (r_{\text{ear}}, r_{\text{ear}})$$
- The slope matches the horizontal screen edge at $P_0$ ($\frac{dy}{dx} = 0$) and transitions smoothly to vertical at $P_3$ ($\frac{dx}{dy} = 0$).

### 4.2 Non-Inverting Scaling Constraint
To prevent control points from overlapping or inverting when width $w$ or height $h$ is small (such as on $32\text{ px}$ side pills or $30\text{ px}$ compact notches):
$$\text{scale} = \min\left(1.0, \frac{\max(4.0, h - 2.0)}{r_{\text{ear}} + r_{\text{bot}}}\right)$$
Both $r_{\text{ear}}$ and $r_{\text{bot}}$ scale proportionally by $\text{scale}$. Control points are guaranteed never to self-intersect.

### 4.3 Corner Squircle Superellipse
Album art covers, connection cards, and corner hubs use continuous squircles ($n = 4$ superellipses) or rounded rectangles with corner radius:
$$r_{\text{art}} = \text{size} \times 0.25$$
A $1\text{ px}$ diagonal specular highlight (`#FFFFFF` at $20\%$ alpha fading to $0\%$) is overlaid across the squircle surface to emulate 2.5D optical glass.

---

## 5. Spatial Docking Paradigms

```
Dock Target     Compact Form Factor            Expanded Form Factor
─────────────── ────────────────────────────── ──────────────────────────────
Top Bezel       Horizontal Notch (280x30 px)   Horizontal Card (460x200 px)
Bottom Bezel    Horizontal Notch (280x30 px)   Horizontal Card (460x200 px)
Left / Right    Vertical Pill    (32x260 px)   Vertical Card   (230x370 px)
Corners (x4)    L-Bracket        (230x180 px)  Square Card     (280x280 px)
Floating        Capsule          (280x30 px)   Horizontal Card (460x200 px)
```

### 5.1 Top Bezel Notch
Anchored flush to $y = 0$ of the active screen. Spreads horizontally with symmetrical inverse fillets. Perfect for primary monitors with centered webcams or displays with top bezels.

### 5.2 Bottom Dock & Taskbar Layering
- Anchored to the bottom edge of the display work area.
- Automatically positioned immediately behind Windows Taskbars (`Shell_TrayWnd`) in the Win32 Z-order.
- When an auto-hiding taskbar pops up, the taskbar slides over the island without clipping or obscuring taskbar icons. When the taskbar hides, the island sits flush against the bottom monitor edge.

### 5.3 Side Bezel Vertical Pills
- Width is fixed at $32\text{ px}$ (compact) to minimize screen real-estate impact along display perimeters.
- Arranged vertically: Album art squircle at top, $12$-band frequency ladder in the center, and stacked $24\text{h}$ clock at the bottom.

### 5.4 Corner Reverse-L Architecture (`⌈`, `⌉`, `⌊`, `⌋`)
- Dual-arm bracket geometry ($230 \times 180\text{ px}$ in compact idle and music states).
- **Horizontal Arm ($36\text{ px}$ thick)**: Houses track title, artist label, and mouse-seekable scrub bar.
- **Vertical Arm ($36\text{ px}$ thick)**: Houses stacked $24\text{h}$ digital clock and 10-band audio spectrum ladder.
- **Corner Hub ($36 \times 36\text{ px}$)**: Houses the album art squircle with glass highlight rim.
- In idle mode, seamlessly presents system status ("Ready · Standing By") and current date without truncation.

---

## 6. Motion Design & Animation Physics

All transitions run at $60\text{ FPS}$ driven by `QPropertyAnimation` over normalized progress parameter $p \in [0.0, 1.0]$.

### 6.1 Easing & Timing Specifications

| Interaction | Duration | Easing Curve | Character / Feel |
| :--- | :--- | :--- | :--- |
| **Hover Expand** | $320\text{ ms}$ | `OutCubic` | Responsive burst, gentle deceleration into full size. |
| **Hover Collapse** | $260\text{ ms}$ | `OutQuad` | Crisp, rapid retraction without perceived lag. |
| **Snap-to-Dock** | $300\text{ ms}$ | `OutBack(1.2)` | Gentle magnetic latch when dropping window near screen edges. |
| **Notification Toast** | $280\text{ ms}$ | `OutBack(1.4)` | Playful overshoot when popping up incoming alerts. |
| **State Cross-Fade** | $200\text{ ms}$ | `InOutQuad` | Seamless dissolve between idle status and media player. |

### 6.2 Staged Cross-Fade Architecture
To guarantee that compact elements (clock, mini-visualizer) and expanded elements (80px cover art, volume controls, scrubber) never visually collide during resizing:
1. **Compact Elements Alpha**:
   $$\alpha_{\text{compact}}(p) = \max\left(0.0, \min\left(1.0, \frac{0.28 - p}{0.28}\right)\right)$$
   Compact UI elements dissolve to $0\%$ opacity by $p = 0.28$.
2. **Expanded Container Alpha**:
   $$\alpha_{\text{expanded}}(p) = \max\left(0.0, \min\left(1.0, \frac{p - 0.25}{0.75}\right)\right)$$
   Expanded container remains completely hidden while $p < 0.25$, preventing layout squishing, and fades in smoothly from $p = 0.25 \to 1.0$.

### 6.3 3D Directional Cursor Perspective Tilt
Across the expanded card surface ($460 \times 200\text{ px}$), cursor movements impart a subtle physical tilt:
- Tilt range: $\pm 1.5^\circ$ along the $X$ and $Y$ axes.
- Driven by normalized cursor offset from card center:
  $$\Delta x = \frac{x_{\text{cursor}} - x_{\text{center}}}{w / 2}, \quad \Delta y = \frac{y_{\text{cursor}} - y_{\text{center}}}{h / 2}$$
- Produces a dynamic optical shift in specular highlight reflections, enhancing perceived surface depth.

---

## 7. Audio Spectrum Visualization Design

The audio visualizer translates live PC playback into geometric motion via the WASAPI audio spectrum engine.

### 7.1 Visualizer Form Factors
1. **Expanded Notch Visualizer**:
   - $22$ or $26$ vertical frequency bars centered below track info.
   - Bar width: $2.5\text{ px}$, bar spacing: $2.5\text{ px}$.
   - Vertical gradient: Rooted in translucent white (`#FFFFFF`, $45\%$ alpha), rising to extracted album art accent color at peak.
2. **Side Dock Visualizer**:
   - $12$ horizontal bars arranged vertically in a ladder.
   - Bar height: $3.0\text{ px}$, vertical gap: $4.8\text{ px}$.
   - Bars expand horizontally outward from center axis ($w_{\text{min}} = 4\text{ px}$, $w_{\text{max}} = 24\text{ px}$).
3. **Corner Bracket Visualizer**:
   - $10$ horizontal bars arranged along the vertical arm.
   - Bar height: $2.5\text{ px}$, vertical gap: $3.2\text{ px}$.
   - Pulses outwards proportionally to low/mid/high frequency bands.

### 7.2 Ballistics
- **Attack ($0.65$)**: Instantaneous reaction to transients, snare hits, and bass kicks.
- **Decay ($0.82$)**: Smooth, fluid descent preventing nervous jitter.
- **Peak Hold**: Subtle floating indicator holds peak levels for $120\text{ ms}$ before descending via gravitational falloff.

---

## 8. Component Design Specifications

### 8.1 Vector Media Transport Controls
- Buttons are rendered as vector paths inside translucent squircle button capsules (`rgba(255, 255, 255, 0.12)`).
- **Play/Pause**: Primary center pill ($40 \times 32\text{ px}$) rendered in white or active cover accent.
- **Previous/Next**: Secondary frosted glass pills ($32 \times 32\text{ px}$) rendered at $60\%$ white opacity.
- **Hover Micro-interaction**: Capsule fill brightens to $24\%$ alpha, scale expands by $1.04\times$.

### 8.2 Interactive Timeline Scrubber
- Hit-test area: $14\text{ px}$ vertical band centered on scrubber.
- Track height: $2.5\text{ px}$ (normal), expands to $4.0\text{ px}$ on hover.
- Background track: `rgba(255, 255, 255, 0.20)`.
- Played track: Filled with cover art accent color.
- Thumb cap: $6.0\text{ px}$ glowing circular head (`rgba(255, 255, 255, 0.95)` with $2\text{ px}$ drop shadow).

### 8.3 3D Accessory Connection Sheet (`340 × 330 px`)
- Displays real-time pairing status when AirPods, headphones, or Bluetooth speakers connect.
- **Hero Asset**: Floating 3D device rendering ($175 \times 175\text{ px}$) with gentle floating bob motion ($f = 0.5\text{ Hz}$).
- **Contact Shadow**: Soft elliptical shadow below device model scaling inversely with bob height.
- **Battery Arc**: Circular segmented gauge showing individual left, right, and case percentages.
- **Audio Routing Pill**: Quick-switch capsule allowing one-click redirection between speakers and headphones.

---

## 9. Accessibility & Ergonomics

- **Contrast Ratios**: All primary text (`#FFFFFF`) against obsidian backgrounds exceeds WCAG AAA standard ($> 14:1$). Secondary text (`rgba(255, 255, 255, 0.60)`) meets WCAG AA ($> 4.5:1$).
- **Click Target Sizes**: All interactive buttons maintain a minimum touch/click bounding box of $32 \times 32\text{ px}$.
- **Text Elision**: Long track titles, artist names, and status labels use intelligent `QFontMetrics.elidedText` with trailing ellipsis, preventing layout displacement or overflow.
- **Color Independence**: System states (charging, audio playing, errors) pair color changes with distinct geometric icon transformations (lightning bolt, spectrum motion, pause glyph) to accommodate color-vision deficiencies.
