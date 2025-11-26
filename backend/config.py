import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the same directory as this config file
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Alpha Vantage API
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_KEY", "")

# Database
DATABASE_PATH = BASE_DIR / "price_cache.db"

# WebSocket
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", "8000"))
