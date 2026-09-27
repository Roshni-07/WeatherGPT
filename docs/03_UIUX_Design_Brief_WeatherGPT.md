# UI/UX Design Brief
## WeatherGPT

---

### 1. Design Philosophy
Not a "chatbot with a blue theme." WeatherGPT should feel like **looking at the sky through glass** — living, atmospheric, alive. The interface should visually *react* to real weather: subtle rain particles when it's raining at the user's location, drifting clouds on overcast days, a warm gradient shift at sunset. Motion is a data channel, not decoration.

Avoid: generic SaaS blue/purple gradients, flat weather-icon-pack look, static cards.
Aim for: cinematic, tactile, ambient — closer to a premium climate/atmosphere app than a utility tool.

### 2. Visual Identity
- **Color system:** dynamic, time- and weather-reactive palette — not a fixed brand blue.
  - Clear day: warm amber → soft sky cyan gradient
  - Rain: desaturated slate with animated rain-streak overlay
  - Storm/alert: deep charcoal + amber-red pulse accents (urgency without panic)
  - Night: indigo-to-black gradient with subtle star particles
- **Typography:** a humanist sans for warmth (e.g., a variable-weight font) for conversational text; a condensed technical mono for data readouts (temperature, wind speed) to signal precision.
- **Depth:** soft glassmorphism panels (frosted blur) floating over the live animated background — not flat cards.

### 3. Signature Motion Elements (the "vibe" differentiators)
1. **Live sky canvas** — background is a lightweight animated canvas/Lottie/Rive layer reflecting real current conditions at the user's location (cloud drift speed tied to actual wind speed data).
2. **Breathing confidence badge** — the High/Medium/Low confidence indicator has a subtle pulse animation, reinforcing "this is a living estimate," not a dead fact.
3. **Voice orb** — mic input isn't a static button; it's a soft glowing orb that ripples in sync with the user's voice amplitude while listening, and morphs into a waveform while processing.
4. **Alert takeover transition** — a severe weather alert doesn't just pop a banner; the entire screen ambient color shifts over 400ms to the alert palette with a soft haptic pulse, then reveals the warning card — clear escalation of visual urgency.
5. **Micro-interactions on data** — tapping a temperature number "un-crumples" into a 7-day trend sparkline with spring physics, not an instant cut.

### 4. Core Screens
1. **Home / Conversation** — chat-first interface, live sky canvas background, quick-chip suggestions ("Will it rain today?", "Cyclone update").
2. **Advisory Card** — persona-aware (farmer/fisherman/commuter) actionable card with icon + one-line action + confidence badge.
3. **Alert Screen** — full-bleed takeover for severe warnings, large legible type, share/call-emergency-services shortcut.
4. **Map/Location View** — PostGIS-backed radius view showing hyperlocal crowd reports as glowing pins over satellite cloud layer.
5. **Voice Mode (IVR-parity in-app)** — full-screen orb interface for hands-free rural use, minimal text, icon-led.
6. **History/Trends** — scrollable climate trend view with animated chart draw-in for researcher persona.

### 5. Accessibility & Rural-First UX
- Icon-first, text-secondary layout for low-literacy users
- Large tap targets, high contrast mode toggle
- Regional language font rendering tested for Devanagari, Tamil, Telugu, Kannada, Bengali scripts (no clipped glyphs)
- Voice-first flow always available as parallel path to every text screen
- Works acceptably at 2G data speeds — canvas animation degrades to static illustration below a bandwidth threshold

### 6. Tone of Voice
Calm, plain-spoken, never alarmist except during genuine severe alerts. Advisory language, not raw meteorological jargon ("good day to sow" not "72% probability of precipitation exceeding 2.5mm").

### 7. Recommended Build Approach
Prototype the animated sky canvas and voice orb first (these are the "wow" demo moments for judges) using Lottie/Rive or a lightweight Canvas/WebGL layer in React Native — keep it performant on mid-range Android devices, the real target hardware in rural India.
