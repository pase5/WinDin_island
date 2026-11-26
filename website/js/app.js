/**
 * WinDin — Dynamic Island for Windows & Mobile Companion
 * Production Static Website Engine & GitHub Releases Integration
 */

// ── GitHub Repository Configuration ──────────────────────────────────────
const GITHUB_REPO = "pase5/WinDin";

document.addEventListener("DOMContentLoaded", () => {
  initClock();
  initSimulator();
  initBentoDocking();
  fetchGitHubReleases();
});

/* ── 1. Dual-Color Live 24h Clock ───────────────────────────────────────── */
function initClock() {
  const hhEl = document.getElementById("simClockHh");
  const mmEl = document.getElementById("simClockMm");

  function update() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    if (hhEl) hhEl.textContent = hh;
    if (mmEl) mmEl.textContent = mm;
  }

  update();
  setInterval(update, 1000);
}

/* ── 2. Interactive Web Dynamic Island Simulator ────────────────────────── */
function initSimulator() {
  const notch = document.getElementById("islandSimulator");
  const corona = document.getElementById("islandCoronaBloom");
  const stage = document.getElementById("desktopStage");
  const dragPill = document.getElementById("mockDragPill");

  const viewCompact = document.getElementById("viewCompact");
  const viewExpanded = document.getElementById("viewExpanded");
  const viewWindrop = document.getElementById("viewWindrop");

  const playBtn = document.getElementById("simPlayBtn");
  const equalizer = document.getElementById("simEqualizer");
  const scrubberProgress = document.getElementById("simScrubberProgress");
  const currentTimeEl = document.getElementById("simCurrentTime");

  const ringProg = document.getElementById("windropRingProg");
  const checkmark = document.getElementById("windropCheckmark");
  const dropSub = document.getElementById("windropSubtitle");

  let isPlaying = true;
  let currentState = "compact";
  let isTransferring = false;
  let scrubberInterval = null;
  let scrubberPercent = 42;

  // View Switcher Function
  function setSimulatorState(state) {
    if (isTransferring && state !== "windrop") return;
    currentState = state;

    notch.classList.remove("state-compact", "state-expanded", "state-windrop");
    notch.classList.add(`state-${state}`);

    if (viewCompact) viewCompact.style.display = state === "compact" ? "flex" : "none";
    if (viewExpanded) viewExpanded.style.display = state === "expanded" ? "flex" : "none";
    if (viewWindrop) viewWindrop.style.display = state === "windrop" ? "flex" : "none";
  }

  // Hover & Click Interactions
  notch.addEventListener("mouseenter", () => {
    if (currentState === "compact" && !isTransferring) {
      setSimulatorState("expanded");
    }
  });

  notch.addEventListener("mouseleave", () => {
    if (currentState === "expanded" && !isTransferring) {
      setSimulatorState("compact");
    }
  });

  notch.addEventListener("click", (e) => {
    // Avoid toggling when clicking play button or scrubber
    if (e.target.closest(".ctrl-btn") || e.target.closest(".scrubber-bar-track")) return;
    if (!isTransferring) {
      setSimulatorState(currentState === "compact" ? "expanded" : "compact");
    }
  });

  // Media Player Controls
  if (playBtn) {
    playBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      isPlaying = !isPlaying;

      if (isPlaying) {
        equalizer.classList.remove("paused");
        playBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" rx="1.5"></rect>
            <rect x="14" y="4" width="4" height="16" rx="1.5"></rect>
          </svg>`;
        startScrubber();
      } else {
        equalizer.classList.add("paused");
        playBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>`;
        stopScrubber();
      }
    });
  }

  function startScrubber() {
    stopScrubber();
    scrubberInterval = setInterval(() => {
      scrubberPercent = (scrubberPercent + 0.3) % 100;
      if (scrubberProgress) scrubberProgress.style.width = `${scrubberPercent}%`;
      const totalSec = Math.floor((scrubberPercent / 100) * 225);
      const m = Math.floor(totalSec / 60);
      const s = String(totalSec % 60).padStart(2, "0");
      if (currentTimeEl) currentTimeEl.textContent = `0${m}:${s}`;
    }, 400);
  }

  function stopScrubber() {
    if (scrubberInterval) clearInterval(scrubberInterval);
  }

  startScrubber();

  // ── Drag & Drop Win Drop Experience ─────────────────────────────────────
  if (dragPill) {
    dragPill.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", "screenshot_2026.png");
      e.dataTransfer.effectAllowed = "copy";
      if (corona) corona.classList.add("active");
    });

    dragPill.addEventListener("dragend", () => {
      if (!isTransferring) {
        if (corona) corona.classList.remove("active");
        setSimulatorState("compact");
      }
    });
  }

  if (stage) {
    stage.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      if (corona) corona.classList.add("active");
      if (!isTransferring && currentState !== "windrop") {
        setSimulatorState("windrop");
        if (dropSub) dropSub.textContent = "Drop to Send";
        if (checkmark) checkmark.classList.remove("show");
        if (ringProg) ringProg.style.strokeDashoffset = "75.4";
      }
    });

    stage.addEventListener("dragleave", (e) => {
      if (!stage.contains(e.relatedTarget) && !isTransferring) {
        if (corona) corona.classList.remove("active");
        setSimulatorState("compact");
      }
    });

    stage.addEventListener("drop", (e) => {
      e.preventDefault();
      triggerWinDropTransfer("screenshot_2026.png");
    });
  }

  // Also support clicking the drag pill directly for mobile/touch users
  if (dragPill) {
    dragPill.addEventListener("click", () => {
      if (!isTransferring) {
        triggerWinDropTransfer("screenshot_2026.png");
      }
    });
  }

  function triggerWinDropTransfer(filename) {
    if (isTransferring) return;
    isTransferring = true;
    setSimulatorState("windrop");

    if (corona) corona.classList.add("active");
    if (checkmark) checkmark.classList.remove("show");

    let progress = 0;
    const totalCircumference = 75.4; // 2 * PI * r (r = 12)

    const interval = setInterval(() => {
      progress += 4;
      const offset = totalCircumference - (progress / 100) * totalCircumference;
      if (ringProg) ringProg.style.strokeDashoffset = offset;
      if (dropSub) dropSub.textContent = `Sending ${filename} • ${progress}%`;

      if (progress >= 100) {
        clearInterval(interval);
        if (dropSub) dropSub.textContent = `Sent ${filename}`;
        if (ringProg) ringProg.style.strokeDashoffset = "0";
        if (checkmark) checkmark.classList.add("show");
        if (corona) corona.classList.remove("active");

        // Retract back after 1.4s hold
        setTimeout(() => {
          isTransferring = false;
          if (checkmark) checkmark.classList.remove("show");
          setSimulatorState("compact");
        }, 1400);
      }
    }, 45);
  }
}

/* ── 3. Bento 9-Edge Docking Interactive Preview ────────────────────────── */
function initBentoDocking() {
  const pills = document.querySelectorAll(".dock-target-pill");
  if (!pills || pills.length === 0) return;

  pills.forEach((pill) => {
    pill.addEventListener("mouseenter", () => {
      pills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
    });
  });
}

/* ── 4. Automatic GitHub Releases Hub ───────────────────────────────────── */
async function fetchGitHubReleases() {
  const CACHE_KEY = "windin_releases_cache";
  const CACHE_TIME_KEY = "windin_releases_cache_time";
  const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes cache

  // Default fallback payload in case of rate limits or offline
  const fallbackRelease = {
    tag_name: "v2.0.0",
    published_at: new Date().toISOString(),
    name: "WinDin 2.0.0 Liquid Obsidian Release",
    body: `### What's New in WinDin v2.0
- **Win Drop Proximity**: Seamless file and photo beam between Windows 11 and Android via zero-cloud local WebSocket.
- **Top-Edge Light Corona**: High-performance radiant iridescent glow bloom during active dragging.
- **Pure Vector Obsidian Aesthetics**: Zero emojis; anti-aliased subpixel rendering across all 9 screen edge docking geometries.
- **Hardware Audio Loopback**: 26-band sub-millisecond FFT visualizer powered by WASAPI loopback.`,
    assets: [
      {
        name: "DynamicIsland.exe",
        size: 52649804, // 50.2 MB
        browser_download_url: `https://github.com/${GITHUB_REPO}/releases/latest/download/DynamicIsland.exe`
      },
      {
        name: "WinDinCompanion.apk",
        size: 41413083, // 39.5 MB
        browser_download_url: `https://github.com/${GITHUB_REPO}/releases/latest/download/WinDin.apk`
      }
    ]
  };

  try {
    const cachedData = localStorage.getItem(CACHE_KEY);
    const cachedTime = localStorage.getItem(CACHE_TIME_KEY);

    if (cachedData && cachedTime && (Date.now() - parseInt(cachedTime, 10) < CACHE_TTL_MS)) {
      applyReleaseData(JSON.parse(cachedData));
      return;
    }

    const apiUrl = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;
    const res = await fetch(apiUrl, { headers: { "Accept": "application/vnd.github.v3+json" } });

    if (res.ok) {
      const data = await res.json();
      localStorage.setItem(CACHE_KEY, JSON.stringify(data));
      localStorage.setItem(CACHE_TIME_KEY, String(Date.now()));
      applyReleaseData(data);
    } else {
      // If 404 (no releases published yet), try fetching all releases
      const allRes = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/releases`);
      if (allRes.ok) {
        const allData = await allRes.json();
        if (allData && allData.length > 0) {
          localStorage.setItem(CACHE_KEY, JSON.stringify(allData[0]));
          localStorage.setItem(CACHE_TIME_KEY, String(Date.now()));
          applyReleaseData(allData[0]);
          return;
        }
      }
      applyReleaseData(fallbackRelease);
    }
  } catch (err) {
    console.warn("GitHub API error, using verified fallback release metadata:", err);
    applyReleaseData(fallbackRelease);
  }
}

function applyReleaseData(release) {
  if (!release) return;

  const version = release.tag_name || "v2.0.0";
  const releaseDate = release.published_at
    ? new Date(release.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : "November 2026";

  // Match Windows exe asset
  let winAsset = (release.assets || []).find((a) => a.name.toLowerCase().endsWith(".exe"));
  if (!winAsset) {
    winAsset = {
      name: "DynamicIsland.exe",
      size: 52649804,
      browser_download_url: `https://github.com/${GITHUB_REPO}/releases/latest/download/DynamicIsland.exe`
    };
  }

  // Match Android apk asset
  let apkAsset = (release.assets || []).find((a) => a.name.toLowerCase().endsWith(".apk"));
  if (!apkAsset) {
    apkAsset = {
      name: "WinDin.apk",
      size: 41413083,
      browser_download_url: `https://github.com/${GITHUB_REPO}/releases/latest/download/WinDin.apk`
    };
  }

  const winSizeMb = (winAsset.size / (1024 * 1024)).toFixed(1) + " MB";
  const apkSizeMb = (apkAsset.size / (1024 * 1024)).toFixed(1) + " MB";

  // Populate Windows Card
  const winVerEl = document.getElementById("winVersionTag");
  const winSizeEl = document.getElementById("winFileSize");
  const winDateEl = document.getElementById("winReleaseDate");
  const winBtn = document.getElementById("winDownloadBtn");

  if (winVerEl) winVerEl.textContent = version;
  if (winSizeEl) winSizeEl.textContent = winSizeMb;
  if (winDateEl) winDateEl.textContent = releaseDate;
  if (winBtn) winBtn.href = winAsset.browser_download_url;

  // Populate Android Card
  const apkVerEl = document.getElementById("apkVersionTag");
  const apkSizeEl = document.getElementById("apkFileSize");
  const apkDateEl = document.getElementById("apkReleaseDate");
  const apkBtn = document.getElementById("apkDownloadBtn");

  if (apkVerEl) apkVerEl.textContent = version;
  if (apkSizeEl) apkSizeEl.textContent = apkSizeMb;
  if (apkDateEl) apkDateEl.textContent = releaseDate;
  if (apkBtn) apkBtn.href = apkAsset.browser_download_url;

  // Populate Auto-Updating Changelog
  const changelogBody = document.getElementById("changelogContent");
  const changelogVer = document.getElementById("changelogVersion");

  if (changelogVer) changelogVer.textContent = `${version} • ${releaseDate}`;
  if (changelogBody && release.body) {
    changelogBody.innerHTML = formatMarkdown(release.body);
  }
}

// Lightweight Markdown Formatter for Changelog
function formatMarkdown(md) {
  if (!md) return "<p>Latest performance improvements, Win Drop continuity updates, and bug fixes.</p>";

  const lines = md.split("\n");
  let html = "";
  let inList = false;

  for (let line of lines) {
    line = line.trim();
    if (!line) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      continue;
    }

    if (line.startsWith("### ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h4 style="font-size:0.95rem; font-weight:700; color:#FFFFFF; margin-top:1rem; margin-bottom:0.4rem;">${escapeHtml(line.slice(4))}</h4>`;
    } else if (line.startsWith("## ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h3 style="font-size:1.05rem; font-weight:700; color:#FFFFFF; margin-top:1.2rem; margin-bottom:0.5rem;">${escapeHtml(line.slice(3))}</h3>`;
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      if (!inList) {
        html += '<ul style="padding-left:1.2rem; margin-bottom:0.8rem;">';
        inList = true;
      }
      const itemContent = parseInlineStyles(line.slice(2));
      html += `<li style="margin-bottom:0.35rem; color:rgba(255,255,255,0.78);">${itemContent}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<p style="margin-bottom:0.6rem; color:rgba(255,255,255,0.78);">${parseInlineStyles(line)}</p>`;
    }
  }

  if (inList) html += "</ul>";
  return html;
}

function parseInlineStyles(str) {
  return escapeHtml(str)
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#FFFFFF;">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="font-family:var(--font-mono); background:rgba(255,255,255,0.08); padding:0.1rem 0.35rem; border-radius:4px; font-size:0.82rem; color:#A3E635;">$1</code>');
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
