"""
Скрипт для автоматического анализа диалогов и генерации dialogue_patterns.json.

Этот скрипт читает сырые диалоги из папки source_dialogues/, анализирует их
с помощью Gemini AI, извлекает паттерны диалогов и сохраняет результат
в структурированном JSON-файле.
"""

import asyncio
import json
import os
import glob
from typing import List, Dict, Any
from pathlib import Path

import google.generativeai as genai
from google.oauth2 import service_account
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv(os.getenv("ENV_FILE", ".env"))


class DialogueAnalyzer:
    """AI-аналитик для анализа диалогов и извлечения паттернов."""
    
    def __init__(self):
        """Инициализирует клиент Gemini для анализа диалогов."""
        self._setup_gemini_client()
        self._model = genai.GenerativeModel("gemini-2.5-flash")
    
    def _setup_gemini_client(self):
        """Настраивает клиент Gemini с учетными данными."""
        credentials = self._load_credentials()
        genai.configure(credentials=credentials)
    
    def _load_credentials(self) -> service_account.Credentials:
        """
        Загружает credentials для Google Cloud.
        Использует ту же логику, что и в GeminiService.
        """
        # Вариант 1: JSON напрямую в переменной окружения
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if credentials_json:
            credentials_info = json.loads(credentials_json)
            return service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=["https://www.googleapis.com/auth/generative-language"]
            )
        
        # Вариант 2: Путь к файлу credentials или JSON строка
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path:
            if os.path.isfile(credentials_path):
                return service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=["https://www.googleapis.com/auth/generative-language"]
                )
            else:
                try:
                    credentials_info = json.loads(credentials_path)
                    return service_account.Credentials.from_service_account_info(
                        credentials_info,
                        scopes=["https://www.googleapis.com/auth/generative-language"]
                    )
                except json.JSONDecodeError:
                    raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS не является валидным путем или JSON: {credentials_path}")
        
        # Вариант 3: Application Default Credentials
        import google.auth
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/generative-language"]
        )
        return credentials
    
    async def extract_patterns_from_dialogue(self, dialogue_text: str) -> List[Dict[str, Any]]:
        """
        Извлекает паттерны диалога с помощью Gemini AI.
        
        Args:
            dialogue_text: Текст диалога для анализа
            
        Returns:
            Список словарей с паттернами диалога
        """
        prompt = f"""
Твоя задача — выступить в роли опытного бизнес-аналитика и проанализировать диалог менеджера салона красоты с клиентом. Твоя цель — извлечь из него только **самые качественные, универсальные и переиспользуемые "Паттерны Диалога"**, которые можно использовать для обучения AI-ассистента.

**Игнорируй тривиальные, специфичные или неудачные части диалога.** Сосредоточься только на тех моментах, где менеджер демонстрирует **образцовое поведение**.

Один диалог может содержать НЕСКОЛЬКО таких образцовых паттернов.

Для каждого найденного **качественного** паттерна ты должен определить:
1.  `stage`: Короткий, уникальный ID стадии диалога на английском. Используй один из следующих: `greeting` (приветствие/начало диалога), `service_inquiry` (вопрос об услугах), `price_inquiry` (вопрос о цене), `availability_check` (проверка свободного времени), `booking_confirmation` (подтверждение записи), `rescheduling` (перенос записи), `cancellation` (отмена записи), `handle_issue` (решение проблемы клиента), `logistics` (вопросы адреса/парковки). **Если паттерн не подходит ни под одну из этих стадий, проигнорируй его.**
2.  `principles`: JSON-массив из 1-2 ключевых принципов, которые можно извлечь из **образцового** ответа менеджера. Принципы должны быть сформулированы как универсальные инструкции.
3.  `examples`: JSON-массив, содержащий **только один, самый лучший и показательный** пример реплик "вопрос-ответ" с этой стадии в формате `{{"user": "...", "assistant": "..."}}`. Пример должен быть очищен от лишних деталей и легко адаптируем.
4.  `proactive_params`: JSON-объект, описывающий, какие параметры для инструментов бот может определить самостоятельно на этой стадии. Формат: `{{"tool_name": {{"param_name": "описание логики определения параметра"}}}}`. Например: `{{"get_available_slots": {{"date": "Если пользователь просит 'ближайшее' или 'скорее', используй 'сегодня' в качестве даты по умолчанию"}}}}`. Если для стадии нет параметров для самостоятельного определения, используй пустой объект `{{}}`.

Проанализируй следующий диалог:
---
{dialogue_text}
---

Выдай результат в формате JSON-массива объектов. Если в диалоге нет ни одного образцового паттерна, верни пустой массив `[]`.
"""
        
        try:
            # Используем asyncio для выполнения синхронного вызова
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._model.generate_content(prompt)
            )
            
            # Получаем текст ответа
            response_text = response.text.strip()
            
            # Пытаемся найти JSON в ответе
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start != -1 and json_end != 0:
                json_text = response_text[json_start:json_end]
                try:
                    patterns = json.loads(json_text)
                    # Валидируем структуру паттернов
                    validated_patterns = []
                    for pattern in patterns:
                        if isinstance(pattern, dict) and 'stage' in pattern:
                            validated_pattern = {
                                'stage': pattern.get('stage', ''),
                                'principles': pattern.get('principles', []),
                                'examples': pattern.get('examples', []),
                                'proactive_params': pattern.get('proactive_params', {})
                            }
                            # Фильтруем некорректные примеры
                            if isinstance(validated_pattern['examples'], list):
                                validated_pattern['examples'] = [
                                    ex for ex in validated_pattern['examples'] 
                                    if isinstance(ex, dict) and 'user' in ex and 'assistant' in ex
                                ]
                            validated_patterns.append(validated_pattern)
                    return validated_patterns
                except json.JSONDecodeError as json_err:
                    print(f"Ошибка парсинга JSON: {json_err}")
                    print(f"Проблемный JSON: {json_text}")
                    return []
            else:
                print(f"Не удалось найти JSON в ответе: {response_text}")
                return []
                
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}")
            print(f"Ответ модели: {response_text}")
            return []
        except Exception as e:
            print(f"Ошибка при анализе диалога: {e}")
            return []
    
    def clean_dialogue_text(self, text: str) -> str:
        """
        Очищает текст диалога от временных меток и форматирует для анализа.
        
        Args:
            text: Исходный текст диалога
            
        Returns:
            Очищенный текст диалога
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Убираем временные метки WhatsApp/Telegram формата
            # [5/26/25, 1:37:26 PM] ~Daria: сообщение
            if ']' in line and ':' in line:
                # Ищем паттерн: [время] имя: сообщение
                # Находим позицию последнего ': '
                colon_pos = line.rfind(': ')
                if colon_pos != -1:
                    # Берем все после последнего ': '
                    message_part = line[colon_pos + 2:]
                    
                    # Берем часть до ': ' и извлекаем имя отправителя
                    before_colon = line[:colon_pos]
                    # Ищем имя после последнего '] '
                    bracket_pos = before_colon.rfind('] ')
                    if bracket_pos != -1:
                        sender_name = before_colon[bracket_pos + 2:].replace('~', '').strip()
                        
                        # Определяем, кто говорит (клиент или менеджер)
                        if any(name in sender_name.lower() for name in ['daria', 'менеджер', 'администратор']):
                            # Это менеджер
                            cleaned_lines.append(f"Менеджер: {message_part}")
                        else:
                            # Это клиент
                            cleaned_lines.append(f"Клиент: {message_part}")
            else:
                # Если строка не содержит временных меток, добавляем как есть
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def load_dialogues_from_directory(self, directory_path: str) -> List[str]:
        """
        Загружает все текстовые файлы с диалогами из указанной директории.
        
        Args:
            directory_path: Путь к директории с диалогами
            
        Returns:
            Список текстов диалогов
        """
        dialogues = []
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"Директория {directory_path} не существует")
            return dialogues
        
        # Ищем все текстовые файлы
        text_files = glob.glob(str(directory / "*.txt"))
        
        for file_path in text_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        # Очищаем диалог от временных меток
                        cleaned_content = self.clean_dialogue_text(content)
                        dialogues.append(cleaned_content)
                        print(f"Загружен диалог из {file_path}")
            except Exception as e:
                print(f"Ошибка при загрузке файла {file_path}: {e}")
        
        return dialogues
    
    def merge_patterns(self, all_patterns: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Объединяет паттерны по стадиям, удаляя дубликаты.
        
        Args:
            all_patterns: Словарь с паттернами по стадиям
            
        Returns:
            Объединенный словарь паттернов
        """
        merged_patterns = {}
        
        for stage, pattern_data in all_patterns.items():
            # Объединяем принципы и удаляем дубликаты
            all_principles = []
            for principles in pattern_data.get('principles', []):
                all_principles.extend(principles)
            
            unique_principles = list(dict.fromkeys(all_principles))  # Сохраняем порядок
            
            # Объединяем примеры
            all_examples = []
            for examples in pattern_data.get('examples', []):
                all_examples.extend(examples)
            
            # Объединяем proactive_params
            merged_proactive_params = {}
            for proactive_params in pattern_data.get('proactive_params', []):
                if isinstance(proactive_params, dict):
                    merged_proactive_params.update(proactive_params)
            
            merged_patterns[stage] = {
                'principles': unique_principles,
                'examples': all_examples,
                'proactive_params': merged_proactive_params
            }
        
        return merged_patterns
    
    async def analyze_all_dialogues(self, source_directory: str = "source_dialogues") -> Dict[str, Dict[str, Any]]:
        """
        Анализирует все диалоги и возвращает объединенные паттерны.
        
        Args:
            source_directory: Путь к директории с исходными диалогами
            
        Returns:
            Словарь с объединенными паттернами по стадиям
        """
        print("Загружаем диалоги из директории...")
        dialogues = self.load_dialogues_from_directory(source_directory)
        
        if not dialogues:
            print("Диалоги не найдены!")
            return {}
        
        print(f"Найдено {len(dialogues)} диалогов для анализа")
        
        all_patterns = {}
        
        # Асинхронно обрабатываем каждый диалог
        tasks = []
        for i, dialogue in enumerate(dialogues):
            task = self.process_dialogue(dialogue, i)
            tasks.append(task)
        
        print("Начинаем анализ диалогов...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем результаты
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Ошибка при обработке диалога {i}: {result}")
                continue
            
            patterns = result
            for pattern in patterns:
                stage = pattern.get('stage')
                if not stage:
                    continue
                
                if stage not in all_patterns:
                    all_patterns[stage] = {
                        'principles': [],
                        'examples': [],
                        'proactive_params': []
                    }
                
                # Добавляем принципы, примеры и proactive_params
                all_patterns[stage]['principles'].append(pattern.get('principles', []))
                all_patterns[stage]['examples'].append(pattern.get('examples', []))
                all_patterns[stage]['proactive_params'].append(pattern.get('proactive_params', {}))
        
        # Объединяем паттерны
        merged_patterns = self.merge_patterns(all_patterns)
        
        print(f"Найдено {len(merged_patterns)} уникальных стадий диалога")
        return merged_patterns
    
    async def process_dialogue(self, dialogue: str, index: int) -> List[Dict[str, Any]]:
        """
        Обрабатывает один диалог и возвращает найденные паттерны.
        
        Args:
            dialogue: Текст диалога
            index: Индекс диалога для логирования
            
        Returns:
            Список найденных паттернов
        """
        print(f"Анализируем диалог {index + 1}...")
        patterns = await self.extract_patterns_from_dialogue(dialogue)
        print(f"Диалог {index + 1}: найдено {len(patterns)} паттернов")
        return patterns
    
    def save_patterns_to_file(self, patterns: Dict[str, Dict[str, Any]], output_file: str = "dialogue_patterns.json"):
        """
        Сохраняет паттерны в JSON-файл с красивым форматированием.
        
        Args:
            patterns: Словарь с паттернами
            output_file: Путь к выходному файлу
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(patterns, f, ensure_ascii=False, indent=2)
            print(f"Паттерны сохранены в файл {output_file}")
        except Exception as e:
            print(f"Ошибка при сохранении файла {output_file}: {e}")


async def main():
    """Основная функция скрипта."""
    print("=== AI-Аналитик диалогов ===")
    print("Запускаем анализ диалогов и генерацию паттернов...")
    
    analyzer = DialogueAnalyzer()
    
    # Анализируем все диалоги
    patterns = await analyzer.analyze_all_dialogues()
    
    if patterns:
        # Сохраняем результат
        analyzer.save_patterns_to_file(patterns)
        
        # Выводим статистику
        print("\n=== Статистика анализа ===")
        for stage, data in patterns.items():
            principles_count = len(data.get('principles', []))
            examples_count = len(data.get('examples', []))
            proactive_params_count = len(data.get('proactive_params', {}))
            print(f"{stage}: {principles_count} принципов, {examples_count} примеров, {proactive_params_count} proactive параметров")
    else:
        print("Паттерны не найдены. Проверьте наличие диалогов в папке source_dialogues/")


if __name__ == "__main__":
    asyncio.run(main())
