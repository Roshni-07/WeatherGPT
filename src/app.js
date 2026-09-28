// Global dismissal function for inline fallback resilience
window.dismissAlertBanner = function() {
  const takeover = document.getElementById("alert-takeover");
  if (takeover) {
    takeover.hidden = true;
    takeover.style.display = "none";
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const api = window.apiService;
  const cfg = window.WEATHERGPT_CONFIG || {};

  // ---- App state -----------------------------------------------------
  let currentLocation = cfg.DEFAULT_LOCATION || { name: "Bengaluru", lat: 12.9716, lon: 77.5946 };
  let currentTheme = "clear-day";
  let currentPersona = "farmer";

  // ---- Background Motion Canvas (fix: previously only "rain"/"storm"
  // themes had any animation at all -- clear-day and night rendered a
  // blank canvas). Now every theme has real motion. -------------------
  const canvas = document.getElementById("weather-canvas");
  const ctx = canvas?.getContext("2d");
  let width, height;
  let rainParticles = [], clouds = [], stars = [];

  function resizeCanvas() {
    if (!canvas) return;
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    initParticles();
  }

  function initParticles() {
    const density = api?.is2G ? 0.3 : 1;

    rainParticles = Array.from({ length: Math.round(50 * density) }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      length: Math.random() * 20 + 10,
      speed: Math.random() * 10 + 5
    }));

    clouds = Array.from({ length: Math.round(6 * density) }, () => ({
      x: Math.random() * width,
      y: Math.random() * height * 0.5,
      r: Math.random() * 60 + 40,
      speed: Math.random() * 0.15 + 0.05
    }));

    stars = Array.from({ length: Math.round(60 * density) }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      r: Math.random() * 1.5 + 0.5,
      twinkleOffset: Math.random() * Math.PI * 2
    }));
  }

  function renderCanvas(t) {
    if (!ctx) { requestAnimationFrame(renderCanvas); return; }
    ctx.clearRect(0, 0, width, height);

    if (currentTheme === "rain" || currentTheme === "storm") {
      ctx.strokeStyle = currentTheme === "storm" ? "rgba(220, 80, 60, 0.4)" : "rgba(112, 200, 210, 0.5)";
      ctx.lineWidth = 1.5;
      for (const p of rainParticles) {
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x, p.y + p.length);
        ctx.stroke();
        p.y += p.speed;
        if (p.y > height) { p.y = -20; p.x = Math.random() * width; }
      }
    } else if (currentTheme === "night") {
      for (const s of stars) {
        const twinkle = 0.5 + 0.5 * Math.sin((t || 0) / 800 + s.twinkleOffset);
        ctx.beginPath();
        ctx.fillStyle = `rgba(255,255,255,${0.3 + 0.5 * twinkle})`;
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      // clear-day: soft drifting cloud blobs
      ctx.fillStyle = "rgba(255,255,255,0.05)";
      for (const c of clouds) {
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2);
        ctx.fill();
        c.x += c.speed;
        if (c.x - c.r > width) c.x = -c.r;
      }
    }

    requestAnimationFrame(renderCanvas);
  }

  function setTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute("data-theme", theme);
  }

  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();
  requestAnimationFrame(renderCanvas);
  dismissAlertBanner();

  // ---- Confidence badge -----------------------------------------------
  function setConfidenceBadge(label) {
    const el = document.getElementById("confidence-indicator");
    if (!el) return;
    el.classList.remove("high", "medium", "low");
    el.classList.add(label || "low");
    const text = el.querySelector(".badge-label");
    if (text) text.textContent = `${(label || "unknown").toUpperCase()} confidence`;
  }

  // ---- Location bar (fix: app previously had no real location concept
  // at all -- everything was hardcoded region names in canned strings) --
  const detectBtn = document.getElementById("detect-location-btn");
  const locationInput = document.getElementById("location-search");
  const locationLabel = document.getElementById("current-location-label");
  const suggestionsBox = document.getElementById("location-suggestions");

  function updateLocationLabel() {
    if (locationLabel) locationLabel.textContent = `📍 ${currentLocation.name}`;
  }

  async function refreshThemeForLocation() {
    const weather = await api.getCurrentWeatherTheme(currentLocation.lat, currentLocation.lon);
    setTheme(weather.theme || "clear-day");
  }

  detectBtn?.addEventListener("click", () => {
    if (!navigator.geolocation) return;
    detectBtn.textContent = "Locating...";
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const { latitude: lat, longitude: lon } = pos.coords;
      const place = await api.reverseGeocode(lat, lon);
      currentLocation = { name: place?.name || "Current location", lat, lon };
      updateLocationLabel();
      detectBtn.textContent = "📍 Use my location";
      await refreshThemeForLocation();
      renderAdvisory(currentPersona);
    }, () => {
      detectBtn.textContent = "📍 Use my location";
      alert("Location permission denied or unavailable.");
    });
  });

  let searchDebounce;
  locationInput?.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    const q = locationInput.value.trim();
    if (q.length < 2) { suggestionsBox.classList.remove("visible"); return; }
    searchDebounce = setTimeout(async () => {
      const results = await api.searchLocation(q);
      if (!results.length) { suggestionsBox.classList.remove("visible"); return; }
      suggestionsBox.innerHTML = results.map((r, i) =>
        `<div data-idx="${i}">${r.name}${r.state ? ", " + r.state : ""}, ${r.country}</div>`
      ).join("");
      suggestionsBox.classList.add("visible");
      suggestionsBox.querySelectorAll("div").forEach((el, i) => {
        el.addEventListener("click", async () => {
          const r = results[i];
          currentLocation = { name: r.name, lat: r.lat, lon: r.lon };
          locationInput.value = "";
          suggestionsBox.classList.remove("visible");
          updateLocationLabel();
          await refreshThemeForLocation();
          renderAdvisory(currentPersona);
        });
      });
    }, 350);
  });

  updateLocationLabel();
  refreshThemeForLocation();

  // ---- Bottom Rail Navigation ------------------------------------------
  const navItems = document.querySelectorAll(".nav-item");
  const viewPanels = document.querySelectorAll(".view-panel");

  navItems.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetView = btn.getAttribute("data-target");
      navItems.forEach(i => i.classList.remove("active"));
      viewPanels.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(targetView)?.classList.add("active");

      if (targetView === "view-advisory") renderAdvisory(currentPersona);
      if (targetView === "view-trends") renderTrends(document.querySelector(".metric-btn.active")?.getAttribute("data-metric") || "precipitation");
    });
  });

  // ---- Persona-aware Advisory (now backed by a real query, not a dict) --
  const advisoryContainer = document.getElementById("advisory-card-content");
  const personaBtns = document.querySelectorAll(".persona-btn");

  async function renderAdvisory(persona) {
    if (!advisoryContainer) return;
    currentPersona = persona;
    advisoryContainer.innerHTML = `<p class="ai-text">Fetching live advisory...</p>`;
    const data = await api.getAdvisory(persona, currentLocation.lat, currentLocation.lon);
    setTheme(data.theme);
    setConfidenceBadge(data.confidence);

    advisoryContainer.innerHTML = `
      <div class="advisory-header">
        <h3 class="advisory-title">${data.title}</h3>
        <span class="confidence-badge ${data.confidence}">${data.confidence.toUpperCase()}</span>
      </div>
      <p class="advisory-body">${data.body}</p>
    `;
  }

  personaBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      personaBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderAdvisory(btn.getAttribute("data-persona"));
    });
  });

  // ---- Map filter tabs (fix: buttons existed in HTML with zero listeners) --
  const mapFilters = document.querySelectorAll(".map-filter");
  const mapCanvas = document.getElementById("interactive-map-canvas");

  mapFilters.forEach(btn => {
    btn.addEventListener("click", () => {
      mapFilters.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      mapCanvas?.setAttribute("data-layer", btn.getAttribute("data-layer"));
    });
  });

  // ---- Trends metric tabs (fix: buttons existed with zero listeners --
  // chart only ever rendered "precipitation" once on view switch) --------
  const metricBtns = document.querySelectorAll(".metric-btn");
  metricBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      metricBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderTrends(btn.getAttribute("data-metric"));
    });
  });

  async function renderTrends(metric) {
    const chartWrapper = document.getElementById("trends-chart-wrapper");
    if (!chartWrapper) return;
    const data = await api.getTrends(metric);
    const max = Math.max(...data.values, 1);
    const points = data.values.map((v, i) => {
      const x = (i / (data.values.length - 1)) * 300 + 20;
      const y = 120 - (v / max) * 90;
      return `${x},${y}`;
    }).join(' ');

    chartWrapper.innerHTML = `
      <svg viewBox="0 0 340 150" style="width: 100%; height: 160px;">
        <polyline fill="none" stroke="var(--accent-weather)" stroke-width="3" points="${points}" />
        ${data.values.map((v, i) => {
          const x = (i / (data.values.length - 1)) * 300 + 20;
          const y = 120 - (v / max) * 90;
          return `<circle cx="${x}" cy="${y}" r="4" fill="var(--ks-champagne)" />`;
        }).join('')}
      </svg>
      <div style="display:flex;justify-content:space-between;font-family:var(--ks-font-mono);font-size:0.75rem;color:var(--ks-text-muted);margin-top:8px;">
        ${data.labels.map(l => `<span>${l}</span>`).join('')}
      </div>
    `;
  }

  // ---- Chat (fix: always hit a dead external domain and fell back to
  // one hardcoded string no matter what was typed) -----------------------
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatStream = document.getElementById("chat-stream");

  async function submitQuery(query) {
    if (!query || !chatStream) return;

    const userMsg = document.createElement("div");
    userMsg.className = "chat-message user-message";
    userMsg.innerHTML = `<div class="message-bubble">${query}</div>`;
    chatStream.appendChild(userMsg);
    chatStream.scrollTop = chatStream.scrollHeight;

    const aiMsg = document.createElement("div");
    aiMsg.className = "chat-message ai-message";
    aiMsg.innerHTML = `<div class="message-avatar">AI</div><div class="message-bubble"><p class="ai-text">Checking live data...</p></div>`;
    chatStream.appendChild(aiMsg);
    chatStream.scrollTop = chatStream.scrollHeight;

    const result = await api.sendQuery({
      text: query,
      persona: currentPersona,
      lat: currentLocation.lat,
      lon: currentLocation.lon
    });

    const aiText = aiMsg.querySelector(".ai-text");
    if (aiText) aiText.textContent = result.answer;
    setConfidenceBadge(result.confidence);
    if (result.theme) setTheme(result.theme);
    chatStream.scrollTop = chatStream.scrollHeight;
  }

  chatForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = chatInput?.value.trim();
    chatInput.value = "";
    submitQuery(query);
  });

  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => submitQuery(chip.getAttribute("data-query") || ""));
  });

  // ---- Voice Mode: real browser speech recognition (fix: previously a
  // fake toggle that always showed the same canned transcript) -----------
  const voiceOrb = document.getElementById("voice-orb-btn");
  const voiceStatus = document.getElementById("voice-status");
  const voiceTranscript = document.getElementById("voice-transcript");
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let isListening = false;

  if (SpeechRecognitionImpl) {
    recognizer = new SpeechRecognitionImpl();
    recognizer.continuous = false;
    recognizer.interimResults = true;
    recognizer.lang = "en-IN"; // browser STT language; swap per selected UI language

    recognizer.onresult = (event) => {
      const transcript = Array.from(event.results).map(r => r[0].transcript).join(" ");
      if (voiceTranscript) voiceTranscript.textContent = `"${transcript}"`;
    };
    recognizer.onend = () => {
      isListening = false;
      voiceOrb?.classList.remove("listening");
      if (voiceStatus) voiceStatus.textContent = "Tap Orb to Listen";
      const finalText = voiceTranscript?.textContent?.replace(/"/g, "").trim();
      if (finalText) submitQuery(finalText);
    };
    recognizer.onerror = () => {
      isListening = false;
      voiceOrb?.classList.remove("listening");
      if (voiceStatus) voiceStatus.textContent = "Tap Orb to Listen";
    };
  }

  voiceOrb?.addEventListener("click", () => {
    if (!recognizer) {
      if (voiceStatus) voiceStatus.textContent = "Speech recognition not supported in this browser";
      return;
    }
    if (isListening) {
      recognizer.stop();
      return;
    }
    isListening = true;
    voiceOrb.classList.add("listening");
    if (voiceStatus) voiceStatus.textContent = "Listening...";
    if (voiceTranscript) voiceTranscript.textContent = '"Speak now..."';
    recognizer.start();
  });

  // ---- Google Sign-In ----------------------------------------------------
  function initGoogleSignIn() {
    if (!window.google?.accounts?.id || !cfg.GOOGLE_CLIENT_ID || cfg.GOOGLE_CLIENT_ID.startsWith("REPLACE_")) {
      return; // not configured yet -- silently skip rather than error
    }
    window.google.accounts.id.initialize({
      client_id: cfg.GOOGLE_CLIENT_ID,
      callback: async (response) => {
        const profile = await api.verifyGoogleLogin(response.credential);
        const slot = document.getElementById("google-signin-slot");
        if (profile && slot) {
          slot.innerHTML = `<div class="user-chip"><img src="${profile.picture}" alt=""><span>${profile.name}</span></div>`;
        }
      }
    });
    window.google.accounts.id.renderButton(
      document.getElementById("google-signin-slot"),
      { theme: "filled_black", size: "medium", type: "standard" }
    );
  }
  // Google's script loads async -- retry briefly until it's ready.
  let gsiAttempts = 0;
  const gsiInterval = setInterval(() => {
    gsiAttempts++;
    if (window.google?.accounts?.id || gsiAttempts > 20) {
      clearInterval(gsiInterval);
      initGoogleSignIn();
    }
  }, 250);

  // ---- Misc --------------------------------------------------------------
  document.getElementById("alert-dismiss-btn")?.addEventListener("click", dismissAlertBanner);
  document.getElementById("contrast-toggle")?.addEventListener("click", () => {
    document.body.classList.toggle("high-contrast");
  });

  renderAdvisory("farmer");
});
