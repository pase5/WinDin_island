"""
WindowLand Dynamic Island — Web Application & Mobile Companion UI.
Strictly implements DESIGN.md and AGENTS.md:
- Frosted dark liquid glassmorphism (rgba(20, 18, 32, 0.65), backdrop-filter: blur(24px))
- Ambient radial neon glow blobs (magenta, violet, and mint)
- Rule 1: Zero System Emojis (100% crisp anti-aliased inline vector SVGs)
- Real-time REST API integration with Dynamic Island desktop engine
- Responsive for both desktop browsers and mobile touchscreens
"""

WEB_COMPANION_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>WindowLand • Control Center & Companion</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --canvas-bg: #09090F;
    --surface-glass: rgba(20, 18, 32, 0.65);
    --surface-glass-hover: rgba(28, 25, 44, 0.75);
    --surface-card: rgba(22, 20, 35, 0.70);
    --surface-well: rgba(0, 0, 0, 0.40);
    --surface-nested: rgba(255, 255, 255, 0.05);
    --surface-nested-hover: rgba(255, 255, 255, 0.09);
    --border-glass: rgba(255, 255, 255, 0.12);
    --border-subtle: rgba(255, 255, 255, 0.07);
    --primary-grad: linear-gradient(135deg, #FF43A8 0%, #7C03D3 100%);
    --primary-glow: 0 4px 24px rgba(255, 67, 168, 0.35);
    --emerald: #10B981;
    --emerald-bg: rgba(16, 185, 129, 0.14);
    --emerald-border: rgba(16, 185, 129, 0.35);
    --emerald-glow: 0 0 12px rgba(16, 185, 129, 0.50);
    --text-primary: #FFFFFF;
    --text-secondary: #94A3B8;
    --text-muted: #64748B;
    --eyebrow: #F472B6;
    --font-heading: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-body: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    background-color: var(--canvas-bg);
    color: var(--text-primary);
    font-family: var(--font-body);
    font-size: 13.5px;
    line-height: 1.5;
    min-height: 100vh;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  /* ── Background Radial Glow Blobs (DESIGN.md) ────────── */
  .ambient-glows {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
  }
  .glow-blob {
    position: absolute;
    border-radius: 50%;
    filter: blur(130px);
    opacity: 0.75;
    animation: pulseBlob 12s ease-in-out infinite alternate;
  }
  .blob-magenta {
    top: -120px;
    left: -120px;
    width: 440px;
    height: 440px;
    background: radial-gradient(circle, rgba(255, 67, 168, 0.22) 0%, transparent 70%);
  }
  .blob-violet {
    top: 35%;
    right: -100px;
    width: 520px;
    height: 520px;
    background: radial-gradient(circle, rgba(124, 3, 211, 0.20) 0%, transparent 70%);
    animation-delay: -4s;
  }
  .blob-mint {
    bottom: -140px;
    left: 25%;
    width: 460px;
    height: 460px;
    background: radial-gradient(circle, rgba(78, 222, 163, 0.12) 0%, transparent 70%);
    animation-delay: -8s;
  }
  @keyframes pulseBlob {
    0% { transform: scale(0.95) translate(0, 0); opacity: 0.65; }
    100% { transform: scale(1.08) translate(15px, 20px); opacity: 0.85; }
  }

  /* ── App Shell & Sidebar Grid ───────────────────────── */
  .app-shell {
    position: relative;
    z-index: 1;
    display: flex;
    min-height: 100vh;
    max-width: 1440px;
    margin: 0 auto;
  }

  /* Desktop Sidebar (260px) */
  .sidebar {
    width: 260px;
    flex-shrink: 0;
    background: var(--surface-glass);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border-right: 1px solid var(--border-glass);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 24px 18px;
    position: sticky;
    top: 0;
    height: 100vh;
  }

  .brand-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px 6px 20px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .brand-logo {
    width: 38px;
    height: 38px;
    border-radius: 11px;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .brand-logo svg { width: 100%; height: 100%; }
  .brand-info { display: flex; flex-direction: column; }
  .brand-title {
    font-family: var(--font-heading);
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }
  .brand-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--eyebrow);
  }

  /* Navigation Pills */
  .nav-menu {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 18px;
    flex: 1;
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 10px;
    color: var(--text-secondary);
    font-weight: 500;
    font-size: 13px;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.18s ease;
    border: 1px solid transparent;
    user-select: none;
  }
  .nav-item svg { width: 18px; height: 18px; flex-shrink: 0; transition: transform 0.18s; }
  .nav-item:hover {
    background: var(--surface-nested-hover);
    color: var(--text-primary);
  }
  .nav-item.active {
    background: var(--primary-grad);
    color: #FFFFFF;
    font-weight: 600;
    box-shadow: var(--primary-glow);
    border-color: rgba(255, 255, 255, 0.15);
  }
  .nav-item.active svg { transform: scale(1.05); }

  /* Sidebar Status Pill */
  .sidebar-status {
    background: var(--emerald-bg);
    border: 1px solid var(--emerald-border);
    border-radius: 20px;
    padding: 8px 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--emerald);
    font-size: 11.5px;
    font-weight: 600;
  }
  .beacon-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--emerald);
    box-shadow: var(--emerald-glow);
    animation: beaconPulse 2s infinite ease-in-out;
  }
  @keyframes beaconPulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.45; transform: scale(0.85); }
  }

  /* ── Mobile Top Header & Segmented Scroller ─────────── */
  .mobile-header {
    display: none;
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(15, 14, 25, 0.85);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border-bottom: 1px solid var(--border-glass);
    padding: 12px 16px 8px;
  }
  .mobile-brand-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }
  .mobile-nav-scroll {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }
  .mobile-nav-scroll::-webkit-scrollbar { display: none; }
  .mobile-tab-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 13px;
    border-radius: 20px;
    background: var(--surface-nested);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }
  .mobile-tab-pill svg { width: 15px; height: 15px; }
  .mobile-tab-pill.active {
    background: var(--primary-grad);
    color: #FFFFFF;
    box-shadow: var(--primary-glow);
    border-color: rgba(255, 255, 255, 0.2);
  }

  /* ── Main Content Area ──────────────────────────────── */
  .main-content {
    flex: 1;
    padding: 32px 36px 64px;
    overflow-y: auto;
    min-width: 0;
  }
  .view-header {
    margin-bottom: 24px;
  }
  .view-title {
    font-family: var(--font-heading);
    font-size: 26px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.015em;
    margin-bottom: 4px;
  }
  .view-subtitle {
    font-size: 13.5px;
    color: var(--text-secondary);
  }

  /* ── Card & Glass Container System ──────────────────── */
  .section-eyebrow {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--eyebrow);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .glass-card {
    background: var(--surface-card);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid var(--border-glass);
    border-radius: 16px;
    padding: 22px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  }

  .setting-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-radius: 12px;
    background: var(--surface-nested);
    margin-bottom: 10px;
    transition: background 0.15s ease;
  }
  .setting-row:last-child { margin-bottom: 0; }
  .setting-row:hover { background: var(--surface-nested-hover); }
  .row-info { display: flex; flex-direction: column; gap: 2px; }
  .row-title { font-weight: 600; color: var(--text-primary); font-size: 13.5px; }
  .row-desc { font-size: 12px; color: var(--text-secondary); }

  /* ── Interactive Vector Buttons ─────────────────────── */
  .btn-gradient {
    background: var(--primary-grad);
    color: #FFFFFF;
    font-weight: 600;
    font-size: 13px;
    border: none;
    border-radius: 10px;
    padding: 9px 18px;
    cursor: pointer;
    box-shadow: var(--primary-glow);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: transform 0.15s ease, opacity 0.15s ease;
    user-select: none;
  }
  .btn-gradient:active { transform: scale(0.97); opacity: 0.92; }
  .btn-gradient svg { width: 16px; height: 16px; }

  .btn-ghost {
    background: var(--surface-nested);
    color: var(--text-primary);
    font-weight: 600;
    font-size: 13px;
    border: 1px solid var(--border-glass);
    border-radius: 10px;
    padding: 9px 16px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.15s ease;
    user-select: none;
  }
  .btn-ghost:hover {
    background: var(--surface-nested-hover);
    border-color: rgba(255, 255, 255, 0.22);
  }
  .btn-ghost:active { transform: scale(0.97); }
  .btn-ghost svg { width: 16px; height: 16px; }

  /* ── Switch Toggle (DESIGN.md Pill) ─────────────────── */
  .switch-toggle {
    position: relative;
    width: 48px;
    height: 26px;
    border-radius: 9999px;
    background: rgba(255, 255, 255, 0.12);
    cursor: pointer;
    transition: background 0.2s ease;
    flex-shrink: 0;
  }
  .switch-toggle::after {
    content: '';
    position: absolute;
    top: 3px;
    left: 3px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #FFFFFF;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    box-shadow: 0 2px 5px rgba(0,0,0,0.4);
  }
  .switch-toggle.active {
    background: var(--primary-grad);
    box-shadow: var(--primary-glow);
  }
  .switch-toggle.active::after {
    transform: translateX(22px);
  }

  /* ── Live Notch Preview Card ────────────────────────── */
  .notch-preview-stage {
    background: radial-gradient(circle at 50% 30%, rgba(255, 67, 168, 0.12), rgba(0, 0, 0, 0.6) 70%);
    border: 1px solid var(--border-glass);
    border-radius: 14px;
    height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.2s;
  }
  .notch-preview-stage:hover { border-color: rgba(255, 67, 168, 0.4); }
  .preview-notch-pill {
    background: #08080C;
    border: 1.5px solid rgba(255, 255, 255, 0.14);
    border-radius: 20px;
    padding: 6px 18px;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.8), 0 0 20px rgba(255, 67, 168, 0.25);
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .preview-notch-pill:hover { transform: scale(1.03); }
  .preview-equalizer {
    display: flex;
    align-items: center;
    gap: 2.5px;
    height: 14px;
  }
  .eq-bar {
    width: 2.5px;
    border-radius: 2px;
    background: #FF43A8;
    animation: eqAnim 1s ease-in-out infinite alternate;
  }
  .eq-bar:nth-child(2) { animation-delay: -0.2s; background: #7C03D3; height: 12px; }
  .eq-bar:nth-child(3) { animation-delay: -0.5s; background: #4EDEA3; height: 16px; }
  .eq-bar:nth-child(4) { animation-delay: -0.3s; background: #FF43A8; height: 10px; }
  @keyframes eqAnim {
    0% { height: 4px; }
    100% { height: 15px; }
  }

  /* ── 3x3 Docking Grid Matrix ────────────────────────── */
  .docking-matrix {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 16px;
  }
  .dock-cell {
    background: var(--surface-nested);
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    transition: all 0.18s ease;
    user-select: none;
    text-align: center;
  }
  .dock-cell svg { width: 22px; height: 22px; color: var(--text-secondary); transition: all 0.18s; }
  .dock-cell span { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
  .dock-cell:hover {
    background: var(--surface-nested-hover);
    border-color: rgba(255, 255, 255, 0.22);
  }
  .dock-cell:hover svg, .dock-cell:hover span { color: var(--text-primary); }
  .dock-cell.active {
    background: var(--primary-grad);
    border-color: rgba(255, 255, 255, 0.3);
    box-shadow: var(--primary-glow);
  }
  .dock-cell.active svg, .dock-cell.active span { color: #FFFFFF; font-weight: 700; }

  /* ── Surface Materials & Color Swatches ─────────────── */
  .material-deck {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  .material-tile {
    background: var(--surface-nested);
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 14px;
    cursor: pointer;
    text-align: center;
    transition: all 0.18s ease;
  }
  .material-tile.active {
    border-color: #FF43A8;
    background: rgba(255, 67, 168, 0.12);
    box-shadow: 0 0 16px rgba(255, 67, 168, 0.25);
  }
  .material-title { font-weight: 600; font-size: 12.5px; margin-bottom: 2px; }
  .material-sub { font-size: 11px; color: var(--text-secondary); }

  .swatch-palette {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 14px;
  }
  .swatch-btn {
    border-radius: 10px;
    border: 1px solid var(--border-glass);
    padding: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    color: #FFFFFF;
    transition: transform 0.15s, border-color 0.15s;
  }
  .swatch-btn:hover { transform: scale(1.02); border-color: rgba(255, 255, 255, 0.35); }
  .swatch-btn .dot-preview {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 1.5px solid rgba(255, 255, 255, 0.25);
    flex-shrink: 0;
  }

  /* ── Presets & Form Elements (Tools Tab) ────────────── */
  .preset-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 18px;
  }
  .preset-card {
    background: var(--surface-nested);
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .preset-card:hover {
    background: var(--surface-nested-hover);
    border-color: rgba(255, 255, 255, 0.25);
    transform: translateY(-1px);
  }
  .preset-card:active { transform: scale(0.98); }
  .preset-icon {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .preset-icon svg { width: 17px; height: 17px; color: #FFFFFF; }
  .preset-text { display: flex; flex-direction: column; overflow: hidden; }
  .preset-name { font-weight: 600; font-size: 12.5px; }
  .preset-sub { font-size: 11px; color: var(--text-secondary); text-overflow: ellipsis; white-space: nowrap; overflow: hidden; }

  /* Input fields */
  .form-group { margin-bottom: 12px; }
  .form-label {
    display: block;
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .form-input, .form-textarea, .form-select {
    width: 100%;
    background: var(--surface-well);
    border: 1px solid var(--border-glass);
    border-radius: 10px;
    padding: 10px 14px;
    color: var(--text-primary);
    font-size: 13.5px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.18s;
  }
  .form-input:focus, .form-textarea:focus, .form-select:focus {
    border-color: #FF43A8;
    box-shadow: 0 0 10px rgba(255, 67, 168, 0.2);
  }

  /* ── Diagnostics Simulation Deck ────────────────────── */
  .deck-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .deck-item {
    background: var(--surface-nested);
    border: 1px solid var(--border-glass);
    border-radius: 12px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: all 0.15s ease;
  }
  .deck-item:hover { background: var(--surface-nested-hover); }
  .deck-left { display: flex; align-items: center; gap: 14px; }
  .deck-icon-badge {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .deck-icon-badge svg { width: 19px; height: 19px; color: #FFFFFF; }
  .deck-info { display: flex; flex-direction: column; }
  .deck-name { font-weight: 600; font-size: 13.5px; }
  .deck-desc { font-size: 11.5px; color: var(--text-secondary); }

  /* ── Floating Toast Feedback ────────────────────────── */
  .feedback-toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: rgba(18, 16, 28, 0.95);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid #FF43A8;
    color: #FFFFFF;
    padding: 10px 22px;
    border-radius: 9999px;
    font-size: 13px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 16px rgba(255, 67, 168, 0.35);
    z-index: 9999;
    opacity: 0;
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.28s;
    pointer-events: none;
  }
  .feedback-toast.show {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
  }
  .feedback-toast svg { width: 16px; height: 16px; color: #4EDEA3; }

  /* ── Responsive Mobile Overrides (< 768px) ──────────── */
  @media (max-width: 768px) {
    .sidebar { display: none; }
    .mobile-header { display: block; }
    .main-content { padding: 18px 14px 72px; }
    .docking-matrix { grid-template-columns: repeat(3, 1fr); gap: 6px; }
    .dock-cell { padding: 12px 6px; }
    .dock-cell span { font-size: 10.5px; }
    .material-deck { grid-template-columns: 1fr; }
    .swatch-palette { grid-template-columns: repeat(2, 1fr); }
    .preset-grid { grid-template-columns: 1fr; }
    .view-title { font-size: 22px; }
  }
</style>
</head>
<body>

<!-- Ambient Glow Blobs -->
<div class="ambient-glows">
  <div class="glow-blob blob-magenta"></div>
  <div class="glow-blob blob-violet"></div>
  <div class="glow-blob blob-mint"></div>
</div>

<div class="app-shell">
  <!-- Desktop Sidebar Navigation -->
  <aside class="sidebar">
    <div>
      <div class="brand-header">
        <div class="brand-logo">
          <!-- WindowLand Dynamic Island Brand Logo -->
          <svg viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="bg_b1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#16161D" />
                <stop offset="100%" stop-color="#07070A" />
              </linearGradient>
              <linearGradient id="rim_b1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.22" />
                <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.06" />
              </linearGradient>
            </defs>
            <rect x="32" y="32" width="448" height="448" rx="112" fill="url(#bg_b1)" stroke="url(#rim_b1)" stroke-width="4" />
            <rect x="108" y="196" width="296" height="120" rx="60" fill="#000000" stroke="#262630" stroke-width="4" />
            <circle cx="176" cy="256" r="18" fill="#34C759" />
            <rect x="248" y="236" width="14" height="40" rx="7" fill="#FFFFFF" />
            <rect x="278" y="220" width="14" height="72" rx="7" fill="#34C759" />
            <rect x="308" y="232" width="14" height="48" rx="7" fill="#FFFFFF" fill-opacity="0.7" />
          </svg>
        </div>
        <div class="brand-info">
          <span class="brand-title">WindowLand</span>
          <span class="brand-badge">Control Center</span>
        </div>
      </div>

      <nav class="nav-menu">
        <div class="nav-item active" onclick="switchTab('general')" data-tab="general">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
          <span>General Island</span>
        </div>
        <div class="nav-item" onclick="switchTab('appearance')" data-tab="appearance">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.563-2.512 5.563-5.563C21.999 6.375 17.437 2 12 2z"/></svg>
          <span>Appearance Glow</span>
        </div>
        <div class="nav-item" onclick="switchTab('docking')" data-tab="docking">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="18" rx="3"/><path d="M2 15h20"/></svg>
          <span>Position Docking</span>
        </div>
        <div class="nav-item" onclick="switchTab('tools')" data-tab="tools">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="3"/><path d="M12 18h.01"/></svg>
          <span>Tools & Companion</span>
        </div>
        <div class="nav-item" onclick="switchTab('diagnostics')" data-tab="diagnostics">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          <span>Diagnostics Simulator</span>
        </div>
        <div class="nav-item" onclick="switchTab('about')" data-tab="about">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span>About WindowLand</span>
        </div>
      </nav>
    </div>

    <!-- Active Island Badge -->
    <div class="sidebar-status">
      <div class="beacon-dot"></div>
      <span id="sidebarStatusText">Dynamic Island Active</span>
    </div>
  </aside>

  <!-- Mobile Top Bar with Scrolling Navigation -->
  <header class="mobile-header">
    <div class="mobile-brand-bar">
      <div style="display:flex; align-items:center; gap:8px;">
        <div class="brand-logo" style="width:30px; height:30px; border-radius:8px;">
          <svg viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="bg_b2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#16161D" />
                <stop offset="100%" stop-color="#07070A" />
              </linearGradient>
              <linearGradient id="rim_b2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.22" />
                <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.06" />
              </linearGradient>
            </defs>
            <rect x="32" y="32" width="448" height="448" rx="112" fill="url(#bg_b2)" stroke="url(#rim_b2)" stroke-width="4" />
            <rect x="108" y="196" width="296" height="120" rx="60" fill="#000000" stroke="#262630" stroke-width="4" />
            <circle cx="176" cy="256" r="18" fill="#34C759" />
            <rect x="248" y="236" width="14" height="40" rx="7" fill="#FFFFFF" />
            <rect x="278" y="220" width="14" height="72" rx="7" fill="#34C759" />
            <rect x="308" y="232" width="14" height="48" rx="7" fill="#FFFFFF" fill-opacity="0.7" />
          </svg>
        </div>
        <span style="font-family:var(--font-heading); font-weight:700; font-size:14px;">WindowLand</span>
      </div>
      <div class="sidebar-status" style="padding:4px 10px; font-size:10.5px;">
        <div class="beacon-dot" style="width:6px; height:6px;"></div>
        <span>Active</span>
      </div>
    </div>
    <div class="mobile-nav-scroll">
      <div class="mobile-tab-pill active" onclick="switchTab('general')" data-tab="general">General</div>
      <div class="mobile-tab-pill" onclick="switchTab('appearance')" data-tab="appearance">Appearance</div>
      <div class="mobile-tab-pill" onclick="switchTab('docking')" data-tab="docking">Docking</div>
      <div class="mobile-tab-pill" onclick="switchTab('tools')" data-tab="tools">Phone Sync</div>
      <div class="mobile-tab-pill" onclick="switchTab('diagnostics')" data-tab="diagnostics">Simulator</div>
      <div class="mobile-tab-pill" onclick="switchTab('about')" data-tab="about">About</div>
    </div>
  </header>

  <!-- Main View Area -->
  <main class="main-content">

    <!-- ── TAB 1: GENERAL ISLAND CONTROLS ──────────────── -->
    <section id="tab-general" class="tab-pane">
      <div class="view-header">
        <h1 class="view-title">General & Island Controls</h1>
        <p class="view-subtitle">Manage island behavior, startup preferences, and primary triggers.</p>
      </div>

      <div class="section-eyebrow">LIVE ISLAND PREVIEW</div>
      <div class="glass-card" style="padding:16px;">
        <div class="notch-preview-stage" onclick="triggerToggle()">
          <div class="preview-notch-pill">
            <div class="beacon-dot" style="background:#4EDEA3; box-shadow:0 0 8px #4EDEA3;"></div>
            <span style="font-weight:600; font-size:12.5px; letter-spacing:0.02em;" id="previewClock">19:30</span>
            <div class="preview-equalizer">
              <div class="eq-bar"></div>
              <div class="eq-bar"></div>
              <div class="eq-bar"></div>
              <div class="eq-bar"></div>
            </div>
          </div>
          <span style="position:absolute; bottom:8px; font-size:10.5px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;">Tap to Morph Island</span>
        </div>
      </div>

      <div class="section-eyebrow">QUICK ACTIONS</div>
      <div class="glass-card">
        <div class="setting-row">
          <div class="row-info">
            <span class="row-title">Expand / Collapse Island</span>
            <span class="row-desc">Instantly morph between compact notch and expanded music/multitasking view.</span>
          </div>
          <button class="btn-ghost" onclick="triggerToggle()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
            <span>Toggle</span>
          </button>
        </div>
        <div class="setting-row">
          <div class="row-info">
            <span class="row-title">Recenter to Top Bezel</span>
            <span class="row-desc">Instantly snap the island back to the center of your primary top screen bezel.</span>
          </div>
          <button class="btn-ghost" onclick="triggerDock('top')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
            <span>Recenter</span>
          </button>
        </div>
        <div class="setting-row">
          <div class="row-info">
            <span class="row-title">Open Desktop Settings Window</span>
            <span class="row-desc">Display the native Windows desktop settings application.</span>
          </div>
          <button class="btn-gradient" onclick="triggerOpenSettings()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            <span>Launch Settings</span>
          </button>
        </div>
      </div>

      <div class="section-eyebrow">ISLAND BEHAVIOR</div>
      <div class="glass-card">
        <div class="setting-row">
          <div class="row-info">
            <span class="row-title">Auto-Hide when Idle</span>
            <span class="row-desc">Collapses the island into an ultra-thin hidden tab when idle. Expands smoothly on hover.</span>
          </div>
          <div class="switch-toggle" id="toggleAutoHide" onclick="toggleSwitch('toggleAutoHide')"></div>
        </div>
        <div class="setting-row">
          <div class="row-info">
            <span class="row-title">24-Hour Clock Format</span>
            <span class="row-desc">Format used for the compact notch clock and schedule notifications.</span>
          </div>
          <div class="switch-toggle active" id="toggle24H" onclick="toggleSwitch('toggle24H')"></div>
        </div>
      </div>
    </section>

    <!-- ── TAB 2: APPEARANCE & THEME GLOW ─────────────── -->
    <section id="tab-appearance" class="tab-pane" style="display:none;">
      <div class="view-header">
        <h1 class="view-title">Appearance & Theme</h1>
        <p class="view-subtitle">Personalize surface materials, accent gradients, and ambient backlight glow.</p>
      </div>

      <div class="section-eyebrow">LIVE PREVIEW</div>
      <div class="glass-card" style="padding:18px;">
        <div class="notch-preview-stage" id="appearanceStage" style="height:140px;">
          <div class="preview-notch-pill" id="appearancePill" style="padding:8px 24px;">
            <div class="beacon-dot" style="background:#10B981; box-shadow:0 0 10px #10B981;"></div>
            <span style="font-weight:600; font-size:13px;" id="themeTrackTitle">WindowLand Dynamic Island</span>
            <div class="preview-equalizer">
              <div class="eq-bar" style="background:#FF43A8"></div>
              <div class="eq-bar" style="background:#7C03D3"></div>
              <div class="eq-bar" style="background:#4EDEA3"></div>
              <div class="eq-bar" style="background:#FF43A8"></div>
            </div>
          </div>
        </div>
      </div>

      <div class="section-eyebrow">SURFACE MATERIAL & MODE</div>
      <div class="glass-card">
        <div class="material-deck">
          <div class="material-tile active" id="mat-ambient" onclick="selectMaterial('ambient', this)">
            <div class="material-title">Ambient Reactive</div>
            <div class="material-sub">Dynamic Cover Art Glow</div>
          </div>
          <div class="material-tile" id="mat-obsidian" onclick="selectMaterial('solid', this, '#08080C')">
            <div class="material-title">OLED Obsidian</div>
            <div class="material-sub">Deep Black Glass</div>
          </div>
          <div class="material-tile" id="mat-titanium" onclick="selectMaterial('frosted', this, '#1E2028')">
            <div class="material-title">Frosted Titanium</div>
            <div class="material-sub">Dark Translucent Glass</div>
          </div>
        </div>
      </div>

      <div class="section-eyebrow">SOLID COLORS PALETTE</div>
      <div class="glass-card">
        <div class="swatch-palette">
          <div class="swatch-btn" style="background:#08080C;" onclick="selectColor('#08080C')">
            <div class="dot-preview" style="background:#08080C;"></div>
            <span>Obsidian Black</span>
          </div>
          <div class="swatch-btn" style="background:#0E1428;" onclick="selectColor('#0E1428')">
            <div class="dot-preview" style="background:#193060;"></div>
            <span>Midnight Blue</span>
          </div>
          <div class="swatch-btn" style="background:#1E2028;" onclick="selectColor('#1E2028')">
            <div class="dot-preview" style="background:#323644;"></div>
            <span>Space Gray</span>
          </div>
          <div class="swatch-btn" style="background:#0A2818;" onclick="selectColor('#0A2818')">
            <div class="dot-preview" style="background:#145232;"></div>
            <span>Deep Emerald</span>
          </div>
          <div class="swatch-btn" style="background:#240E38;" onclick="selectColor('#240E38')">
            <div class="dot-preview" style="background:#4A1C74;"></div>
            <span>Royal Amethyst</span>
          </div>
          <div class="swatch-btn" style="background:#2C303E;" onclick="selectColor('#2C303E')">
            <div class="dot-preview" style="background:#484F66;"></div>
            <span>Slate Titanium</span>
          </div>
        </div>

        <div style="display:flex; align-items:center; gap:12px; margin-top:10px;">
          <input type="color" id="customColorPicker" value="#08080C" onchange="selectColor(this.value)" style="width:40px; height:40px; border-radius:10px; border:1px solid var(--border-glass); background:none; cursor:pointer;">
          <span style="font-size:12.5px; color:var(--text-secondary);">Pick custom desktop color...</span>
        </div>
      </div>

      <div class="section-eyebrow">AMBIENT GLOW INTENSITY</div>
      <div class="glass-card">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;">
          <span style="font-weight:600; font-size:13px;">Glow Strength</span>
          <span style="font-weight:700; color:#FF43A8; font-size:13px;" id="glowValText">25%</span>
        </div>
        <input type="range" min="0" max="50" value="25" id="glowSlider" oninput="updateGlow(this.value)" style="width:100%; accent-color:#FF43A8; cursor:pointer;">
      </div>
    </section>

    <!-- ── TAB 3: POSITION & DOCKING MATRIX ────────────── -->
    <section id="tab-docking" class="tab-pane" style="display:none;">
      <div class="view-header">
        <h1 class="view-title">Position & Docking</h1>
        <p class="view-subtitle">Choose how the Dynamic Island anchors to your screen bezels, corners, or taskbar.</p>
      </div>

      <div class="section-eyebrow">SCREEN DOCKING SELECTOR</div>
      <div class="glass-card">
        <p style="font-size:12.5px; color:var(--text-secondary); margin-bottom:14px;">Select an anchor position on your desktop (the island will animate live to that edge):</p>
        <div class="docking-matrix">
          <div class="dock-cell" onclick="triggerDock('top-left', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="7 17 7 7 17 7"/><line x1="7" y1="7" x2="17" y2="17"/></svg>
            <span>Top-Left Corner</span>
          </div>
          <div class="dock-cell active" onclick="triggerDock('top', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
            <span>Top Bezel (Default)</span>
          </div>
          <div class="dock-cell" onclick="triggerDock('top-right', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 17 17 7 7 7"/><line x1="17" y1="7" x2="7" y2="17"/></svg>
            <span>Top-Right Corner</span>
          </div>

          <div class="dock-cell" onclick="triggerDock('left', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
            <span>Left Screen Edge</span>
          </div>
          <div class="dock-cell" onclick="triggerDock('floating', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>
            <span>Free Floating</span>
          </div>
          <div class="dock-cell" onclick="triggerDock('right', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            <span>Right Screen Edge</span>
          </div>

          <div class="dock-cell" onclick="triggerDock('bottom-left', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 17 7 17 7 7"/><line x1="7" y1="17" x2="17" y2="7"/></svg>
            <span>Bottom-Left Corner</span>
          </div>
          <div class="dock-cell" onclick="triggerDock('bottom', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            <span>Bottom Taskbar</span>
          </div>
          <div class="dock-cell" onclick="triggerDock('bottom-right', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="7 17 17 17 17 7"/><line x1="17" y1="17" x2="7" y2="7"/></svg>
            <span>Bottom-Right Corner</span>
          </div>
        </div>

        <button class="btn-ghost" style="width:100%;" onclick="triggerDock('top')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><polyline points="3 3 3 8 8 8"/></svg>
          <span>Snap to Screen Center / Default Top</span>
        </button>
      </div>
    </section>

    <!-- ── TAB 4: TOOLS & PHONE COMPANION ─────────────── -->
    <section id="tab-tools" class="tab-pane" style="display:none;">
      <div class="view-header">
        <h1 class="view-title">Tools & Phone Companion</h1>
        <p class="view-subtitle">Access mobile notifications pairing, wireless companion dashboard, and quick desktop shortcuts.</p>
      </div>

      <div class="section-eyebrow">PHONE COMPANION DASHBOARD</div>
      <div class="glass-card">
        <p style="font-size:12.5px; color:var(--text-secondary); margin-bottom:14px;">Connect your iPhone (iOS Shortcuts) or Android device to mirror live phone notifications, calls, and 2FA codes directly onto your Windows Dynamic Island.</p>
        <div style="background:var(--surface-well); border:1px solid var(--border-glass); border-radius:12px; padding:12px 16px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <div class="beacon-dot"></div>
            <code style="font-family:monospace; color:#4EDEA3; font-size:13px;" id="companionHostUrl">http://{HOST}</code>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn-ghost" onclick="copyLink()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <span>Copy Link</span>
            </button>
            <button class="btn-gradient" onclick="triggerWake()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
              <span>Wake Island</span>
            </button>
          </div>
        </div>
      </div>

      <div class="section-eyebrow">QUICK NOTIFICATION PRESETS</div>
      <div class="glass-card">
        <div class="preset-grid">
          <div class="preset-card" onclick="sendPreset('Messages', 'Alex Johnson', 'Hey! Let me know when you arrive.')">
            <div class="preset-icon" style="background:#2563EB;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <div class="preset-text">
              <span class="preset-name">iMessage</span>
              <span class="preset-sub">Alex Johnson</span>
            </div>
          </div>
          <div class="preset-card" onclick="sendPreset('WhatsApp', 'Sarah Miller', 'Meeting moved to 3:00 PM in Room B.')">
            <div class="preset-icon" style="background:#059669;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
            </div>
            <div class="preset-text">
              <span class="preset-name">WhatsApp</span>
              <span class="preset-sub">Sarah Miller</span>
            </div>
          </div>
          <div class="preset-card" onclick="sendPreset('Slack', 'David Chen', 'PR #6 approved by team lead.')">
            <div class="preset-icon" style="background:#7C3AED;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>
            </div>
            <div class="preset-text">
              <span class="preset-name">Slack</span>
              <span class="preset-sub">#engineering</span>
            </div>
          </div>
          <div class="preset-card" onclick="sendPreset('Phone Call', 'Mom (Mobile)', 'Incoming Call...')">
            <div class="preset-icon" style="background:#10B981;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
            </div>
            <div class="preset-text">
              <span class="preset-name">Incoming Call</span>
              <span class="preset-sub">Mom (Mobile)</span>
            </div>
          </div>
          <div class="preset-card" onclick="sendPreset('Calendar', '12:30 PM Standup', 'Sprint Architecture Review in 5 min.')">
            <div class="preset-icon" style="background:#D97706;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            </div>
            <div class="preset-text">
              <span class="preset-name">Calendar</span>
              <span class="preset-sub">Standup Alert</span>
            </div>
          </div>
          <div class="preset-card" onclick="sendPreset('Mail', 'Stripe Billing', 'Your WindowLand Pro invoice is ready.')">
            <div class="preset-icon" style="background:#DC2626;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
            </div>
            <div class="preset-text">
              <span class="preset-name">Email Receipt</span>
              <span class="preset-sub">Stripe Billing</span>
            </div>
          </div>
        </div>
      </div>

      <div class="section-eyebrow">CUSTOM NOTIFICATION COMPOSER</div>
      <div class="glass-card">
        <form onsubmit="handleCustomSend(event)">
          <div class="form-group">
            <label class="form-label">Application Name</label>
            <input type="text" class="form-input" id="notifApp" value="WhatsApp" placeholder="e.g. WhatsApp, Slack, Teams, Instagram" required>
          </div>
          <div class="form-group">
            <label class="form-label">Sender / Title</label>
            <input type="text" class="form-input" id="notifTitle" value="Sarah Jenkins" placeholder="e.g. John Doe, Verification Code, Meeting" required>
          </div>
          <div class="form-group">
            <label class="form-label">Notification Message</label>
            <textarea class="form-textarea" id="notifMsg" rows="2" placeholder="e.g. Your verification code is 482 910" required>Hey, can you review the latest pull request?</textarea>
          </div>
          <button type="submit" class="btn-gradient" style="width:100%; padding:12px;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            <span>Send to Windows Dynamic Island</span>
          </button>
        </form>
      </div>
    </section>

    <!-- ── TAB 5: DIAGNOSTICS & LIVE SIMULATOR ─────────── -->
    <section id="tab-diagnostics" class="tab-pane" style="display:none;">
      <div class="view-header">
        <h1 class="view-title">Diagnostics & Live Simulator</h1>
        <p class="view-subtitle">Test all Dynamic Island morph states, HUD overlays, accessory connection popups, and alerts.</p>
      </div>

      <div class="section-eyebrow">INTERACTIVE STATE SIMULATION DECK (9 STATES)</div>
      <div class="glass-card">
        <div class="deck-grid">

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#2563EB;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">Volume OSD HUD</span>
                <span class="deck-desc">Simulate liquid-glass volume slider overlay (72%)</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('osd')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#10B981;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">Incoming Phone Call</span>
                <span class="deck-desc">Simulate live incoming call card with Accept / Decline controls</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('call')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#0D9488;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-1.5 1.5L14 9l-1.5-1.5-1.5 1.5-1.5-1.5-1.5 1.5-1.5-1.5-1.5 1.5L2 15v7h7l7.5-7.5"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">Two-Factor OTP Code</span>
                <span class="deck-desc">Simulate 2FA verification code card with one-click copy button</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('otp')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#4F46E5;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">File Shelf Drag Tray</span>
                <span class="deck-desc">Simulate liquid drag-and-drop file stash tray</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('shelf')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#D97706;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">Download Hairline Progress</span>
                <span class="deck-desc">Simulate animated sub-2px progress line along bottom curve</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('download')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#7C3AED;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">Snipping Tool Toast</span>
                <span class="deck-desc">Simulate screenshot notification toast</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('snip_toast')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#0891B2;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">Calendar Event Toast</span>
                <span class="deck-desc">Simulate calendar reminder alert toast</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('cal_toast')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#DB2777;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 3a4 4 0 0 0-4 4v2a4 4 0 0 0 6.5 3.14L10 21"/><path d="M17 3a4 4 0 0 1 4 4v2a4 4 0 0 1-6.5 3.14L14 21"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">AirPods Pro Pairing Sheet</span>
                <span class="deck-desc">Simulate 3D wireless earphone accessory pairing card</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('airpods')">Simulate</button>
          </div>

          <div class="deck-item">
            <div class="deck-left">
              <div class="deck-icon-badge" style="background:#4338CA;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>
              </div>
              <div class="deck-info">
                <span class="deck-name">Over-Ear Headphones Pairing Sheet</span>
                <span class="deck-desc">Simulate Sony WH-1000XM5 wireless headphone card</span>
              </div>
            </div>
            <button class="btn-ghost" onclick="triggerSimulate('headphones')">Simulate</button>
          </div>

        </div>
      </div>
    </section>

    <!-- ── TAB 6: ABOUT WINDOWLAND ─────────────────────── -->
    <section id="tab-about" class="tab-pane" style="display:none;">
      <div class="view-header">
        <h1 class="view-title">About WindowLand</h1>
        <p class="view-subtitle">Product information, keyboard shortcuts, and application lifecycle controls.</p>
      </div>

      <div class="section-eyebrow">APPLICATION DETAILS</div>
      <div class="glass-card">
        <div style="display:flex; align-items:center; gap:16px;">
          <div class="brand-logo" style="width:52px; height:52px; border-radius:14px;">
            <svg viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="bg_b3" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#16161D" />
                  <stop offset="100%" stop-color="#07070A" />
                </linearGradient>
                <linearGradient id="rim_b3" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.22" />
                  <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.06" />
                </linearGradient>
              </defs>
              <rect x="32" y="32" width="448" height="448" rx="112" fill="url(#bg_b3)" stroke="url(#rim_b3)" stroke-width="4" />
              <rect x="108" y="196" width="296" height="120" rx="60" fill="#000000" stroke="#262630" stroke-width="4" />
              <circle cx="176" cy="256" r="18" fill="#34C759" />
              <rect x="248" y="236" width="14" height="40" rx="7" fill="#FFFFFF" />
              <rect x="278" y="220" width="14" height="72" rx="7" fill="#34C759" />
              <rect x="308" y="232" width="14" height="48" rx="7" fill="#FFFFFF" fill-opacity="0.7" />
            </svg>
          </div>
          <div>
            <div style="font-family:var(--font-heading); font-size:18px; font-weight:700;">WindowLand Dynamic Island</div>
            <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">Apple-grade hardware notch & liquid multitasking overlay for Windows 11 / 10.</div>
            <div style="font-size:11px; color:#FF43A8; font-weight:600; margin-top:4px;">Version 2.0.0 • Windows 15 Fluent Architecture</div>
          </div>
        </div>
      </div>

      <div class="section-eyebrow">KEYBOARD SHORTCUTS & GESTURES</div>
      <div class="glass-card">
        <div class="setting-row">
          <span style="background:rgba(255,255,255,0.08); border:1px solid var(--border-glass); padding:4px 10px; border-radius:6px; font-family:monospace; font-weight:600; font-size:12px;">Alt + Space</span>
          <span class="row-desc" style="font-size:12.5px;">Expand or Collapse Dynamic Island from any application</span>
        </div>
        <div class="setting-row">
          <span style="background:rgba(255,255,255,0.08); border:1px solid var(--border-glass); padding:4px 10px; border-radius:6px; font-family:monospace; font-weight:600; font-size:12px;">Right Click</span>
          <span class="row-desc" style="font-size:12.5px;">Open desktop Settings & Control Center application</span>
        </div>
        <div class="setting-row">
          <span style="background:rgba(255,255,255,0.08); border:1px solid var(--border-glass); padding:4px 10px; border-radius:6px; font-family:monospace; font-weight:600; font-size:12px;">Left Drag</span>
          <span class="row-desc" style="font-size:12.5px;">Drag island to reposition or snap to any screen edge</span>
        </div>
        <div class="setting-row">
          <span style="background:rgba(255,255,255,0.08); border:1px solid var(--border-glass); padding:4px 10px; border-radius:6px; font-family:monospace; font-weight:600; font-size:12px;">Mouse Hover</span>
          <span class="row-desc" style="font-size:12.5px;">Peek & reveal hidden notch when cursor reaches bezel edge</span>
        </div>
      </div>
    </section>

  </main>
</div>

<!-- Floating Feedback Toast -->
<div class="feedback-toast" id="toast">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
  <span id="toastMsg">Action delivered</span>
</div>

<script>
  // ── Tab Navigation ────────────────────────────────────
  function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(el => el.style.display = 'none');
    const target = document.getElementById('tab-' + tabId);
    if (target) target.style.display = 'block';

    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.getAttribute('data-tab') === tabId);
    });
    document.querySelectorAll('.mobile-tab-pill').forEach(el => {
      el.classList.toggle('active', el.getAttribute('data-tab') === tabId);
    });

    if (navigator.vibrate) navigator.vibrate(10);
  }

  // ── Toast Feedback ───────────────────────────────────
  let toastTimer = null;
  function showToast(msg) {
    const toast = document.getElementById('toast');
    document.getElementById('toastMsg').textContent = msg;
    toast.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 2400);
    if (navigator.vibrate) navigator.vibrate(14);
  }

  // ── REST API Triggers ────────────────────────────────
  async function triggerToggle() {
    try {
      await fetch('/api/toggle', { method: 'POST' });
      showToast('Toggled Island Expansion');
    } catch(e) {
      showToast('Sent toggle command');
    }
  }

  async function triggerWake() {
    try {
      await fetch('/api/wake', { method: 'POST' });
      showToast('Woke up Desktop Dynamic Island');
    } catch(e) {
      showToast('Wake signal sent');
    }
  }

  async function triggerOpenSettings() {
    try {
      await fetch('/api/open_settings', { method: 'POST' });
      showToast('Opening Desktop Settings');
    } catch(e) {
      showToast('Settings launch request sent');
    }
  }

  async function triggerDock(edge, el) {
    if (el) {
      document.querySelectorAll('.dock-cell').forEach(c => c.classList.remove('active'));
      el.classList.add('active');
    }
    try {
      await fetch('/api/dock?edge=' + encodeURIComponent(edge), { method: 'POST' });
      const name = edge.replace('-', ' ').toUpperCase();
      showToast('Docked to: ' + name);
    } catch(e) {
      showToast('Dock command sent: ' + edge);
    }
  }

  async function triggerSimulate(kind) {
    try {
      await fetch('/api/simulate?kind=' + encodeURIComponent(kind), { method: 'POST' });
      showToast('Simulating: ' + kind.toUpperCase());
    } catch(e) {
      showToast('Simulation command sent');
    }
  }

  async function selectMaterial(mode, el, color) {
    document.querySelectorAll('.material-tile').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    try {
      let url = '/api/theme?mode=' + encodeURIComponent(mode);
      if (color) url += '&color=' + encodeURIComponent(color);
      await fetch(url, { method: 'POST' });
      showToast('Material updated: ' + mode);
    } catch(e) {}
  }

  async function selectColor(color) {
    try {
      await fetch('/api/theme?mode=solid&color=' + encodeURIComponent(color), { method: 'POST' });
      showToast('Accent color updated');
      const pill = document.getElementById('appearancePill');
      if (pill) pill.style.borderColor = color;
    } catch(e) {}
  }

  async function updateGlow(val) {
    document.getElementById('glowValText').textContent = val + '%';
    const stage = document.getElementById('appearanceStage');
    if (stage) {
      const alpha = (val / 100).toFixed(2);
      stage.style.background = 'radial-gradient(circle at 50% 30%, rgba(255, 67, 168, ' + alpha + '), rgba(0, 0, 0, 0.6) 70%)';
    }
    try {
      const op = (val / 100).toFixed(2);
      await fetch('/api/theme?opacity=' + op, { method: 'POST' });
    } catch(e) {}
  }

  function toggleSwitch(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('active');
    showToast('Preference updated');
  }

  async function sendPreset(app, title, msg) {
    await sendNotificationPayload({ app, title, message: msg, phone: 'Mobile' });
  }

  async function handleCustomSend(e) {
    e.preventDefault();
    const app = document.getElementById('notifApp').value.trim();
    const title = document.getElementById('notifTitle').value.trim();
    const msg = document.getElementById('notifMsg').value.trim();
    await sendNotificationPayload({ app, title, message: msg, phone: 'Mobile' });
  }

  async function sendNotificationPayload(payload) {
    try {
      const res = await fetch('/api/notify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showToast('Notification sent to Dynamic Island!');
    } catch(err) {
      showToast('Delivery failed: Network error');
    }
  }

  function copyLink() {
    const url = document.getElementById('companionHostUrl').textContent.trim();
    navigator.clipboard.writeText(url).then(() => {
      showToast('Pairing link copied to clipboard!');
    }).catch(() => {
      showToast('Copied: ' + url);
    });
  }

  // Update clock in preview
  function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const el = document.getElementById('previewClock');
    if (el) el.textContent = `${h}:${m}`;
  }
  setInterval(updateClock, 1000);
  updateClock();
</script>
</body>
</html>
'''
