from typing import Any, Generic, Type, TypeVar
from sqlalchemy.orm import Session
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: Session):
        self.model = model
        self.db = session

    def get_by_id(self, id: Any) -> ModelType | None:
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        return self.db.query(self.model).offset(skip).limit(limit).all()

