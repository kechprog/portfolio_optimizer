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

# PostgreSQL Database URL (optional, for production use)
# Format: postgresql+asyncpg://user:password@host:port/dbname
# If not set, the application will fall back to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")

# SSL Configuration (for production HTTPS)
# Set these environment variables in production to enable HTTPS
SSL_CERTFILE = os.getenv("SSL_CERTFILE", "")  # e.g., /etc/letsencrypt/live/domain/fullchain.pem
SSL_KEYFILE = os.getenv("SSL_KEYFILE", "")    # e.g., /etc/letsencrypt/live/domain/privkey.pem

# WebSocket / HTTP Server
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
# Default to port 443 when SSL is enabled, otherwise 8000
_default_port = "443" if (SSL_CERTFILE and SSL_KEYFILE) else "8000"
WS_PORT = int(os.getenv("WS_PORT", _default_port))

# CORS
# Parse CORS_ORIGINS from comma-separated string or use default development origins
# In production, set CORS_ORIGINS="https://yourapp.com,https://www.yourapp.com"
# Use "*" only for development (WARNING: insecure for production)
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "")
if CORS_ORIGINS_ENV:
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_ENV.split(",")]
else:
    # Default development origins for Vite dev server
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
    ]

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/" if AUTH0_DOMAIN else ""
AUTH0_JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json" if AUTH0_DOMAIN else ""
