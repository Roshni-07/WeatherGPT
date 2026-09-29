// Fill these in before demoing with real data + real login.
// BACKEND_URL: where your FastAPI backend is running (docker-compose default: 8000).
// GOOGLE_CLIENT_ID: from Google Cloud Console -> APIs & Services -> Credentials
//   -> OAuth 2.0 Client ID (type: Web application). Add your dev URL
//   (e.g. http://localhost:5500) under "Authorized JavaScript origins".
window.WEATHERGPT_CONFIG = {
  BACKEND_URL: (typeof window !== "undefined" && window.location && window.location.origin) ? window.location.origin : "http://localhost:8000",
  GOOGLE_CLIENT_ID: "138769986717-52vn8g5d07c5rk89jj0tfs0cv9dltum0.apps.googleusercontent.com",
  DEFAULT_LOCATION: { name: "Bengaluru", lat: 12.9716, lon: 77.5946 },
};
