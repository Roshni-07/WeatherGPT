# WeatherGPT

Conversational AI weather platform — SIH 2025, Problem Statement 26068.

## Structure
```
backend/    FastAPI service — LLM orchestration, data aggregation, alerts
mobile/     React Native app
ml/         Prompts, intent schema, few-shot examples (shared contract)
infra/      docker-compose, k8s manifests
docs/       PRD, TRD, UI/UX brief, app flow, schema, implementation plan, AI prompts
```

## Setup
```bash
git clone <repo-url>
cd weathergpt
cp .env.example .env        # fill in your free-tier keys (see below)
docker compose -f infra/docker-compose.yml up --build
```
Backend runs at `http://localhost:8000`. Health check: `GET /health`.

Then serve the prototype frontend separately (it's a static site, don't open via double-click once it's calling the API):
```bash
npx serve .        # or: python -m http.server 5500
```
Open the printed local URL. Edit `src/config.js` first if your backend isn't on `localhost:8000` or you're setting up Google Sign-In.

### Minimum keys to get real (non-fallback) answers
- `GEMINI_API_KEY` — https://aistudio.google.com/apikey (free tier)
- `OPENWEATHERMAP_API_KEY` — https://openweathermap.org/api (free tier; powers current weather, forecast, and geocoding/location search)

Without these, the app still runs and stays visually functional (canvas, tabs, navigation all work), but chat/advisory answers fall back to an honest "offline preview" message instead of live data — see `src/services/api.js` `_offlineFallback()`.

### Optional: Google Sign-In
1. Google Cloud Console → APIs & Services → Credentials → Create OAuth 2.0 Client ID (type: Web application).
2. Add your dev URL (e.g. `http://localhost:5500`) under "Authorized JavaScript origins".
3. Put the client ID in both `.env` (`GOOGLE_CLIENT_ID`, for server-side token verification) and `src/config.js` (`GOOGLE_CLIENT_ID`, for the button to render).
Without this configured, the sign-in button simply doesn't render — nothing breaks.

## Branch convention
- `main` — protected, demo-ready only
- `feat/<module>` — one branch per owner (backend-api, voice-pipeline, ui-canvas, alerts-engine, crowd-fusion)
- PR into `main`, no direct push
- Commit style: `feat(voice): add whisper stt`, `fix(alerts): geo-match radius bug`

## Required free-tier keys (see .env.example)
Gemini, Groq, Bhashini, OpenWeatherMap, Twilio (trial), Firebase.

## Shared contract
Every module reads intent shape from `ml/schemas/intent.json`. Never hardcode the shape elsewhere.
