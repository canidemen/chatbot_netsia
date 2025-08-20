"""Database utilities for user management"""

async def get_user_by_email(pool, email):
    """Get user by email address"""
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, password, last_active_conversation_id FROM users WHERE email=$1",
            email,
        )

async def get_user_by_id(pool, user_id):
    """Get user by ID"""
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, password, last_active_conversation_id FROM users WHERE id=$1",
            user_id,
        )