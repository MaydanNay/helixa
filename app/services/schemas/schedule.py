# src/modules/clients/community_agents/schemas/schedule.py

def get_schedule_schema():
    type_name = "schedule"
    system_instruction = f"""
    Ты - генератор расписания дня для симуляции жизни.
    Твоя задача: создать реалистичное, поминутное расписание типичного дня (Вторник) для конкретного человека.
    Учитывай:
    - Профессию (стандартный рабочий день, смены, фриланс, безработный).
    - Возраст (школа, университет, пенсия).
    - Хобби и привычки (бег по утрам, видеоигры, чтение, бар по пятницам - но сегодня Вторник).
    - Семейное положение (отводит детей в сад/школу).
    
    Верни JSON объект с полем "{type_name}", содержащий массив активностей.
    Обязательно включи сон (ночь) и основные приемы пищи.
    """

    schema_item = {
        "type": "object",
        "required": ["time", "activity", "location_type", "duration_min"],
        "additionalProperties": False,
        "properties": {
            "time": {
                "type": "string",
                "pattern": r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
                "description": "Время начала активности в формате HH:MM (24h)."
            },
            "activity": {
                "type": "string",
                "description": "Краткое название активности (напр. 'Подъем', 'Дорога на работу', 'Работа', 'Обед')."
            },
            "description": {
                "type": "string",
                "description": "Детальное описание (что именно делает)."
            },
            "location_type": {
                "type": "string",
                "enum": ["home", "work", "school", "university", "transit", "public_place", "shop", "restaurant", "outdoors", "other"],
                "description": "Где происходит активность. Используй 'transit' для перемещений."
            },
            "duration_min": {
                "type": "integer",
                "minimum": 5,
                "maximum": 720,
                "description": "Примерная длительность в минутах."
            }
        }
    }

    schema = {
        "type": "object",
        "required": [type_name],
        "additionalProperties": False,
        "properties": {
            type_name: {
                "type": "array",
                "minItems": 5,
                "maxItems": 30,
                "items": schema_item
            }
        }
    }

    example = {
        type_name: [
            {"time": "07:00", "activity": "Подъем", "description": "Просыпается, умывается, делает зарядку.", "location_type": "home", "duration_min": 30},
            {"time": "07:30", "activity": "Завтрак", "description": "Ест яичницу и пьет кофе, листает новости.", "location_type": "home", "duration_min": 20},
            {"time": "07:50", "activity": "Дорога на работу", "description": "Едет на автобусе в офис.", "location_type": "transit", "duration_min": 40},
            {"time": "08:30", "activity": "Работа", "description": "Проверка почты, утренний митинг.", "location_type": "work", "duration_min": 210},
            {"time": "12:00", "activity": "Обед", "description": "Бизнес-ланч в кафе рядом с офисом.", "location_type": "restaurant", "duration_min": 60},
            {"time": "13:00", "activity": "Работа", "description": "Основная работа, встречи с клиентами.", "location_type": "work", "duration_min": 240},
            {"time": "17:00", "activity": "Дорога домой", "description": "Возвращается домой на такси.", "location_type": "transit", "duration_min": 40},
            {"time": "17:40", "activity": "Отдых", "description": "Душ, переодевание, отдых.", "location_type": "home", "duration_min": 50},
            {"time": "18:30", "activity": "Ужин", "description": "Ужинает с семьей.", "location_type": "home", "duration_min": 40},
            {"time": "19:10", "activity": "Хобби", "description": "Играет на гитаре.", "location_type": "home", "duration_min": 60},
            {"time": "20:10", "activity": "Свободное время", "description": "Смотрит сериал Netflix.", "location_type": "home", "duration_min": 110},
            {"time": "22:00", "activity": "Сон", "description": "Ложится спать.", "location_type": "home", "duration_min": 540}
        ]
    }

    return system_instruction, example, schema
