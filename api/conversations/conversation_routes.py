"""Conversation and message routes"""
from fastapi import APIRouter, HTTPException, Depends, Request
from core.models import ConversationCreate, MessageIn
from api.auth.dependencies import get_current_user

router = APIRouter(prefix="/conversations")

@router.get("/boot")
async def boot_info(request: Request, user=Depends(get_current_user)):
    """Returns sidebar and last active conversation on load"""
    pool = request.app.state.pool
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
            
        conversations = await conn.fetch(
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

    return {
        "user": user, 
        "last_conversation_id": last_active, 
        "conversations": [
            {"id": r["id"], "title": r["title"], "updated_at": r["updated_at"].isoformat()}
            for r in conversations
        ], 
        "messages": [{"role": r["role"], "content": r["content"]} for r in msgs],
    }

@router.get("")
async def list_conversations(request: Request, user=Depends(get_current_user)):
    """List user's conversations"""
    pool = request.app.state.pool
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
async def create_conversation(payload: ConversationCreate, request: Request, user=Depends(get_current_user)):
    """Create a new conversation"""
    pool = request.app.state.pool
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
async def get_messages(conversation_id: str, request: Request, limit: int = 200, user=Depends(get_current_user)):
    """Get messages for a conversation"""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        ok = await conn.fetchval(
            "SELECT 1 FROM conversations WHERE id=$1 AND user_id=$2",
            conversation_id, user["id"]
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        await conn.execute(
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
            ORDER BY position ASC
            LIMIT $2
            """,
            conversation_id, limit,
        )
        print("rows")
        print([{"role": r["role"], "content": r["content"]} for r in rows])
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    
@router.post("/{conversation_id}/messages")
async def add_message(conversation_id: str, payload: MessageIn, request: Request, user=Depends(get_current_user)):
    """Add a message to a conversation"""
    pool = request.app.state.pool
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

@router.put("/{conversation_id}/title")
async def update_conversation_title(conversation_id: str, title: str, request: Request, user=Depends(get_current_user)):
    """Update conversation title"""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        # Verify user owns this conversation
        ok = await conn.fetchval(
            "SELECT 1 FROM conversations WHERE id=$1 AND user_id=$2",
            conversation_id, user["id"]
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Update the title
        await conn.execute(
            """
            UPDATE conversations SET title=$1, updated_at=now()
            WHERE id=$2
            """,
            title, conversation_id
        )
        return {"ok": True, "title": title}

@router.get("/{conversation_id}/is-first-message")
async def is_first_message(conversation_id: str, request: Request, user=Depends(get_current_user)):
    """Check if this would be the first user message in the conversation"""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        # Verify user owns this conversation
        ok = await conn.fetchval(
            "SELECT 1 FROM conversations WHERE id=$1 AND user_id=$2",
            conversation_id, user["id"]
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Check if there are any user messages
        user_message_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM messages 
            WHERE conversation_id=$1 AND role='user'
            """,
            conversation_id
        )
        
        # Also check if title is still default
        current_title = await conn.fetchval(
            "SELECT title FROM conversations WHERE id=$1",
            conversation_id
        )
        
        is_first = user_message_count == 0 and current_title == "New Conversation"
        return {"is_first_message": is_first}