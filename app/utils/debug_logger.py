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


# Создаем единственный экземпляр логгера
gemini_debug_logger = GeminiDebugLogger()

