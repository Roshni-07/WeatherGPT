# Technical Requirements Document (TRD)
## WeatherGPT

---

### 1. System Overview
WeatherGPT is a multi-channel conversational layer (App / WhatsApp / IVR) sitting on top of an orchestration backend that fuses LLM query understanding with real meteorological data sources, returning localized, multilingual, confidence-scored responses.

### 2. High-Level Architecture

```
[User Channels]
 ├── Mobile App (React Native)
 ├── WhatsApp Business API
 └── IVR / Voice Call (Twilio/Exotel + regional STT-TTS)
        │
        ▼
[API Gateway / FastAPI]
        │
        ▼
[Language Layer]
 ├── Language Detection
 ├── Speech-to-Text (Whisper / Google STT)
 └── Translation (IndicTrans2 / Google Translate)
        │
        ▼
[LLM Orchestration Layer]
 ├── Intent & Entity Extraction (location, time, weather-type, persona)
 ├── Query Router
 └── Response Generator (LLM: Gemini/Llama/GPT — pluggable)
        │
        ▼
[Data Aggregation Layer]
 ├── IMD API (bulletins, warnings)
 ├── OpenWeatherMap / NASA POWER (current + historical)
 ├── GFS/NOMADS (raw NWP grid, future scope)
 ├── Crowd Report Service (hyperlocal correction)
 └── Confidence Scoring Engine
        │
        ▼
[Alert & Dissemination Engine]
 ├── FCM Push (app)
 ├── WhatsApp broadcast
 ├── SMS Gateway
 └── Outbound IVR call trigger
        │
        ▼
[Persistence Layer]
 ├── PostgreSQL + PostGIS (structured, geo)
 ├── MongoDB (chat logs, unstructured)
 └── Redis (cache, session state)
```

### 3. Technology Stack
| Layer | Tech |
|---|---|
| Backend framework | FastAPI (Python) |
| Real-time transport | WebSocket for app; MQTT for future sensor/IoT ingestion; WIS2.0-aligned message schema for interoperability with met agencies |
| LLM | Gemini 1.5 / Llama 3 / GPT-4o — abstracted via a model-agnostic wrapper |
| STT/TTS | Whisper (STT), Google Cloud TTS / Bhashini (Indian language TTS) |
| Translation | IndicTrans2 (offline-capable, India-tuned), Google Translate API fallback |
| Weather data | IMD public API, OpenWeatherMap, NASA POWER, NOAA GFS/NOMADS |
| Geo | PostGIS, GeoPandas for spatial joins (village → grid cell mapping) |
| Databases | PostgreSQL (structured/geo), MongoDB (chat/unstructured), Redis (cache/session) |
| Messaging/Alerts | Firebase Cloud Messaging, WhatsApp Business API, Twilio/Exotel (SMS + voice) |
| Containerization | Docker, Kubernetes (horizontal scaling of API + worker pods) |
| Frontend | React Native (mobile), lightweight React/Next.js web console for disaster managers |

### 4. Non-Functional Requirements
- **Latency:** end-to-end response < 3s for cached/common queries, < 6s for cold LLM+data fetch
- **Availability:** 99.5% target for alert dissemination path (highest priority path)
- **Scalability:** stateless API pods behind load balancer; horizontal auto-scale under alert-storm conditions (e.g., cyclone landfall spike in query volume)
- **Data freshness:** weather cache TTL 10–15 min for current conditions; alerts pushed near-real-time on IMD bulletin ingestion (webhook/poll)
- **Security:** API key rotation, rate limiting per user, PII minimization (location stored as geohash, not raw address, where possible)
- **Offline degradation:** last fetched forecast cached locally in app for offline viewing; IVR works with zero data connectivity

### 5. Query Understanding Engine (Core AI Component)
1. Language ID → route to correct STT/translation pipeline
2. LLM extracts structured intent: `{location, time_window, weather_parameter, persona_context}`
3. Router decides data source(s): current conditions → OpenWeatherMap; official warning → IMD; historical trend → NASA POWER; hyperlocal correction → crowd report service
4. Aggregator merges sources, computes confidence score (based on source agreement + recency + crowd-report corroboration)
5. LLM composes final natural-language response in original query language, in persona-appropriate tone (farmer advisory vs. aviation briefing vs. general public)

### 6. Confidence Scoring (Differentiator, technical detail)
`confidence = f(source_agreement, data_recency, spatial_resolution_gap, crowd_corroboration_count)`
Displayed to user as High/Medium/Low badge — never a bare probability number without context.

### 7. Alert Pipeline (Critical Path)
IMD/NDMA bulletin ingested (webhook or scheduled poll) → geo-matched to affected user base (PostGIS radius/polygon query) → prioritized queue → multi-channel fan-out (push → WhatsApp → SMS → IVR outbound call, escalating channel if previous unacknowledged) within defined SLA window.

### 8. Failure Modes & Mitigation
| Failure | Mitigation |
|---|---|
| LLM API downtime | Fallback to templated rule-based response using cached data |
| Weather API rate-limited | Multi-provider fallback chain + Redis cache |
| No internet (rural) | IVR/SMS channel unaffected by app connectivity |
| Translation inaccuracy | Confidence flag + option to switch to English/simplified mode |
