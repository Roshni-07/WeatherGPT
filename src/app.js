// =====================================================================
// WeatherGPT — Personal Weather Intelligence for India
// Living sky canvas, multi-persona advisory, all-India alerts,
// Aaj Tak news-style weather map, and Google Stocks-style trends scrubber.
// =====================================================================

function startWeatherApp() {
  const cfg = window.WEATHERGPT_CONFIG || {};
  const baseURL = cfg.BACKEND_URL || "http://localhost:8000";

  function getApiClient() {
    if (window.apiService) return window.apiService;
    if (typeof WeatherAPI !== "undefined") {
      window.apiService = new WeatherAPI();
      return window.apiService;
    }
    return {
      async sendQuery({ text, persona = "general", lat, lon, language = "en" }) {
        try {
          const resp = await fetch(`${baseURL}/query/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, user_id: "demo-user", language, persona, lat, lon })
          });
          return await resp.json();
        } catch (e) {
          return { answer: "Current conditions are steady with partly cloudy skies and comfortable temperatures.", confidence: "medium" };
        }
      },
      async getBriefing(lat, lon, name, persona, am = 9, pm = 18) {
        try {
          const q = new URLSearchParams({ lat, lon, persona, am, pm });
          if (name) q.append("name", name);
          const resp = await fetch(`${baseURL}/weather/briefing?${q.toString()}`);
          return await resp.json();
        } catch (e) { return null; }
      },
      async getPulse(lat, lon, name, persona, am = 9, pm = 18) {
        try {
          const q = new URLSearchParams({ lat, lon, persona, am, pm });
          if (name) q.append("name", name);
          const resp = await fetch(`${baseURL}/weather/pulse?${q.toString()}`);
          return await resp.json();
        } catch (e) { return null; }
      },
      async getSeries(lat, lon, name, range = "3d") {
        try {
          const q = new URLSearchParams({ lat, lon, range });
          if (name) q.append("name", name);
          const resp = await fetch(`${baseURL}/weather/series?${q.toString()}`);
          return await resp.json();
        } catch (e) { return null; }
      },
      async getAdvisoryFull(persona, lat, lon, name, am = 9, pm = 18) {
        try {
          const q = new URLSearchParams({ persona, lat, lon, am, pm });
          if (name) q.append("name", name);
          const resp = await fetch(`${baseURL}/advisory?${q.toString()}`);
          return await resp.json();
        } catch (e) { return null; }
      },
      async getPersonas() {
        try {
          const resp = await fetch(`${baseURL}/advisory/personas`);
          const d = await resp.json();
          return d.personas || [];
        } catch (e) { return []; }
      },
      async getAllPlaces() {
        try {
          const resp = await fetch(`${baseURL}/places/all`);
          const d = await resp.json();
          return d.results || [];
        } catch (e) { return []; }
      },
      async suggestPlaces(q) {
        try {
          const resp = await fetch(`${baseURL}/places/suggest?q=${encodeURIComponent(q)}&limit=15`);
          const d = await resp.json();
          return d.results || [];
        } catch (e) { return []; }
      },
      async reverseGeocode(lat, lon) {
        try {
          const resp = await fetch(`${baseURL}/places/reverse?lat=${lat}&lon=${lon}`);
          return await resp.json();
        } catch (e) { return null; }
      },
      async getIndiaAlerts(lat, lon) {
        try {
          const q = new URLSearchParams();
          if (lat != null && lon != null) { q.append("lat", lat); q.append("lon", lon); }
          const resp = await fetch(`${baseURL}/alerts/india?${q.toString()}`);
          return await resp.json();
        } catch (e) { return { alerts: [], total: 0, near_count: 0 }; }
      },
      async getMapPoints() {
        try {
          const resp = await fetch(`${baseURL}/map/points`);
          const d = await resp.json();
          return d.points || [];
        } catch (e) { return []; }
      },
      async analyzeSky(imageB64, mime, lat, lon, name) {
        try {
          const resp = await fetch(`${baseURL}/sky/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image_b64: imageB64, mime, lat, lon, name })
          });
          return await resp.json();
        } catch (e) { return { error: e.message }; }
      },
      async verifyGoogleLogin(idToken) {
        try {
          const resp = await fetch(`${baseURL}/auth/google`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: idToken })
          });
          return await resp.json();
        } catch (e) { return null; }
      }
    };
  }

  const api = getApiClient();

  // ---- App State ----------------------------------------------------
  let currentLocation = cfg.DEFAULT_LOCATION || { name: "Bengaluru", lat: 12.9716, lon: 77.5946 };
  let currentTheme = "clear-day";
  let currentPersona = "office"; // Office worker default
  let currentTab = "chat";
  let currentTrendMetric = "temp";
  let allPlacesList = [];
  let mapInstance = null;
  let alertsMapInstance = null;
  let currentBriefingData = null;
  let currentSeriesData = null;
  let currentAlertsData = null;
  let mapPointsData = null;
  let weatherPulseTimer = null;
  let routineAm = 9;
  let routinePm = 18;

  // ===================================================================
  // 1. Living Sky Canvas (Requirement 4: Background keeps changing)
  // ===================================================================
  const skyCanvas = document.getElementById("sky");
  const skyCtx = skyCanvas?.getContext("2d");
  let skyW = 0, skyH = 0;
  let rainParticles = [];
  let cloudPuffs = [];
  let starField = [];
  let lightningAlpha = 0;
  let nextLightningTime = 0;
  let shootingStar = null;

  function resizeSkyCanvas() {
    if (!skyCanvas) return;
    skyW = skyCanvas.width = window.innerWidth;
    skyH = skyCanvas.height = window.innerHeight;
    initSkyEntities();
  }

  function initSkyEntities() {
    // Rain
    rainParticles = Array.from({ length: 60 }, () => ({
      x: Math.random() * skyW,
      y: Math.random() * skyH,
      len: Math.random() * 22 + 12,
      speed: Math.random() * 14 + 10,
      opacity: Math.random() * 0.4 + 0.3
    }));

    // Soft drifting cumulus clouds
    cloudPuffs = Array.from({ length: 7 }, () => ({
      x: Math.random() * skyW,
      y: Math.random() * (skyH * 0.55),
      r: Math.random() * 80 + 50,
      vx: Math.random() * 0.18 + 0.06,
      opacity: Math.random() * 0.07 + 0.03
    }));

    // Twinkling stars for night
    starField = Array.from({ length: 80 }, () => ({
      x: Math.random() * skyW,
      y: Math.random() * skyH,
      r: Math.random() * 1.6 + 0.6,
      twinkleSpeed: Math.random() * 0.003 + 0.001,
      phase: Math.random() * Math.PI * 2
    }));
  }

  function renderSky(t) {
    if (!skyCtx) {
      requestAnimationFrame(renderSky);
      return;
    }

    skyCtx.clearRect(0, 0, skyW, skyH);

    // Dynamic procedural background by weather theme
    if (currentTheme === "night") {
      // Starfield
      for (const s of starField) {
        const tw = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * s.twinkleSpeed + s.phase));
        skyCtx.beginPath();
        skyCtx.fillStyle = `rgba(220, 230, 255, ${tw})`;
        skyCtx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        skyCtx.fill();
      }

      // Moon glow
      const moonX = skyW * 0.82;
      const moonY = skyH * 0.16;
      const moonGlow = skyCtx.createRadialGradient(moonX, moonY, 10, moonX, moonY, 110);
      moonGlow.addColorStop(0, "rgba(220, 230, 255, 0.22)");
      moonGlow.addColorStop(1, "rgba(220, 230, 255, 0)");
      skyCtx.fillStyle = moonGlow;
      skyCtx.beginPath();
      skyCtx.arc(moonX, moonY, 110, 0, Math.PI * 2);
      skyCtx.fill();

      // Periodic shooting star
      if (!shootingStar && Math.random() < 0.003) {
        shootingStar = {
          x: Math.random() * skyW * 0.7,
          y: Math.random() * skyH * 0.3,
          vx: Math.random() * 8 + 8,
          vy: Math.random() * 4 + 3,
          len: 60,
          life: 1.0
        };
      }
      if (shootingStar) {
        skyCtx.strokeStyle = `rgba(255, 255, 255, ${shootingStar.life * 0.8})`;
        skyCtx.lineWidth = 1.5;
        skyCtx.beginPath();
        skyCtx.moveTo(shootingStar.x, shootingStar.y);
        skyCtx.lineTo(shootingStar.x - shootingStar.vx * 4, shootingStar.y - shootingStar.vy * 4);
        skyCtx.stroke();
        shootingStar.x += shootingStar.vx;
        shootingStar.y += shootingStar.vy;
        shootingStar.life -= 0.035;
        if (shootingStar.life <= 0) shootingStar = null;
      }
    } else if (currentTheme === "rain" || currentTheme === "storm") {
      // Lightning flash in storm mode
      if (currentTheme === "storm") {
        if (t > nextLightningTime) {
          lightningAlpha = 0.55;
          nextLightningTime = t + Math.random() * 7000 + 4000;
        }
        if (lightningAlpha > 0) {
          skyCtx.fillStyle = `rgba(230, 240, 255, ${lightningAlpha})`;
          skyCtx.fillRect(0, 0, skyW, skyH);
          lightningAlpha -= 0.04;
        }
      }

      // Rain particles
      const rainColor = currentTheme === "storm" ? "rgba(180, 210, 230, 0.55)" : "rgba(110, 200, 230, 0.45)";
      skyCtx.strokeStyle = rainColor;
      skyCtx.lineWidth = 1.4;
      for (const p of rainParticles) {
        skyCtx.beginPath();
        skyCtx.moveTo(p.x, p.y);
        skyCtx.lineTo(p.x - 2, p.y + p.len);
        skyCtx.stroke();

        p.y += p.speed;
        p.x -= 1.2; // angled fall
        if (p.y > skyH) {
          p.y = -20;
          p.x = Math.random() * (skyW + 100);
        }
      }
    } else {
      // Clear-day / overcast: Sun radiance and drifting clouds
      const sunX = skyW * 0.78;
      const sunY = skyH * 0.14;
      const sunGlow = skyCtx.createRadialGradient(sunX, sunY, 15, sunX, sunY, 180);
      sunGlow.addColorStop(0, "rgba(255, 200, 80, 0.18)");
      sunGlow.addColorStop(0.5, "rgba(255, 230, 140, 0.05)");
      sunGlow.addColorStop(1, "rgba(255, 255, 255, 0)");
      skyCtx.fillStyle = sunGlow;
      skyCtx.beginPath();
      skyCtx.arc(sunX, sunY, 180, 0, Math.PI * 2);
      skyCtx.fill();

      // Soft clouds
      for (const c of cloudPuffs) {
        skyCtx.fillStyle = `rgba(255, 255, 255, ${c.opacity})`;
        skyCtx.beginPath();
        skyCtx.arc(c.x, c.y, c.r, 0, Math.PI * 2);
        skyCtx.fill();
        c.x += c.vx;
        if (c.x - c.r > skyW) c.x = -c.r;
      }
    }

    requestAnimationFrame(renderSky);
  }

  function setTheme(theme) {
    currentTheme = theme || "clear-day";
    document.documentElement.setAttribute("data-theme", currentTheme);
  }

  window.addEventListener("resize", resizeSkyCanvas);
  resizeSkyCanvas();
  requestAnimationFrame(renderSky);

  // Triple-click brand for dynamic sky demo
  let brandClicks = 0;
  let brandClickTimer = null;
  document.getElementById("brand")?.addEventListener("click", () => {
    brandClicks++;
    clearTimeout(brandClickTimer);
    brandClickTimer = setTimeout(() => { brandClicks = 0; }, 600);
    if (brandClicks >= 3) {
      brandClicks = 0;
      const themes = ["clear-day", "rain", "storm", "night"];
      const nextIdx = (themes.indexOf(currentTheme) + 1) % themes.length;
      setTheme(themes[nextIdx]);
      showToast(`Sky mode: ${themes[nextIdx]}`);
    }
  });

  // ===================================================================
  // 2. City Search & Alphabetical Suggestions (Requirement 1 & 3)
  // ===================================================================
  const locBtn = document.getElementById("loc-btn");
  const locSheet = document.getElementById("loc-sheet");
  const locClose = document.getElementById("loc-close");
  const locInput = document.getElementById("loc-input");
  const locList = document.getElementById("loc-list");
  const useGpsBtn = document.getElementById("use-gps");
  const locNameEl = document.getElementById("loc-name");
  const locSubEl = document.getElementById("loc-sub");

  function updateLocbarDisplay() {
    if (locNameEl) locNameEl.textContent = currentLocation.name;
    if (locSubEl) {
      const statePart = currentLocation.state ? `${currentLocation.state} • ` : "";
      locSubEl.textContent = `${statePart}Live weather`;
    }
  }

  async function loadAllPlaces() {
    allPlacesList = await api.getAllPlaces();
    if (!allPlacesList || !allPlacesList.length) {
      // Fallback major Indian cities if backend not populated
      allPlacesList = [
        { name: "Agra", state: "Uttar Pradesh", lat: 27.18, lon: 78.01 },
        { name: "Ahmedabad", state: "Gujarat", lat: 23.02, lon: 72.57 },
        { name: "Amritsar", state: "Punjab", lat: 31.63, lon: 74.87 },
        { name: "Bengaluru", state: "Karnataka", lat: 12.97, lon: 77.59 },
        { name: "Bhopal", state: "Madhya Pradesh", lat: 23.25, lon: 77.41 },
        { name: "Bhubaneswar", state: "Odisha", lat: 20.30, lon: 85.82 },
        { name: "Chandigarh", state: "Punjab", lat: 30.73, lon: 76.78 },
        { name: "Chennai", state: "Tamil Nadu", lat: 13.08, lon: 80.27 },
        { name: "Coimbatore", state: "Tamil Nadu", lat: 11.01, lon: 76.96 },
        { name: "Dehradun", state: "Uttarakhand", lat: 30.32, lon: 78.03 },
        { name: "Delhi", state: "Delhi", lat: 28.61, lon: 77.21 },
        { name: "Guwahati", state: "Assam", lat: 26.14, lon: 91.74 },
        { name: "Hyderabad", state: "Telangana", lat: 17.38, lon: 78.48 },
        { name: "Indore", state: "Madhya Pradesh", lat: 22.72, lon: 75.86 },
        { name: "Jaipur", state: "Rajasthan", lat: 26.91, lon: 75.79 },
        { name: "Jammu", state: "Jammu and Kashmir", lat: 32.73, lon: 74.87 },
        { name: "Kochi", state: "Kerala", lat: 9.93, lon: 76.27 },
        { name: "Kolkata", state: "West Bengal", lat: 22.57, lon: 88.36 },
        { name: "Lucknow", state: "Uttar Pradesh", lat: 26.85, lon: 80.95 },
        { name: "Madurai", state: "Tamil Nadu", lat: 9.93, lon: 78.12 },
        { name: "Mangaluru", state: "Karnataka", lat: 12.91, lon: 74.86 },
        { name: "Mumbai", state: "Maharashtra", lat: 19.08, lon: 72.88 },
        { name: "Nagpur", state: "Maharashtra", lat: 21.15, lon: 79.08 },
        { name: "Patna", state: "Bihar", lat: 25.61, lon: 85.14 },
        { name: "Pune", state: "Maharashtra", lat: 18.52, lon: 73.86 },
        { name: "Raipur", state: "Chhattisgarh", lat: 21.25, lon: 81.63 },
        { name: "Ranchi", state: "Jharkhand", lat: 23.34, lon: 85.31 },
        { name: "Shillong", state: "Meghalaya", lat: 25.58, lon: 91.89 },
        { name: "Shimla", state: "Himachal Pradesh", lat: 31.10, lon: 77.17 },
        { name: "Srinagar", state: "Jammu and Kashmir", lat: 34.08, lon: 74.80 },
        { name: "Surat", state: "Gujarat", lat: 21.17, lon: 72.83 },
        { name: "Thiruvananthapuram", state: "Kerala", lat: 8.52, lon: 76.94 },
        { name: "Varanasi", state: "Uttar Pradesh", lat: 25.32, lon: 83.01 },
        { name: "Visakhapatnam", state: "Andhra Pradesh", lat: 17.69, lon: 83.22 }
      ];
    }
  }

  function renderAlphabeticalList(places, query = "") {
    if (!locList) return;
    if (!places || !places.length) {
      locList.innerHTML = `<div class="empty"><span class="em">🔍</span>No places found for "${escapeHtml(query)}"</div>`;
      return;
    }

    // Group sorted by first letter
    const groups = {};
    for (const p of places) {
      const firstLetter = (p.name[0] || "#").toUpperCase();
      if (!groups[firstLetter]) groups[firstLetter] = [];
      groups[firstLetter].push(p);
    }

    const sortedLetters = Object.keys(groups).sort();
    let html = "";

    for (const letter of sortedLetters) {
      html += `<div class="letter">${letter}</div>`;
      for (const p of groups[letter]) {
        const highlightedName = highlightMatch(p.name, query);
        html += `
          <button type="button" class="place" data-name="${escapeHtml(p.name)}" data-state="${escapeHtml(p.state || '')}" data-lat="${p.lat}" data-lon="${p.lon}">
            <div>
              <b>${highlightedName}</b>
              <small>${escapeHtml(p.state || 'India')}</small>
            </div>
            <span class="tag">📍</span>
          </button>
        `;
      }
    }

    locList.innerHTML = html;

    // Attach click listener
    locList.querySelectorAll(".place").forEach(btn => {
      btn.addEventListener("click", () => {
        const name = btn.getAttribute("data-name");
        const state = btn.getAttribute("data-state");
        const lat = parseFloat(btn.getAttribute("data-lat"));
        const lon = parseFloat(btn.getAttribute("data-lon"));
        selectCity({ name, state, lat, lon });
      });
    });
  }

  function highlightMatch(text, query) {
    if (!query) return escapeHtml(text);
    const q = query.trim().toLowerCase();
    const idx = text.toLowerCase().indexOf(q);
    if (idx === -1) return escapeHtml(text);
    return escapeHtml(text.slice(0, idx)) +
      `<em>${escapeHtml(text.slice(idx, idx + q.length))}</em>` +
      escapeHtml(text.slice(idx + q.length));
  }

  let searchTimeout = null;
  locInput?.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    const q = locInput.value.trim();
    if (!q) {
      renderAlphabeticalList(allPlacesList);
      return;
    }

    // Instant local filtering
    const ql = q.toLowerCase();
    const filtered = allPlacesList.filter(p =>
      p.name.toLowerCase().includes(ql) || (p.state && p.state.toLowerCase().includes(ql))
    );

    renderAlphabeticalList(filtered, q);

    // If query is 3+ characters and local results are sparse, search backend geocoding
    if (q.length >= 3) {
      searchTimeout = setTimeout(async () => {
        const remoteResults = await api.suggestPlaces(q);
        if (remoteResults && remoteResults.length) {
          // Merge unique
          const combined = [...filtered];
          for (const r of remoteResults) {
            if (!combined.some(c => Math.abs(c.lat - r.lat) < 0.1 && Math.abs(c.lon - r.lon) < 0.1)) {
              combined.push(r);
            }
          }
          renderAlphabeticalList(combined, q);
        }
      }, 350);
    }
  });

  function openLocationSheet() {
    if (locSheet) {
      locSheet.hidden = false;
      if (locInput) {
        locInput.value = "";
        locInput.focus();
      }
      renderAlphabeticalList(allPlacesList);
    }
  }

  function closeLocationSheet() {
    if (locSheet) locSheet.hidden = true;
  }

  locBtn?.addEventListener("click", openLocationSheet);
  locClose?.addEventListener("click", closeLocationSheet);

  useGpsBtn?.addEventListener("click", () => {
    if (!navigator.geolocation) {
      showToast("GPS is not available on this device");
      return;
    }
    showToast("Detecting GPS coordinates…");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        const rev = await api.reverseGeocode(lat, lon);
        selectCity({
          name: rev?.name || "My Location",
          state: rev?.state || "",
          lat,
          lon
        });
        showToast(`Located: ${rev?.name || 'Your position'}`);
      },
      (err) => {
        showToast("GPS access was denied or timed out");
      },
      { timeout: 8000 }
    );
  });

  async function selectCity(city) {
    currentLocation = city;
    closeLocationSheet();
    updateLocbarDisplay();
    showToast(`Switched location to ${city.name}`);

    // Refresh active data
    await refreshActiveView();
  }

  // ===================================================================
  // 3. Navigation / Tabbar (Requirement 11: 5 tabs, Voice in Chat)
  // ===================================================================
  const tabButtons = document.querySelectorAll(".tabbar .tab");
  const views = {
    chat: document.getElementById("view-chat"),
    advisory: document.getElementById("view-advisory"),
    alerts: document.getElementById("view-alerts"),
    map: document.getElementById("view-map"),
    trends: document.getElementById("view-trends")
  };

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-tab");
      switchTab(tab);
    });
  });

  function switchTab(tab) {
    if (!views[tab]) return;
    currentTab = tab;

    tabButtons.forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-tab") === tab);
    });

    Object.keys(views).forEach(key => {
      views[key]?.classList.toggle("active", key === tab);
    });

    if (tab === "chat") renderChatBriefing();
    if (tab === "advisory") renderAdvisoryView();
    if (tab === "alerts") renderAlertsView();
    if (tab === "map") renderMapView();
    if (tab === "trends") renderTrendsView();
  }

  // ===================================================================
  // 4. Chat View & Real-Time Layman Briefing (Requirement 2 & 5)
  // ===================================================================
  const streamEl = document.getElementById("stream");
  const chipsEl = document.getElementById("chips");
  const composerForm = document.getElementById("composer");
  const askInput = document.getElementById("ask");

  async function renderChatBriefing() {
    if (!streamEl) return;

    // Show initial skeleton if first time loading
    if (!currentBriefingData) {
      streamEl.innerHTML = `
        <div class="card skeleton" style="height: 180px;"></div>
        <div class="card skeleton" style="height: 100px; margin-top: 12px;"></div>
      `;
    }

    const data = await api.getBriefing(currentLocation.lat, currentLocation.lon, currentLocation.name, currentPersona, routineAm, routinePm);
    if (!data) {
      streamEl.innerHTML = `
        <div class="card err-card">
          <b>Unable to fetch live briefing</b>
          <p class="muted">Check internet connection or ensure backend is running.</p>
          <button class="retry" type="button" onclick="window.location.reload()">Retry</button>
        </div>
      `;
      return;
    }

    currentBriefingData = data;
    if (data.sky?.theme) setTheme(data.sky.theme);

    // Render Hero Card in plain layman terms
    const now = data.now || {};
    const heroTemp = now.temp != null ? `${now.temp}°` : "—";
    const feelsLike = now.feels != null ? now.feels : now.temp;
    const emoji = now.emoji || "⛅";
    const headline = data.headline || `${now.text || 'Partly cloudy'} in ${currentLocation.name}`;
    const sentences = data.sentences || [
      `It's ${heroTemp}C in ${currentLocation.name} right now — ${now.text || 'clear'}.`,
      `Feels like ${feelsLike}°C with comfortable conditions.`
    ];

    // Day plan tiles
    const plan = data.plan || [];
    let planTilesHtml = "";
    if (plan.length) {
      planTilesHtml = `
        <div class="card">
          <div class="card-title">Day Plan Breakdown</div>
          <div class="plan">
            ${plan.map(p => `
              <div class="plan-tile" style="--tone: var(--${p.tone || 'ok'})">
                <div class="lab"><span>${escapeHtml(p.label)}</span><span>${escapeHtml(p.range)}</span></div>
                <b>${p.emoji || ''} ${escapeHtml(p.title)}</b>
                <small>${escapeHtml(p.detail || '')}</small>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // Best Window card
    let bestWindowHtml = "";
    if (data.best_window && data.best_window.range) {
      const bw = data.best_window;
      let whyText = "Ideal conditions for commuting, exercise, and errands.";
      if (Array.isArray(bw.why) && bw.why.length) {
        whyText = bw.why.filter(Boolean).join(" • ");
      } else if (typeof bw.why === "string" && bw.why) {
        whyText = bw.why;
      }
      bestWindowHtml = `
        <div class="card win" style="--tone: var(--${bw.tone || 'good'})">
          <div class="win-head">
            <span class="win-day">${escapeHtml(bw.day || 'Today')}</span>
            <span class="win-time">${escapeHtml(bw.range)}</span>
            <span class="win-score">Optimal outdoor slot (${bw.score || 85}%)</span>
          </div>
          <div class="win-why">${escapeHtml(whyText)}</div>
        </div>
      `;
    }

    // Commute note
    let commuteHtml = "";
    if (data.commute && data.commute.length) {
      commuteHtml = `
        <div class="card">
          <div class="card-title">Commute Notice</div>
          ${data.commute.map(c => `
            <div class="note-line t-${c.tone || 'ok'}">${escapeHtml(c.text)}</div>
          `).join('')}
        </div>
      `;
    }

    // Construct full Hero & Briefing HTML
    streamEl.innerHTML = `
      <div class="card hero">
        <div class="hero-top">
          <div>
            <div class="hero-temp">${heroTemp}</div>
            <div class="hero-head">${formatMarkdown(headline).replace(/^<p>|<\/p>$/g, '')}</div>
          </div>
          <div class="hero-emoji">${emoji}</div>
        </div>
        <div class="hero-lines">
          ${sentences.map(s => `<p>${formatMarkdown(s).replace(/^<p>|<\/p>$/g, '')}</p>`).join('')}
        </div>
        <div class="hero-meta">
          <span class="pill">💧 Humidity ${now.humidity || '—'}%</span>
          <span class="pill">💨 Wind ${now.wind || '—'} km/h (${now.wind_dir || ''})</span>
          <span class="pill">👁️ Vis ${now.vis_km || '—'} km</span>
          <span class="conf ${data.confidence || 'high'}"><i></i> ${(data.confidence || 'HIGH').toUpperCase()} confidence</span>
        </div>
      </div>
      ${bestWindowHtml}
      ${commuteHtml}
      ${planTilesHtml}
    `;

    // Render Real-time Suggestion Chips (Requirement 5)
    renderSuggestionChips(data.suggestions || []);
  }

  function renderSuggestionChips(suggestions) {
    if (!chipsEl) return;
    if (!suggestions || !suggestions.length) {
      suggestions = [
        { q: "Will rain affect me today?", kind: "alert" },
        { q: "Do I need an umbrella right now?", kind: "tip" },
        { q: "What is the best time for outdoor cycling?", kind: "tip" },
        { q: "How will the weather be tomorrow morning?", kind: "alert" }
      ];
    }

    chipsEl.innerHTML = suggestions.map((s, i) => `
      <button type="button" class="chip ${s.kind === 'alert' ? 'alert' : ''}" data-q="${escapeHtml(s.q)}">
        ${escapeHtml(s.q)}
      </button>
    `).join("");

    chipsEl.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const query = chip.getAttribute("data-q");
        if (query) submitChatQuery(query);
      });
    });
  }

  async function submitChatQuery(query) {
    if (!query || !streamEl) return;

    // Append User Message
    const userMsg = document.createElement("div");
    userMsg.className = "msg user";
    userMsg.innerHTML = `<div class="bubble">${escapeHtml(query)}</div>`;
    streamEl.appendChild(userMsg);
    streamEl.scrollTop = streamEl.scrollHeight;

    // Append AI Typing indicator
    const aiMsg = document.createElement("div");
    aiMsg.className = "msg ai";
    aiMsg.innerHTML = `
      <div class="bubble">
        <div class="typing"><i></i><i></i><i></i></div>
      </div>
    `;
    streamEl.appendChild(aiMsg);
    streamEl.scrollTop = streamEl.scrollHeight;

    // Send query to backend
    const res = await api.sendQuery({
      text: query,
      persona: currentPersona,
      lat: currentLocation.lat,
      lon: currentLocation.lon
    });

    // Update AI Bubble with layman plain-English response
    const bubble = aiMsg.querySelector(".bubble");
    if (bubble) {
      let blocksHtml = "";
      if (res.blocks && Array.isArray(res.blocks)) {
        for (const b of res.blocks) {
          if (b.type === "strip" && b.items && b.items.length) {
            blocksHtml += `
              <div class="strip" style="margin-top: 10px;">
                ${b.items.map(it => `
                  <div class="cell" style="--tone: var(--${it.tone || 'ok'})">
                    <div class="t">${escapeHtml(it.label)}</div>
                    <div class="e">${it.emoji || '⛅'}</div>
                    <div class="d">${it.temp != null ? it.temp + '°' : '—'}</div>
                    <div class="p">${it.pop ? it.pop + '%' : ''}</div>
                    <div class="bar"></div>
                  </div>
                `).join('')}
              </div>
            `;
          }
        }
      }

      bubble.innerHTML = `
        <div class="bubble-content">${formatMarkdown(res.answer || "Unable to get an answer right now. Please try again.")}</div>
        ${blocksHtml}
        <div class="meta">
          <span class="conf ${res.confidence || 'high'}"><i></i> ${(res.confidence || 'HIGH').toUpperCase()} confidence</span>
          <span class="small muted">📍 ${escapeHtml(res.location_name || currentLocation.name)}</span>
        </div>
      `;
    }

    if (res.theme) setTheme(res.theme);
    streamEl.scrollTop = streamEl.scrollHeight;
  }

  composerForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = askInput?.value.trim();
    if (query) {
      askInput.value = "";
      submitChatQuery(query);
    }
  });

  // Sky Photo Upload
  const skyPhotoBtn = document.getElementById("sky-photo-btn");
  const skyFileInput = document.getElementById("sky-file");

  skyPhotoBtn?.addEventListener("click", () => skyFileInput?.click());
  skyFileInput?.addEventListener("change", async () => {
    const file = skyFileInput.files?.[0];
    if (!file) return;

    showToast("Analyzing sky photo with AI…");
    const reader = new FileReader();
    reader.onload = async () => {
      const b64 = reader.result;
      const res = await api.analyzeSky(b64, file.type, currentLocation.lat, currentLocation.lon, currentLocation.name);
      if (res.error) {
        showToast(res.error);
        return;
      }
      submitChatQuery(`I submitted a sky photo. Analysis: ${res.analysis || 'Cloud cover validated.'}`);
    };
    reader.readAsDataURL(file);
  });

  // ===================================================================
  // 5. Embedded Voice Mode inside Chat (Requirement 11)
  // ===================================================================
  const micBtn = document.getElementById("mic-btn");
  const voiceOverlay = document.getElementById("voice");
  const voiceClose = document.getElementById("voice-close");
  const voiceOrb = document.getElementById("orb");
  const voiceStatus = document.getElementById("voice-status");
  const voiceText = document.getElementById("voice-text");
  const voiceLangContainer = document.getElementById("voice-lang");

  const SpeechImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let isListeningVoice = false;
  let activeVoiceLang = "en-IN";

  const voiceLangs = [
    { code: "en-IN", name: "English" },
    { code: "hi-IN", name: "हिंदी (Hindi)" },
    { code: "kn-IN", name: "ಕನ್ನಡ (Kannada)" },
    { code: "ta-IN", name: "தமிழ் (Tamil)" },
    { code: "te-IN", name: "తెలుగు (Telugu)" },
    { code: "bn-IN", name: "বাংলা (Bengali)" }
  ];

  function initVoiceLanguages() {
    if (!voiceLangContainer) return;
    voiceLangContainer.innerHTML = voiceLangs.map(l => `
      <button type="button" class="${l.code === activeVoiceLang ? 'on' : ''}" data-code="${l.code}">${l.name}</button>
    `).join("");

    voiceLangContainer.querySelectorAll("button").forEach(btn => {
      btn.addEventListener("click", () => {
        activeVoiceLang = btn.getAttribute("data-code");
        voiceLangContainer.querySelectorAll("button").forEach(b => b.classList.remove("on"));
        btn.classList.add("on");
        if (recognizer) recognizer.lang = activeVoiceLang;
        showToast(`Voice language: ${btn.textContent}`);
      });
    });
  }
  initVoiceLanguages();

  if (SpeechImpl) {
    recognizer = new SpeechImpl();
    recognizer.continuous = false;
    recognizer.interimResults = true;
    recognizer.lang = activeVoiceLang;

    recognizer.onresult = (evt) => {
      const transcript = Array.from(evt.results).map(r => r[0].transcript).join(" ");
      if (voiceText) voiceText.textContent = `“${transcript}”`;
    };

    recognizer.onend = () => {
      isListeningVoice = false;
      voiceOverlay?.classList.remove("live");
      if (voiceStatus) voiceStatus.textContent = "Processing speech…";

      const query = voiceText?.textContent?.replace(/[“”"]/g, "").trim();
      if (query && query !== "Say something like “will it rain when I leave office?”") {
        setTimeout(() => {
          closeVoiceOverlay();
          submitChatQuery(query);
        }, 600);
      } else {
        if (voiceStatus) voiceStatus.textContent = "Tap Orb to speak";
      }
    };

    recognizer.onerror = (e) => {
      isListeningVoice = false;
      voiceOverlay?.classList.remove("live");
      if (voiceStatus) voiceStatus.textContent = "Tap Orb to try again";
    };
  }

  function openVoiceOverlay() {
    if (voiceOverlay) {
      voiceOverlay.hidden = false;
      if (voiceText) voiceText.textContent = "Say something like “will it rain when I leave office?”";
      if (voiceStatus) voiceStatus.textContent = "Listening…";
      startListening();
    }
  }

  function closeVoiceOverlay() {
    if (voiceOverlay) voiceOverlay.hidden = true;
    if (isListeningVoice && recognizer) {
      recognizer.stop();
      isListeningVoice = false;
    }
  }

  function startListening() {
    if (!recognizer) {
      if (voiceStatus) voiceStatus.textContent = "Speech recognition not supported in this browser";
      return;
    }
    try {
      recognizer.lang = activeVoiceLang;
      recognizer.start();
      isListeningVoice = true;
      voiceOverlay?.classList.add("live");
      if (voiceStatus) voiceStatus.textContent = "Listening…";
    } catch (e) {
      // already started
    }
  }

  micBtn?.addEventListener("click", openVoiceOverlay);
  voiceClose?.addEventListener("click", closeVoiceOverlay);
  voiceOrb?.addEventListener("click", () => {
    if (isListeningVoice) {
      recognizer?.stop();
    } else {
      startListening();
    }
  });

  // ===================================================================
  // 6 & 7. Multi-Persona Advisory & Custom UI (Requirements 6 & 7)
  // ===================================================================
  const personaBarEl = document.getElementById("persona-bar");
  const advisoryBodyEl = document.getElementById("advisory-body");

  async function renderAdvisoryView() {
    if (!personaBarEl || !advisoryBodyEl) return;

    // Load available personas
    const personas = await api.getPersonas();
    personaBarEl.innerHTML = personas.map(p => `
      <button type="button" class="persona ${p.id === currentPersona ? 'on' : ''}" data-persona="${p.id}">
        <span class="em">${p.emoji}</span>
        <span>${escapeHtml(p.name)}</span>
      </button>
    `).join("");

    personaBarEl.querySelectorAll(".persona").forEach(btn => {
      btn.addEventListener("click", () => {
        currentPersona = btn.getAttribute("data-persona");
        personaBarEl.querySelectorAll(".persona").forEach(b => b.classList.remove("on"));
        btn.classList.add("on");
        loadPersonaAdvisoryContent(currentPersona);
      });
    });

    await loadPersonaAdvisoryContent(currentPersona);
  }

  async function loadPersonaAdvisoryContent(persona) {
    if (!advisoryBodyEl) return;
    advisoryBodyEl.innerHTML = `<div class="card skeleton" style="height: 260px;"></div>`;

    const data = await api.getAdvisoryFull(persona, currentLocation.lat, currentLocation.lon, currentLocation.name, routineAm, routinePm);
    if (!data) {
      advisoryBodyEl.innerHTML = `
        <div class="card err-card">
          <b>Could not load advisory</b>
          <p class="muted">Check internet or backend connection.</p>
        </div>
      `;
      return;
    }

    const verdict = data.verdict || {
      level: "good",
      label: "Good to go",
      emoji: "🟢",
      headline: "Conditions look favorable",
      detail: "No weather risks that interfere with normal plans."
    };

    // Custom stats grid per persona
    const stats = data.stats || [];
    const statsHtml = stats.length ? `
      <div class="stats">
        ${stats.map(s => `
          <div class="stat">
            <div class="l">${escapeHtml(s.label)}</div>
            <div class="v">${escapeHtml(s.value)}</div>
            ${s.sub ? `<div class="s">${escapeHtml(s.sub)}</div>` : ''}
          </div>
        `).join('')}
      </div>
    ` : "";

    // Do's and Don'ts
    let dosDontsHtml = "";
    if ((data.do && data.do.length) || (data.dont && data.dont.length)) {
      dosDontsHtml = `
        <div class="two">
          <div class="col do">
            <h4>✓ Recommended</h4>
            <ul>
              ${(data.do || []).map(d => `<li>${escapeHtml(d)}</li>`).join('')}
            </ul>
          </div>
          <div class="col dont">
            <h4>✕ Avoid</h4>
            <ul>
              ${(data.dont || []).map(d => `<li>${escapeHtml(d)}</li>`).join('')}
            </ul>
          </div>
        </div>
      `;
    }

    // Commute routine time selector for Office / Student / Commuter
    let routineSelectorHtml = "";
    if (persona === "office" || persona === "student" || persona === "commuter") {
      routineSelectorHtml = `
        <div class="card">
          <div class="card-title">Custom Commute Timing</div>
          <div class="routine">
            <label>
              Morning Commute
              <select id="sel-am">
                ${[7, 8, 9, 10, 11].map(h => `<option value="${h}" ${h === routineAm ? 'selected' : ''}>${h} AM</option>`).join('')}
              </select>
            </label>
            <label>
              Evening Commute
              <select id="sel-pm">
                ${[16, 17, 18, 19, 20].map(h => `<option value="${h}" ${h === routinePm ? 'selected' : ''}>${h > 12 ? h - 12 : h} PM</option>`).join('')}
              </select>
            </label>
          </div>
        </div>
      `;
    }

    // Explain-Why section
    let whyHtml = "";
    if (data.why) {
      let whyItems = [];
      if (Array.isArray(data.why)) {
        whyItems = data.why.map(w => {
          if (typeof w === "string") return { title: "Observation", text: w };
          return { title: w.title || "Reason", text: w.text || "" };
        });
      } else if (typeof data.why === "object") {
        if (data.why.analysis) {
          whyItems.push({ title: "Analysis", text: data.why.analysis });
        }
        if (data.why.suggestion) {
          whyItems.push({ title: "Recommendation", text: data.why.suggestion });
        }
        if (Array.isArray(data.why.facts)) {
          data.why.facts.forEach((f, idx) => {
            whyItems.push({ title: `Fact #${idx + 1}`, text: f });
          });
        }
      }

      if (whyItems.length) {
        whyHtml = `
          <details class="why" open>
            <summary>Why this advice? (Layman explanation)</summary>
            ${whyItems.map(w => `
              <div class="why-part">
                <h5>${escapeHtml(w.title)}</h5>
                <p>${escapeHtml(w.text)}</p>
              </div>
            `).join('')}
          </details>
        `;
      }
    }

    advisoryBodyEl.innerHTML = `
      <div class="verdict t-${verdict.level || 'good'}" style="--tone: var(--${verdict.level || 'good'})">
        <div class="who">${escapeHtml(data.persona_name || persona)} Advisory • ${escapeHtml(currentLocation.name)}</div>
        <div class="vh">${escapeHtml(verdict.headline)}</div>
        <div class="vd">${escapeHtml(verdict.detail)}</div>
        <div class="badge">${verdict.emoji} ${escapeHtml(verdict.label)}</div>
        <div class="big-em">${data.emoji || '💼'}</div>
      </div>
      ${statsHtml}
      ${routineSelectorHtml}
      ${dosDontsHtml}
      ${whyHtml}
    `;

    // Routine change listeners
    document.getElementById("sel-am")?.addEventListener("change", (e) => {
      routineAm = parseInt(e.target.value, 10);
      loadPersonaAdvisoryContent(persona);
    });
    document.getElementById("sel-pm")?.addEventListener("change", (e) => {
      routinePm = parseInt(e.target.value, 10);
      loadPersonaAdvisoryContent(persona);
    });
  }

  // ===================================================================
  // 8 & 9. All-India Alerts, Mini Map, Moving SVGs (Requirements 8 & 9)
  // ===================================================================
  const alertsBodyEl = document.getElementById("alerts-body");
  const alertsBadgeEl = document.getElementById("alerts-badge");
  const alertBannerEl = document.getElementById("alert-banner");

  async function renderAlertsView() {
    if (!alertsBodyEl) return;
    alertsBodyEl.innerHTML = `<div class="card skeleton" style="height: 280px;"></div>`;

    const data = await api.getIndiaAlerts(currentLocation.lat, currentLocation.lon);
    currentAlertsData = data;

    const total = data.total || 0;
    const nearCount = data.near_count || 0;
    const sev = data.by_severity || { yellow: 0, orange: 0, red: 0 };

    if (alertsBadgeEl) {
      if (total > 0) {
        alertsBadgeEl.textContent = total;
        alertsBadgeEl.hidden = false;
      } else {
        alertsBadgeEl.hidden = true;
      }
    }

    // Top Banner if near alerts exist
    if (alertBannerEl) {
      if (nearCount > 0) {
        alertBannerEl.innerHTML = `⚠️ <b>${nearCount} Active Weather Alert(s)</b> near ${escapeHtml(currentLocation.name)}! Tap to view.`;
        alertBannerEl.hidden = false;
        alertBannerEl.onclick = () => switchTab("alerts");
      } else {
        alertBannerEl.hidden = true;
      }
    }

    // Hero overview
    const heroTitle = nearCount > 0
      ? `Active Alerts Near ${currentLocation.name}`
      : `All Clear in ${currentLocation.name}`;
    const heroDesc = nearCount > 0
      ? `${nearCount} alert(s) within your region. Check precautions below.`
      : `No severe cyclone, thunderstorm or flood warnings within 100 km. Displaying ${total} alerts across India.`;

    alertsBodyEl.innerHTML = `
      <div class="al-hero" style="--tone: var(--${nearCount > 0 ? 'sev-orange' : 'good'})">
        <h2>${escapeHtml(heroTitle)}</h2>
        <p>${escapeHtml(heroDesc)}</p>
        <div class="al-counts">
          <button type="button" class="sev red" data-filter="red" title="Filter Red Alerts"><i></i> ${sev.red} Red</button>
          <button type="button" class="sev orange" data-filter="orange" title="Filter Orange Alerts"><i></i> ${sev.orange} Orange</button>
          <button type="button" class="sev yellow" data-filter="yellow" title="Filter Yellow Alerts"><i></i> ${sev.yellow} Yellow</button>
        </div>
        <div class="illo">${getAlertSvg("storm")}</div>
      </div>

      <div class="sec-h">India Weather Alert Hotspots</div>
      <div class="mini-map" id="alerts-mini-map"></div>

      <div class="filters" id="alert-filters">
        <button type="button" class="filter on" data-filter="all">All India (${total})</button>
        <button type="button" class="filter" data-filter="near">Near You (${nearCount})</button>
        <button type="button" class="filter" data-filter="red">🔴 Red (${sev.red})</button>
        <button type="button" class="filter" data-filter="orange">🟠 Orange (${sev.orange})</button>
        <button type="button" class="filter" data-filter="yellow">🟡 Yellow (${sev.yellow})</button>
        <button type="button" class="filter" data-filter="storm">Rain & Storm</button>
      </div>

      <div id="alerts-card-list"></div>
    `;

    // Initialize Leaflet Mini-Map
    initAlertsMiniMap(data.alerts || []);

    // Filter listeners on both filter bar and hero badges
    const allFilterBtns = alertsBodyEl.querySelectorAll("#alert-filters .filter, .al-counts .sev");
    allFilterBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        const filter = btn.getAttribute("data-filter");
        allFilterBtns.forEach(b => {
          b.classList.toggle("on", b.getAttribute("data-filter") === filter);
        });
        renderAlertCards(data.alerts || [], filter);
      });
    });

    renderAlertCards(data.alerts || [], "all");
  }

  function initAlertsMiniMap(alerts) {
    const mapEl = document.getElementById("alerts-mini-map");
    if (!mapEl || typeof L === "undefined") return;

    if (alertsMapInstance) {
      alertsMapInstance.remove();
      alertsMapInstance = null;
    }

    alertsMapInstance = L.map(mapEl, {
      center: [currentLocation.lat, currentLocation.lon],
      zoom: 5,
      zoomControl: false,
      attributionControl: false
    });

    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 16
    }).addTo(alertsMapInstance);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 16
    }).addTo(alertsMapInstance);

    // User location marker
    L.circleMarker([currentLocation.lat, currentLocation.lon], {
      radius: 8,
      fillColor: "#4aa8ff",
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.9
    }).addTo(alertsMapInstance).bindTooltip(`You: ${currentLocation.name}`, { permanent: false });

    // Alert markers
    for (const a of (alerts || []).slice(0, 40)) {
      if (a.lat && a.lon) {
        const color = a.color === "red" ? "#eb5757" : a.color === "orange" ? "#f2994a" : "#f2c94c";
        L.circleMarker([a.lat, a.lon], {
          radius: a.near ? 9 : 6,
          fillColor: color,
          color: "#fff",
          weight: a.near ? 2 : 1,
          opacity: 1,
          fillOpacity: 0.85
        }).addTo(alertsMapInstance).bindTooltip(`<b>${escapeHtml(a.place)}</b>: ${escapeHtml(a.title)}`);
      }
    }
  }

  function renderAlertCards(alerts, filter = "all") {
    const listEl = document.getElementById("alerts-card-list");
    if (!listEl) return;

    let filtered = alerts;
    if (filter === "near") {
      filtered = alerts.filter(a => a.near || (a.distance_km && a.distance_km <= 200));
    } else if (filter === "red") {
      filtered = alerts.filter(a => (a.color && a.color.toLowerCase() === "red") || a.severity === 3);
    } else if (filter === "orange") {
      filtered = alerts.filter(a => (a.color && a.color.toLowerCase() === "orange") || a.severity === 2);
    } else if (filter === "yellow") {
      filtered = alerts.filter(a => (a.color && a.color.toLowerCase() === "yellow") || a.severity === 1);
    } else if (filter === "severe") {
      filtered = alerts.filter(a => a.color === "red" || a.color === "orange" || a.severity >= 2);
    } else if (filter === "storm") {
      filtered = alerts.filter(a => a.type === "storm" || a.type === "rain");
    }

    if (!filtered.length) {
      listEl.innerHTML = `
        <div class="empty">
          <span class="em">🛡️</span>
          No alerts match the selected filter. You are safe!
        </div>
      `;
      return;
    }

    listEl.innerHTML = filtered.slice(0, 30).map(a => `
      <div class="alert ${a.color || 'yellow'} ${a.near ? 'flash' : ''}">
        <div class="alert-top">
          <div class="illo">${getAlertSvg(a.type || 'storm')}</div>
          <div style="flex: 1;">
            <h3>${escapeHtml(a.title)}</h3>
            <div class="place">${escapeHtml(a.place)}${a.state ? ', ' + escapeHtml(a.state) : ''} • ${a.distance_km != null ? Math.round(a.distance_km) + ' km away' : 'India'}</div>
            <span class="lvl">${escapeHtml((a.color || 'yellow').toUpperCase())} ADVISORY</span>
          </div>
        </div>
        <div class="what"><b>What's happening:</b> ${escapeHtml(a.what)}</div>
        <div class="what" style="margin-top: 4px; color: var(--muted);"><b>Why it matters:</b> ${escapeHtml(a.why)}</div>
        ${a.do && a.do.length ? `
          <ul class="do-list">
            ${a.do.map(d => `<li>${escapeHtml(d)}</li>`).join('')}
          </ul>
        ` : ''}
        <div class="alert-actions">
          <span class="pill">⏰ ${escapeHtml(a.when || 'Next 24h')}</span>
          <span class="src ${a.source === 'official' ? 'official' : ''}">Source: ${escapeHtml(a.source_label || 'IMD / Open-Meteo')}</span>
        </div>
      </div>
    `).join("");
  }

  // Moving SVG illustrations
  function getAlertSvg(type) {
    if (type === "heat") {
      return `
        <svg viewBox="0 0 100 100">
          <g class="i-rays"><circle cx="50" cy="50" r="28" fill="none" stroke="#f2994a" stroke-width="3" stroke-dasharray="4 8"/></g>
          <circle class="i-sun" cx="50" cy="50" r="20" fill="#f2b84b"/>
          <path class="i-wave" d="M30 82 Q40 76 50 82 T70 82" fill="none" stroke="#f2994a" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
      `;
    }
    if (type === "fog") {
      return `
        <svg viewBox="0 0 100 100">
          <path class="i-fog" d="M20 40 H80 M15 54 H85 M25 68 H75" fill="none" stroke="#a0b0c0" stroke-width="4" stroke-linecap="round"/>
        </svg>
      `;
    }
    if (type === "wind") {
      return `
        <svg viewBox="0 0 100 100">
          <path class="i-wind" d="M15 45 H75 C82 45 85 38 80 34" fill="none" stroke="#5ec8d4" stroke-width="3.5" stroke-linecap="round"/>
          <path class="i-wind" d="M22 60 H65 C72 60 75 66 70 70" fill="none" stroke="#5ec8d4" stroke-width="3.5" stroke-linecap="round"/>
        </svg>
      `;
    }
    // Default Storm / Rain
    return `
      <svg viewBox="0 0 100 100">
        <path class="i-cloud" d="M28 55 A16 16 0 0 1 56 42 A22 22 0 0 1 80 55 A12 12 0 0 1 76 68 H26 A12 12 0 0 1 28 55 Z" fill="#4a5568"/>
        <line class="i-drop" x1="38" y1="72" x2="34" y2="82" stroke="#5ec8d4" stroke-width="2.5" stroke-linecap="round"/>
        <line class="i-drop" x1="52" y1="72" x2="48" y2="82" stroke="#5ec8d4" stroke-width="2.5" stroke-linecap="round"/>
        <line class="i-drop" x1="66" y1="72" x2="62" y2="82" stroke="#5ec8d4" stroke-width="2.5" stroke-linecap="round"/>
        <polygon class="i-bolt" points="50,48 44,62 52,62 46,78 58,60 50,60" fill="#f2c94c"/>
      </svg>
    `;
  }

  // ===================================================================
  // 10. Aaj Tak News-Style Weather Map (Requirement 10)
  // ===================================================================
  const mapLayersEl = document.getElementById("map-layers");
  const mapLegendEl = document.getElementById("map-legend");
  const mapCardEl = document.getElementById("map-card");

  async function renderMapView() {
    const mapContainer = document.getElementById("map");
    if (!mapContainer || typeof L === "undefined") return;

    if (!mapInstance) {
      mapInstance = L.map(mapContainer, {
        center: [22.5, 79.5], // Center of India
        zoom: 5,
        minZoom: 4,
        maxZoom: 9,
        attributionControl: false
      });

      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 16
      }).addTo(mapInstance);
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 16
      }).addTo(mapInstance);
    }

    // Layer options
    if (mapLayersEl) {
      mapLayersEl.innerHTML = `
        <button type="button" class="layer on" data-layer="news">📺 Aaj Tak Weather</button>
        <button type="button" class="layer" data-layer="temp">🌡️ Temperature</button>
        <button type="button" class="layer" data-layer="rain">🌧️ Rain Chance</button>
        <button type="button" class="layer" data-layer="wind">💨 Wind Flow</button>
      `;

      mapLayersEl.querySelectorAll(".layer").forEach(btn => {
        btn.addEventListener("click", () => {
          mapLayersEl.querySelectorAll(".layer").forEach(b => b.classList.remove("on"));
          btn.classList.add("on");
          drawMapCityBubbles(btn.getAttribute("data-layer"));
        });
      });
    }

    if (mapLegendEl) {
      mapLegendEl.innerHTML = `
        <span class="legend-bar" style="background: linear-gradient(90deg, #5ec8d4, #f2c94c, #eb5757);"></span>
        <span>Aaj Tak India Live News Map</span>
      `;
    }

    // Wire up pinpoint location button
    const pinpointBtn = document.getElementById("map-pinpoint-btn");
    if (pinpointBtn) {
      pinpointBtn.onclick = () => pinpointUserOnMap();
    }

    // Fetch live cities weather across India
    mapPointsData = await api.getMapPoints();
    drawMapCityBubbles("news");
  }

  let userPinpointMarker = null;

  function pinpointUserOnMap() {
    if (!mapInstance) return;

    function applyPinpoint(lat, lon, name) {
      mapInstance.flyTo([lat, lon], 10, { animate: true, duration: 1.2 });

      if (userPinpointMarker) {
        mapInstance.removeLayer(userPinpointMarker);
      }

      // Add a distinct glowing pinpoint beacon
      const pinpointHtml = `
        <div class="user-beacon">
          <span class="beacon-wave"></span>
          <span class="beacon-wave w2"></span>
          <span class="beacon-dot">📍</span>
        </div>
      `;

      userPinpointMarker = L.marker([lat, lon], {
        icon: L.divIcon({
          className: "custom-city-icon",
          html: pinpointHtml,
          iconSize: [40, 40],
          iconAnchor: [20, 20]
        }),
        zIndexOffset: 1000
      }).addTo(mapInstance);

      userPinpointMarker.bindPopup(`
        <div style="font-family: var(--font); color: #fff; padding: 4px; min-width: 140px;">
          <b style="font-size: 14px;">📍 You Are Here</b>
          <div style="color: var(--accent); font-weight: 600; margin-top: 2px;">${escapeHtml(name)}</div>
          <small style="color: #aaa; display: block; margin-top: 4px;">${lat.toFixed(3)}°N, ${lon.toFixed(3)}°E</small>
        </div>
      `).openPopup();

      showToast(`Pinpointed location: ${name}`);
    }

    if (navigator.geolocation) {
      showToast("Detecting GPS position…");
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const { latitude: lat, longitude: lon } = pos.coords;
          const rev = await api.reverseGeocode(lat, lon);
          const name = rev?.name || currentLocation.name || "Your Position";
          selectCity({ name, state: rev?.state || "", lat, lon });
          applyPinpoint(lat, lon, name);
        },
        () => {
          applyPinpoint(currentLocation.lat, currentLocation.lon, currentLocation.name);
        },
        { timeout: 7000 }
      );
    } else {
      applyPinpoint(currentLocation.lat, currentLocation.lon, currentLocation.name);
    }
  }

  let cityMarkersGroup = null;

  function drawMapCityBubbles(layerMode = "news") {
    if (!mapInstance || !mapPointsData) return;

    if (cityMarkersGroup) {
      mapInstance.removeLayer(cityMarkersGroup);
    }
    cityMarkersGroup = L.layerGroup().addTo(mapInstance);

    // Add user marker
    const userMarker = L.marker([currentLocation.lat, currentLocation.lon], {
      icon: L.divIcon({
        className: "me-dot",
        iconSize: [16, 16],
        iconAnchor: [8, 8]
      })
    }).addTo(cityMarkersGroup);
    userMarker.bindTooltip(`📍 You are in ${currentLocation.name}`, { permanent: false });

    // Add Aaj Tak style floating news badges
    for (const city of mapPointsData) {
      const temp = city.temp != null ? `${city.temp}°` : "—";
      const emoji = city.emoji || "🌤️";
      const badgeColor = getTemperatureColor(city.temp);

      const html = `
        <div class="city-bubble" style="--bc: ${badgeColor};">
          <div class="b">
            <span class="e">${emoji}</span>
            <span>${temp}</span>
          </div>
          <div class="n">${escapeHtml(city.name)}</div>
        </div>
      `;

      const marker = L.marker([city.lat, city.lon], {
        icon: L.divIcon({
          className: "custom-city-icon",
          html: html,
          iconSize: [60, 40],
          iconAnchor: [30, 20]
        })
      }).addTo(cityMarkersGroup);

      marker.on("click", () => {
        showMapCityCard(city);
      });
    }
  }

  function getTemperatureColor(temp) {
    if (temp == null) return "#4a5568";
    if (temp >= 35) return "#ff6b6b";
    if (temp >= 30) return "#ffa94d";
    if (temp >= 25) return "#fcc419";
    if (temp >= 20) return "#51cf66";
    if (temp >= 15) return "#38d9a9";
    return "#339af0";
  }

  function showMapCityCard(city) {
    if (!mapCardEl) return;
    mapCardEl.hidden = false;
    mapCardEl.innerHTML = `
      <button class="x" type="button" id="map-card-close">✕</button>
      <h3>${city.emoji || '🌤️'} ${escapeHtml(city.name)} • ${city.temp || '—'}°C</h3>
      <p class="muted">${escapeHtml(city.text || 'Fair')} • Feels like ${city.feels || city.temp}°C</p>
      <div class="row">
        <span class="pill">💧 Humidity ${city.humidity || '—'}%</span>
        <span class="pill">💨 Wind ${city.wind || '—'} km/h ${city.wind_dir || ''}</span>
        <span class="pill">🌧️ Rain ${city.rain_today || '0'} mm (${city.pop || '0'}%)</span>
        <span class="pill">🏭 AQI ${city.aqi || '—'}</span>
      </div>
      <div style="margin-top: 12px; display: flex; gap: 8px;">
        <button type="button" class="btn primary" id="set-city-active-btn">
          Select ${escapeHtml(city.name)} as active city
        </button>
      </div>
    `;

    document.getElementById("map-card-close")?.addEventListener("click", () => {
      mapCardEl.hidden = true;
    });

    document.getElementById("set-city-active-btn")?.addEventListener("click", () => {
      selectCity({
        name: city.name,
        state: city.state || "",
        lat: city.lat,
        lon: city.lon
      });
      mapCardEl.hidden = true;
      switchTab("chat");
    });
  }

  // ===================================================================
  // 12 & 13. Trends Tab & Google Stocks Interactive Scrubbing (Req 12 & 13)
  // ===================================================================
  const trendsBodyEl = document.getElementById("trends-body");

  async function renderTrendsView() {
    if (!trendsBodyEl) return;
    trendsBodyEl.innerHTML = `<div class="card skeleton" style="height: 320px;"></div>`;

    const data = await api.getSeries(currentLocation.lat, currentLocation.lon, currentLocation.name, "3d");
    if (!data) {
      trendsBodyEl.innerHTML = `
        <div class="card err-card">
          <b>Unable to load trends data</b>
          <p class="muted">Check internet or backend connection.</p>
        </div>
      `;
      return;
    }

    currentSeriesData = data;

    trendsBodyEl.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
        <h3 style="font: 600 20px var(--display);">Atmospheric Trends</h3>
        <button type="button" class="pill" id="trends-loc-change">📍 ${escapeHtml(currentLocation.name)} ▾</button>
      </div>

      <div class="seg" id="trends-metric-seg">
        <button type="button" class="${currentTrendMetric === 'temp' ? 'on' : ''}" data-metric="temp">🌡️ Temp</button>
        <button type="button" class="${currentTrendMetric === 'rain_mm' ? 'on' : ''}" data-metric="rain_mm">🌧️ Rain</button>
        <button type="button" class="${currentTrendMetric === 'wind' ? 'on' : ''}" data-metric="wind">💨 Wind</button>
        <button type="button" class="${currentTrendMetric === 'humidity' ? 'on' : ''}" data-metric="humidity">💧 Humidity</button>
        <button type="button" class="${currentTrendMetric === 'uv' ? 'on' : ''}" data-metric="uv">☀️ UV</button>
      </div>

      <div class="readout" id="trends-readout">
        <div class="when" id="scrub-when">Slide across chart to view date & time</div>
        <div class="val" id="scrub-val">—</div>
        <div class="sub" id="scrub-sub"></div>
      </div>

      <div class="chart-box" id="trends-chart-box">
        <svg id="trends-svg" preserveAspectRatio="none" viewBox="0 0 600 240"></svg>
        <div class="chart-tip" id="chart-tooltip" hidden></div>
      </div>

      <div class="sumgrid" id="trends-sumgrid"></div>
    `;

    document.getElementById("trends-loc-change")?.addEventListener("click", openLocationSheet);

    const metricSegBtns = trendsBodyEl.querySelectorAll("#trends-metric-seg button");
    metricSegBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        metricSegBtns.forEach(b => b.classList.remove("on"));
        btn.classList.add("on");
        currentTrendMetric = btn.getAttribute("data-metric");
        buildInteractiveTrendsChart(currentSeriesData, currentTrendMetric);
      });
    });

    buildInteractiveTrendsChart(data, currentTrendMetric);
  }

  function buildInteractiveTrendsChart(seriesData, metricKey) {
    const svg = document.getElementById("trends-svg");
    const tooltip = document.getElementById("chart-tooltip");
    const readoutWhen = document.getElementById("scrub-when");
    const readoutVal = document.getElementById("scrub-val");
    const readoutSub = document.getElementById("scrub-sub");
    const sumgrid = document.getElementById("trends-sumgrid");
    const chartBox = document.getElementById("trends-chart-box");

    if (!svg || !seriesData) return;

    const points = seriesData.points || [];
    const values = seriesData[metricKey] || [];
    const emojis = seriesData.emoji || [];
    const texts = seriesData.text || [];
    const n = Math.min(points.length, values.length);

    if (n < 2) {
      svg.innerHTML = `<text x="300" y="120" text-anchor="middle" fill="#888">Not enough data points</text>`;
      return;
    }

    // Config per metric
    const meta = {
      temp: { unit: "°C", label: "Temperature", color: "#f2b84b", subUnit: "Feels like" },
      rain_mm: { unit: " mm", label: "Rainfall", color: "#5ec8d4", subUnit: "Rain chance" },
      wind: { unit: " km/h", label: "Wind speed", color: "#68d391", subUnit: "Gusts up to" },
      humidity: { unit: "%", label: "Humidity", color: "#63b3ed", subUnit: "Moisture" },
      uv: { unit: "", label: "UV Index", color: "#ed8936", subUnit: "Sun intensity" }
    }[metricKey] || { unit: "", label: metricKey, color: "#f2b84b" };

    const validVals = values.slice(0, n).map(v => (v == null ? 0 : v));
    let minVal = Math.min(...validVals);
    let maxVal = Math.max(...validVals);
    if (minVal === maxVal) { maxVal += 5; minVal -= 5; }

    const svgW = 600, svgH = 240;
    const padTop = 30, padBottom = 40, padLeft = 20, padRight = 20;
    const plotW = svgW - padLeft - padRight;
    const plotH = svgH - padTop - padBottom;

    // Calculate (x, y) coords
    const coords = validVals.map((v, i) => {
      const x = padLeft + (i / (n - 1)) * plotW;
      const y = padTop + (1 - (v - minVal) / (maxVal - minVal)) * plotH;
      return { x, y, v, i };
    });

    // Create smooth SVG path
    let pathD = `M ${coords[0].x} ${coords[0].y}`;
    for (let i = 0; i < coords.length - 1; i++) {
      const p0 = coords[i === 0 ? 0 : i - 1];
      const p1 = coords[i];
      const p2 = coords[i + 1];
      const p3 = coords[i + 2 >= coords.length ? coords.length - 1 : i + 2];

      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;

      pathD += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }

    // Fill area below path
    const areaD = `${pathD} L ${coords[coords.length - 1].x} ${svgH - padBottom} L ${coords[0].x} ${svgH - padBottom} Z`;

    // Grid lines & labels
    let gridLines = "";
    for (let g = 0; g <= 4; g++) {
      const y = padTop + (g / 4) * plotH;
      const val = (maxVal - (g / 4) * (maxVal - minVal)).toFixed(1);
      gridLines += `
        <line x1="${padLeft}" y1="${y}" x2="${svgW - padRight}" y2="${y}" class="gl" />
        <text x="${svgW - padRight - 4}" y="${y - 4}" class="ax" text-anchor="end">${val}${meta.unit}</text>
      `;
    }

    // X-axis day labels
    let dayLabels = "";
    const step = Math.floor(n / 6);
    for (let i = 0; i < n; i += step) {
      const pt = points[i];
      const cx = coords[i].x;
      dayLabels += `
        <text x="${cx}" y="${svgH - 12}" class="ax" text-anchor="middle">${escapeHtml(pt.time || '')}</text>
      `;
    }

    svg.innerHTML = `
      <defs>
        <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${meta.color}" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="${meta.color}" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      ${gridLines}
      ${dayLabels}
      <path d="${areaD}" fill="url(#chartGrad)"/>
      <path d="${pathD}" fill="none" stroke="${meta.color}" stroke-width="2.8" stroke-linecap="round"/>
      <line id="scrub-crosshair" x1="0" y1="${padTop}" x2="0" y2="${svgH - padBottom}" class="cross" hidden/>
      <circle id="scrub-dot" cx="0" cy="0" r="5" fill="#fff" stroke="${meta.color}" stroke-width="2.5" hidden/>
    `;

    // Render Summary grid
    if (sumgrid) {
      const avg = (validVals.reduce((a, b) => a + b, 0) / validVals.length).toFixed(1);
      sumgrid.innerHTML = `
        <div class="stat"><div class="l">Maximum</div><div class="v">${maxVal.toFixed(1)}${meta.unit}</div></div>
        <div class="stat"><div class="l">Minimum</div><div class="v">${minVal.toFixed(1)}${meta.unit}</div></div>
        <div class="stat"><div class="l">Average</div><div class="v">${avg}${meta.unit}</div></div>
      `;
    }

    // Default readout to current hour
    const nowIdx = seriesData.now_index || 0;
    updateScrubReadout(nowIdx, coords[nowIdx], meta);

    // Google Stocks style scrubbing on mouse / touch
    const crosshair = document.getElementById("scrub-crosshair");
    const dot = document.getElementById("scrub-dot");

    function onPointerMove(clientX) {
      const rect = chartBox.getBoundingClientRect();
      const relX = clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, (relX - (padLeft / svgW) * rect.width) / ((plotW / svgW) * rect.width)));
      const closestIdx = Math.round(ratio * (n - 1));
      const targetPoint = coords[closestIdx];

      if (!targetPoint) return;

      if (crosshair) {
        crosshair.setAttribute("x1", targetPoint.x);
        crosshair.setAttribute("x2", targetPoint.x);
        crosshair.removeAttribute("hidden");
      }
      if (dot) {
        dot.setAttribute("cx", targetPoint.x);
        dot.setAttribute("cy", targetPoint.y);
        dot.removeAttribute("hidden");
      }

      // Tooltip
      if (tooltip) {
        const pt = points[closestIdx];
        const val = targetPoint.v;
        const em = emojis[closestIdx] || "🌤️";
        const cond = texts[closestIdx] || "";

        tooltip.removeAttribute("hidden");
        tooltip.innerHTML = `
          <div><b>${em} ${val}${meta.unit}</b> • ${escapeHtml(cond)}</div>
          <div style="color: var(--muted); font-size: 11px;">${escapeHtml(pt.label || '')} • ${escapeHtml(pt.time || '')}</div>
        `;
        const tipX = (targetPoint.x / svgW) * rect.width;
        tooltip.style.left = `${Math.max(60, Math.min(rect.width - 60, tipX))}px`;
      }

      updateScrubReadout(closestIdx, targetPoint, meta);
    }

    function onPointerLeave() {
      if (crosshair) crosshair.setAttribute("hidden", "true");
      if (dot) dot.setAttribute("hidden", "true");
      if (tooltip) tooltip.setAttribute("hidden", "true");
      updateScrubReadout(nowIdx, coords[nowIdx], meta);
    }

    chartBox.onmousemove = (e) => onPointerMove(e.clientX);
    chartBox.onmouseleave = onPointerLeave;

    chartBox.ontouchstart = (e) => {
      if (e.touches[0]) onPointerMove(e.touches[0].clientX);
    };
    chartBox.ontouchmove = (e) => {
      if (e.touches[0]) onPointerMove(e.touches[0].clientX);
    };
    chartBox.ontouchend = onPointerLeave;
  }

  function updateScrubReadout(idx, coord, meta) {
    const readoutWhen = document.getElementById("scrub-when");
    const readoutVal = document.getElementById("scrub-val");
    const readoutSub = document.getElementById("scrub-sub");

    if (!readoutVal || !currentSeriesData) return;

    const pt = currentSeriesData.points?.[idx] || {};
    const val = coord?.v != null ? coord.v : "—";
    const emoji = currentSeriesData.emoji?.[idx] || "🌤️";
    const text = currentSeriesData.text?.[idx] || "";

    if (readoutWhen) {
      readoutWhen.textContent = `${pt.label || 'Today'} • ${pt.time || ''}`;
    }
    readoutVal.innerHTML = `${emoji} ${val}<small>${meta.unit}</small>`;

    if (readoutSub) {
      readoutSub.innerHTML = `
        <span class="pill">${escapeHtml(text)}</span>
        <span class="pill">📍 ${escapeHtml(currentLocation.name)}</span>
      `;
    }
  }

  // ===================================================================
  // 14. Toast Helpers & App Initialization
  // ===================================================================
  function showToast(msg, isError = false) {
    const container = document.getElementById("toasts");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${isError ? 'err' : ''}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
  }

  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMarkdown(str) {
    if (!str) return "";
    let raw = String(str).trim();

    // Escape basic HTML characters first
    let out = raw
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Bold: **text** or __text__
    out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/__(.+?)__/g, '<strong>$1</strong>');

    // Italic: *text* or _text_
    out = out.replace(/(^|[^\*])\*([^\*\n]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');
    out = out.replace(/(^|[^_])_([^_\n]+)_([^_]|$)/g, '$1<em>$2</em>$3');

    // Bullet list items (- item or * item)
    out = out.replace(/(?:^|\n)\s*[\*\-]\s+(.+)/g, (match, item) => {
      return `\n<li class="chat-li">${item}</li>`;
    });
    out = out.replace(/(<li class="chat-li"[\s\S]+?<\/li>)+/g, '<ul class="chat-ul">$&</ul>');

    // Numbered list items (1. item)
    out = out.replace(/(?:^|\n)\s*(\d+)\.\s+(.+)/g, (match, num, item) => {
      return `\n<li class="chat-oli"><span class="chat-num">${num}.</span> <span>${item}</span></li>`;
    });
    out = out.replace(/(<li class="chat-oli"[\s\S]+?<\/li>)+/g, '<ul class="chat-ol">$&</ul>');

    // Paragraph breaks
    const parts = out.split(/\n\s*\n/).filter(p => p.trim());
    return parts.map(p => {
      if (p.startsWith("<ul") || p.startsWith("<ol")) return p;
      return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join("");
  }

  async function refreshActiveView() {
    currentBriefingData = null;
    currentSeriesData = null;
    if (currentTab === "chat") await renderChatBriefing();
    if (currentTab === "advisory") await renderAdvisoryView();
    if (currentTab === "alerts") await renderAlertsView();
    if (currentTab === "map") await renderMapView();
    if (currentTab === "trends") await renderTrendsView();
  }

  // Periodic pulse every 3 minutes
  clearInterval(weatherPulseTimer);
  weatherPulseTimer = setInterval(async () => {
    if (currentTab === "chat") {
      const pulse = await api.getPulse(currentLocation.lat, currentLocation.lon, currentLocation.name, currentPersona);
      if (pulse?.suggestions) renderSuggestionChips(pulse.suggestions);
    }
  }, 180000);

  // Initialize Google Sign-in if configured
  function initGoogleSignIn() {
    const slot = document.getElementById("google-signin-slot");
    if (!slot || !cfg.GOOGLE_CLIENT_ID || typeof google === "undefined" || !google.accounts?.id) {
      return;
    }
    try {
      google.accounts.id.initialize({
        client_id: cfg.GOOGLE_CLIENT_ID,
        callback: async (response) => {
          if (response.credential) {
            showToast("Verifying Google account…");
            const res = await api.verifyGoogleLogin(response.credential);
            if (res && res.user) {
              slot.innerHTML = `
                <div class="user-chip" title="${escapeHtml(res.user.email || '')}">
                  <img src="${res.user.picture || 'https://via.placeholder.com/26'}" alt="${escapeHtml(res.user.name)}">
                  <span>${escapeHtml((res.user.name || 'User').split(' ')[0])}</span>
                </div>
              `;
              showToast(`Welcome back, ${res.user.name}!`);
            }
          }
        }
      });
      google.accounts.id.renderButton(slot, {
        theme: "outline",
        size: "small",
        type: "icon",
        shape: "circle"
      });
    } catch (e) {
      console.warn("Google Sign-in init:", e);
    }
  }

  initGoogleSignIn();
  window.addEventListener("load", () => setTimeout(initGoogleSignIn, 600));

  // Initial load
  try {
    loadAllPlaces();
    updateLocbarDisplay();
    renderChatBriefing();
  } catch (err) {
    console.error("Initial load error:", err);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startWeatherApp);
} else {
  startWeatherApp();
}

