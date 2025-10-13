from typing import List, Dict
from sqlalchemy.orm import Session
from app.repositories.dialog_history_repository import DialogHistoryRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.gemini_service import gemini_service
from app.services.tool_service import ToolService


class DialogService:
    """
    Оркестратор диалоговой логики.
    Координирует работу между хранилищем истории диалогов и AI-моделью.
    """
    
    def __init__(self, db_session: Session):
        """
        Инициализирует сервис диалога.
        
        Args:
            db_session: Сессия базы данных SQLAlchemy
        """
        self.repository = DialogHistoryRepository(db_session)
        self.gemini_service = gemini_service
        
        # Инициализируем репозитории для ToolService
        self.service_repository = ServiceRepository(db_session)
        self.master_repository = MasterRepository(db_session)
        
        # Создаем экземпляр ToolService
        self.tool_service = ToolService(
            service_repository=self.service_repository,
            master_repository=self.master_repository
        )

    async def process_user_message(self, user_id: int, text: str) -> str:
        """
        Обрабатывает сообщение пользователя:
        1. Получает историю диалога из БД
        2. Сохраняет новое сообщение пользователя
        3. Генерирует ответ через Gemini
        4. Сохраняет ответ бота в БД
        5. Возвращает сгенерированный текст
        
        Args:
            user_id: ID пользователя Telegram
            text: Текст сообщения пользователя
            
        Returns:
            Сгенерированный ответ бота
        """
        # 1. Получаем историю диалога (последние 20 сообщений)
        history_records = self.repository.get_recent_messages(user_id, limit=20)
        
        # Преобразуем историю в формат для Gemini
        dialog_history: List[Dict[str, str]] = [
            {
                "role": record.role,
                "text": record.message_text
            }
            for record in history_records
        ]
        
        # 2. Сохраняем новое сообщение пользователя в БД
        self.repository.add_message(
            user_id=user_id,
            role="user",
            message_text=text
        )
        
        # 3. Генерируем ответ через Gemini с передачей ToolService
        bot_response = await self.gemini_service.generate_response(
            user_message=text,
            tool_service=self.tool_service,
            dialog_history=dialog_history
        )
        
        # 4. Сохраняем ответ бота в БД
        self.repository.add_message(
            user_id=user_id,
            role="model",
            message_text=bot_response
        )
        
        # 5. Возвращаем сгенерированный текст
        return bot_response




