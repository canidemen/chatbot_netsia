import asyncpg
from redis.asyncio import Redis
from core.cache import ChatCache
from core.config import PG_DSN, REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD

# =============================================================================
# CONNECTION SETUP
# =============================================================================

async def create_database_pool():
    """Create PostgreSQL connection pool"""
    return await asyncpg.create_pool(
        dsn=PG_DSN,
        min_size=1,
        max_size=10,
    )

async def create_redis_client():
    """Create Redis client"""
    redis = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    await redis.ping()  # fail fast if creds/TLS are wrong
    return redis

def create_cache(redis_client):
    """Create ChatCache instance"""
    return ChatCache(redis_client)

# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

async def db_insert_async(pool, ticket: dict):
    """Insert ticket data using asyncpg pool"""
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO tickets (user_id, message, label, confidence, escalated)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, created_at;
                """,
                ticket.get("userId"),
                ticket.get("message"),
                ticket.get("label"),
                ticket.get("confidence"),
                ticket.get("escalated", False),
            )
            return result
    except Exception as e:
        print(f"Database insert error: {e}")
        raise