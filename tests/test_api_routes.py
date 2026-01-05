import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

# Create a TestClient
client = TestClient(app)

def test_root():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to Fundametrics Scraper API"

def test_docs_exist():
    """Verify that Swagger UI is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()

if __name__ == "__main__":
    print("Testing API Root...")
    test_root()
    print("Root Test Passed!")
    
    print("Testing API Docs...")
    test_docs_exist()
    print("Docs Test Passed!")
    
    print("API verification complete!")
