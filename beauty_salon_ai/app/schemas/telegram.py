from pydantic import BaseModel
from typing import Optional

class Chat(BaseModel):
    id: int
    type: str

class Message(BaseModel):
    message_id: int
    chat: Chat
    text: Optional[str] = None

class Update(BaseModel):
    update_id: int
    message: Optional[Message] = None

