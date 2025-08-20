import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
PG_DSN = os.getenv("DATABASE_URL", "ENTER DATABASE URL")

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "ENTER REDIS URL")
REDIS_PORT = int(os.getenv("REDIS_PORT", "ENTER REDIS PORT"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "ENTER REDIS USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "ENTER REDIS PASSWORD")

# Session Configuration
SESSION_TTL = int(os.getenv("SESSION_TTL", "600"))  # 10 minutes

# App Configuration
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
