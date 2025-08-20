"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import gradio as gr

# Import modules
from core.database import create_database_pool, create_redis_client, create_cache
from api.auth.auth_routes import router as auth_router
from api.conversations.conversation_routes import router as conversations_router
from ui.login import create_login_page
from ui.register import create_register_page
from ui.chat import create_chat_page

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    redis = await create_redis_client()
    app.state.redis = redis
    app.state.cache = create_cache(redis)
    app.state.pool = await create_database_pool()

    try:
        yield  # App runs here
    finally:
        # Shutdown
        await redis.close()
        await app.state.pool.close()

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Include routers
app.include_router(auth_router)
app.include_router(conversations_router)

# Create UI pages
login_page = create_login_page()
register_page = create_register_page()
chat_page = create_chat_page()

# Mount Gradio apps
app = gr.mount_gradio_app(app, login_page, path="/login")
app = gr.mount_gradio_app(app, register_page, path="/register")
app = gr.mount_gradio_app(app, chat_page, path="/chat")

@app.get("/")
async def root():
    """Redirect root to login"""
    return RedirectResponse(url="/login", status_code=307)