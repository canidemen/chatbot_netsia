import asyncio


def db_insert(pool, ticket: dict):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tickets (user_id, message, label, confidence, escalated)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, created_at;
                    """,
                    (
                        ticket.get("userId"),
                        ticket.get("message"),
                        ticket.get("label"),
                        ticket.get("confidence"),
                        ticket.get("escalated", False),
                    ),
                )
                return cur.fetchone()  # (id, created_at)
    finally:
        pool.putconn(conn)

async def db_insert_async(pool, ticket):
    return await asyncio.to_thread(db_insert, pool, ticket)