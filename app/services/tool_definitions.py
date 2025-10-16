from google.generativeai.types import FunctionDeclaration, Tool


# Определение инструмента для получения всех услуг
get_all_services_declaration = FunctionDeclaration(
    name="get_all_services",
    description=(
        "Получает полный список всех доступных услуг салона красоты. "
        "Возвращает название услуги, цену и длительность."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)


# Определение инструмента для поиска мастеров по услуге
get_masters_for_service_declaration = FunctionDeclaration(
    name="get_masters_for_service",
    description=(
        "Находит мастеров, которые выполняют конкретную услугу. "
        "Принимает точное название услуги и возвращает список мастеров."
    ),
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": (
                    "Точное название услуги, для которой нужно найти мастеров. "
                    "Например: 'Женская стрижка', 'Мужская стрижка', 'Маникюр', 'Окрашивание волос'."
                )
            }
        },
        "required": ["service_name"]
    }
)


# Определение инструмента для получения свободных слотов
get_available_slots_declaration = FunctionDeclaration(
    name="get_available_slots",
    description=(
        "Получает список всех свободных временных интервалов для конкретной услуги на указанную дату. "
        "Возвращает СЫРЫЕ данные в формате интервалов (например, '10:15-13:45, 15:00-17:30'). "
        "Требует точное название услуги и дату в формате YYYY-MM-DD."
    ),
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": (
                    "Название услуги, для которой нужно найти свободные интервалы. "
                    "Например: 'Женская стрижка', 'Маникюр', 'Окрашивание волос'. "
                    "Точное название услуги из прайс-листа."
                )
            },
            "date": {
                "type": "string",
                "description": (
                    "Дата для поиска в формате 'YYYY-MM-DD'"
                )
            }
        },
        "required": ["service_name", "date"]
    }
)


# Определение инструмента для создания записи
create_appointment_declaration = FunctionDeclaration(
    name="create_appointment",
    description=(
        "Создает запись в календаре для мастера и услуги. "
        "Автоматически вычисляет время окончания на основе длительности услуги и создает событие в календаре."
    ),
    parameters={
        "type": "object",
        "properties": {
            "master_name": {
                "type": "string",
                "description": (
                    "Имя мастера, к которому записывается клиент. "
                    "Например: 'Анна', 'Мария', 'Елена'. "
                    "Должно точно соответствовать имени мастера из базы данных."
                )
            },
            "service_name": {
                "type": "string",
                "description": (
                    "Название услуги, на которую записывается клиент. "
                    "Например: 'Женская стрижка', 'Маникюр', 'Окрашивание волос'. "
                    "Должно точно соответствовать названию услуги из прайс-листа."
                )
            },
            "date": {
                "type": "string",
                "description": (
                    "Дата записи в формате YYYY-MM-DD (например, '2025-10-15'). "
                    "Если клиент говорит 'на завтра' или 'на понедельник', "
                    "нужно преобразовать это в конкретную дату."
                )
            },
            "time": {
                "type": "string",
                "description": (
                    "Время записи в формате HH:MM (например, '14:30', '10:00'). "
                    "Время должно быть в 24-часовом формате."
                )
            },
            "client_name": {
                "type": "string",
                "description": (
                    "Имя клиента, который записывается на услугу. "
                    "Это обязательный параметр - без имени запись не создается."
                )
            }
        },
        "required": ["master_name", "service_name", "date", "time", "client_name"]
    }
)


# Определение инструмента для просмотра записей пользователя
get_my_appointments_declaration = FunctionDeclaration(
    name="get_my_appointments",
    description=(
        "Получает все предстоящие записи пользователя в структурированном виде. "
        "Возвращает структурированные данные с ID записей для внутреннего использования."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)


# Определение инструмента для отмены записи по ID
cancel_appointment_by_id_declaration = FunctionDeclaration(
    name="cancel_appointment_by_id",
    description="Отменяет запись по её уникальному числовому ID.",
    parameters={
        "type": "object",
        "properties": {
            "appointment_id": {
                "type": "integer",
                "description": (
                    "ID записи для отмены. "
                    "Этот ID должен быть определен на основе ранее показанного списка записей клиента."
                )
            }
        },
        "required": ["appointment_id"]
    }
)


# Определение инструмента для переноса записи по ID
reschedule_appointment_by_id_declaration = FunctionDeclaration(
    name="reschedule_appointment_by_id",
    description="Переносит запись на новую дату и время по её уникальному числовому ID.",
    parameters={
        "type": "object",
        "properties": {
            "appointment_id": {
                "type": "integer",
                "description": (
                    "ID записи для переноса. "
                    "Этот ID должен быть определен на основе ранее показанного списка записей клиента."
                )
            },
            "new_date": {
                "type": "string",
                "description": (
                    "Новая дата записи в формате YYYY-MM-DD (например, '2025-10-15'). "
                    "Если клиент говорит 'на завтра' или 'на понедельник', "
                    "нужно преобразовать это в конкретную дату."
                )
            },
            "new_time": {
                "type": "string",
                "description": (
                    "Новое время записи в формате HH:MM (например, '14:30', '10:00'). "
                    "Время должно быть в 24-часовом формате."
                )
            }
        },
        "required": ["appointment_id", "new_date", "new_time"]
    }
)


# Определение инструмента для вызова менеджера
call_manager_declaration = FunctionDeclaration(
    name="call_manager",
    description=(
        "Вызывает менеджера для решения сложных вопросов. "
        "В параметре 'reason' кратко описывает причину вызова."
    ),
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": (
                    "Краткое описание причины вызова менеджера. "
                    "Например: 'Клиент недоволен качеством услуги', "
                    "'Запрос на особую скидку', 'Прямой запрос на менеджера'."
                )
            }
        },
        "required": ["reason"]
    }
)


# Определение инструмента для получения полной истории диалога
get_full_history_declaration = FunctionDeclaration(
    name="get_full_history",
    description=(
        "Получает полную историю диалога для дополнительного контекста."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)


# Разделяем инструменты на два набора согласно двухэтапной архитектуре

# Инструменты для получения информации (разведывательные) - доступны на этапе планирования
read_only_tools = [
    get_all_services_declaration,
    get_masters_for_service_declaration,
    get_available_slots_declaration,
    get_my_appointments_declaration,
    get_full_history_declaration
]

# Инструменты для изменения данных (исполнительные) - доступны только на этапе синтеза
write_tools = [
    create_appointment_declaration,
    cancel_appointment_by_id_declaration,
    reschedule_appointment_by_id_declaration,
    call_manager_declaration
]

# Создаем Tool объекты для каждого набора
read_only_tools_obj = Tool(function_declarations=read_only_tools)
write_tools_obj = Tool(function_declarations=write_tools)

# Общий Tool объект для обратной совместимости (содержит все инструменты)
salon_tools = Tool(
    function_declarations=read_only_tools + write_tools
)

# Словарь всех инструментов для удобного доступа по имени
all_tools_dict = {
    tool.name: tool for tool in read_only_tools + write_tools
}

