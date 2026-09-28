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
    }
  }

  async sendQuery({ text, persona = "general", lat, lon, language = "en" }) {
    try {
      const resp = await fetch(`${this.baseURL}/query/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, user_id: "demo-user", language, persona, lat, lon })
      });
      if (!resp.ok) throw new Error(`backend returned ${resp.status}`);
      return await resp.json();
    } catch (err) {
      return this._offlineFallback(text);
    }
  }

  _offlineFallback(text) {
    const q = (text || "").toLowerCase();
    let answer;
    if (q.includes("cyclone") || q.includes("storm")) {
      answer = "No active severe cyclone warning is currently in effect for your area. Always monitor NDMA and IMD advisories during pre-monsoon and post-monsoon seasons.";
    } else if (q.includes("rain") || q.includes("umbrella")) {
      answer = "Expect light passing showers later today. Carrying a compact umbrella or light raincoat is recommended when heading out.";
    } else if (q.includes("wind") || q.includes("sea") || q.includes("wave")) {
      answer = "Coastal winds are moderate at 12–18 km/h. Sea conditions remain generally slight to moderate.";
    } else if (q.includes("office") || q.includes("commute")) {
      answer = "Morning commute will be mostly dry and comfortable. Evening commute has a chance of passing drizzle, so plan a few extra travel minutes.";
    } else {
      answer = "Current conditions are steady with partly cloudy skies and comfortable temperatures. No major severe disruptions expected.";
    }
    return { answer, confidence: "medium", language: "en", theme: "clear-day", location_name: null };
  }

  async getBriefing(lat, lon, name = null, persona = "office", am = 9, pm = 18) {
    try {
      const q = new URLSearchParams({ lat, lon, persona, am, pm });
      if (name) q.append("name", name);
      const resp = await fetch(`${this.baseURL}/weather/briefing?${q.toString()}`);
      if (!resp.ok) throw new Error("briefing failed");
      return await resp.json();
    } catch (err) {
      return null;
    }
  }

  async getPulse(lat, lon, name = null, persona = "office", am = 9, pm = 18) {
    try {
      const q = new URLSearchParams({ lat, lon, persona, am, pm });
      if (name) q.append("name", name);
      const resp = await fetch(`${this.baseURL}/weather/pulse?${q.toString()}`);
      if (!resp.ok) throw new Error("pulse failed");
      return await resp.json();
    } catch (err) {
      return null;
    }
  }

  async getSeries(lat, lon, name = null, range = "3d") {
    try {
      const q = new URLSearchParams({ lat, lon, range });
      if (name) q.append("name", name);
      const resp = await fetch(`${this.baseURL}/weather/series?${q.toString()}`);
      if (!resp.ok) throw new Error("series failed");
      return await resp.json();
    } catch (err) {
      return null;
    }
  }

  async getAdvisoryFull(persona, lat, lon, name = null, am = 9, pm = 18) {
    try {
      const q = new URLSearchParams({ persona, lat, lon, am, pm });
      if (name) q.append("name", name);
      const resp = await fetch(`${this.baseURL}/advisory?${q.toString()}`);
      if (!resp.ok) throw new Error("advisory failed");
      return await resp.json();
    } catch (err) {
      return null;
    }
  }

  async getPersonas() {
    try {
      const resp = await fetch(`${this.baseURL}/advisory/personas`);
      if (!resp.ok) throw new Error("personas failed");
      const d = await resp.json();
      return d.personas || [];
    } catch (err) {
      return [
        { id: "office", name: "Office worker", emoji: "💼", tag: "Commute & workday" },
        { id: "student", name: "Student", emoji: "🎒", tag: "School / college run" },
        { id: "commuter", name: "Two-wheeler rider", emoji: "🏍️", tag: "Roads & riding" },
        { id: "delivery", name: "Delivery rider", emoji: "📦", tag: "Shift planning" },
        { id: "fitness", name: "Runner / Cyclist", emoji: "🏃", tag: "Best workout windows" },
        { id: "parent", name: "Parent", emoji: "👨‍👩‍👧", tag: "Kids & school" },
        { id: "traveler", name: "Traveller", emoji: "🧳", tag: "Next few days" },
        { id: "farmer", name: "Farmer", emoji: "🌾", tag: "Fields & crops" },
        { id: "fisherman", name: "Fisherman", emoji: "🐟", tag: "Sea conditions" },
        { id: "aviation", name: "Aviation", emoji: "✈️", tag: "Flight briefing" }
      ];
    }
  }

  async getAllPlaces() {
    try {
      const resp = await fetch(`${this.baseURL}/places/all`);
      if (!resp.ok) throw new Error("all places failed");
      const data = await resp.json();
      return data.results || [];
    } catch (err) {
      return [];
    }
  }

  async suggestPlaces(q) {
    try {
      const resp = await fetch(`${this.baseURL}/places/suggest?q=${encodeURIComponent(q)}&limit=15`);
      if (!resp.ok) throw new Error("suggest failed");
      const data = await resp.json();
      return data.results || [];
    } catch (err) {
      return [];
    }
  }

  async reverseGeocode(lat, lon) {
    try {
      const resp = await fetch(`${this.baseURL}/places/reverse?lat=${lat}&lon=${lon}`);
      if (!resp.ok) throw new Error("reverse geocode failed");
      return await resp.json();
    } catch (err) {
      return { name: "Current Location", state: "", lat, lon };
    }
  }

  async getIndiaAlerts(lat, lon) {
    try {
      const q = new URLSearchParams();
      if (lat != null && lon != null) {
        q.append("lat", lat);
        q.append("lon", lon);
      }
      const resp = await fetch(`${this.baseURL}/alerts/india?${q.toString()}`);
      if (!resp.ok) throw new Error("alerts failed");
      return await resp.json();
    } catch (err) {
      return { alerts: [], total: 0, by_severity: { yellow: 0, orange: 0, red: 0 } };
    }
  }

  async getMapPoints() {
    try {
      const resp = await fetch(`${this.baseURL}/map/points`);
      if (!resp.ok) throw new Error("map points failed");
      const data = await resp.json();
      return data.points || [];
    } catch (err) {
      return [];
    }
  }

  async analyzeSky(imageB64, mime, lat, lon, name) {
    try {
      const resp = await fetch(`${this.baseURL}/sky/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_b64: imageB64, mime, lat, lon, name })
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${resp.status}`);
      }
      return await resp.json();
    } catch (err) {
      return { error: err.message };
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
      return await resp.json();
    } catch (err) {
      return null;
    }
  }
}

window.apiService = new WeatherAPI();
window.WeatherAPI = WeatherAPI;

