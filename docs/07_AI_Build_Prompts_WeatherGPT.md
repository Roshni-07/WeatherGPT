# AI Build Prompts — WeatherGPT

Copy-paste ready. Each feeds a specific free-tier AI for a specific module. Paste the relevant repo files (schema, existing stub) into the same chat before running each prompt so the AI writes against your real contract, not a guess.

---

## 1. Backend core (feed to: Claude / Gemini / any strong code-gen model)

```
You are building the backend for WeatherGPT, a FastAPI conversational weather platform.

Context: intent contract lives at ml/schemas/intent.json. Stub routers exist at
backend/app/routers/query.py and alerts.py.

Task: implement backend/app/services/intent_extraction.py that:
- takes raw user text (already translated to English) and a persona hint
- calls the Gemini API (google-generativeai SDK) with a structured-output prompt
- returns a dict matching intent.json exactly, validated with pydantic
- raises a clear error if the model returns invalid JSON, with one retry

Also implement backend/app/services/data_router.py that:
- takes a validated intent dict
- routes to OpenWeatherMap (current/short-term), NASA POWER (historical), or IMD
  bulletin cache (warnings) based on intent["parameter"] and intent["time_window"]
- returns a normalized dict: {source, fetched_at, raw_payload}
- reads all API keys from environment variables, never hardcoded

Wire both into routers/query.py replacing the stub logic.
Use httpx.AsyncClient for all external calls. Add basic error handling and a 5s timeout.
Write it production-clean, typed, with docstrings.
```

---

## 2. Gemini prompt for intent extraction (feed to: Gemini API at runtime — this is the actual system prompt your backend sends)

```
You are the query understanding engine for WeatherGPT, a weather assistant for India.

Extract structured intent from the user's message. Output ONLY valid JSON matching
this exact schema, no prose, no markdown fences:

{
  "location": string,
  "time_window": "now" | "today" | "tomorrow" | "this_week" | "historical" | "unspecified",
  "parameter": "rain" | "temperature" | "wind" | "cyclone" | "flood" | "general" | "aqi" | "sea_state",
  "persona_context": "farmer" | "fisherman" | "general" | "aviation" | "researcher" | "disaster_officer"
}

Rules:
- If location is not mentioned, use "unspecified".
- If persona is not obvious from the message, default to "general".
- Never invent a location that wasn't stated or clearly implied.

User message: "{{user_message}}"
Known persona (from user profile, if any): "{{persona}}"
```

---

## 3. Gemini prompt for response composition (feed to: Gemini API at runtime)

```
You are WeatherGPT, a calm, plain-spoken weather assistant for Indian users.

Given this data, write ONE short natural-language answer in {{target_language}}:
- Intent: {{intent_json}}
- Data source: {{source_name}}
- Raw values: {{raw_payload}}
- Confidence score: {{confidence_score}} ({{confidence_label}})

Rules:
- Persona = farmer/fisherman → give one concrete action ("spray before 3pm", "return to shore by 5pm"), not just numbers.
- Persona = aviation/researcher → precise figures, no fluff.
- Always mention the confidence label naturally, never a bare decimal.
- Never claim certainty language ("definitely will rain") — use "likely", "expected", "possible" appropriately.
- Keep it under 3 sentences.
- If confidence is "low", explicitly say the estimate is uncertain and suggest checking again closer to the time.
```

---

## 4. Voice pipeline (feed to: Claude/Gemini code-gen)

```
Implement backend/app/services/voice_pipeline.py for WeatherGPT.

Requirements:
- Accept an audio file (bytes, format agnostic — wav/mp3/ogg)
- Transcribe using Groq's Whisper-large-v3 endpoint (groq SDK, GROQ_API_KEY env var)
- Detect language from transcription result
- If language != English, call Bhashini translation API (REST, endpoint and auth
  from BHASHINI_USER_ID / BHASHINI_API_KEY / BHASHINI_INFERENCE_KEY env vars) to
  get English text for intent extraction
- Return: {original_language, transcript, translated_text}

For the reverse path, implement synthesize_speech(text, target_language) that
calls Bhashini TTS and returns audio bytes.

Handle Bhashini's two-step pipeline (pipeline config fetch, then compute call) —
look up the current Bhashini API contract and implement it exactly; don't guess
the payload shape.
```

---

## 5. Alerts / geo fan-out (feed to: Claude/Gemini code-gen)

```
Implement backend/app/services/alert_dispatch.py.

Requirements:
- Function ingest_bulletin(bulletin: dict) that stores a row in the `alerts`
  table (schema in docs/05_Backend_Schema_WeatherGPT.md) with a PostGIS polygon
  for affected_area
- Function dispatch_alert(alert_id) that:
  - queries `users` where home_location intersects alert.affected_area (PostGIS
    ST_Intersects)
  - for severity == "severe": fan out via Firebase push AND Twilio SMS
    simultaneously, log each attempt to alert_dispatch_log
  - for "moderate": push only
  - for "advisory": store as in-app notification only, no external call
- Use SQLAlchemy + GeoAlchemy2 for the geo query.
- Read Firebase service account and Twilio credentials from env vars.
- Include a retry-once-then-escalate-channel rule for unacknowledged severe alerts
  after 10 minutes (simple background task or cron-callable function is fine for MVP).
```

---

## 6. Mobile UI — sky canvas + voice orb (feed to: Claude with the frontend-design context, or v0.dev / Gemini)

```
Build a React Native (Expo) chat screen for WeatherGPT with these exact motion
requirements — do not use generic blue/purple gradients or static weather icons:

1. Full-screen animated background canvas reflecting current weather condition
   passed as a prop (clear/rain/storm/night), using react-native-reanimated +
   react-native-skia (or Lottie/Rive if simpler) — clouds drift at a speed tied
   to a `windSpeed` prop, rain uses animated streak particles, night mode adds
   slow-drifting star particles.
2. A glassmorphism (frosted blur, react-native-blur) chat panel floating over
   the canvas — never opaque flat cards.
3. A voice input "orb" component: idle state gently pulses; while listening, it
   ripples outward in sync with mic amplitude (expo-av metering); while
   processing, it morphs into a small waveform loader.
4. A confidence badge component (High/Medium/Low) with a slow breathing
   opacity animation — color maps green/amber/red but never harsh saturated tones.
5. An alert takeover: when an alert prop is present, animate the whole screen's
   background color to the alert palette over 400ms before revealing the
   warning card, with a haptic pulse via expo-haptics.

Keep it performant on mid-range Android (Snapdragon 6-series). Ship one
self-contained screen component with mock data props so it can be demoed
without a live backend connection.
```

---

## 7. Database migrations (feed to: any code-gen AI)

```
Given the schema in docs/05_Backend_Schema_WeatherGPT.md, write:
- backend/app/db/models.py — SQLAlchemy models for users, persona_context,
  weather_cache, alerts, alert_dispatch_log, crowd_reports, confidence_scores,
  using GeoAlchemy2 Geography columns where the doc specifies GEOGRAPHY types
- backend/app/db/init_db.sql — raw SQL to enable the postgis extension and
  create GIST indexes on every geography column
- A single Alembic migration that creates all tables from the models
```

---

## 8. Crowd-fusion confidence scoring (feed to: Claude/Gemini code-gen)

```
Implement backend/app/services/confidence_engine.py.

def compute_confidence(sources: list[dict], crowd_reports: list[dict]) -> dict:
    Inputs: list of {source_name, value, fetched_at} for the same parameter/geohash,
    and list of recent crowd_reports for that geohash with confidence_weight.

    Logic:
    - source_agreement: how closely sources agree (normalize numeric values,
      compute inverse of variance)
    - recency: decay factor based on fetched_at age (fresher = higher)
    - crowd_corroboration: boost if >=2 crowd reports in last 2 hours agree
      with the official sources' direction (rain vs no-rain)
    - Combine into a 0-1 score, then map to "high" (>0.75), "medium" (0.4-0.75),
      "low" (<0.4)
    Return: {score: float, label: str, factors: dict} for storage in
    confidence_scores table.

Write it as a pure function with unit tests covering: all sources agree, sources
disagree, no crowd data, strong crowd corroboration.
```

---

## Order to run these in
1 → 7 (backend skeleton + db) → 2/3 (wire LLM prompts into service 1) → 4 (voice) → 5 (alerts) → 8 (differentiator scoring) → 6 (UI, can run in parallel from hour 0 with mock data).
