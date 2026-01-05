"""
Start the Fundametrics API server with proper database initialization
"""
import os
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize database before starting the server
from db.manager import init_db

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env file")
    exit(1)

print(f"Initializing database connection...")
init_db(DATABASE_URL)
print(f"✅ Database initialized successfully!")

# Import the app after database is initialized
from api.main import app

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Starting Fundametrics API Server")
    print("=" * 60)
    print(f"📍 URL: http://localhost:8000")
    print(f"📚 Docs: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        "start_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
