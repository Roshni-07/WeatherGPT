# AI Build Sequence v2 — WeatherGPT
Using: obra/superpowers (dev methodology), pbakaus/impeccable + emilkowalski/skill (design taste), Gemini/Groq/Bhashini (product AI).

Run phases in order. Each names the exact tool/agent to run it in.

---

## Phase 0 — One-time setup (run in your coding agent's terminal, once per machine)

If using Claude Code:
```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```
If using Cursor, Codex, Gemini CLI, or others:
```
npx skills add obra/superpowers
npx skills add pbakaus/impeccable
npx skills add emilkowalski/skill
```
For the design skills specifically (frontend/mobile teammate only):
```
npx impeccable install
# then inside the agent:
/impeccable init
```
This writes `PRODUCT.md` and `DESIGN.md` so every later design command knows your product, audience, and voice — do this before any UI prompt below.

---

## Phase 1 — Brainstorm & lock the design doc (feed to: any agent with Superpowers installed)

```
Use your brainstorming skill. I'm building WeatherGPT — a conversational weather
AI for India (voice + text + IVR, multilingual, hyperlocal alerts). I already
have a PRD, TRD, UI/UX brief, app flow, and backend schema in docs/. Read all
five, then ask me clarifying questions about anything genuinely ambiguous before
proposing an implementation design. Present the design in sections for me to
approve one at a time. Once approved, use your writing-plans skill to produce
an implementation plan broken into independently-buildable tasks (backend core,
voice pipeline, alerts engine, crowd-fusion scoring, mobile UI). Save the design
doc and plan to docs/09_Agent_Design_Doc.md and docs/10_Agent_Plan.md.
```

---

## Phase 2 — Design system setup (feed to: Claude Code / Cursor with Impeccable installed — the frontend teammate)

```
/impeccable init
```
When it asks for product context, answer with:
```
Product: WeatherGPT, a conversational weather app for India — farmers,
fishermen, commuters, disaster officers. Register: consumer product, not a
brand site. Voice: calm, plain-spoken, trustworthy, never alarmist except
during real severe alerts. Explicitly avoid: Inter-everywhere, purple-to-blue
SaaS gradients, cards nested in cards, generic rounded-square icon tiles —
this must look like a living sky, not a dashboard. Reference docs/03_UIUX_Design_Brief_WeatherGPT.md
for the full motion and color spec (dynamic weather-reactive palette, live sky
canvas, voice orb, glassmorphism panels).
```

Then, once the chat screen exists as a first draft:
```
/impeccable audit mobile/screens/ChatScreen.tsx
```
Fix what it flags, then:
```
/impeccable polish mobile/screens/ChatScreen.tsx
```

For the animation-heavy pieces specifically (sky canvas, voice orb, alert transition), invoke the emilkowalski skill directly:
```
Use the emil-design-eng skill. Build the voice-orb component described in
docs/03_UIUX_Design_Brief_WeatherGPT.md: idle pulse, amplitude-synced ripple
while listening, morph to waveform while processing. Pick the correct easing
curve for each state transition (not a default ease-in-out) and justify the
choice in a one-line comment above each animation definition.
```
After it's built, run the review skill:
```
Use the review-animations skill on mobile/components/VoiceOrb.tsx and
mobile/components/AlertTakeover.tsx. Flag anything that runs but feels
sluggish, fires too often, or uses the wrong easing for its direction.
```

---

## Phase 3 — Backend core, TDD-first (feed to: any agent with Superpowers installed)

```
Use your test-driven-development skill. Before writing any implementation:

1. Write failing tests for backend/app/services/intent_extraction.py — given a
   sample English sentence, assert the returned dict matches ml/schemas/intent.json
   exactly, and assert it raises on malformed model output.
2. Write failing tests for backend/app/services/data_router.py — given a mocked
   intent dict, assert it calls the correct data source (OpenWeatherMap vs NASA
   POWER vs IMD cache) based on parameter/time_window, using mocked httpx calls.

Confirm both test files fail for the right reason (red), then implement the
minimum code to pass them (green), then refactor for clarity without changing
behavior. Show me the red output before you write implementation code.
```

Then feed the actual LLM prompts (these go INTO your running app, not into your coding agent — paste as-is into `backend/app/services/intent_extraction.py`'s prompt template and `response_composer.py`'s prompt template):

**Intent extraction prompt (Gemini, runtime):**
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

**Response composer prompt (Gemini, runtime):**
```
You are WeatherGPT, a calm, plain-spoken weather assistant for Indian users.

Given this data, write ONE short natural-language answer in {{target_language}}:
- Intent: {{intent_json}}
- Data source: {{source_name}}
- Raw values: {{raw_payload}}
- Confidence score: {{confidence_score}} ({{confidence_label}})

Rules:
- Persona = farmer/fisherman → give one concrete action, not just numbers.
- Persona = aviation/researcher → precise figures, no fluff.
- Always mention the confidence label naturally, never a bare decimal.
- Never claim certainty language ("definitely will rain") — use "likely",
  "expected", "possible" appropriately.
- Keep it under 3 sentences.
- If confidence is "low", say so explicitly and suggest checking again closer
  to the time.
```

---

## Phase 4 — Parallel independent modules (feed to: any agent with Superpowers installed)

Once Phase 3's core is merged, the remaining modules have no shared state — build them concurrently:

```
Use your dispatching-parallel-agents skill. Dispatch three subagents, each
working from docs/10_Agent_Plan.md:

Agent A — Voice pipeline: implement backend/app/services/voice_pipeline.py.
  Groq Whisper for STT (GROQ_API_KEY env var), Bhashini for translation and TTS
  (BHASHINI_* env vars). Look up Bhashini's actual two-step pipeline contract
  (config fetch, then compute call) rather than guessing the payload shape.

Agent B — Alerts engine: implement backend/app/services/alert_dispatch.py per
  docs/05_Backend_Schema_WeatherGPT.md — PostGIS geo-match, tiered fan-out
  (severe: push+SMS simultaneous, moderate: push only, advisory: in-app only),
  retry-and-escalate after 10 minutes for unacknowledged severe alerts.

Agent C — Confidence scoring: implement backend/app/services/confidence_engine.py
  — compute_confidence(sources, crowd_reports) combining source agreement,
  recency decay, and crowd corroboration into a 0-1 score mapped to
  high/medium/low. Include unit tests for: all sources agree, sources disagree,
  no crowd data, strong crowd corroboration.

Each agent works in its own git worktree on its own feat/ branch. Review each
before merging.
```

---

## Phase 5 — Verify before demo (feed to: any agent with Superpowers installed)

```
Use your verification-before-completion skill. Run the full test suite fresh,
start the docker-compose stack, and hit /health, /query, and /alerts/active
with real requests. Show me the actual command output as evidence — don't just
report "tests pass" from memory. Flag anything that fails silently or returns
a stub response instead of real data.
```

---

## Phase 6 — Merge and freeze (feed to: any agent with Superpowers installed, per branch)

```
Use your finishing-a-development-branch skill on feat/<module-name>. All tests
pass and the feature is complete — present my options for merge/PR/cleanup and
carry out the one I pick.
```

---

## Optional / educational only (not on the critical path)
`codecrafters-io/build-your-own-x` — if a teammate has slack time and wants to
actually understand how something like an IVR system or a basic HTTP server
works under the hood rather than just calling Twilio, its "build your own X"
guides are good for that. Don't route hackathon-critical work through it —
it's for learning internals, not for shipping under a deadline.
