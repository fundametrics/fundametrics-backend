"""
Compatibility module to support Render's existing uvicorn start command:
`uvicorn scraper.api.app:app --host 0.0.0.0 --port 10000`

This routes the execution directly into the new architecture.
"""
import os
from api.main import app

# Keep a simple direct fallback health check just in case
@app.get("/ping")
def ping():
    return {"status": "ok"}
