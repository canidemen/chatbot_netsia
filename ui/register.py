"""Register page UI"""
import gradio as gr

def create_register_page():
    """Create the register page interface"""
    with gr.Blocks(title="Register") as register_page:
        gr.Markdown("## Register")
        r_email = gr.Textbox(label="Email")
        r_pw = gr.Textbox(label="Password", type="password")
        r_status = gr.Markdown()
        back_to_login = gr.Button("Back to Login")
        submit_reg = gr.Button("Create Account")

        submit_reg.click(
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
                window.location.href = '/login';
                return '✅ Registered. Redirecting to login...';
              } catch(e) {
                return '❌ Network error';
              }
            }
            """
        )
        back_to_login.click(None, js="() => { window.location.href = '/login'; }")

    return register_page