import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from classifier import classify
from datetime import datetime, timezone
from aiokafka import AIOKafkaProducer
import json, asyncio
import db
import time

BOOTSTRAP = "localhost:9092"
TOPIC = "support-tickets"

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

openai = AsyncOpenAI()
system_prompt = [{
    "role": "system",
    "content": (
        "You are an expert Tier-2 telecom-support engineer for Netsia Inc. "
        "Always ask 1-2 clarifying questions if the user's description is incomplete. "
        "When you give a fix, list steps in numbered order and cite the exact menu names/buttons. "
        "Escalate to human only after you've run through all scripted diagnostics unless the user clearly requests escalation. "
        "If the user explicitly requests a human, or uses phrases like 'agent', 'representative', 'supervisor', or 'escalate', CALL the escalate_ticket function with reason='user_requested' instead of answering normally. "
        "After any tool call, summarize succinctly and ask if anything else is needed. "
        "If you have already escalated within the last 5 minutes for this user, do not escalate again; instead inform them it's already escalated."
    )
}]

escalate_function = {
    "name": "escalate_ticket",
    "description": (
        "Escalate the current support interaction to a human Tier-3 agent. "
        "Call this when the user explicitly asks for a human/manager/escalation OR when troubleshooting is blocked."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "Customer user ID."},
            "user_message": {"type": "string", "description": "The latest user message."},
            "reason": {"type": "string", "description": "Reason for escalation (user_requested, low_confidence, billing_exception, abusive_language, etc.)."}
        },
        "required": ["user_id", "user_message", "reason"],
        "additionalProperties": False
    }
}

functions = [escalate_function]

async def escalate(ticket):
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await producer.start()
    try:
        await producer.send_and_wait(
            TOPIC,
            json.dumps(ticket).encode(),
            key=ticket["userId"].encode()
        )
        print("ticket sent")
    finally:
        await producer.stop()

async def escalate_and_record(pool, user_id, user_message, reason):
    ticket = {
        "userId": user_id,
        "message": user_message,
        "label": None,
        "confidence": None,
        "escalated": True,
        "reason": reason,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    ticket_id, created_at = await db.db_insert_async(pool, ticket)

    asyncio.create_task(escalate(ticket | {"id": ticket_id}))

    return escalation_message(ticket_id, created_at)

async def call_tool(name, arguments, pool):
    if name == "escalate_ticket":
        result_message = await escalate_and_record(
            pool,
            arguments["user_id"],
            arguments["user_message"],
            arguments["reason"],
        )
        return {"status": "ok", "tool": name, "result": result_message}
    return {"status": "error", "error": f"Unknown tool {name}"}

async def stream_answer(messages):
    stream = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream=True,
        temperature=0.3,
    )
    resp = ""
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            resp += delta
            yield resp

async def process_user_message(user_id, text, history, pool, label, confidence):
    ticket = {
        "userId": user_id,
        "message": text,
        "label": label,
        "confidence": confidence,
        "escalated": False,
        "reason": "",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await db.db_insert_async(pool, ticket)

    messages = system_prompt + history + [{"role": "user", "content": text}]

    # Decision pass (no streaming) to see if model wants a tool
    first = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        functions=functions,
        function_call="auto",
        temperature=0.3,
    )

    choice = first.choices[0]
    fn_call = getattr(choice.message, "function_call", None)

    if fn_call and fn_call.name == "escalate_ticket":
        args = json.loads(fn_call.arguments or "{}")
        args.setdefault("user_id", user_id)
        args.setdefault("user_message", text)
        args.setdefault("reason", "user_requested")

        tool_result = await call_tool(fn_call.name, args, pool)

        #Append the original assistant message (with function_call) + function result
        followup_messages = (
            messages
            + [choice.message]          #contains function_call
            + [{
                "role": "function",
                "name": fn_call.name,
                "content": json.dumps(tool_result),
            }]
        )

        final_resp = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=followup_messages,
            temperature=0.3,
        )
        yield final_resp.choices[0].message.content
        return
    
    # no tool: stream answer
    async for chunk in stream_answer(messages):
        yield chunk

async def handle_message(user_id, text, history, pool):

    raw_label, confidence = classify(text)
    label = normalize_label(raw_label)

    if label is None or confidence is None:
        msg = await escalate_and_record(pool, user_id, text, reason="low_confidence")
        yield msg
        return

    async for output in process_user_message(user_id, text, history, pool, label, confidence):
        yield output

def normalize_label(raw_label):
    if not raw_label:
        return None

    short = raw_label.split(":")[0].strip()

    return short[:32]

def escalation_message(ticket_id, created_at):
    ts = created_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"I'm transferring this to a human agent (Ticket #{ticket_id} created at {ts}). "
        "They'll get back to you as soon as possible. Is there anything else I can help you with?"
    )


async def safe_escalate(ticket):
    print("in safe escalate")
    try:
        await escalate(ticket)
    except Exception as e:
        print("ESCALATION FAILED")
