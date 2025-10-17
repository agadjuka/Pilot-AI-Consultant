import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import logging

from app.core.config import settings
from app.services.s3_logger_service import S3LoggerService

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


class DialogueTracer:
    """
    Мощный сервис трассировки диалогов.
    Собирает всю хронологию обработки одного сообщения в единый Markdown-файл.
    """
    
    def __init__(self, user_id: int, user_message: str, debug_dir: str = "debug_logs"):
        """
        Инициализирует трейсер для одного диалога.
        
        Args:
            user_id: ID пользователя
            user_message: Исходное сообщение пользователя
            debug_dir: Папка для сохранения логов (по умолчанию debug_logs)
        """
        self.user_id = user_id
        self.user_message = user_message
        self.debug_dir = Path(debug_dir)
        self.trace_events: List[Dict[str, Any]] = []
        
        # Создаем уникальное имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{timestamp}_user{user_id}.md"
        self.filepath = self.debug_dir / self.filename
        
        # Добавляем начальное событие
        self.add_event(
            "🚀 Начало обработки сообщения",
            f"**Пользователь ID:** {user_id}\n**Сообщение:** {user_message}\n**Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    def add_event(self, title: str, content: Union[str, Dict, List], is_json: bool = False) -> None:
        """
        Добавляет новое событие в трассировку.
        
        Args:
            title: Заголовок события
            content: Содержимое события (строка, словарь или список)
            is_json: Если True, содержимое будет отформатировано как JSON
        """
        # Форматируем содержимое в зависимости от типа
        if isinstance(content, (dict, list)):
            # Если это словарь или список, форматируем как JSON
            formatted_content = json.dumps(content, indent=2, ensure_ascii=False)
            formatted_content = f"```json\n{formatted_content}\n```"
        else:
            # Если это строка, оборачиваем в блок цитаты
            formatted_content = f"> {content}"
        
        event = {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],  # Миллисекунды
            "title": title,
            "content": formatted_content,
            "is_json": is_json
        }
        self.trace_events.append(event)
    
    def save_trace(self) -> None:
        """
        Сохраняет всю трассировку в зависимости от режима логирования.
        Поддерживает как локальное сохранение, так и загрузку в S3.
        """
        try:
            # Формируем содержимое файла
            content_lines = []
            
            # Заголовок файла
            content_lines.append(f"# Трассировка диалога - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content_lines.append("")
            content_lines.append(f"**Пользователь ID:** {self.user_id}")
            content_lines.append(f"**Исходное сообщение:** {self.user_message}")
            content_lines.append("")
            content_lines.append("---")
            content_lines.append("")
            
            # Добавляем все события
            for i, event in enumerate(self.trace_events, 1):
                content_lines.append(f"## {i}. {event['title']}")
                content_lines.append("")
                content_lines.append(f"**Время:** {event['timestamp']}")
                content_lines.append("")
                
                # Содержимое уже отформатировано в add_event
                content_lines.append(event['content'])
                
                content_lines.append("")
                content_lines.append("---")
                content_lines.append("")
            
            # Финальная информация
            content_lines.append("## ✅ Завершение трассировки")
            content_lines.append("")
            content_lines.append(f"**Всего событий:** {len(self.trace_events)}")
            content_lines.append(f"**Время завершения:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Получаем содержимое файла как строку
            file_content = "\n".join(content_lines)
            
            # Выбираем способ сохранения в зависимости от режима
            if settings.LOG_MODE == "cloud":
                self._save_to_cloud(file_content)
            else:
                self._save_to_local(file_content)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении трассировки: {e}")
    
    def _save_to_local(self, file_content: str) -> None:
        """
        Сохраняет трассировку в локальный файл.
        
        Args:
            file_content: Содержимое файла для сохранения
        """
        try:
            # Создаем папку если не существует
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем файл локально
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(file_content)
            
            logger.info(f"✅ Трассировка сохранена локально: {self.filepath}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при локальном сохранении трассировки: {e}")
            raise
    
    def _save_to_cloud(self, file_content: str) -> None:
        """
        Сохраняет трассировку в S3-хранилище.
        
        Args:
            file_content: Содержимое файла для сохранения
        """
        try:
            # Создаем экземпляр S3LoggerService
            s3_logger = S3LoggerService()
            
            # Загружаем лог в S3
            success = s3_logger.upload_log(file_content, self.filename)
            
            if success:
                logger.info(f"✅ Трассировка загружена в S3: {self.filename}")
            else:
                logger.error(f"❌ Не удалось загрузить трассировку в S3: {self.filename}")
                # В случае ошибки S3, сохраняем локально как fallback
                logger.warning("🔄 Переключаемся на локальное сохранение как fallback")
                self._save_to_local(file_content)
                
        except Exception as e:
            logger.error(f"❌ Ошибка при облачном сохранении трассировки: {e}")
            # В случае ошибки S3, сохраняем локально как fallback
            logger.warning("🔄 Переключаемся на локальное сохранение как fallback")
            try:
                self._save_to_local(file_content)
            except Exception as fallback_error:
                logger.error(f"❌ Критическая ошибка: не удалось сохранить ни в S3, ни локально: {fallback_error}")
                raise


def clear_debug_logs(debug_dir: str = "debug_logs") -> None:
    """
    Очищает папку с логами при старте приложения.
    Удаляет все файлы и папку, затем создает пустую папку заново.
    В облачном режиме эта функция не выполняет никаких действий.
    
    Args:
        debug_dir: Папка для очистки (по умолчанию debug_logs)
    """
    # В облачном режиме не очищаем локальную папку
    if settings.LOG_MODE == "cloud":
        logger.info("🌤️ Облачный режим логирования: пропускаем очистку локальной папки")
        return
    
    debug_path = Path(debug_dir)
    
    if debug_path.exists():
        shutil.rmtree(debug_path)
        logger.info(f"🗑️ Папка {debug_dir} очищена")
    
    debug_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Папка {debug_dir} создана")
