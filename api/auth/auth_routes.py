"""Authentication routes"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends
from core.models import RegisterIn, LoginIn
from .utils import get_user_by_email
from .dependencies import get_current_user
from core.cache import ChatCache
from core.config import SESSION_TTL

router = APIRouter(prefix="/auth")

@router.post("/register")
async def register(payload: RegisterIn, request: Request):
    """Register a new user"""
    pool = request.app.state.pool
    existing_user = await get_user_by_email(pool, payload.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")
    
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

@router.post("/login")
async def login(payload: LoginIn, response: Response, request: Request):
    """Login user and create session"""
    pool = request.app.state.pool
    cache = request.app.state.cache
    
    user = await get_user_by_email(pool, payload.email)
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create session
    sid = await cache.create_session(user["id"], ttl=SESSION_TTL)

    response.set_cookie(
        key="sid",
        value=sid,
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "sid": sid}

@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout user and destroy session"""
    cache = request.app.state.cache
    sid = request.cookies.get("sid") or request.headers.get("x-sid")
    if sid:
        await cache.close_session(sid)
    response.delete_cookie("sid", path="/")
    return {"ok": True}

@router.get("/me")
async def me(user=Depends(get_current_user)):
    """Get current user info"""
    return user