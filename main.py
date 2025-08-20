from fastapi import FastAPI, Depends, APIRouter, HTTPException, Response, Request
import gradio as gr, uuid
from chatbot import handle_message
from cache import ChatCache
from contextlib import asynccontextmanager
import asyncpg
from redis.asyncio import Redis
import hashlib
import time
from pydantic import BaseModel, EmailStr
import httpx

PG_DSN = "postgresql://postgres:admin123@localhost:5432/postgres"

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis(
        host="redis-15242.c241.us-east-1-4.ec2.redns.redis-cloud.com",
        port=15242,
        username="default",
        password="c5yOQ9dO6PcoVPxEx9ZGxpaKhnzdZnJp",
        decode_responses=True,
        #ssl=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    await redis.ping()  # fail fast if creds/TLS are wrong

    app.state.redis = redis
    app.state.cache = ChatCache(redis)

    pool = await asyncpg.create_pool(
        dsn=PG_DSN,
        min_size=1,
        max_size=10,
    )
    app.state.pool = pool

    try:
        yield  #app runs here
    finally:
        await redis.close()
        await pool.close()


app = FastAPI(lifespan=lifespan)

#----------------
# DB Helpers
#----------------

async def get_user_by_email(pool, email):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, password, last_active_conversation_id FROM users WHERE email=$1",
            email,
        )

async def get_user_by_id(pool, user_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, password, last_active_conversation_id FROM users WHERE id=$1",
            user_id,
        )

# ------------------------------
# Pydantic models for auth
# ------------------------------
class RegisterIn(BaseModel):  # [NEW]
    email: EmailStr
    password: str

class LoginIn(BaseModel):  # [NEW]
    email: EmailStr
    password: str

# ------------------------------
# Auth endpoints (Redis-only auth session, 10-min TTL)
# ------------------------------
@app.post("/auth/register")  # [NEW]
async def register(payload: RegisterIn):
    pool = app.state.pool
    existing_user = await get_user_by_email(pool, payload.email)
    if existing_user:
        raise HTTPException(status_code = 409, detail="Email already registered")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, password)
            VALUES ($1, $2)
            RETURNING id, email, password, last_active_conversation_id
            """,
            payload.email, payload.password,
        )
    return {"id": str(row["id"]), "email": row["email"]}

@app.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    pool = app.state.pool
    cache = ChatCache(app.state.redis)
    user = await get_user_by_email(pool, payload.email)
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    #sid expiration: 10 mins
    sid = await cache.create_session(user["id"], ttl = 600) #SESSION EXPIRES AFTER 10 MINUTES

    response.set_cookie(
        key="sid",
        value=sid,
        max_age=600,  # 10 minutes
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "sid": sid}

@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    cache = app.state.cache
    sid = request.cookies.get("sid") or request.headers.get("x-sid")
    if sid:
        await cache.close_session(sid)
    response.delete_cookie("sid", path="/")
    return {"ok": True}

@app.get("/me")
async def me(user=Depends(lambda request: get_current_user(request))):
    return user

# ------------------------------
# Auth dependency
# ------------------------------

async def get_current_user(request: Request):
    sid = request.cookies.get("sid") or request.headers.get("x-sid")
    if not sid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    cache = app.state.cache
    pool = app.state.pool

    user_id = await cache.get_user_id_for_sid(sid)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired")

    #Sliding 10 min keep-alive
    await cache.refresh_sid(sid, ttl=600)

    user = await get_user_by_id(pool, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"id": str(user["id"]), "email": user["email"]}

# ------------------------------
# Conversations and Messages APIs
# ------------------------------

router = APIRouter(prefix="/conversations")

class ConversationCreate(BaseModel):
    title: str

class MessageIn(BaseModel):
    role: str    #'user' or 'assistant' or 'system' (or 'tool'?)
    content: str

@app.get("/boot")   # [NEW]#returns sidebar and last active conversation on load
async def boot_info(user=Depends(get_current_user)):
    pool = app.state.pool
    async with pool.acquire() as conn:
        last_active = await conn.fetchval(
            "SELECT last_active_conversation_id FROM users WHERE id=$1",
            user["id"],
        )

        if not last_active:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (user_id, title)
                VALUES ($1, $2)
                RETURNING id::text
                """,
                user["id"], "New Conversation",
            )
            last_active = row["id"]
            await conn.execute(
                "UPDATE users SET last_active_conversation_id=$1 WHERE id=$2",
                last_active, user["id"]
            )
        conversations = await conn.fetch(     #might fail, check
            """
            SELECT id::text, COALESCE(title,'') AS title, updated_at
            FROM conversations
            WHERE user_id=$1
            ORDER BY updated_at DESC
            LIMIT 100
            """,
            user["id"]
        )   
        print("SIDEBAR RETRIEVED")

        msgs = await conn.fetch(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id=$1
            ORDER BY id ASC
            LIMIT 200
            """,
            last_active
        )
        print("MESSAGES RETRIEVED")

    return {"user": user, "last_conversation_id": last_active, "conversations": [
            {"id": r["id"], "title": r["title"], "updated_at": r["updated_at"].isoformat()}
            for r in conversations
        ], 
        "messages": [{"role": r["role"], "content": r["content"]} for r in msgs],
    }

@router.get("")
async def list_conversations(user=Depends(get_current_user)):
    pool = app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, COALESCE(title,'') AS title, updated_at
            FROM conversations
            WHERE user_id=$1
            ORDER BY updated_at DESC
            LIMIT 100
            """,
            user["id"]
        )
    return [
        {"id": r["id"], "title": r["title"], "updated_at": r["updated_at"].isoformat()}
        for r in rows
    ]

@router.post("")
async def create_conversation(payload: ConversationCreate, user=Depends(get_current_user)):
    pool = app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations(user_id, title)
            VALUES ($1, $2)
            RETURNING id::text, title, updated_at
            """,
            user["id"], payload.title
        )
        await conn.execute(
            "UPDATE users SET last_active_conversation_id=$1 WHERE id=$2",
            row["id"], user["id"]
        )
        return {"id": row["id"], "title": row["title"]}

@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit = 200, user=Depends(get_current_user)):
    pool = app.state.pool
    async with pool.acquire() as conn:
        ok = await conn.fetchval(
            "SELECT 1 FROM conversations WHERE id=$1 AND user_id=$2",
            conversation_id, user["id"]
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        rows = await conn.execute(
            """
            UPDATE users SET last_active_conversation_id=$1
            WHERE id=$2
            """,
            conversation_id, user["id"]
        )

        rows = await conn.fetch(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id=$1
            ORDER BY id ASC
            LIMIT $2
            """,
            conversation_id, limit,
        )
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    
@router.post("/{conversation_id}/messages")
async def add_message(conversation_id: str, payload: MessageIn, user=Depends(get_current_user)):
    pool = app.state.pool
    async with pool.acquire() as conn:
        ok = await conn.fetchval(
            "SELECT 1 FROM conversations WHERE id=$1 AND user_id=$2",
            conversation_id, user["id"]
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found")

        await conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES ($1, $2, $3)
            """,
            conversation_id, payload.role, payload.content
        )
        await conn.execute(
            """
            UPDATE conversations SET updated_at=now()
            WHERE id=$1
            """,
            conversation_id
        )
        await conn.execute(
            """
            UPDATE users SET last_active_conversation_id=$1
            WHERE id=$2
            """,
            conversation_id, user["id"]
        )
        return {"ok": True}

app.include_router(router)

'''
def create_user_fingerprint(request: gr.Request) -> str:
    """
    ip|user_agent|accept_language|accept_encoding -> sha256 -> fingerprint user_id
    
    """
    
    ip_address = getattr(request.client, "host", "") if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    accept_language = request.headers.get("accept-language", "")
    accept_encoding = request.headers.get("accept-encoding", "")

    fingerprint_data = f"{ip_address}|{user_agent}|{accept_language}|{accept_encoding}"
    fingerprint_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()
    return f"user_{fingerprint_hash[:12]}"
'''

# -----------------------------------------------------
# Gradio UI
# -----------------------------------------------------

with gr.Blocks(title="Login") as login_page:  # [ADDED]
    gr.Markdown("## Login")  # [ADDED]
    email = gr.Textbox(label="Email")  # [ADDED]
    pw = gr.Textbox(label="Password", type="password")  # [ADDED]
    out = gr.Markdown()  # [ADDED]
    go_register = gr.Button("Go to Register")  # [ADDED]
    login_btn = gr.Button("Login")  # [ADDED]

    login_btn.click(  # [ADDED]
        None,
        inputs=[email, pw],
        outputs=out,
        js="""
        async (email, pw) => {
          try {
            const resp = await fetch('/auth/login', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({email, password: pw}),
              credentials: 'include'  // [ADDED] ensures cookie is stored
            });
            if (!resp.ok) {
              const body = await resp.json().catch(()=>({detail:'Login failed'}));
              return '❌ ' + (body.detail || 'Login failed');
            }
            window.location.href = '/chat';  // [ADDED] navigate to chat page
            return '✅ Logged in. Redirecting...';
          } catch (e) {
            return '❌ Network error';
          }
        }
        """
    )
    go_register.click(None, js="() => { window.location.href = '/register'; }")  # [ADDED]

# [ADDED] 2) REGISTER PAGE
with gr.Blocks(title="Register") as register_page:  # [ADDED]
    gr.Markdown("## Register")  # [ADDED]
    r_email = gr.Textbox(label="Email")  # [ADDED]
    r_pw = gr.Textbox(label="Password", type="password")  # [ADDED]
    r_status = gr.Markdown()  # [ADDED]
    back_to_login = gr.Button("Back to Login")  # [ADDED]
    submit_reg = gr.Button("Create Account")  # [ADDED]

    submit_reg.click(  # [ADDED]
        None,
        inputs=[r_email, r_pw],
        outputs=r_status,
        js="""
        async (email, pw) => {
          try {
            const resp = await fetch('/auth/register', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({email, password: pw}),
              credentials: 'include'
            });
            if (!resp.ok) {
              const body = await resp.json().catch(()=>({detail:'Registration failed'}));
              return '❌ ' + (body.detail || 'Registration failed');
            }
            window.location.href = '/login';  // [ADDED] go back to login
            return '✅ Registered. Redirecting to login...';
          } catch(e) {
            return '❌ Network error';
          }
        }
        """
    )
    back_to_login.click(None, js="() => { window.location.href = '/login'; }")  # [ADDED]

with gr.Blocks(title="Telecom Support Chatbot") as chat_page:  # [ADDED]
    gr.Markdown("## Telecom Support Chatbot")  # [ADDED]

    convo_dropdown = gr.Dropdown(label="Conversations", choices=[], interactive=True)  # [ADDED]
    chatbot = gr.Chatbot(type="messages", height=560, label=None)  # [ADDED]
    with gr.Row():  # [ADDED]
        txt = gr.Textbox(placeholder="Enter your message…", scale=5)
        send_btn = gr.Button("Send", scale=1)
    status = gr.Markdown()  # [ADDED]

    async def load_boot(request: gr.Request):  # [ADDED]
        sid = request.cookies.get("sid")
        if not sid:
            # [ADDED] soft bounce to /login
            return gr.update(choices=[]), [], "Not logged in. Redirecting to /login...", gr.update(value=None)
        import httpx
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            resp = await client.get("/boot", headers={"x-sid": sid})
            if resp.status_code != 200:
                return gr.update(choices=[]), [], "Session expired. Redirecting to /login...", gr.update(value=None)
            data = resp.json()
            convs = data["conversations"]  # [FIX] matches /boot output
            labels = [f"{(c['title'] or 'Untitled')} ({c['id'][:6]})" for c in convs]
            curr_id = data["last_conversation_id"]
            label_value = next((lbl for lbl, c in zip(labels, convs) if c["id"] == curr_id), None)
            return gr.update(choices=labels, value=label_value), data["messages"], "", gr.update(value=label_value)

    chat_page.load(load_boot, inputs=None, outputs=[convo_dropdown, chatbot, status, convo_dropdown])  # [ADDED]

    async def pick_conversation(label, request: gr.Request):  # [ADDED]
        sid = request.cookies.get("sid")
        if not (sid and label):
            return []
        import httpx
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            convs = await client.get("/conversations", headers={"x-sid": sid})
            if convs.status_code != 200:
                return []
            convs = convs.json()
            labels = [f"{(c['title'] or 'Untitled')} ({c['id'][:6]})" for c in convs]
            id_by_label = {labels[i]: convs[i]["id"] for i in range(len(convs))}
            cid = id_by_label.get(label)
            if not cid:
                return []
            msgs = await client.get(f"/conversations/{cid}/messages", headers={"x-sid": sid})
            return msgs.json() if msgs.status_code == 200 else []

    convo_dropdown.change(pick_conversation, inputs=[convo_dropdown], outputs=[chatbot])  # [ADDED]

    async def on_send(user_text, messages, request: gr.Request):  # [ADDED]
        sid = request.cookies.get("sid")
        if not sid:
            yield messages + [{"role": "assistant", "content": "Please log in."}], ""
            return

        import httpx
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            boot = await client.get("/boot", headers={"x-sid": sid})
            cid = boot.json()["last_conversation_id"]
            await client.post(f"/conversations/{cid}/messages", headers={"x-sid": sid},
                              json={"role": "user", "content": user_text})

        messages = list(messages or [])
        messages.append({"role": "user", "content": user_text})
        yield messages, ""

        messages.append({"role": "assistant", "content": "..."})
        yield messages, ""

        pool = app.state.pool
        async with app.state.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content FROM messages WHERE conversation_id=$1 ORDER BY id ASC LIMIT 200", cid
            )
            history = [{"role": r["role"], "content": r["content"]} for r in rows]

        assistant_text = ""
        async for chunk in handle_message("webuser", user_text, history, pool):
            assistant_text += chunk
            messages[-1]["content"] = assistant_text
            yield messages, ""

        import httpx
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            await client.post(f"/conversations/{cid}/messages", headers={"x-sid": sid},
                              json={"role": "assistant", "content": assistant_text})

    txt.submit(on_send, inputs=[txt, chatbot], outputs=[chatbot, txt])  # [ADDED]
    send_btn.click(on_send, inputs=[txt, chatbot], outputs=[chatbot, txt])  # [ADDED]

# --------------------------
# Mount each page separately
# --------------------------
app = gr.mount_gradio_app(app, login_page, path="/login")      # [ADDED]
gr.mount_gradio_app(app, register_page, path="/register")      # [ADDED]
gr.mount_gradio_app(app, chat_page, path="/chat")              # [ADDED]

# [ADDED] redirect "/" to "/login"
@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login", status_code=307)
