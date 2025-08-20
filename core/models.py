from pydantic import BaseModel, EmailStr

# Auth Models
class RegisterIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

# Conversation Models
class ConversationCreate(BaseModel):
    title: str

class MessageIn(BaseModel):
    role: str    # 'user' or 'assistant' or 'system' (or 'tool'?)
    content: str