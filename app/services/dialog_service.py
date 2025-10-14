from typing import List, Dict
from sqlalchemy.orm import Session
import google.generativeai as genai
from google.generativeai import protos
from datetime import datetime, timedelta
from app.repositories.dialog_history_repository import DialogHistoryRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.gemini_service import get_gemini_service
from app.services.tool_service import ToolService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.classification_service import ClassificationService
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
        self.gemini_service = get_gemini_service()
        
        # Инициализируем ClassificationService
        self.classification_service = ClassificationService(self.gemini_service)
        
        # Инициализируем репозитории для ToolService
        self.service_repository = ServiceRepository(db_session)
        self.master_repository = MasterRepository(db_session)
        
        # Инициализируем Google Calendar Service
        self.google_calendar_service = GoogleCalendarService()
        
        # Создаем экземпляр ToolService
        self.tool_service = ToolService(
            service_repository=self.service_repository,
            master_repository=self.master_repository,
            google_calendar_service=self.google_calendar_service
        )

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
        dialogue_stage = await self.classification_service.get_dialogue_stage(
            history=dialog_history,
            user_message=text
        )
        
        # 4. Этап 2: Определение стратегии обработки (План А или План Б)
        if dialogue_stage is not None:
            # План А: Валидная стадия найдена - используем паттерны диалога
            stage_patterns = dialogue_patterns.get(dialogue_stage, {})
            principles = stage_patterns.get("principles", [])
            examples = stage_patterns.get("examples", [])
            
            # Формируем динамический системный промпт на основе паттернов
            system_prompt = self._build_dynamic_system_prompt(principles, examples, dialog_history)
        else:
            # План Б: Fallback - используем универсальный системный промпт
            system_prompt = self._build_fallback_system_prompt()
        
        # 5. Этап 3: Генерация и выполнение инструментов
        bot_response_text = await self._execute_generation_cycle(
            user_id=user_id,
            user_message=text,
            dialog_history=dialog_history,
            system_prompt=system_prompt
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
    
    def _build_dynamic_system_prompt(self, principles: List[str], examples: List[str], dialog_history: List[Dict]) -> str:
        """
        Формирует динамический системный промпт на основе паттернов стадии диалога.
        
        Args:
            principles: Принципы для текущей стадии диалога
            examples: Примеры для текущей стадии диалога
            dialog_history: История диалога
            
        Returns:
            Сформированный системный промпт
        """
        # Базовая персона
        base_persona = """Ты — AI-консультант салона красоты "Элегант". Твоя задача — помочь клиентам записаться на услуги, предоставить информацию о мастерах и услугах, ответить на вопросы о ценах и расписании.

Твой стиль общения:
- Дружелюбный и профессиональный
- Используй эмодзи для создания теплой атмосферы
- Будь конкретным в ответах
- Всегда предлагай конкретные варианты записи
- Если информации недостаточно — задавай уточняющие вопросы"""

        # Определяем контекст диалога
        dialog_context = ""
        if not dialog_history:
            dialog_context = "Это первое сообщение клиента. Обязательно поздоровайся в ответ."

        # Формируем принципы
        principles_text = ""
        if principles:
            principles_text = "\n\nПринципы для текущей стадии диалога:\n"
            for i, principle in enumerate(principles, 1):
                principles_text += f"{i}. {principle}\n"

        # Формируем примеры
        examples_text = ""
        if examples:
            examples_text = "\n\nПримеры ответов для текущей стадии:\n"
            for i, example in enumerate(examples, 1):
                examples_text += f"{i}. {example}\n"

        # Собираем финальный промпт
        system_prompt = f"{base_persona}{principles_text}{examples_text}"
        
        if dialog_context:
            system_prompt += f"\n\nКонтекст диалога: {dialog_context}"

        return system_prompt
    
    def _build_fallback_system_prompt(self) -> str:
        """
        Формирует универсальный системный промпт для fallback режима.
        Используется когда классификация стадии диалога не удалась.
        
        Returns:
            Универсальный системный промпт
        """
        return """Ты — Кэт, вежливый и услужливый администратор салона красоты "Элегант". 

Твоя основная задача — помогать клиентам с записью на услуги салона красоты. 

Если клиент задает вопрос не по теме салона красоты (например, о науке, политике, личных темах), вежливо ответь, что ты не можешь помочь с этим, и верни диалог к услугам салона.

Всегда будь дружелюбной, используй эмодзи для создания теплой атмосферы, и предлагай конкретные варианты записи на услуги салона."""
    
    async def _execute_generation_cycle(self, user_id: int, user_message: str, dialog_history: List[Dict], system_prompt: str) -> str:
        """
        Выполняет цикл генерации ответа с вызовами инструментов.
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            dialog_history: История диалога
            system_prompt: Системный промпт
            
        Returns:
            Финальный ответ бота
        """
        # Формируем полную историю с системной инструкцией
        full_history = self._build_full_history_with_system_prompt(dialog_history, system_prompt)
        
        # Создаем чат один раз для всего цикла
        chat = self.gemini_service.create_chat(full_history)
        
        # Запускаем цикл обработки Function Calling
        max_iterations = 5
        iteration = 0
        bot_response_text = None
        current_message = user_message
        
        # Для логирования - собираем информацию о каждой итерации
        debug_iterations = []
        
        while iteration < max_iterations:
            iteration += 1
            
            # Информация для debug логирования текущей итерации
            iteration_log = {
                "iteration": iteration,
                "request": "",
                "response": "",
                "function_calls": [],
                "final_answer": ""
            }
            
            # Логируем запрос
            if isinstance(current_message, str):
                iteration_log["request"] = f"Текст: {current_message}"
            else:
                iteration_log["request"] = f"Function Response (результаты {len(current_message)} функций)"
            
            # Получаем ответ от Gemini
            response_content = await self.gemini_service.send_message_to_chat(
                chat=chat,
                message=current_message
            )
            
            # Анализируем ответ
            has_function_call = False
            has_text = False
            function_response_parts = []
            
            for part in response_content.parts:
                # Проверяем наличие вызова функции
                if hasattr(part, 'function_call') and part.function_call:
                    has_function_call = True
                    function_call = part.function_call
                    
                    # Извлекаем имя и аргументы функции
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    
                    # Выполняем функцию через ToolService
                    try:
                        result = self._execute_function(function_name, function_args)
                    except Exception as e:
                        result = f"Ошибка при выполнении функции: {str(e)}"
                    
                    # Логируем вызов функции
                    iteration_log["function_calls"].append({
                        "name": function_name,
                        "args": function_args,
                        "result": result
                    })
                    iteration_log["response"] = f"Model вызвала функцию: {function_name}"
                    
                    # Формируем ответ функции для отправки обратно в модель
                    function_response_part = protos.Part(
                        function_response=protos.FunctionResponse(
                            name=function_name,
                            response={"result": result}
                        )
                    )
                    function_response_parts.append(function_response_part)
                    
                # Проверяем наличие текста
                elif hasattr(part, 'text') and part.text:
                    has_text = True
                    bot_response_text = part.text
                    iteration_log["response"] = part.text
            
            # Сохраняем информацию об итерации
            debug_iterations.append(iteration_log)
            
            # Если есть текстовый ответ - это финальный ответ
            if has_text and not has_function_call:
                iteration_log["final_answer"] = bot_response_text
                break
            
            # Если есть вызовы функций - подготавливаем их результаты для следующей итерации
            if has_function_call:
                current_message = function_response_parts
                # Если это последняя итерация и Gemini не вернул текст, 
                # попробуем принудительно запросить итоговый ответ
                if iteration == max_iterations - 1:
                    # Добавляем явный запрос на формирование ответа
                    current_message = function_response_parts + [
                        protos.Part(text="Пожалуйста, сформируй итоговый ответ для пользователя на основе полученной информации о свободных слотах.")
                    ]
                continue
            
            # Если нет ни функции, ни текста - выходим с ошибкой
            if not has_function_call and not has_text:
                bot_response_text = "Извините, произошла ошибка при обработке вашего запроса."
                iteration_log["final_answer"] = bot_response_text
                break
        
        # Проверка на превышение лимита итераций
        if iteration >= max_iterations and not bot_response_text:
            # Если мы достигли лимита итераций, но функции выполнились успешно,
            # попробуем сформировать ответ на основе собранной информации
            if debug_iterations and any(iter_log.get("function_calls") for iter_log in debug_iterations):
                # Собираем результаты всех выполненных функций
                all_results = []
                for iter_log in debug_iterations:
                    for func_call in iter_log.get("function_calls", []):
                        if "get_available_slots" in func_call.get("name", ""):
                            all_results.append(func_call.get("result", ""))
                
                if all_results:
                    # Формируем сводный ответ на основе результатов
                    bot_response_text = self._generate_summary_response(all_results)
                else:
                    bot_response_text = "Извините, не удалось обработать ваш запрос. Попробуйте переформулировать вопрос."
            else:
                bot_response_text = "Извините, не удалось обработать ваш запрос. Попробуйте переформулировать вопрос."
        
        # Логируем весь цикл Function Calling
        gemini_debug_logger.log_function_calling_cycle(
            user_id=user_id,
            user_message=user_message,
            iterations=debug_iterations
        )
        
        return bot_response_text
    
    def _build_full_history_with_system_prompt(self, dialog_history: List[Dict], system_prompt: str) -> List[Dict]:
        """
        Формирует полную историю диалога с системной инструкцией.
        
        Args:
            dialog_history: История диалога
            system_prompt: Системный промпт
            
        Returns:
            Полная история с системной инструкцией
        """
        # Добавляем системную инструкцию в начало истории
        full_history = [
            {
                "role": "user",
                "parts": [{"text": system_prompt}]
            }
        ]
        
        # Добавляем историю диалога
        full_history.extend(dialog_history)
        
        return full_history
    
    def _execute_function(self, function_name: str, function_args: Dict) -> str:
        """
        Динамически выполняет функцию из ToolService.
        
        Args:
            function_name: Имя функции для вызова
            function_args: Аргументы функции
            
        Returns:
            Результат выполнения функции
        """
        # Проверяем, существует ли метод в ToolService
        if not hasattr(self.tool_service, function_name):
            return f"Ошибка: функция '{function_name}' не найдена в ToolService"
        
        # Получаем метод динамически
        method = getattr(self.tool_service, function_name)
        
        # Вызываем метод с аргументами
        if function_name == "get_all_services":
            return method()
        
        elif function_name == "get_masters_for_service":
            service_name = function_args.get("service_name", "")
            return method(service_name)
        
        elif function_name == "get_available_slots":
            service_name = function_args.get("service_name", "")
            date = function_args.get("date", "")
            return method(service_name, date)
        
        elif function_name == "create_appointment":
            master_name = function_args.get("master_name", "")
            service_name = function_args.get("service_name", "")
            date = function_args.get("date", "")
            time = function_args.get("time", "")
            return method(master_name, service_name, date, time)
        
        else:
            return f"Ошибка: неизвестная функция '{function_name}'"
    
    def _generate_summary_response(self, results: List[str]) -> str:
        """
        Формирует сводный ответ на основе результатов выполнения функций.
        
        Args:
            results: Список результатов выполнения функций get_available_slots
            
        Returns:
            Отформатированный ответ для пользователя
        """
        available_slots = []
        no_slots = []
        
        # Анализируем результаты
        for result in results:
            if "есть свободные окна" in result or "свободные окна" in result:
                available_slots.append(result)
            elif "нет свободных окон" in result:
                no_slots.append(result)
        
        # Формируем ответ
        if available_slots:
            response = "📅 Вот доступные варианты записи:\n\n"
            for slot_info in available_slots:
                response += f"• {slot_info}\n\n"
            
            if no_slots:
                response += "❌ К сожалению, у некоторых мастеров нет свободного времени.\n\n"
            
            response += "💡 Чтобы записаться, уточните пожалуйста:\n"
            response += "• К какому мастеру хотите записаться?\n"
            response += "• На какое время?\n"
            response += "• Какую услугу планируете?"
            
            return response
        else:
            return "😔 К сожалению, на выбранную дату нет свободных окон у мастеров. Попробуйте выбрать другую дату или обратитесь к администратору салона."





