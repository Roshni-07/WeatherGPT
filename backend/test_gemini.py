"""
Run this directly to check your Gemini key and model name in isolation,
without going through the FastAPI app. From backend/ with venv active:
    python test_gemini.py
"""
import os
import google.generativeai as genai

key = os.getenv("GEMINI_API_KEY")
if not key:
    # In case the env var isn't picked up standalone, paste it here temporarily:
    key = "PASTE_YOUR_KEY_HERE_IF_ENV_VAR_IS_EMPTY"

print(f"Key present: {bool(key) and key != 'PASTE_YOUR_KEY_HERE_IF_ENV_VAR_IS_EMPTY'}")
genai.configure(api_key=key)

print("\n--- Models available to this key ---")
try:
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"FAILED to list models: {e}")

print("\n--- Test call ---")
try:
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content("Say OK if you can read this.")
    print("SUCCESS:", resp.text)
except Exception as e:
    print(f"FAILED with gemini-2.0-flash: {e}")
