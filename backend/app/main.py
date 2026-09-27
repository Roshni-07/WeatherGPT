from fastapi import FastAPI
from app.routers import query, alerts

app = FastAPI(title="WeatherGPT API")

app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])


@app.get("/health")
def health():
    return {"status": "ok"}
