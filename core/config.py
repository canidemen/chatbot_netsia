import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
PG_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:admin123@localhost:5432/postgres")

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis-15242.c241.us-east-1-4.ec2.redns.redis-cloud.com")
REDIS_PORT = int(os.getenv("REDIS_PORT", "15242"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "c5yOQ9dO6PcoVPxEx9ZGxpaKhnzdZnJp")

# Session Configuration
SESSION_TTL = int(os.getenv("SESSION_TTL", "600"))  # 10 minutes

# App Configuration
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")