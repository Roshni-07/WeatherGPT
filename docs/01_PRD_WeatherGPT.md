# Product Requirements Document (PRD)
## WeatherGPT — Conversational AI for Weather Forecasting, Alerts & Climate Information
**SIH 2025 | Problem Statement 26068**

---

### 1. Problem Statement (Plain Language)
Weather data today lives in a dozen scattered places — IMD bulletins, satellite portals, forecast apps, disaster helplines. A farmer, fisherman, or city commuter can't quickly get a straight answer to "will it rain on my field tomorrow?" or "is a cyclone coming?" WeatherGPT collapses all of this into one conversation — text, voice, or call — in the user's own language.

### 2. Vision
A single conversational assistant that any Indian — rural or urban, literate or not, smartphone or feature phone — can ask about weather and get an accurate, actionable, local-language answer in under 3 seconds.

### 3. Target Users
| Persona | Need |
|---|---|
| Farmer | Crop-specific advisory: spray, irrigate, harvest timing |
| Fisherman | Sea-state, wind, cyclone warnings for safe return |
| Aviation ops | Quick METAR/TAF-style briefing in natural language |
| Urban commuter | Rain-now, flooding risk, AQI |
| Disaster management officer | Bulk alert dissemination, historical trend queries |
| Researcher | Climate trend analysis, historical data queries |

### 4. Goals & Success Metrics
- **Latency:** < 3s for real-time query response
- **Language coverage:** 8+ Indian languages + English at MVP, expandable
- **Accessibility:** Works via app, WhatsApp, and plain phone call (IVR)
- **Alert reach:** Push + SMS + voice-call fallback for zero-connectivity users
- **Accuracy:** Forecast matches IMD ground truth within acceptable variance; system discloses confidence, never overclaims

### 5. Core Features (MVP)
1. Natural language weather query (text + voice)
2. Real-time current conditions + short-term forecast
3. Location-based advisory (auto-detect or manual village/city entry)
4. Extreme weather alert push (cyclone, flood, heatwave, thunderstorm)
5. Multilingual input/output (auto-detect language)
6. Historical/climate trend Q&A ("how much rain did this district get last monsoon?")
7. Voice-call (IVR) access for feature-phone users

### 6. Differentiating Features (Why We Win)
1. **Hyperlocal Fusion Advisory** — blends IMD gridded forecast with crowd-submitted ground reports (voice notes: "raining here now") to correct satellite blind spots at village level.
2. **Agentic Proactive Alerts** — doesn't wait to be asked. Learns user's crop cycle / fishing route / commute pattern and pushes a warning before the user thinks to ask.
3. **"Explain Why" Mode** — instead of just "70% rain chance," explains the meteorological cause in one simple sentence ("a low-pressure system from the Bay of Bengal is moving toward your district"), building public trust and weather literacy.
4. **Confidence-Scored Forecasts** — every answer carries a visible trust/confidence indicator instead of false certainty — a rarity among consumer weather tools.
5. **Zero-Smartphone Access** — plain voice call (IVR) in regional language, no app or data plan required — true last-mile reach.
6. **Photo-to-Insight** — user sends a sky/field photo; model cross-validates against satellite cloud cover for hyperlocal confirmation.
7. **Decision-Support Phrasing** — outputs actions, not just data: "spray before 3 PM, rain expected after" rather than a raw percentage.
8. **Community Feedback Loop** — verified ground reports continuously retrain the hyperlocal correction layer — accuracy compounds with usage (network effect).

### 7. Out of Scope (MVP)
- Full custom NWP model training (use existing GFS/IMD outputs, not building new weather physics)
- Global coverage (India-first)
- Paid/commercial tiering

### 8. Constraints
- Must work on low-bandwidth 2G/3G rural networks
- Must degrade gracefully with no internet (IVR/SMS fallback)
- Data licensing: must use publicly permitted IMD/OpenWeather/NASA sources

### 9. Evaluation Alignment (per problem statement)
Accuracy & relevance, response latency, multilingual capability, UI/accessibility, scalability, real-time system integration, voice accessibility — each mapped to a corresponding feature above.
