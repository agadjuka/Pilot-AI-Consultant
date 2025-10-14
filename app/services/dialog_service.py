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
        full_history = self.prompt_builder.build_full_history_with_system_prompt(dialog_history, system_prompt)
        
        # Создаем чат один раз для всего цикла
        chat = self.llm_service.create_chat(full_history)
        
        # Запускаем цикл обработки Function Calling
        max_iterations = 5
        iteration = 0
        bot_response_text = None
        current_message = user_message
        
        # Для логирования - собираем информацию о каждой итерации
        debug_iterations = []
        
        # Добавляем информацию о системном промпте и истории в первую итерацию
        debug_iterations.append({
            "iteration": 0,
            "request": f"СИСТЕМНЫЙ ПРОМПТ:\n{system_prompt}\n\nИСТОРИЯ ДИАЛОГА:\n{self._format_dialog_history(dialog_history)}",
            "response": "Инициализация чата с Gemini",
            "function_calls": [],
            "final_answer": ""
        })
        
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
            
            # Логируем запрос с детальной информацией
            if isinstance(current_message, str):
                iteration_log["request"] = f"Текст: {current_message}"
            else:
                iteration_log["request"] = f"Function Response (результаты {len(current_message)} функций)"
                # Добавляем детали о результатах функций
                for i, part in enumerate(current_message):
                    if hasattr(part, 'function_response'):
                        func_name = part.function_response.name
                        func_result = part.function_response.response
                        iteration_log["request"] += f"\n  Функция {i+1}: {func_name} -> {func_result}"
            
            # Получаем ответ от LLM
            response_content = await self.llm_service.send_message_to_chat(
                chat=chat,
                message=current_message,
                user_id=user_id
            )
            
            # Анализируем ответ
            has_function_call = False
            has_text = False
            function_response_parts = []
            # Специальный контекст: если это просмотр записей — подготовим данные заранее
            precomputed_tool_result: str | None = None
            try:
                # Попробуем извлечь стадию из системного промпта (последняя добавленная строка в начале истории)
                # и если это view_booking, заранее получим список записей
                if "view_booking" in system_prompt:
                    precomputed_tool_result = self.tool_service.get_my_appointments(user_id)
            except Exception:
                precomputed_tool_result = None
            
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
                        result = self._execute_function(function_name, function_args, user_id)
                    except Exception as e:
                        result = f"Ошибка при выполнении функции: {str(e)}"
                    
                    # Компактный лог вызова инструмента
                    def _short(v):
                        try:
                            s = str(v)
                            return (s[:120] + '…') if len(s) > 120 else s
                        except Exception:
                            return '—'
                    print(f"[Tool] {function_name} args={_short(function_args)} → {_short(result)}")
                    
                    # Логируем вызов функции
                    iteration_log["function_calls"].append({
                        "name": function_name,
                        "args": function_args,
                        "result": result
                    })
                    iteration_log["response"] = f"Model вызвала функцию: {function_name}"
                    
                    # Специальная обработка для call_manager - завершаем цикл
                    if function_name == "call_manager":
                        bot_response_text = result
                        iteration_log["final_answer"] = bot_response_text
                        break

                    # Обработка ситуации, когда нужны ПДн для записи
                    if function_name == "create_appointment" and isinstance(result, str) and result.startswith("Требуются данные клиента"):
                        # Принудительно переключаемся на стадию contact_info_request и запускаем второй цикл
                        contact_stage = 'contact_info_request'
                        # Попробуем обратиться по имени, если оно уже есть в БД
                        client = self.client_repository.get_or_create_by_telegram_id(user_id)
                        
                        # Формируем промпт через PromptBuilderService
                        contact_prompt = self.prompt_builder.build_generation_prompt(
                            stage=contact_stage,
                            dialog_history=dialog_history,
                            dialog_context="",
                            client_name=client.first_name,
                            client_phone_saved=bool(client.phone_number)
                        )
                        # Запускаем отдельный цикл генерации с новой инструкцией
                        final_text = await self._execute_generation_cycle(user_id, user_message, dialog_history, contact_prompt)
                        return final_text
                    
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
                    text_payload = part.text.strip()
                    # Доп. обработка: парсим текстовый формат [TOOL: func(arg="val", ...)]
                    # Это нужно для провайдеров без нативного function_call (например, Yandex)
                    import re
                    tool_match = re.search(r"\[TOOL:\s*(\w+)\((.*?)\)\]", text_payload)
                    if tool_match:
                        has_function_call = True
                        function_name = tool_match.group(1)
                        raw_args = tool_match.group(2).strip()
                        args: Dict[str, str] = {}
                        if raw_args:
                            # Разбираем пары key="value" (поддерживаем русские символы и пробелы внутри значений)
                            for m in re.finditer(r"(\w+)\s*=\s*\"([^\"]*)\"", raw_args):
                                args[m.group(1)] = m.group(2)
                        try:
                            result = self._execute_function(function_name, args, user_id)
                        except Exception as e:
                            result = f"Ошибка при выполнении функции: {str(e)}"
                        print(f"[Tool] {function_name} args={args} → {str(result)[:120]}")
                        iteration_log["function_calls"].append({
                            "name": function_name,
                            "args": args,
                            "result": result
                        })
                        iteration_log["response"] = f"Model вызвала функцию (text): {function_name}"

                        # Обработка нехватки ПДн
                        if function_name == "create_appointment" and isinstance(result, str) and result.startswith("Требуются данные клиента"):
                            contact_stage = 'contact_info_request'
                            client = self.client_repository.get_or_create_by_telegram_id(user_id)
                            
                            # Формируем промпт через PromptBuilderService
                            contact_prompt = self.prompt_builder.build_generation_prompt(
                                stage=contact_stage,
                                dialog_history=dialog_history,
                                dialog_context="",
                                client_name=client.first_name,
                                client_phone_saved=bool(client.phone_number)
                            )
                            final_text = await self._execute_generation_cycle(user_id, user_message, dialog_history, contact_prompt)
                            return final_text

                        # Готовим ответ функции для следующей итерации
                        function_response_part = protos.Part(
                            function_response=protos.FunctionResponse(
                                name=function_name,
                                response={"result": result}
                            )
                        )
                        function_response_parts.append(function_response_part)
                        # Не выставляем текстовый финальный ответ — отдадим шанс модели сгенерировать подтверждение
                    else:
                        # Если это стадия просмотра записей и текст не вызвал инструмент —
                        # мягко вставим в ответ данные инструментов как контекст для LLM:
                        if precomputed_tool_result is not None and "get_my_appointments" not in text_payload:
                            text_payload = (
                                f"КОНТЕКСТ_ЗАПИСЕЙ: {precomputed_tool_result}\n\n"
                                f"СФОРМИРУЙ ОТВЕТ: {text_payload}"
                            )
                        has_text = True
                        bot_response_text = text_payload
                        iteration_log["response"] = text_payload
                        print(f"[Answer] {bot_response_text[:140]}")
            
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
        
        # Логируем диалог
        if debug_iterations and any(iter_log.get("function_calls") for iter_log in debug_iterations):
            # Если были вызовы функций - логируем как Function Calling цикл
            gemini_debug_logger.log_function_calling_cycle(
                user_id=user_id,
                user_message=user_message,
                iterations=debug_iterations
            )
        else:
            # Если не было вызовов функций - логируем как простой диалог
            gemini_debug_logger.log_simple_dialog(
                user_id=user_id,
                user_message=user_message,
                system_prompt=system_prompt,
                dialog_history=dialog_history,
                gemini_response=bot_response_text or "Ошибка генерации ответа"
            )
        
        return bot_response_text
    
    
    def _format_dialog_history(self, dialog_history: List[Dict]) -> str:
        """
        Форматирует историю диалога для логирования.
        
        Args:
            dialog_history: История диалога
            
        Returns:
            Отформатированная строка истории
        """
        if not dialog_history:
            return "История диалога пуста"
        
        formatted_history = []
        for i, msg in enumerate(dialog_history, 1):
            role = msg.get("role", "unknown")
            parts = msg.get("parts", [])
            text_content = ""
            for part in parts:
                if isinstance(part, dict) and "text" in part:
                    text_content += part["text"]
                elif hasattr(part, 'text'):
                    text_content += part.text
            
            formatted_history.append(f"[{i}] {role.upper()}: {text_content}")
        
        return "\n".join(formatted_history)
    
    def _execute_function(self, function_name: str, function_args: Dict, user_id: int = None) -> str:
        """
        Динамически выполняет функцию из ToolService.
        
        Args:
            function_name: Имя функции для вызова
            function_args: Аргументы функции
            user_id: ID пользователя для функций, требующих его
            
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
            client_name = function_args.get("client_name", "")
            return method(master_name, service_name, date, time, client_name, user_id)
        
        elif function_name == "get_my_appointments":
            return method(user_id)
        
        elif function_name == "cancel_appointment_by_id":
            appointment_id = function_args.get("appointment_id", 0)
            return method(appointment_id)
        
        elif function_name == "reschedule_appointment_by_id":
            appointment_id = function_args.get("appointment_id", 0)
            new_date = function_args.get("new_date", "")
            new_time = function_args.get("new_time", "")
            return method(appointment_id, new_date, new_time)
        
        elif function_name == "call_manager":
            reason = function_args.get("reason", "")
            result = method(reason)
            # Возвращаем только response_to_user для совместимости с существующей логикой
            return result.get("response_to_user", "Ошибка при вызове менеджера")
        
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
            response = "Вот доступные варианты записи:\n\n"
            for slot_info in available_slots:
                response += f"• {slot_info}\n\n"
            
            if no_slots:
                response += "К сожалению, у некоторых мастеров нет свободного времени.\n\n"
            
            response += "Чтобы записаться, уточните пожалуйста:\n"
            response += "• К какому мастеру хотите записаться?\n"
            response += "• На какое время?\n"
            response += "• Какую услугу планируете?"
            
            return response
        else:
            return "К сожалению, на выбранную дату нет свободных окон у мастеров. Попробуйте выбрать другую дату или обратитесь к администратору салона."





