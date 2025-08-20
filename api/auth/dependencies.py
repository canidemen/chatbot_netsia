"""Auth dependencies for FastAPI"""
from fastapi import HTTPException, Request
from .utils import get_user_by_id
from core.config import SESSION_TTL

async def get_current_user(request: Request):
    """Dependency to get current authenticated user"""
    sid = request.cookies.get("sid") or request.headers.get("x-sid")
    if not sid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    cache = request.app.state.cache
    pool = request.app.state.pool

    user_id = await cache.get_user_id_for_sid(sid)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired")

    # Sliding session keep-alive
    await cache.refresh_sid(sid, ttl=SESSION_TTL)

    user = await get_user_by_id(pool, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"id": str(user["id"]), "email": user["email"]}