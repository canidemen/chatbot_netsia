"""AI-powered conversation title generation"""
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def generate_conversation_title(user_message: str) -> str:
    """
    Generate a concise, descriptive title for a conversation based on the first user message.
    
    Args:
        user_message: The first message from the user
        
    Returns:
        A short, descriptive title (3-6 words)
    """
    try:
        prompt = f"""Generate a short, descriptive title (3-6 words) for a telecom support conversation based on this user message:

"{user_message}"

The title should:
- Be concise and professional
- Capture the main issue or topic
- Be suitable for a support ticket
- Not include quotes or special characters

Examples:
- "Internet Connection Issues"
- "Billing Question"
- "Router Setup Help"
- "Slow WiFi Speed"

Title:"""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,  # Keep it short
            temperature=0.3,  # Consistent but not too rigid
        )
        
        title = response.choices[0].message.content.strip()
        
        # Clean up the title (remove quotes, limit length)
        title = title.replace('"', '').replace("'", "")
        if len(title) > 50:
            title = title[:47] + "..."
            
        return title
        
    except Exception as e:
        print(f"Error generating title: {e}")
        # Fallback to a simple truncated version
        fallback = user_message[:30] + "..." if len(user_message) > 30 else user_message
        return fallback