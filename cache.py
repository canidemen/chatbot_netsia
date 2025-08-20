import json
from datetime import datetime, timezone
import uuid
import secrets
from typing import Optional, List
from redis.asyncio import Redis

class ChatCache:
    def __init__(self, redis_client):
        self.redis = redis_client

    # ----------------------------
    # SESSION MANAGEMENT 
    # ----------------------------

    async def issue_sid(self, user_id, ttl = 600) -> str:
        # cryptographically strong, URL-safe; much lower collision risk vs 8-char uuid slice
        sid = "sid_" + secrets.token_urlsafe(32)
        await self.redis.setex(sid, ttl, str(user_id))
        return sid

    async def get_user_id_for_sid(self, sid):
        return await self.redis.get(sid)

    async def refresh_sid(self, sid, ttl = 600):
        await self.redis.expire(sid, ttl)

    async def create_session(self, user_id, ttl = 600):
        return await self.issue_sid(user_id, ttl)

    # async def get_session_user(self, session_id):
    #     return await self.get_user_id_for_sid(session_id)

    async def close_session(self, session_id):
        await self.redis.delete(session_id)

    # ---------------------------------------------------
    # old code
    # ---------------------------------------------------
    # async def store_message(self, session_id: str, role: str, content: str, ttl: int = 600) -> None:
    #     history_key = f"chat:{session_id}"
    #     entry = json.dumps({
    #         "role": role,
    #         "content": content,
    #         "ts": datetime.now(timezone.utc).isoformat()
    #     })
    #     # [KEEP] list append + sliding TTL
    #     await self.redis.rpush(history_key, entry)
    #     await self.redis.expire(history_key, ttl)

    # async def get_history(self, session_id: str) -> List[dict]:
    #     history_key = f"chat:{session_id}"
    #     raw = await self.redis.lrange(history_key, 0, -1)
    #     return [json.loads(x) for x in raw]

    # async def list_sessions_for_user(self, user_id: str) -> List[str]:
    #     """
    #     v1 tracked `user:{user_id}:sessions` via a set; v2 doesn't.
    #     For backcompat, this returns an empty list unless you also add tracking.
    #     If you still need this, uncomment the SADD in create_session and SREM in revoke.
    #     """
    #     return []
    #     # If you want to restore tracking, add these in create_session/revoke_sid:
    #     # await self.redis.sadd(f"user:{user_id}:sessions", sid)
    #     # await self.redis.srem(f"user:{user_id}:sessions", sid)
