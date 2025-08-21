"""Chat page UI"""
import gradio as gr
import httpx
from services.chatbot import handle_message
from core.config import BASE_URL

def create_chat_page():
    """Create the chat page interface"""
    with gr.Blocks(
        title="Telecom Support Chatbot",
        css="""
        /* Chat Interface Styles */

        /* Prevent page scrolling and fit to viewport */
        html, body {
            height: 100vh;
            overflow: hidden;
            margin: 0;
            padding: 0;
        }

        .gradio-container {
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
        }

        .main {
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
        }

        /* Sidebar Styles */
        .sidebar {
            background-color: #f7f7f8;
            border-right: 1px solid #e5e5e5;
            height: 100vh;
            max-height: 100vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        
        .sidebar:hover {
            background-color: transparent !important;
        }

        .sidebar-header {
            padding: 16px;
            border-bottom: 1px solid #e5e5e5;
            font-weight: 600;
            color: #374151;
            margin: 0;
            font-size: 1.5em;
        }

        /* Conversation List Styles */
        .conversation-item {
            padding: 12px 16px;
            margin: 4px 8px;
            border-radius: 8px;
            cursor: pointer;
            transition: background-color 0.2s;
            border: 1px solid transparent;
            display: block !important;
            width: 95% !important;
            box-sizing: border-box;
            background-color: transparent;
        }

        .conversation-item label:hover {
            background-color: #d0e7ff !important;
            border-radius: 8px;
            cursor: pointer;
        }

        .conversation-item.selected {
            background-color: #e3f2fd;
            border-color: #2196f3;
        }

        .conversation-item label {
            display: block !important;
            width: 100% !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Force radio buttons to stack vertically */
        .conversation-item .wrap {
            flex-direction: column !important;
        }

        .conversation-item input[type="radio"] {
            margin-right: 8px;
        }

        /* New Chat Button */
        .new-chat-btn {
            margin: 16px 8px 8px 8px;
            width: calc(100% - 16px);
            background-color: #10a37f;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px;
            font-weight: 500;
        }

        .new-chat-btn:hover {
            background-color: #0d8f6f;
        }

        /* Main Chat Area */
        .main-header {
            padding: 16px;
            margin: 0;
            font-weight: 600;
            color: #374151;
            font-size: 1.5em;
        }

        .chat-column {
            height: 150vh;
            max-height: 200vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .chat-messages {
            flex: 5;
            overflow-y: auto;
            min-height: 0;
        }

        .chat-input {
            flex: 1;
            flex-shrink: 0;
            padding: 16px;
            border-top: 1px solid #e5e5e5;
            background: white;
        }
        """
    ) as chat_page:
        
        with gr.Row():
            # Left Sidebar (25% width)
            with gr.Column(scale=1, elem_classes=["sidebar"]):
                gr.Markdown("## Conversations", elem_classes=["sidebar-header"])
                new_chat_btn = gr.Button("+ New Chat", variant="primary", elem_classes=["new-chat-btn"])
                
                # Conversation list using Radio buttons for better UX
                conversation_list = gr.Radio(
                    choices=[],
                    label="",
                    show_label=False,
                    interactive=True,
                    elem_classes=["conversation-item"]
                )
            
            # Main Chat Area (75% width)
            with gr.Column(scale=3, elem_classes=["chat-column"]):
                gr.Markdown("## Telecom Support Chatbot", elem_classes=["main-header"])
                
                # Chat messages area - flexible height
                with gr.Column(elem_classes=["chat-messages"]):
                    chatbot = gr.Chatbot(type="messages", height="100vh", label=None)
                
                # Input area - fixed at bottom
                with gr.Column(elem_classes=["chat-input"]):
                    with gr.Row():
                        txt = gr.Textbox(
                            placeholder="Enter your message…", 
                            scale=5,
                            container=False,
                            show_label=False
                        )
                        send_btn = gr.Button("Send", scale=1, variant="primary")
                    
                    status = gr.Markdown()

        async def load_boot(request: gr.Request):
            """Load initial data on page load"""
            sid = request.cookies.get("sid")
            if not sid:
                return gr.update(choices=[]), [], "Not logged in. Redirecting to /login..."
            
            async with httpx.AsyncClient(base_url=BASE_URL) as client:
                resp = await client.get("/conversations/boot", headers={"x-sid": sid})
                if resp.status_code != 200:
                    return gr.update(choices=[]), [], "Session expired. Redirecting to /login..."
                
                data = resp.json()
                convs = data["conversations"]
                choices = [(c['title'] or 'Untitled', c['id']) for c in convs]
                curr_id = data["last_conversation_id"]
                current_value = curr_id  # Direct ID selection
                return gr.update(choices=choices, value=current_value), data["messages"], ""

        chat_page.load(load_boot, inputs=None, outputs=[conversation_list, chatbot, status])

        async def pick_conversation(conversation_id, request: gr.Request):
            """Switch to a different conversation"""
            sid = request.cookies.get("sid")
            if not (sid and conversation_id):
                return []
            
            async with httpx.AsyncClient(base_url=BASE_URL) as client:
                # Direct ID usage - no need to fetch all conversations!
                msgs = await client.get(f"/conversations/{conversation_id}/messages", headers={"x-sid": sid})
                return msgs.json() if msgs.status_code == 200 else []

        async def create_new_chat(request: gr.Request):
            """Create a new conversation"""
            sid = request.cookies.get("sid")
            if not sid:
                return gr.update(), []
            
            async with httpx.AsyncClient(base_url=BASE_URL) as client:
                # Create new conversation
                resp = await client.post("/conversations", headers={"x-sid": sid}, 
                                       json={"title": "New Conversation"})
                if resp.status_code != 200:
                    return gr.update(), []
                
                # Refresh conversation list
                convs = await client.get("/conversations", headers={"x-sid": sid})
                if convs.status_code != 200:
                    return gr.update(), []
                
                convs = convs.json()
                choices = [(c['title'] or 'Untitled', c['id']) for c in convs]
                new_conv_id = convs[0]['id'] if convs else None  # New conversation should be first
                
                return gr.update(choices=choices, value=new_conv_id), []

        # Event bindings
        conversation_list.change(pick_conversation, inputs=[conversation_list], outputs=[chatbot])
        new_chat_btn.click(create_new_chat, inputs=[], outputs=[conversation_list, chatbot])

        async def on_send(user_text, messages, request: gr.Request):
            """Handle sending a message"""
            sid = request.cookies.get("sid")
            if not sid:
                yield messages + [{"role": "assistant", "content": "Please log in."}], "", gr.update()
                return

            # STEP 1: Show user message immediately
            messages = list(messages or [])
            messages.append({"role": "user", "content": user_text})
            yield messages, "", gr.update()

            # STEP 2: Show "thinking" indicator
            messages.append({"role": "assistant", "content": "..."})
            yield messages, "", gr.update()

            # STEP 3: Save user message to database (in background)
            async with httpx.AsyncClient(base_url=BASE_URL) as client:
                boot = await client.get("/conversations/boot", headers={"x-sid": sid})
                cid = boot.json()["last_conversation_id"]
                
                # Check if this is the first message
                first_check = await client.get(f"/conversations/{cid}/is-first-message", headers={"x-sid": sid})
                is_first_message = first_check.json().get("is_first_message", False) if first_check.status_code == 200 else False
                
                # Save the user message
                await client.post(f"/conversations/{cid}/messages", headers={"x-sid": sid},
                                  json={"role": "user", "content": user_text})
                
                # Generate AI title if this is the first message
                if is_first_message:
                    # Import here to avoid circular imports
                    from services.title_generator import generate_conversation_title
                    
                    try:
                        new_title = await generate_conversation_title(user_text)
                        # Update the conversation title
                        await client.put(f"/conversations/{cid}/title", 
                                       headers={"x-sid": sid},
                                       params={"title": new_title})
                        print(f"✅ Generated title: '{new_title}'")
                        
                        # Refresh conversation list to show new title immediately
                        convs_resp = await client.get("/conversations", headers={"x-sid": sid})
                        if convs_resp.status_code == 200:
                            convs = convs_resp.json()
                            choices = [(c['title'] or 'Untitled', c['id']) for c in convs]
                            # Yield updated conversation list immediately with current conversation selected
                            yield messages, "", gr.update(choices=choices, value=cid)
                            
                    except Exception as e:
                        print(f"❌ Failed to generate title: {e}")
                        # Continue without title update

            # Get conversation history and generate response
            from main import app  # Import here to avoid circular imports
            pool = app.state.pool
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT role, content FROM messages WHERE conversation_id=$1 ORDER BY id ASC LIMIT 200", cid
                )
                history = [{"role": r["role"], "content": r["content"]} for r in rows]

            assistant_text = ""
            async for chunk in handle_message("webuser", user_text, history, pool):
                assistant_text += chunk
                messages[-1]["content"] = assistant_text
                yield messages, "", gr.update()

            # Save assistant response
            async with httpx.AsyncClient(base_url=BASE_URL) as client:
                await client.post(f"/conversations/{cid}/messages", headers={"x-sid": sid},
                                  json={"role": "assistant", "content": assistant_text})

        txt.submit(on_send, inputs=[txt, chatbot], outputs=[chatbot, txt, conversation_list])
        send_btn.click(on_send, inputs=[txt, chatbot], outputs=[chatbot, txt, conversation_list])

    return chat_page