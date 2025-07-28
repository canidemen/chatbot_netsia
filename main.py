from fastapi import FastAPI  
import gradio as gr, uuid
from chatbot import handle_message
from psycopg2.pool import ThreadedConnectionPool
    
app = FastAPI()

pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn="postgresql://postgres:admin123@localhost:5432/postgres")


async def chat(message, history, request:gr.Request):             #add request:gr.Request if you want metadata, cookies etc.
    user_id = request.session_hash or str(uuid.uuid4())[:8]        #random user id, maybe change later

    async for chunk in handle_message(user_id, message, history, pool):
        yield chunk


demo = gr.ChatInterface(
    fn=chat,
    type="messages",
    title="Telecom Support Chatbot",
    description="Enter your message. The AI will classify your issue or escalate it if uncertain."
)


demo.queue()

app = gr.mount_gradio_app(app, demo, path="/gradio")
