from sqlalchemy.orm import Session
from .base import BaseRepository
from app.models.service import Service

class ServiceRepository(BaseRepository[Service]):
    def __init__(self, session: Session):
        super().__init__(Service, session)

