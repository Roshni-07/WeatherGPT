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
cp .env.example .env        # fill in your free-tier keys
docker compose -f infra/docker-compose.yml up --build
```
Backend runs at `http://localhost:8000`. Health check: `GET /health`.

## Branch convention
- `main` — protected, demo-ready only
- `feat/<module>` — one branch per owner (backend-api, voice-pipeline, ui-canvas, alerts-engine, crowd-fusion)
- PR into `main`, no direct push
- Commit style: `feat(voice): add whisper stt`, `fix(alerts): geo-match radius bug`

## Required free-tier keys (see .env.example)
Gemini, Groq, Bhashini, OpenWeatherMap, Twilio (trial), Firebase.

## Shared contract
Every module reads intent shape from `ml/schemas/intent.json`. Never hardcode the shape elsewhere.
