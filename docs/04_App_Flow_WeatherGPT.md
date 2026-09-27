# App Flow Document
## WeatherGPT

---

### 1. Onboarding Flow
```
Launch App
   → Language selection (auto-suggest from device locale)
   → Location permission (GPS) OR manual village/city text entry
   → Persona selection (Farmer / Fisherman / General / Aviation / Researcher / Disaster Officer)
      — drives which advisory phrasing + default query chips are shown
   → Optional: crop type / route / commute details (for personalized proactive alerts)
   → Land on Home/Conversation screen
```

### 2. Core Query Flow (Text or Voice)
```
User types or taps voice orb
   → [If voice] Speech captured → Whisper/regional STT → transcript
   → Language detected
   → [If not English] translated to pivot language for intent parsing
   → LLM extracts: {location, time_window, parameter, persona_context}
   → Router selects data source(s):
        current/short-term → OpenWeatherMap/IMD
        official warning → IMD/NDMA feed
        historical/trend → NASA POWER
        hyperlocal correction → Crowd Report Service (if available for that geohash)
   → Confidence Scoring Engine computes trust badge
   → LLM composes response in original language + persona tone
   → [If voice] TTS generates spoken response
   → Response rendered: text/voice + advisory card + confidence badge
   → Follow-up suggestion chips offered ("Tomorrow?", "Next 3 days?")
```

### 3. Proactive Agentic Alert Flow (Differentiator)
```
Background service monitors:
   - User's saved location(s)
   - Persona context (crop calendar / fishing route / commute window)
IMD/NDMA bulletin ingested
   → Geo-match against all registered users (PostGIS radius/polygon query)
   → Relevance filter (does this affect this user's persona/schedule?)
   → Priority queue assigns urgency tier
   → Dissemination fan-out:
        Tier 1 (severe): Push + WhatsApp + SMS + outbound IVR call, simultaneous
        Tier 2 (moderate): Push + WhatsApp
        Tier 3 (advisory): In-app notification only
   → Delivery acknowledgement tracked; unacknowledged Tier 1 alerts escalate channel after N minutes
```

### 4. Photo-to-Insight Flow (Differentiator)
```
User taps camera icon → captures sky/field photo
   → Image + geolocation sent to backend
   → Vision model extracts cloud density/type cues
   → Cross-referenced against satellite cloud cover data for that grid cell
   → If mismatch detected → logged as crowd-correction signal → feeds Hyperlocal Fusion layer
   → User receives immediate localized comment ("Matches satellite data — rain likely within the hour")
```

### 5. IVR / Feature-Phone Flow (Zero-Smartphone Access)
```
User dials toll-free/short-code number
   → IVR greets in detected/selected regional language
   → User speaks query naturally (no menu-tree navigation required)
   → STT → same LLM/data pipeline as app
   → TTS reads back response in regional language
   → Option: "Press 1 to receive future alerts for this location via call"
```

### 6. Community Feedback Loop Flow (Differentiator)
```
User submits ground report ("raining heavily here now") via voice note/text/photo
   → Tagged with geohash + timestamp
   → Weighted by user's historical report reliability score
   → Fed into Hyperlocal Fusion correction layer
   → Improves future forecast confidence for that micro-region
   → Contributing users optionally shown a "community trust score" (light gamification)
```

### 7. Disaster Manager / Researcher Web Console Flow
```
Login (role-based access)
   → Dashboard: live map of active alerts + acknowledgement rates
   → Query historical trend data via natural language ("rainfall trend last 5 monsoons, district X")
   → Trigger manual bulk alert override for a region if needed
   → Export report (PDF/CSV)
```
