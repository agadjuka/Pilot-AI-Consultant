from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from .base import BaseRepository
from app.models.master import Master

class MasterRepository(BaseRepository[Master]):
    def __init__(self, session: Session):
        super().__init__(Master, session)

    def get_masters_for_service(self, service_id: int) -> list[Master]:
        """Находит всех мастеров, которые выполняют указанную услугу."""
        return (
            self.db.query(Master)
            .join(Master.services)
            .filter(Master.services.any(id=service_id))
            .all()
        )
    
    def get_by_id_with_services(self, id: int) -> Master | None:
        """Находит мастера по ID и сразу подгружает связанные с ним услуги."""
        return (
            self.db.query(Master)
            .options(joinedload(Master.services))
            .filter(Master.id == id)
            .first()
        )

