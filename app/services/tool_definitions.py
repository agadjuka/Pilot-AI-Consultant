from google.generativeai.types import FunctionDeclaration, Tool


# Определение инструмента для получения всех услуг
get_all_services_declaration = FunctionDeclaration(
    name="get_all_services",
    description=(
        "Получает полный список всех доступных услуг салона красоты. "
        "Используй эту функцию, когда клиент спрашивает о том, какие услуги доступны, "
        "что можно сделать в салоне, или когда нужно показать прайс-лист. "
        "Функция возвращает название услуги, цену и длительность."
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
        "Используй эту функцию, когда клиент уже определился с услугой и хочет узнать, "
        "какие мастера могут её выполнить. Например, если клиент сказал 'Я хочу женскую стрижку' "
        "или 'Покажи мастеров для маникюра'. Функция принимает точное название услуги."
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
        "Получает список свободных временных слотов для конкретного мастера на указанную дату. "
        "Используй эту функцию, когда клиент выбрал мастера и хочет узнать, в какое время можно записаться. "
        "Например, если клиент говорит 'Когда свободна Анна?' или 'Покажи свободное время на завтра'. "
        "ВНИМАНИЕ: Это пока заглушка, но работает как реальная функция."
    ),
    parameters={
        "type": "object",
        "properties": {
            "master_name": {
                "type": "string",
                "description": (
                    "Имя мастера, для которого нужно получить свободные слоты. "
                    "Например: 'Анна', 'Мария', 'Елена'."
                )
            },
            "date": {
                "type": "string",
                "description": (
                    "Дата в формате YYYY-MM-DD (например, '2025-10-15'). "
                    "Если клиент говорит 'на завтра' или 'на понедельник', "
                    "нужно преобразовать это в конкретную дату."
                )
            }
        },
        "required": ["master_name", "date"]
    }
)


# Создаем Tool объект, содержащий все наши функции
salon_tools = Tool(
    function_declarations=[
        get_all_services_declaration,
        get_masters_for_service_declaration,
        get_available_slots_declaration
    ]
)

