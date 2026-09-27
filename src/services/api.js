class WeatherAPI {
  constructor() {
    const cfg = window.WEATHERGPT_CONFIG || {};
    this.baseURL = cfg.BACKEND_URL || "http://localhost:8000";
    this.is2G = false;
    this.checkConnectionQuality();
  }

  checkConnectionQuality() {
    if (navigator.connection) {
      this.is2G = navigator.connection.effectiveType === '2g' || navigator.connection.saveData;
      if (this.is2G) {
        document.getElementById('network-badge')?.classList.add('visible');
      }
    }
  }

  // Real query call to the FastAPI backend. Replaces the old fixed-domain
  // (api.weathergpt.in) call that never resolved and always fell through
  // to one hardcoded string regardless of what was asked.
  async sendQuery({ text, persona = "general", lat, lon, language = "en" }) {
    try {
      const resp = await fetch(`${this.baseURL}/query/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, user_id: "demo-user", language, persona, lat, lon })
      });
      if (!resp.ok) throw new Error(`backend returned ${resp.status}`);
      return await resp.json(); // { answer, confidence, language, theme, location_name }
    } catch (err) {
      // Backend not running -- degrade honestly, and still vary the reply
      // by keyword match instead of returning one fixed sentence for
      // every query.
      return this._offlineFallback(text);
    }
  }

  _offlineFallback(text) {
    const q = (text || "").toLowerCase();
    let answer;
    if (q.includes("cyclone") || q.includes("storm")) {
      answer = "Offline preview: no live cyclone data available -- start the backend to check the current NDMA/IMD bulletin.";
    } else if (q.includes("rain")) {
      answer = "Offline preview: rain outlook needs a live connection -- start the backend for a real forecast.";
    } else if (q.includes("wind") || q.includes("sea") || q.includes("wave")) {
      answer = "Offline preview: sea-state/wind data needs a live connection -- start the backend for real values.";
    } else {
      answer = "Offline preview mode -- start the backend (docker compose up) for real weather answers.";
    }
    return { answer, confidence: "low", language: "en", theme: "clear-day", location_name: null };
  }

  async getCurrentWeatherTheme(lat, lon) {
    try {
      const resp = await fetch(`${this.baseURL}/weather/current?lat=${lat}&lon=${lon}`);
      if (!resp.ok) throw new Error("weather endpoint failed");
      return await resp.json(); // { theme, condition, temp_c, wind_speed_ms, location_name, ... }
    } catch (err) {
      return { theme: "clear-day", condition: "unavailable", temp_c: null, location_name: null };
    }
  }

  async searchLocation(query) {
    try {
      const resp = await fetch(`${this.baseURL}/geocode/search?q=${encodeURIComponent(query)}`);
      if (!resp.ok) throw new Error("geocode search failed");
      const data = await resp.json();
      return data.results || [];
    } catch (err) {
      return [];
    }
  }

  async reverseGeocode(lat, lon) {
    try {
      const resp = await fetch(`${this.baseURL}/geocode/reverse?lat=${lat}&lon=${lon}`);
      if (!resp.ok) throw new Error("reverse geocode failed");
      return await resp.json();
    } catch (err) {
      return null;
    }
  }

  async verifyGoogleLogin(idToken) {
    try {
      const resp = await fetch(`${this.baseURL}/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: idToken })
      });
      if (!resp.ok) throw new Error("token rejected");
      return await resp.json(); // { sub, email, name, picture }
    } catch (err) {
      return null;
    }
  }

  // Still-mocked persona advisories, now driven by a real query call
  // instead of a static hardcoded dict.
  async getAdvisory(persona, lat, lon) {
    const personaQueries = {
      farmer: "Give me a crop and field advisory for today.",
      fisherman: "Give me the sea state and fishing advisory for today.",
      commuter: "Give me a commute and traffic-relevant weather advisory for today.",
      aviation: "Give me a flight briefing: wind, visibility, and wind shear."
    };
    const result = await this.sendQuery({
      text: personaQueries[persona] || personaQueries.farmer,
      persona,
      lat,
      lon
    });
    return {
      title: this._titleFor(persona, result.location_name),
      confidence: result.confidence,
      theme: result.theme,
      body: result.answer,
      actions: []
    };
  }

  _titleFor(persona, place) {
    const p = place || "your area";
    const labels = {
      farmer: `🌾 Field Advisory — ${p}`,
      fisherman: `🐟 Sea State — ${p}`,
      commuter: `🚗 Commute Outlook — ${p}`,
      aviation: `✈️ Flight Briefing — ${p}`
    };
    return labels[persona] || labels.farmer;
  }

  async getTrends(metric = 'precipitation') {
    // TODO: replace with a real /weather/forecast-backed 7-day series once
    // the forecast endpoint is wired to the Trends screen.
    return {
      metric,
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      values: metric === 'precipitation' ? [0, 12, 45, 80, 10, 0, 5]
             : metric === 'wind' ? [8, 12, 15, 22, 18, 10, 9]
             : [28, 29, 27, 24, 26, 30, 31]
    };
  }
}

window.apiService = new WeatherAPI();
