import json
from datetime import datetime, timezone
import uuid

from redis.asyncio import Redis

'''
r = redis.Redis(
    host="redis-15242.c241.us-east-1-4.ec2.redns.redis-cloud.com",
    port=15242,
    password="Def.ine!23",  # copy from your Redis Cloud console
    ssl=True,                  # enable TLS
    decode_responses=True,     # strings instead of bytes
    socket_connect_timeout=5,  # seconds
    socket_timeout=5,
    retry_on_timeout=True
)
'''

class ChatCache:
    def __init__(self, Redis):
        self.redis = Redis

    async def create_session(self, user_id):
        session_id = str(uuid.uuid4())[:8]
        session_key = f"session:{session_id}"
        await self.redis.hset(session_key, mapping={
            "user_id": user_id,
            "status": "active",
            "start_time": datetime.now(timezone.utc).isoformat()
        })
        await self.redis.expire(session_key, 600)   #session expires after 10 minutes

        # track sessions for user
        await self.redis.sadd(f"user:{user_id}:sessions", session_id)

        return session_id

    async def get_session_user(self, session_id):
        return await self.redis.hget(f"session:{session_id}", "user_id")

    async def update_session_end_time(self, session_id):
        await self.redis.hset(f"session:{session_id}", "end_time", datetime.now(timezone.utc).isoformat())

    async def store_message(self, session_id, role, content):
        history_key = f"chat:{session_id}"
        entry = json.dumps({"role": role, "content": content})
        await self.redis.rpush(history_key, entry)
        await self.redis.expire(history_key, 600)

    async def get_history(self, session_id):
        history_key = f"chat:{session_id}"
        raw_entries = await self.redis.lrange(history_key, 0, -1)
        return [json.loads(entry) for entry in raw_entries]

    async def list_sessions_for_user(self, user_id):
        return list(await self.redis.smembers(f"user:{user_id}:sessions"))

    async def close_session(self, session_id):
        await self.redis.hset(f"session:{session_id}", "status", "closed")
        await self.update_session_end_time(session_id)


'''
r = redis.Redis(
    host="redis-15242.c241.us-east-1-4.ec2.redns.redis-cloud.com",
    port= 15242,
    password="c5yOQ9dO6PcoVPxEx9ZGxpaKhnzdZnJp",
    decode_responses=True
)

print(r.ping())

r.set("asad", "123213", ex=60)
print(r.get("age"))


session_id = "sess_123"  # generate or read from user cookie
key = f"chat:{session_id}:messages"

def add_message(role, content):
    msg_id = r.incr(f"{key}:next_id")
    msg = {
        "id": msg_id,
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat()
    }
    pipe = r.pipeline()
    pipe.rpush(key, json.dumps(msg))
    pipe.expire(key, 86400)        # 24h sliding window
    pipe.execute()

def get_history():
    return [json.loads(x) for x in r.lrange(key, 0, -1)]





add_message("user", "Hello") 
add_message("assistant", "Hi Can!")
print(get_history())
'''