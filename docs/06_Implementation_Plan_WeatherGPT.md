# Implementation Plan
## WeatherGPT — Hackathon Build Roadmap

---

### Phase 0: Setup (Hours 0–2)
- Repo scaffold: FastAPI backend, React Native app shell, PostgreSQL+PostGIS + MongoDB + Redis via Docker Compose
- Register API keys: OpenWeatherMap, NASA POWER, IMD (public endpoints), chosen LLM (Gemini/OpenAI), Twilio/Exotel, IndicTrans2 or Google Translate
- Define shared intent schema `{location, time_window, parameter, persona_context}` used across all downstream services

### Phase 1: Core Query Pipeline (Hours 2–10)
- FastAPI endpoint: `/query` accepting text input
- LLM intent extraction (prompt-engineered, structured JSON output)
- Data router: current conditions → OpenWeatherMap; historical → NASA POWER
- Response composer: LLM formats final natural-language answer
- Basic React Native chat UI wired to `/query`
- **Milestone:** typed English query → correct weather answer end-to-end

### Phase 2: Multilingual Layer (Hours 10–16)
- Language detection on input
- STT integration (Whisper) for voice input
- Translation pipeline (IndicTrans2/Google Translate) both directions
- TTS for spoken response
- **Milestone:** Hindi/Kannada voice query → correct spoken regional-language answer

### Phase 3: Alerts & Real-Time Layer (Hours 16–22)
- IMD/NDMA bulletin ingestion (poll or webhook simulation for demo)
- PostGIS geo-match of affected users
- Push notification (FCM) integration
- WhatsApp Business API sandbox integration for alert broadcast
- **Milestone:** simulated cyclone bulletin → correctly geo-targeted push + WhatsApp alert fires

### Phase 4: Differentiator Features (Hours 22–30)
- Confidence scoring engine (rule-based v1: source agreement + recency)
- Crowd report submission endpoint + Hyperlocal Fusion correction logic (v1: simple weighted average override)
- IVR flow via Twilio/Exotel Studio (basic: call in → speak query → hear answer)
- Photo-to-insight (v1: basic image classification for cloud cover, cross-check against satellite data flag)
- **Milestone:** each differentiator demoable in isolation, even if not fully production-hardened

### Phase 5: UI/UX Polish (Hours 30–36)
- Live sky canvas background (Lottie/Rive, tied to fetched weather condition)
- Voice orb animation for mic input
- Alert takeover screen transition
- Confidence badge with pulse animation
- Persona-based advisory card phrasing

### Phase 6: Integration Testing & Demo Prep (Hours 36–40)
- End-to-end run-through: text query, voice query, IVR call, simulated alert
- Fallback path testing (LLM timeout → templated response; API rate limit → cache fallback)
- Prepare demo script: farmer voice query in regional language → advisory → simulated cyclone alert fan-out → dashboard view for disaster officer
- Slide deck: problem → architecture diagram → differentiators → live demo → future scope (full GFS/WRF integration, WIS2.0 compliance, national scale rollout)

### Team Role Split (suggested)
| Role | Responsibility |
|---|---|
| Backend/API | FastAPI, data aggregation, alert pipeline |
| AI/LLM | Intent extraction, response composition, confidence scoring |
| Mobile/Frontend | React Native app, animations, voice orb |
| Data/Geo | PostGIS schema, crowd-report fusion logic |
| Integrations | IVR (Twilio/Exotel), WhatsApp API, translation pipeline |
| Design | Sky canvas, motion assets, persona-based UX copy |

### Future Scope (Post-Hackathon)
- Full GFS/WRF NWP model integration for in-house forecasting
- WIS2.0-compliant data exchange with meteorological agencies
- MQTT-based IoT sensor ingestion (village-level weather stations)
- National-scale Kubernetes deployment with per-state data residency
- Gamified community reporter network with trust-score leaderboard
