import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.endpoints import router as api_router
from db.manager import init_db

load_dotenv()

app = FastAPI(
    title="Fundametrics Scraper API",
    description="Internal API for accessing cached Indian Stock Fundamentals",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database on Startup
@app.on_event("startup")
async def startup_event():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        init_db(db_url)
    else:
        print("WARNING: DATABASE_URL not set. API may fail to connect to DB.")

# Include Routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Welcome to Fundametrics Scraper API",
        "docs": "/docs",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
