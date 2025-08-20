"""Login page UI"""
import gradio as gr

def create_login_page():
    """Create the login page interface"""
    with gr.Blocks(title="Login") as login_page:
        gr.Markdown("## Login")
        email = gr.Textbox(label="Email")
        pw = gr.Textbox(label="Password", type="password")
        out = gr.Markdown()
        go_register = gr.Button("Go to Register")
        login_btn = gr.Button("Login")

        login_btn.click(
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
                  credentials: 'include'
                });
                if (!resp.ok) {
                  const body = await resp.json().catch(()=>({detail:'Login failed'}));
                  return '❌ ' + (body.detail || 'Login failed');
                }
                window.location.href = '/chat';
                return '✅ Logged in. Redirecting...';
              } catch (e) {
                return '❌ Network error';
              }
            }
            """
        )
        go_register.click(None, js="() => { window.location.href = '/register'; }")

    return login_page