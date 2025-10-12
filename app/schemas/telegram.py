from pydantic import BaseModel, Field
from typing import Optional


class User(BaseModel):
    """Модель пользователя Telegram."""
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None


class Chat(BaseModel):
    """Модель чата Telegram."""
    id: int
    type: str


class Message(BaseModel):
    """Модель сообщения Telegram."""
    message_id: int
    chat: Chat
    text: Optional[str] = None
    from_user: Optional[User] = Field(None, alias="from")


class Update(BaseModel):
    """Модель обновления от Telegram."""
    update_id: int
    message: Optional[Message] = None

