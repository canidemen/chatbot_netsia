import redis, json
from datetime import datetime, timezone
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
