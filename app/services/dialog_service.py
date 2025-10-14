from typing import List, Dict
from sqlalchemy.orm import Session
import google.generativeai as genai
from google.generativeai import protos
from datetime import datetime, timedelta
from app.repositories.dialog_history_repository import DialogHistoryRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.client_repository import ClientRepository
from app.services.llm_service import get_llm_service
from app.services.tool_service import ToolService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.classification_service import ClassificationService
from app.services.prompt_builder_service import PromptBuilderService
from app.services.tool_orchestrator_service import ToolOrchestratorService
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.utils.debug_logger import gemini_debug_logger


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
        self.llm_service = get_llm_service()
        
        # Инициализируем ClassificationService
        self.classification_service = ClassificationService(self.llm_service)
        
        # Инициализируем PromptBuilderService
        self.prompt_builder = PromptBuilderService()
        
        # Инициализируем репозитории для ToolService
        self.service_repository = ServiceRepository(db_session)
        self.master_repository = MasterRepository(db_session)
        self.appointment_repository = AppointmentRepository(db_session)
        self.client_repository = ClientRepository(db_session)
        
        # Инициализируем Google Calendar Service
        self.google_calendar_service = GoogleCalendarService()
        
        # Создаем экземпляр ToolService
        self.tool_service = ToolService(
            service_repository=self.service_repository,
            master_repository=self.master_repository,
            appointment_repository=self.appointment_repository,
            google_calendar_service=self.google_calendar_service,
            client_repository=self.client_repository
        )
        
        # Создаем экземпляр ToolOrchestratorService
        self.tool_orchestrator = ToolOrchestratorService(
            llm_service=self.llm_service,
            tool_service=self.tool_service,
            prompt_builder=self.prompt_builder,
            client_repository=self.client_repository
        )
        
        # Кратковременная память о показанных записях для каждого пользователя
        # Формат: {user_id: [{"id": int, "details": str}, ...]}
        self.last_shown_appointments = {}
    
    def _build_dialog_context(self, dialogue_stage: str, user_id: int, client) -> str:
        """
        Формирует дополнительный контекст диалога на основе стадии и данных клиента.
        
        Args:
            dialogue_stage: Стадия диалога
            user_id: ID пользователя
            client: Объект клиента
            
        Returns:
            Строка с дополнительным контекстом
        """
        # Базовый контекст о записях для стадий просмотра, отмены и переноса
        if dialogue_stage in ['view_booking', 'cancellation_request', 'rescheduling']:
            try:
                appointments_data = self.tool_service.get_my_appointments(user_id)
                # Сохраняем записи в кратковременной памяти
                self.last_shown_appointments[user_id] = appointments_data
                
                if appointments_data:
                    if dialogue_stage == 'view_booking':
                        appointments_text = "Ваши предстоящие записи:\n"
                        for appointment in appointments_data:
                            appointments_text += f"- {appointment['details']}\n"
                        return (
                            f"ДАННЫЕ_ЗАПИСЕЙ: {appointments_text}. "
                            "Если данные содержат список записей — перескажи их кратко и дружелюбно, ничего не выдумывай. "
                            "Если там сказано, что записей нет — вежливо предложи помощь с записью."
                        )
                    else:  # cancellation_request или rescheduling
                        appointments_text = "Доступные записи для изменения:\n"
                        for appointment in appointments_data:
                            appointments_text += f"- {appointment['details']}\n"
                        return (
                            f"СКРЫТЫЙ_КОНТЕКСТ_ЗАПИСЕЙ: {appointments_text} "
                            f"Определи, к какой из этих записей относится запрос клиента, и вызови соответствующий инструмент "
                            f"({'cancel_appointment_by_id' if dialogue_stage == 'cancellation_request' else 'reschedule_appointment_by_id'}) "
                            "с правильным ID. Не показывай ID клиенту."
                        )
                else:
                    if dialogue_stage == 'view_booking':
                        return "У вас нет предстоящих записей."
                    else:
                        return "У клиента нет записей для отмены/переноса."
            except Exception:
                self.last_shown_appointments[user_id] = []
                return "Ошибка получения записей."
        
        return ""

    async def process_user_message(self, user_id: int, text: str) -> str:
        """
        Обрабатывает сообщение пользователя с использованием паттернов диалогов:
        1. Получает историю диалога из БД
        2. Сохраняет новое сообщение пользователя
        3. Классифицирует стадию диалога
        4. Извлекает релевантные паттерны для стадии
        5. Формирует динамический промпт с паттернами
        6. Запускает цикл генерации с вызовами инструментов
        7. Сохраняет финальный ответ в БД
        
        Args:
            user_id: ID пользователя Telegram
            text: Текст сообщения пользователя
            
        Returns:
            Сгенерированный ответ бота
        """
        # 0. Загружаем (или создаем) клиента
        client = self.client_repository.get_or_create_by_telegram_id(user_id)

        # 1. Получаем историю диалога (последние 20 сообщений)
        history_records = self.repository.get_recent_messages(user_id, limit=20)
        
        # Преобразуем историю в расширенный формат для Gemini
        dialog_history: List[Dict] = []
        for record in history_records:
            role = "user" if record.role == "user" else "model"
            dialog_history.append({
                "role": role,
                "parts": [{"text": record.message_text}]
            })
        
        # 2. Сохраняем новое сообщение пользователя в БД
        self.repository.add_message(
            user_id=user_id,
            role="user",
            message_text=text
        )
        
        # 3. Этап 1: Классификация стадии диалога
        print(f"[DEBUG] Начинаем классификацию для сообщения: '{text}'")
        print(f"[DEBUG] Доступные паттерны: {list(dialogue_patterns.keys())}")
        
        stage_and_pd = await self.classification_service.get_dialogue_stage(
            history=dialog_history,
            user_message=text,
            user_id=user_id
        )
        if isinstance(stage_and_pd, tuple):
            dialogue_stage, extracted_pd = stage_and_pd
        else:
            dialogue_stage, extracted_pd = stage_and_pd, {}

        # Если классификатор извлек ПДн — сохраняем их в БД
        if extracted_pd:
            update_data = {}
            if extracted_pd.get('name') and not client.first_name:
                update_data['first_name'] = extracted_pd['name']
            if extracted_pd.get('phone') and not client.phone_number:
                update_data['phone_number'] = extracted_pd['phone']
            if update_data:
                client = self.client_repository.update(client.id, update_data)
        
        # 4. Этап 2: Определение стратегии обработки (План А или План Б)
        print(f"[DEBUG] Результат классификации: '{dialogue_stage}'")
        
        # Быстрый путь для конфликтных ситуаций
        if dialogue_stage == 'conflict_escalation':
            print(f"[DEBUG] КОНФЛИКТНАЯ СТАДИЯ: Немедленная эскалация на менеджера")
            
            # Вызываем менеджера с текстом сообщения пользователя как причиной
            manager_response = self.tool_service.call_manager(text)
            
            # Сохраняем системный сигнал для будущей обработки
            print(f"[DEBUG] Системный сигнал: {manager_response['system_signal']}")
            
            # Сохраняем ответ бота в БД
            self.repository.add_message(
                user_id=user_id,
                role="model",
                message_text=manager_response['response_to_user']
            )
            
            # Возвращаем ответ пользователю и завершаем обработку
            return manager_response['response_to_user']
        
        if dialogue_stage is not None:
            # План А: Валидная стадия найдена - используем паттерны диалога
            print(f"[DEBUG] План А: Используем стадию '{dialogue_stage}'")
            
            # Формируем дополнительный контекст диалога
            dialog_context = self._build_dialog_context(dialogue_stage, user_id, client)
            
            # Формируем промпт через PromptBuilderService
            system_prompt = self.prompt_builder.build_generation_prompt(
                stage=dialogue_stage,
                dialog_history=dialog_history,
                dialog_context=dialog_context,
                client_name=client.first_name,
                client_phone_saved=bool(client.phone_number)
            )
        else:
            # План Б: Fallback - используем универсальный системный промпт
            print(f"[DEBUG] План Б: Используем fallback промпт")
            
            # Формируем промпт через PromptBuilderService
            system_prompt = self.prompt_builder.build_fallback_prompt(
                dialog_context="",
                client_name=client.first_name,
                client_phone_saved=bool(client.phone_number)
            )
        
        # 5. Этап 3: Генерация и выполнение инструментов
        bot_response_text, intermediate_history = await self.tool_orchestrator.execute_tool_cycle(
            system_prompt=system_prompt,
            history=dialog_history,
            user_message=text,
            user_id=user_id
        )
        
        # 7. Сохраняем финальный ответ бота в БД
        self.repository.add_message(
            user_id=user_id,
            role="model",
            message_text=bot_response_text
        )
        
        # 8. Возвращаем сгенерированный текст
        return bot_response_text
    
    def clear_history(self, user_id: int) -> int:
        """
        Очищает всю историю диалога для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Количество удаленных записей
        """
        return self.repository.clear_user_history(user_id)
    
    
    
    
    
    





