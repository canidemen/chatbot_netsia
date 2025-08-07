from fastapi import FastAPI
import gradio as gr, uuid
from chatbot import handle_message
from cache import ChatCache
from contextlib import asynccontextmanager
import asyncpg
from redis.asyncio import Redis
import hashlib
import time

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



with gr.Blocks(title="Telecom Support Chatbot") as demo:
    gr.Markdown("## Telecom Support Chatbot")
    chatbot = gr.Chatbot(type="messages", height=560, label=None)
    with gr.Row():
        txt = gr.Textbox(placeholder="Enter your message…", scale=5)
        send_btn = gr.Button("Send", scale=1)

    # Holds "session_<hash>" so we can reuse across events
    session_state = gr.State()

    # 1) Load previous messages on page load (hydrate the chat)
    async def on_load(request: gr.Request):
        user_id = create_user_fingerprint(request)
        session_id = f"session_{user_id}"
        prev = await app.state.cache.get_history(session_id) or []
        # Return: set chatbot to prev messages and remember session_id
        print("prev = ", prev)
        return prev, session_id

    demo.load(on_load, inputs=None, outputs=[chatbot, session_state])

    # 2) Send handler: append user msg, stream assistant, store once at end
    async def on_send(user_text, messages, session_id, request: gr.Request):
        start_1 = time.perf_counter()

        cache = app.state.cache
        pool = app.state.pool

        # Defensive: ensure messages is always a list
        messages = list(messages or [])

        # Step 0: If session_id missing (rare, new tab), regenerate it and load history
        if not session_id:
            user_id = create_user_fingerprint(request)
            session_id = f"session_{user_id}"
            messages = await cache.get_history(session_id) or []

        # Step 1: Add user message, save to cache, and yield so user sees it instantly
        user_msg = {"role": "user", "content": user_text}
        messages.append(user_msg)
        await cache.store_message(session_id, role="user", content=user_text)
        yield messages, ""  # Input clears, user sees their message

        total_1 = time.perf_counter() - start_1
        print(f"Total first half before-stream duration: {total_1:.2f} seconds")

        start_2 = time.perf_counter()

        # Step 2: Add blank assistant message, yield so bubble appears instantly
        assistant_msg = {"role": "assistant", "content": "..."}
        messages.append(assistant_msg)
        yield messages, ""  # User sees empty assistant bubble right away

        total_2 = time.perf_counter() - start_2
        print(f"Total second half before-stream duration: {total_2:.2f} seconds")

        # Step 3: Stream assistant's reply into last message, updating content each chunk
        start_3 = time.perf_counter()

        assistant_text = ""
        user_id = session_id.replace("session_", "", 1)
        prev_history = await cache.get_history(session_id) or []

        total_3_5 = time.perf_counter() - start_3
        print(f"Total third half before-yield duration: {total_3_5:.2f} seconds")


        async for chunk in handle_message(user_id, user_text, prev_history, pool):
            assistant_text += chunk
            messages[-1]["content"] = assistant_text
            yield messages, ""  # UI updates with each token/chunk
        
        total_3 = time.perf_counter() - start_3
        print(f"Total third half stream duration: {total_3:.2f} seconds")

        # Step 4: Store final assistant message in cache (one entry per message)
        if assistant_text:
            await cache.store_message(session_id, role="assistant", content=assistant_text)


    # Wire Enter key and Send button
    txt.submit(on_send, inputs=[txt, chatbot, session_state], outputs=[chatbot, txt])
    send_btn.click(on_send, inputs=[txt, chatbot, session_state], outputs=[chatbot, txt])

# Queue + mount under FastAPI
demo.queue()
app = gr.mount_gradio_app(app, demo, path="/gradio")