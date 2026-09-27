"""
Wraps the Gemini API for the two LLM calls WeatherGPT needs:
1. extract_intent — turn free text into the structured intent contract
2. compose_response — turn real weather data + intent into a natural answer

Model name: check Google AI Studio for the current free-tier model id before
relying on the default below — model names on the free tier change over time.
"""
import os
import json
import google.generativeai as genai

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

if GEMINI_KEY:
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
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
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
