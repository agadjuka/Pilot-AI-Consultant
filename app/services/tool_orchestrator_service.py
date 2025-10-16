from typing import List, Dict, Tuple
import asyncio
import json
import re
import google.generativeai as genai
import logging
from app.services.llm_service import LLMService
from app.services.tool_service import ToolService
from app.services.prompt_builder_service import PromptBuilderService
from app.repositories.client_repository import ClientRepository

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


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
    
    def _serialize_message_for_tracer(self, message) -> str:
        """
        Преобразует сообщение в сериализуемую строку для tracer.
        
        Args:
            message: Сообщение (строка или список объектов Part)
            
        Returns:
            Строковое представление сообщения
        """
        if isinstance(message, str):
            return message
        elif isinstance(message, list):
            # Обрабатываем список объектов Part
            parts_info = []
            for i, part in enumerate(message):
                if hasattr(part, 'text') and part.text:
                    parts_info.append(f"Часть {i+1}: текст '{part.text[:100]}...'")
                elif hasattr(part, 'function_response') and part.function_response:
                    func_name = part.function_response.name
                    # Безопасно извлекаем response
                    try:
                        func_response = part.function_response.response
                        if hasattr(func_response, '__dict__'):
                            func_response = str(func_response)
                        elif isinstance(func_response, dict):
                            func_response = str(func_response)
                        else:
                            func_response = str(func_response)
                    except:
                        func_response = "не удалось извлечь"
                    parts_info.append(f"Часть {i+1}: ответ функции '{func_name}' -> {func_response}")
                else:
                    parts_info.append(f"Часть {i+1}: неизвестный тип")
            return f"Сообщение из {len(message)} частей: " + "; ".join(parts_info)
        else:
            return str(message)
    
    def parse_tool_calls_from_string(self, text: str, dialog_context: Dict = None, tracer=None) -> List[Dict]:
        """
        Парсит строковый формат TOOL_CALL: function_name(param="value") из текста.
        
        Args:
            text: Текст с вызовами инструментов в формате TOOL_CALL:
            dialog_context: Контекст диалога для обогащения параметров
            tracer: Трейсер для логирования
            
        Returns:
            Список вызовов инструментов в формате [{"tool_name": "...", "parameters": {...}}]
        """
        tool_calls = []
        
        # Ищем все строки с форматом TOOL_CALL: function_name(param="value")
        tool_call_pattern = r'TOOL_CALL:\s*(\w+)\((.*?)\)'
        matches = re.finditer(tool_call_pattern, text, re.MULTILINE)
        
        for match in matches:
            function_name = match.group(1)
            raw_params = match.group(2).strip()
            
            # Парсим параметры в формате param="value"
            params = {}
            if raw_params:
                param_pattern = r'(\w+)\s*=\s*"([^"]*)"'
                param_matches = re.finditer(param_pattern, raw_params)
                for param_match in param_matches:
                    param_name = param_match.group(1)
                    param_value = param_match.group(2)
                    params[param_name] = param_value
            
            tool_call = {
                "tool_name": function_name,
                "parameters": params
            }
            tool_calls.append(tool_call)
            
            if tracer:
                tracer.log(f"🔧 [String Format] Найден вызов: {function_name}({params})")
        
        # Обогащаем вызовы инструментов контекстом диалога
        if dialog_context and tool_calls:
            enriched_calls = self.enrich_tool_calls(tool_calls, dialog_context, tracer)
            return enriched_calls
        
        return tool_calls

    def enrich_tool_calls(self, tool_calls: List[Dict], dialog_context: Dict, tracer=None) -> List[Dict]:
        """
        Обогащает вызовы инструментов недостающими параметрами из контекста диалога.
        
        Args:
            tool_calls: Список вызовов инструментов
            dialog_context: Контекст диалога с сохраненными сущностями
            
        Returns:
            Обогащенный список вызовов инструментов
        """
        if not dialog_context:
            return tool_calls
        
        enriched_calls = []
        enrichment_log = []
        
        for call in tool_calls:
            tool_name = call.get('tool_name', '')
            original_parameters = call.get('parameters', {}).copy()
            parameters = original_parameters.copy()
            
            # Обогащаем параметры в зависимости от типа инструмента
            enrichments = []
            
            if tool_name == 'get_available_slots':
                # Если отсутствует service_name, но есть в контексте
                if not parameters.get('service_name') and dialog_context.get('service_name'):
                    parameters['service_name'] = dialog_context['service_name']
                    enrichments.append(f"service_name = {dialog_context['service_name']}")
                    logger.info(f"🔧 Обогащен get_available_slots: добавлен service_name = {dialog_context['service_name']}")
                
                # Если отсутствует date, но есть в контексте
                if not parameters.get('date') and dialog_context.get('date'):
                    parameters['date'] = dialog_context['date']
                    enrichments.append(f"date = {dialog_context['date']}")
                    logger.info(f"🔧 Обогащен get_available_slots: добавлена date = {dialog_context['date']}")
            
            elif tool_name == 'get_masters_for_service':
                # Если отсутствует service_name, но есть в контексте
                if not parameters.get('service_name') and dialog_context.get('service_name'):
                    parameters['service_name'] = dialog_context['service_name']
                    enrichments.append(f"service_name = {dialog_context['service_name']}")
                    logger.info(f"🔧 Обогащен get_masters_for_service: добавлен service_name = {dialog_context['service_name']}")
            
            elif tool_name == 'create_appointment':
                # Маппинг неправильных имен параметров на правильные
                if 'appointment_date' in parameters and 'date' not in parameters:
                    parameters['date'] = parameters.pop('appointment_date')
                    enrichments.append(f"appointment_date -> date")
                    logger.info(f"🔧 Обогащен create_appointment: переименован appointment_date в date")
                
                if 'appointment_time' in parameters and 'time' not in parameters:
                    parameters['time'] = parameters.pop('appointment_time')
                    enrichments.append(f"appointment_time -> time")
                    logger.info(f"🔧 Обогащен create_appointment: переименован appointment_time в time")
                
                if 'service' in parameters and 'service_name' not in parameters:
                    parameters['service_name'] = parameters.pop('service')
                    enrichments.append(f"service -> service_name")
                    logger.info(f"🔧 Обогащен create_appointment: переименован service в service_name")
                
                # Обогащаем все возможные параметры для создания записи
                if not parameters.get('service_name') and dialog_context.get('service_name'):
                    parameters['service_name'] = dialog_context['service_name']
                    enrichments.append(f"service_name = {dialog_context['service_name']}")
                    logger.info(f"🔧 Обогащен create_appointment: добавлен service_name = {dialog_context['service_name']}")
                
                if not parameters.get('master_name') and dialog_context.get('master_name'):
                    parameters['master_name'] = dialog_context['master_name']
                    enrichments.append(f"master_name = {dialog_context['master_name']}")
                    logger.info(f"🔧 Обогащен create_appointment: добавлен master_name = {dialog_context['master_name']}")
                
                if not parameters.get('date') and dialog_context.get('date'):
                    parameters['date'] = dialog_context['date']
                    enrichments.append(f"date = {dialog_context['date']}")
                    logger.info(f"🔧 Обогащен create_appointment: добавлена date = {dialog_context['date']}")
            
            # Логируем обогащение для этого инструмента
            if enrichments:
                enrichment_log.append({
                    "tool_name": tool_name,
                    "original_parameters": original_parameters,
                    "enriched_parameters": parameters,
                    "enrichments": enrichments
                })
            
            # Создаем обогащенный вызов
            enriched_call = {
                'tool_name': tool_name,
                'parameters': parameters
            }
            enriched_calls.append(enriched_call)
        
        # Логируем общее обогащение в трассировку
        if tracer and enrichment_log:
            tracer.add_event("🔧 Обогащение вызовов инструментов", {
                "enrichment_log": enrichment_log,
                "dialog_context": dialog_context,
                "total_enriched": len(enrichment_log)
            })
        
        return enriched_calls
    
    async def execute_tool_cycle(self, system_prompt: str, history: List[Dict], 
                               user_message: str, user_id: int, tracer=None, dialog_context: Dict = None) -> Tuple[str, List[Dict]]:
        """
        Выполняет цикл обработки инструментов с LLM.
        Поддерживает параллельное выполнение нескольких инструментов.
        
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
        
        if tracer:
            tracer.add_event("🔧 Инициализация ToolOrchestrator", f"Системный промпт: {len(system_prompt)} символов, История: {len(history)} сообщений")
        
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
            "response": "Инициализация чата с LLM",
            "function_calls": [],
            "final_answer": ""
        })
        
        while iteration < max_iterations:
            iteration += 1
            
            if tracer:
                tracer.add_event(f"🔄 Итерация {iteration}", f"Максимум итераций: {max_iterations}")
            
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
            
            # Логируем запрос к LLM перед вызовом
            if tracer:
                tracer.add_event(f"📤 Вызов LLM (итерация {iteration})", {
                    "history": history,
                    "message": self._serialize_message_for_tracer(current_message),
                    "iteration": iteration
                })
            
            # Получаем ответ от LLM
            response_content = await self.llm_service.send_message_to_chat(
                chat=chat,
                message=current_message,
                user_id=user_id
            )
            
            # Логируем сырой ответ от LLM
            if tracer:
                # Извлекаем текстовые части ответа
                raw_text_parts = []
                for part in response_content.parts:
                    if hasattr(part, 'text') and part.text:
                        raw_text_parts.append(part.text)
                    elif hasattr(part, 'function_call') and part.function_call:
                        raw_text_parts.append(f"Function call: {part.function_call.name}")
                
                tracer.add_event(f"📥 Ответ LLM (итерация {iteration})", {
                    "raw_response": "\n".join(raw_text_parts) if raw_text_parts else "Пустой ответ",
                    "parts_count": len(response_content.parts),
                    "iteration": iteration
                })
            
            # Анализируем ответ
            has_function_call = False
            has_text = False
            function_calls = []
            
            # Собираем все вызовы функций из ответа
            for part in response_content.parts:
                # Проверяем наличие вызова функции
                if hasattr(part, 'function_call') and part.function_call:
                    has_function_call = True
                    function_calls.append(part.function_call)
                
                # Проверяем наличие текста
                elif hasattr(part, 'text') and part.text:
                    text_payload = part.text.strip()
                    
                    # НОВЫЙ ФОРМАТ: Сначала проверяем строковый формат TOOL_CALL:
                    string_tool_calls = self.parse_tool_calls_from_string(text_payload, dialog_context, tracer)
                    if string_tool_calls:
                        has_function_call = True
                        
                        # Обрабатываем каждый найденный вызов инструмента
                        for tool_call in string_tool_calls:
                            if isinstance(tool_call, dict) and "tool_name" in tool_call:
                                function_name = tool_call["tool_name"]
                                function_args = tool_call.get("parameters", {})
                                
                                # Создаем mock function_call для совместимости
                                class MockFunctionCall:
                                    def __init__(self, name, args):
                                        self.name = name
                                        self.args = args
                                
                                function_calls.append(MockFunctionCall(function_name, function_args))
                        
                        iteration_log["response"] = f"Строковый формат с {len(string_tool_calls)} вызовами инструментов"
                        logger.info(f"🔧 [String Format] {len(string_tool_calls)} инструментов из строкового формата")
                        continue  # Переходим к обработке function_calls
                    
                    # УЛУЧШЕННАЯ ЛОГИКА: Надежный парсер JSON с очисткой (резервный вариант)
                    cleaned_json_str = text_payload.strip()
                    
                    # Проверяем наличие Markdown-блока с JSON
                    if "```json" in cleaned_json_str or "```" in cleaned_json_str:
                        # Извлекаем содержимое из блока ```json ... ``` или ``` ... ```
                        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_json_str)
                        if json_match:
                            cleaned_json_str = json_match.group(1).strip()
                    
                    # Дополнительная очистка: удаляем возможные префиксы/суффиксы
                    cleaned_json_str = cleaned_json_str.strip()
                    if cleaned_json_str.startswith('json'):
                        cleaned_json_str = cleaned_json_str[4:].strip()
                    
                    # Пытаемся распарсить как JSON
                    try:
                        tool_calls_data = json.loads(cleaned_json_str)
                        
                        # Проверяем, что это непустой массив вызовов инструментов
                        if isinstance(tool_calls_data, list) and len(tool_calls_data) > 0:
                            has_function_call = True
                            
                            # Обогащаем вызовы инструментов перед обработкой
                            enriched_tool_calls = self.enrich_tool_calls(tool_calls_data, dialog_context, tracer)
                            
                            # Обрабатываем каждый обогащенный вызов инструмента
                            for tool_call in enriched_tool_calls:
                                if isinstance(tool_call, dict) and "tool_name" in tool_call:
                                    function_name = tool_call["tool_name"]
                                    function_args = tool_call.get("parameters", {})
                                    
                                    # Создаем mock function_call для совместимости
                                    class MockFunctionCall:
                                        def __init__(self, name, args):
                                            self.name = name
                                            self.args = args
                                    
                                    function_calls.append(MockFunctionCall(function_name, function_args))
                            
                            iteration_log["response"] = f"JSON с {len(tool_calls_data)} вызовами инструментов"
                            logger.info(f"🔧 [JSON Tools] {len(tool_calls_data)} инструментов из JSON")
                            continue  # Переходим к обработке function_calls
                        else:
                            # Пустой список или не список - считаем финальным ответом
                            has_text = True
                            bot_response_text = text_payload
                            iteration_log["response"] = text_payload
                            logger.info(f"💬 [Answer] {bot_response_text[:140]}")
                            break
                    
                    except json.JSONDecodeError as e:
                        # Это не JSON, считаем финальным текстовым ответом
                        has_text = True
                        bot_response_text = text_payload
                        iteration_log["response"] = text_payload
                        logger.info(f"💬 [Answer] {bot_response_text[:140]}")
                        break
                    
                    # Доп. обработка: парсим текстовый формат [TOOL: func(arg="val", ...)]
                    # Это нужно для провайдеров без нативного function_call (например, Yandex)
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
                        
                        # Обогащаем параметры из контекста диалога
                        if dialog_context:
                            # Создаем временный tool_call для обогащения
                            temp_tool_call = {
                                'tool_name': function_name,
                                'parameters': args
                            }
                            enriched_calls = self.enrich_tool_calls([temp_tool_call], dialog_context, tracer)
                            if enriched_calls:
                                args = enriched_calls[0]['parameters']
                        
                        # Создаем mock function_call для совместимости
                        class MockFunctionCall:
                            def __init__(self, name, args):
                                self.name = name
                                self.args = args
                        
                        function_calls.append(MockFunctionCall(function_name, args))
                    else:
                        has_text = True
                        bot_response_text = text_payload
                        iteration_log["response"] = text_payload
                        logger.info(f"💬 [Answer] {bot_response_text[:140]}")
            
            # Сохраняем информацию об итерации
            debug_iterations.append(iteration_log)
            
            # Если есть вызовы функций - выполняем их параллельно
            if has_function_call and function_calls:
                if tracer:
                    tracer.add_event(f"⚙️ Параллельное выполнение {len(function_calls)} инструментов", {
                        "tools": [fc.name for fc in function_calls],
                        "iteration": iteration
                    })
                
                # Создаем список асинхронных задач для параллельного выполнения
                tasks = []
                for function_call in function_calls:
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    
                    logger.info(f"🔧 [ORCHESTRATOR] Подготовка к выполнению инструмента: {function_name} с параметрами: {function_args}")
                    
                    # Создаем корутину для выполнения функции
                    task = self._execute_function_async(function_name, function_args, user_id)
                    tasks.append(task)
                
                # Выполняем все функции параллельно
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Формируем текстовое сообщение с результатами для LLM
                    tool_results_message = []
                    
                    for i, (function_call, result) in enumerate(zip(function_calls, results)):
                        function_name = function_call.name
                        function_args = dict(function_call.args)
                        
                        # Обрабатываем исключения
                        if isinstance(result, Exception):
                            result = f"Ошибка при выполнении функции: {str(result)}"
                        
                        if tracer:
                            tracer.add_event(f"⚙️ Результат инструмента: {function_name}", {
                                "tool_name": function_name,
                                "args": function_args,
                                "result": result,
                                "iteration": iteration
                            })
                        
                        # Логируем вызов функции
                        iteration_log["function_calls"].append({
                            "name": function_name,
                            "args": function_args,
                            "result": result
                        })
                        iteration_log["response"] = f"Model вызвала {len(function_calls)} функций параллельно"
                        
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
                            final_text, _ = await self.execute_tool_cycle(contact_prompt, history, user_message, user_id, tracer)
                            return final_text, debug_iterations
                        
                        # Формируем строковое представление результата для LLM
                        result_str = str(result) if result is not None else "Результат не получен"
                        tool_result_text = f"Результат вызова инструмента '{function_name}':\n{result_str}"
                        tool_results_message.append(tool_result_text)
                    
                    # Объединяем все результаты в одно сообщение
                    combined_results = "\n\n".join(tool_results_message)
                    
                    # Добавляем инструкцию для LLM
                    final_instruction = "\n\nТы получил результаты от инструментов. Теперь, основываясь на этих данных, сформулируй финальный, вежливый и краткий ответ для клиента."
                    
                    # Формируем финальное сообщение для LLM
                    current_message = combined_results + final_instruction
                    
                    if tracer:
                        tracer.add_event(f"📤 Передача результатов в LLM", {
                            "results_count": len(tool_results_message),
                            "message_length": len(current_message),
                            "iteration": iteration
                        })
                    
                    continue
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при параллельном выполнении инструментов: {str(e)}")
                    bot_response_text = "Извините, произошла ошибка при обработке вашего запроса."
                    iteration_log["final_answer"] = bot_response_text
                    break
            
            # Если есть текстовый ответ - это финальный ответ
            if has_text and not has_function_call:
                iteration_log["final_answer"] = bot_response_text
                if tracer:
                    tracer.add_event(f"✅ Финальный ответ получен", {
                        "text": bot_response_text,
                        "iteration": iteration,
                        "length": len(bot_response_text)
                    })
                break
            
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
        
        return bot_response_text, debug_iterations
    
    async def execute_single_tool(self, tool_name: str, parameters: Dict, user_id: int, dialog_context: Dict = None, tracer=None) -> str:
        """
        Выполняет одиночный вызов инструмента.
        Упрощенная версия для случаев, когда нужно выполнить только один инструмент.
        
        Args:
            tool_name: Имя инструмента для выполнения
            parameters: Параметры инструмента
            user_id: ID пользователя
            
        Returns:
            Результат выполнения инструмента
        """
        try:
            logger.info(f"🔧 Выполнение одиночного инструмента: {tool_name}")
            
            # Обогащаем параметры из контекста диалога
            if dialog_context:
                temp_tool_call = {
                    'tool_name': tool_name,
                    'parameters': parameters
                }
                enriched_calls = self.enrich_tool_calls([temp_tool_call], dialog_context, tracer)
                if enriched_calls:
                    parameters = enriched_calls[0]['parameters']
                    logger.info(f"🔧 Параметры одиночного инструмента обогащены: {parameters}")
            
            # Выполняем инструмент через ToolService
            result = await self._execute_function_async(tool_name, parameters, user_id)
            
            logger.info(f"✅ Одиночный инструмент выполнен: {tool_name}")
            return result
            
        except Exception as e:
            error_msg = f"Ошибка выполнения инструмента {tool_name}: {str(e)}"
            logger.error(f"❌ Ошибка выполнения одиночного инструмента {tool_name}: {e}")
            return error_msg
    
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
    
    async def _execute_function_async(self, function_name: str, function_args: Dict, user_id: int = None) -> str:
        """
        Асинхронно выполняет функцию из ToolService.
        
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
            return method(appointment_id, user_id)
        
        elif function_name == "reschedule_appointment_by_id":
            appointment_id = function_args.get("appointment_id", 0)
            new_date = function_args.get("new_date", "")
            new_time = function_args.get("new_time", "")
            return method(appointment_id, new_date, new_time, user_id)
        
        elif function_name == "call_manager":
            reason = function_args.get("reason", "")
            result = method(reason)
            # Возвращаем только response_to_user для совместимости с существующей логикой
            return result.get("response_to_user", "Ошибка при вызове менеджера")
        
        elif function_name == "get_full_history":
            return method()
        
        elif function_name == "save_client_name":
            name = function_args.get("name", "")
            return method(name, user_id)
        
        elif function_name == "save_client_phone":
            phone = function_args.get("phone", "")
            return method(phone, user_id)
        
        else:
            return f"Ошибка: неизвестная функция '{function_name}'"
    
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
            return method(appointment_id, user_id)
        
        elif function_name == "reschedule_appointment_by_id":
            appointment_id = function_args.get("appointment_id", 0)
            new_date = function_args.get("new_date", "")
            new_time = function_args.get("new_time", "")
            return method(appointment_id, new_date, new_time, user_id)
        
        elif function_name == "call_manager":
            reason = function_args.get("reason", "")
            result = method(reason)
            # Возвращаем только response_to_user для совместимости с существующей логикой
            return result.get("response_to_user", "Ошибка при вызове менеджера")
        
        elif function_name == "get_full_history":
            return method()
        
        elif function_name == "save_client_name":
            name = function_args.get("name", "")
            return method(name, user_id)
        
        elif function_name == "save_client_phone":
            phone = function_args.get("phone", "")
            return method(phone, user_id)
        
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
