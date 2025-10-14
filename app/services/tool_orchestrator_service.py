from typing import List, Dict, Tuple
import google.generativeai as genai
from google.generativeai import protos
from app.services.llm_service import LLMService
from app.services.tool_service import ToolService
from app.services.prompt_builder_service import PromptBuilderService
from app.repositories.client_repository import ClientRepository
from app.utils.debug_logger import gemini_debug_logger


class ToolOrchestratorService:
    """
    Сервис-оркестратор для обработки циклов вызова инструментов (Function Calling).
    
    Отвечает за сложную логику итеративного общения с LLM:
    - Проверка на function_call
    - Вызов методов ToolService
    - Отправка результатов обратно в LLM
    - Формирование финального ответа
    """
    
    def __init__(self, llm_service: LLMService, tool_service: ToolService, 
                 prompt_builder: PromptBuilderService, client_repository: ClientRepository):
        """
        Инициализирует сервис-оркестратор.
        
        Args:
            llm_service: Сервис для работы с LLM
            tool_service: Сервис для выполнения инструментов
            prompt_builder: Сервис для построения промптов
            client_repository: Репозиторий для работы с клиентами
        """
        self.llm_service = llm_service
        self.tool_service = tool_service
        self.prompt_builder = prompt_builder
        self.client_repository = client_repository
    
    async def execute_tool_cycle(self, system_prompt: str, history: List[Dict], 
                               user_message: str, user_id: int) -> Tuple[str, List[Dict]]:
        """
        Выполняет цикл обработки инструментов с LLM.
        
        Args:
            system_prompt: Системный промпт для LLM
            history: История диалога
            user_message: Сообщение пользователя
            user_id: ID пользователя
            
        Returns:
            Кортеж (финальный_текстовый_ответ_от_LLM, вся_промежуточная_история_цикла)
        """
        # Формируем полную историю с системной инструкцией
        full_history = self.prompt_builder.build_full_history_with_system_prompt(history, system_prompt)
        
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
            "request": f"СИСТЕМНЫЙ ПРОМПТ:\n{system_prompt}\n\nИСТОРИЯ ДИАЛОГА:\n{self._format_dialog_history(history)}",
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
                        client = self.client_repository.get_or_create_by_telegram_id(user_id)
                        
                        # Формируем промпт через PromptBuilderService
                        contact_prompt = self.prompt_builder.build_generation_prompt(
                            stage=contact_stage,
                            dialog_history=history,
                            dialog_context="",
                            client_name=client.first_name,
                            client_phone_saved=bool(client.phone_number)
                        )
                        # Запускаем отдельный цикл генерации с новой инструкцией
                        final_text, _ = await self.execute_tool_cycle(contact_prompt, history, user_message, user_id)
                        return final_text, debug_iterations
                    
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
                                dialog_history=history,
                                dialog_context="",
                                client_name=client.first_name,
                                client_phone_saved=bool(client.phone_number)
                            )
                            final_text, _ = await self.execute_tool_cycle(contact_prompt, history, user_message, user_id)
                            return final_text, debug_iterations

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
                dialog_history=history,
                gemini_response=bot_response_text or "Ошибка генерации ответа"
            )
        
        return bot_response_text, debug_iterations
    
    
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
