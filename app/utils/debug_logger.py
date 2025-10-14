import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class GeminiDebugLogger:
    """Логгер для сохранения всех запросов и ответов Gemini в текстовые файлы."""
    
    def __init__(self, debug_dir: str = "debug_logs"):
        """
        Инициализирует логгер.
        
        Args:
            debug_dir: Папка для сохранения логов (по умолчанию debug_logs)
        """
        self.debug_dir = Path(debug_dir)
        self._request_counter = 0
    
    def clear_debug_logs(self) -> None:
        """
        Очищает папку с логами.
        Удаляет все файлы и папку, затем создает пустую папку заново.
        """
        if self.debug_dir.exists():
            shutil.rmtree(self.debug_dir)
            print(f"   🗑️  Папка {self.debug_dir} очищена")
        
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self._request_counter = 0
        print(f"   📁 Создана папка для дебага: {self.debug_dir}")
    
    def log_request(
        self, 
        user_message: str, 
        dialog_history: List[Dict[str, str]] = None,
        system_instruction: str = None
    ) -> int:
        """
        Сохраняет запрос к Gemini в текстовый файл.
        
        Args:
            user_message: Сообщение пользователя
            dialog_history: История диалога
            system_instruction: Системная инструкция
            
        Returns:
            Номер запроса (счетчик)
        """
        self._request_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._request_counter:04d}_{timestamp}_request.txt"
        filepath = self.debug_dir / filename
        
        # Формируем содержимое файла
        content = []
        content.append("=" * 80)
        content.append(f"ЗАПРОС №{self._request_counter} К GEMINI")
        content.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("=" * 80)
        content.append("")
        
        # Системная инструкция
        if system_instruction:
            content.append("-" * 80)
            content.append("СИСТЕМНАЯ ИНСТРУКЦИЯ:")
            content.append("-" * 80)
            content.append(system_instruction)
            content.append("")
        
        # История диалога
        if dialog_history:
            content.append("-" * 80)
            content.append(f"ИСТОРИЯ ДИАЛОГА ({len(dialog_history)} сообщений):")
            content.append("-" * 80)
            for i, msg in enumerate(dialog_history, 1):
                role = msg.get("role", "unknown")
                text = msg.get("text", "")
                content.append(f"\n[{i}] {role.upper()}:")
                content.append(text)
            content.append("")
        
        # Текущее сообщение пользователя
        content.append("-" * 80)
        content.append("НОВОЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ:")
        content.append("-" * 80)
        content.append(user_message)
        content.append("")
        content.append("=" * 80)
        
        # Сохраняем в файл
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        
        print(f"   📝 Сохранен запрос: {filename}")
        return self._request_counter
    
    def log_response(self, request_number: int, response_text: str) -> None:
        """
        Сохраняет ответ от Gemini в текстовый файл.
        
        Args:
            request_number: Номер запроса (для связи с запросом)
            response_text: Текст ответа от модели
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request_number:04d}_{timestamp}_response.txt"
        filepath = self.debug_dir / filename
        
        # Формируем содержимое файла
        content = []
        content.append("=" * 80)
        content.append(f"ОТВЕТ №{request_number} ОТ GEMINI")
        content.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("=" * 80)
        content.append("")
        content.append(response_text)
        content.append("")
        content.append("=" * 80)
        
        # Сохраняем в файл
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        
        print(f"   💬 Сохранен ответ: {filename}")
    
    def log_function_calling_cycle(
        self,
        user_id: int,
        user_message: str,
        iterations: List[Dict]
    ) -> None:
        """
        Сохраняет полный цикл Function Calling в один файл.
        
        Args:
            user_id: ID пользователя
            user_message: Исходное сообщение пользователя
            iterations: Список итераций с запросами и ответами
                        Формат: [{"iteration": 1, "request": "...", "response": "...", "function_calls": [...]}]
        """
        self._request_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._request_counter:04d}_{timestamp}_function_calling.txt"
        filepath = self.debug_dir / filename
        
        # Формируем содержимое файла
        content = []
        content.append("=" * 80)
        content.append(f"FUNCTION CALLING ЦИКЛ №{self._request_counter}")
        content.append(f"Пользователь ID: {user_id}")
        content.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("=" * 80)
        content.append("")
        
        # Исходное сообщение
        content.append("-" * 80)
        content.append("ИСХОДНОЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ:")
        content.append("-" * 80)
        content.append(user_message)
        content.append("")
        
        # Добавляем информацию о системном промпте и истории из первой итерации
        if iterations and iterations[0].get("iteration") == 0:
            init_info = iterations[0].get("request", "")
            if "СИСТЕМНЫЙ ПРОМПТ:" in init_info:
                content.append("-" * 80)
                content.append("ИНИЦИАЛИЗАЦИЯ ЧАТА С GEMINI:")
                content.append("-" * 80)
                content.append(init_info)
                content.append("")
        
        # Итерации (пропускаем итерацию 0 - она уже обработана выше)
        for iteration_data in iterations:
            iteration = iteration_data.get("iteration", 0)
            if iteration == 0:
                continue  # Пропускаем итерацию инициализации
                
            content.append("=" * 80)
            content.append(f"ИТЕРАЦИЯ {iteration}")
            content.append("=" * 80)
            content.append("")
            
            # Запрос
            request = iteration_data.get("request", "")
            if request:
                content.append("-" * 80)
                content.append("ЗАПРОС К GEMINI:")
                content.append("-" * 80)
                content.append(request)
                content.append("")
            
            # Ответ модели
            response = iteration_data.get("response", "")
            if response:
                content.append("-" * 80)
                content.append("ОТВЕТ ОТ GEMINI:")
                content.append("-" * 80)
                content.append(response)
                content.append("")
            
            # Вызовы функций
            function_calls = iteration_data.get("function_calls", [])
            if function_calls:
                content.append("-" * 80)
                content.append("ВЫЗОВЫ ФУНКЦИЙ:")
                content.append("-" * 80)
                for fc in function_calls:
                    function_name = fc.get("name", "unknown")
                    function_args = fc.get("args", {})
                    function_result = fc.get("result", "")
                    
                    content.append(f"\n📞 Функция: {function_name}")
                    content.append(f"   Аргументы: {function_args}")
                    content.append(f"   Результат:")
                    content.append(f"   {function_result}")
                content.append("")
            
            # Финальный ответ
            final_answer = iteration_data.get("final_answer", "")
            if final_answer:
                content.append("-" * 80)
                content.append("✅ ФИНАЛЬНЫЙ ОТВЕТ ПОЛЬЗОВАТЕЛЮ:")
                content.append("-" * 80)
                content.append(final_answer)
                content.append("")
        
        content.append("=" * 80)
        
        # Сохраняем в файл
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        
        print(f"   📝 Сохранен Function Calling цикл: {filename}")
    
    def _make_json_serializable(self, obj):
        """
        Преобразует произвольные объекты (Part, FunctionResponse и т.п.) в сериализуемый словарь.
        Используется для логирования сырых запросов к провайдерам.
        """
        try:
            import google.ai.generativelanguage as protos  # type: ignore
        except Exception:
            protos = None  # не критично для сериализации
        
        # Примитивы
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        # Списки/кортежи
        if isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(x) for x in obj]
        # Словари
        if isinstance(obj, dict):
            return {str(k): self._make_json_serializable(v) for k, v in obj.items()}
        
        # Объекты Gemini Parts
        text = getattr(obj, 'text', None)
        if text is not None:
            return {"type": "text_part", "text": text}
        
        function_call = getattr(obj, 'function_call', None)
        if function_call is not None:
            try:
                args = dict(getattr(function_call, 'args', {}))
            except Exception:
                args = {}
            return {"type": "function_call", "name": getattr(function_call, 'name', ''), "args": args}
        
        function_response = getattr(obj, 'function_response', None)
        if function_response is not None:
            return {
                "type": "function_response",
                "name": getattr(function_response, 'name', ''),
                "response": getattr(function_response, 'response', {})
            }
        
        # Фоллбек — строковое представление
        try:
            return str(obj)
        except Exception:
            return "<unserializable>"

    def log_provider_call(self, provider: str, history, message) -> None:
        """
        Логирует сырой запрос, отправляемый провайдеру (Gemini/Yandex): полная history и message.
        """
        self._request_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._request_counter:04d}_{timestamp}_{provider.lower()}_raw_request.json"
        filepath = self.debug_dir / filename
        
        try:
            import json
            payload = {
                "provider": provider,
                "history": self._make_json_serializable(history),
                "message": self._make_json_serializable(message)
            }
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"   📦 Сохранен сырой запрос провайдеру: {filename}")
        except Exception as e:
            print(f"[DEBUG LOGGER] Не удалось сохранить сырой запрос: {e}")
    
    def log_simple_dialog(
        self,
        user_id: int,
        user_message: str,
        system_prompt: str,
        dialog_history: List[Dict],
        gemini_response: str
    ) -> None:
        """
        Сохраняет простой диалог (без Function Calling) в один файл.
        
        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            system_prompt: Системный промпт
            dialog_history: История диалога
            gemini_response: Ответ от Gemini
        """
        self._request_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._request_counter:04d}_{timestamp}_simple_dialog.txt"
        filepath = self.debug_dir / filename
        
        # Формируем содержимое файла
        content = []
        content.append("=" * 80)
        content.append(f"ПРОСТОЙ ДИАЛОГ №{self._request_counter}")
        content.append(f"Пользователь ID: {user_id}")
        content.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("=" * 80)
        content.append("")
        
        # Системный промпт
        if system_prompt:
            content.append("-" * 80)
            content.append("СИСТЕМНЫЙ ПРОМПТ:")
            content.append("-" * 80)
            content.append(system_prompt)
            content.append("")
        
        # История диалога
        if dialog_history:
            content.append("-" * 80)
            content.append(f"ИСТОРИЯ ДИАЛОГА ({len(dialog_history)} сообщений):")
            content.append("-" * 80)
            for i, msg in enumerate(dialog_history, 1):
                role = msg.get("role", "unknown")
                parts = msg.get("parts", [])
                text_content = ""
                for part in parts:
                    if isinstance(part, dict) and "text" in part:
                        text_content += part["text"]
                    elif hasattr(part, 'text'):
                        text_content += part.text
                
                content.append(f"\n[{i}] {role.upper()}:")
                content.append(text_content)
            content.append("")
        
        # Новое сообщение пользователя
        content.append("-" * 80)
        content.append("НОВОЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ:")
        content.append("-" * 80)
        content.append(user_message)
        content.append("")
        
        # Ответ от Gemini
        content.append("-" * 80)
        content.append("ОТВЕТ ОТ GEMINI:")
        content.append("-" * 80)
        content.append(gemini_response)
        content.append("")
        
        content.append("=" * 80)
        
        # Сохраняем в файл
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        
        print(f"   💬 Сохранен простой диалог: {filename}")


# Создаем единственный экземпляр логгера
gemini_debug_logger = GeminiDebugLogger()

