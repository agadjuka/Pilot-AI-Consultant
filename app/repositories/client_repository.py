from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository
from app.models.client import Client


class ClientRepository(BaseRepository[Client]):
    def __init__(self, session: Session):
        super().__init__(Client, session)

    def get_by_telegram_id(self, telegram_id: int) -> Optional[Client]:
        return self.db.query(Client).filter(Client.telegram_id == telegram_id).first()

    def get_or_create_by_telegram_id(self, telegram_id: int) -> Client:
        client = self.get_by_telegram_id(telegram_id)
        if client:
            return client
        client = Client(telegram_id=telegram_id)
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def update(self, client_id: int, data: Dict[str, Any]) -> Client:
        client = self.get_by_id(client_id)
        if not client:
            raise ValueError("Клиент не найден")
        for key, value in data.items():
            if hasattr(client, key):
                setattr(client, key, value)
        self.db.commit()
        self.db.refresh(client)
        return client


