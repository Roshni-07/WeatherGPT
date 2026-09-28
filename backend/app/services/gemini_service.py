"""
Wraps the Gemini API for the two LLM calls WeatherGPT needs:
1. extract_intent — turn free text into the structured intent contract
2. compose_response — turn real weather data + intent into a natural answer

Model name: check Google AI Studio for the current free-tier model id before
relying on the default below — model names on the free tier change over time.
"""
import os
import json
try:  # optional: the app works fully without it
    import google.generativeai as genai
except Exception:  # noqa: BLE001
    genai = None

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

if GEMINI_KEY and genai:
    genai.configure(api_key=GEMINI_KEY)

VALID_TIME_WINDOWS = {"now", "today", "tomorrow", "this_week", "historical", "unspecified"}
VALID_PARAMETERS = {"rain", "temperature", "wind", "cyclone", "flood", "general", "aqi", "sea_state"}
VALID_PERSONAS = {"farmer", "fisherman", "general", "aviation", "researcher", "disaster_officer"}

INTENT_PROMPT = """You are the query understanding engine for WeatherGPT, a weather assistant for India.

Extract structured intent from the user's message. Output ONLY valid JSON matching
this exact schema, no prose, no markdown fences:

{{
  "location": string,
  "time_window": "now" | "today" | "tomorrow" | "this_week" | "historical" | "unspecified",
  "parameter": "rain" | "temperature" | "wind" | "cyclone" | "flood" | "general" | "aqi" | "sea_state",
  "persona_context": "farmer" | "fisherman" | "general" | "aviation" | "researcher" | "disaster_officer"
}}

Rules:
- If location is not mentioned, use "unspecified".
- If persona is not obvious from the message, default to "general".
- Never invent a location that wasn't stated or clearly implied.

User message: "{user_message}"
Known persona (from user profile, if any): "{persona}"
"""

RESPONSE_PROMPT = """You are WeatherGPT, a calm, plain-spoken weather assistant for Indian users.

Given this data, write ONE short natural-language answer in {target_language}:
- Intent: {intent_json}
- Real weather data: {weather_json}
- Confidence: {confidence_label}

Rules:
- Persona = farmer/fisherman -> give one concrete action, not just numbers.
- Persona = aviation/researcher -> precise figures, no fluff.
- Mention the confidence label naturally, never a bare decimal.
- Never claim certainty ("definitely will rain") -- use "likely", "expected", "possible".
- Keep it under 3 sentences.
- If confidence is "low", say so explicitly.
"""


def _model():
    if not GEMINI_KEY or genai is None:
        raise RuntimeError("Gemini is not configured")
    return genai.GenerativeModel(MODEL_NAME)


def extract_intent(user_message: str, persona_hint: str = "general") -> dict:
    prompt = INTENT_PROMPT.format(user_message=user_message, persona=persona_hint)
    resp = _model().generate_content(prompt)
    text = resp.text.strip().strip("`").removeprefix("json").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned non-JSON intent: {text!r}") from e

    data.setdefault("location", "unspecified")
    data.setdefault("time_window", "unspecified")
    data.setdefault("parameter", "general")
    data.setdefault("persona_context", persona_hint or "general")

    if data["time_window"] not in VALID_TIME_WINDOWS:
        data["time_window"] = "unspecified"
    if data["parameter"] not in VALID_PARAMETERS:
        data["parameter"] = "general"
    if data["persona_context"] not in VALID_PERSONAS:
        data["persona_context"] = "general"

    return data


def compose_response(intent: dict, weather_summary: dict, confidence_label: str, target_language: str = "en") -> str:
    prompt = RESPONSE_PROMPT.format(
        target_language=target_language,
        intent_json=json.dumps(intent),
        weather_json=json.dumps(weather_summary),
        confidence_label=confidence_label,
    )
    resp = _model().generate_content(prompt)
    return resp.text.strip()


# ------------------------------------------------------------------ v2 helpers
# The core weather engine is deterministic. Gemini is only used for things a
# rules engine can't do: free-form questions, translation, and sky photos.
import time as _time

_llm_state = {"bad_until": 0}


def available():
    """True if a key is set and we haven't just seen a hard failure."""
    return bool(GEMINI_KEY) and genai is not None and _time.time() > _llm_state["bad_until"]


def _mark_bad(err):
    # Back off for 5 minutes after an auth/model error so every request doesn't wait on a broken key.
    msg = str(err).lower()
    if "api key" in msg or "api_key" in msg or "permission" in msg or "not found" in msg or "404" in msg or "403" in msg or "400" in msg:
        _llm_state["bad_until"] = _time.time() + 300


def _text(prompt, parts=None):
    try:
        model = _model()
        resp = model.generate_content(parts if parts else prompt)
        return (resp.text or "").strip()
    except Exception as e:  # noqa: BLE001
        _mark_bad(e)
        raise


def to_english(text):
    return _text("Translate this weather question into plain English. Keep place names. Reply with the translation only.\n\n" + text)


def from_english(text, language_name):
    return _text(f"Translate the following weather answer into {language_name}. Keep every number, unit, time and place name exactly as is. "
                 f"Keep it simple and friendly. Reply with the translation only.\n\n{text}")


def grounded_answer(question, facts_json, persona="general"):
    return _text(
        "You are WeatherGPT, a calm, plain-spoken weather assistant for people in India. Answer the user's question using ONLY the facts below. "
        "If the facts don't cover it, say so honestly. Never invent numbers. Use simple words, max 4 sentences, no markdown headings.\n\n"
        f"User type: {persona}\nFACTS (JSON): {facts_json}\n\nQuestion: {question}")


def analyze_sky(image_bytes, mime, facts_json):
    prompt = (
        "You are WeatherGPT. Look at this sky photo and describe, in simple words, what you can actually see: cloud amount and type, light, haze/visibility, "
        "and any visible signs of developing weather. Then compare it with the forecast FACTS below in 1-2 sentences. "
        "Be honest: a photo cannot give precise measurements, so treat it as one extra signal, not proof. Max 5 sentences.\n\n"
        f"FACTS (JSON): {facts_json}")
    return _text(prompt, parts=[{"mime_type": mime, "data": image_bytes}, prompt])
