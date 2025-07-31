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
