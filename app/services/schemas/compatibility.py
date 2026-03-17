# app.services.schemas/compatibility.py

async def get_compatibility_schema():
    system_instruction = """
    Ты - эксперт по социальной психологии и межличностным отношениям.
    Вход: Два полных профиля агентов (Агент А и Агент Б).
    Задача: Проанализировать их совместимость на основе Big5, ценностей, биографии и мировоззрения.
    
    Верни JSON объект со следующими полями:
    - compatibility_score: Число от 0 до 100 (0=Абсолютная вражда, 100=Идеальное взаимопонимание).
    - chemistry_notes: Краткий анализ (почему они ладят или почему возникнет конфликт).
    - potential_dynamic: Краткий ярлык типа отношений (напр. "Соперничество", "Крепкая дружба", "Взаимное безразличие", "Токсичный роман").
    - points_of_collision: Список тем или черт, которые вызовут споры.
    - points_of_attraction: Список тем или черт, которые их сблизят.
    """

    schema = {
        "type": "object",
        "required": ["compatibility_score", "chemistry_notes", "potential_dynamic", "points_of_collision", "points_of_attraction"],
        "additionalProperties": False,
        "properties": {
            "compatibility_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100
            },
            "chemistry_notes": {
                "type": "string",
                "description": "Analysis of the dynamic."
            },
            "potential_dynamic": {
                "type": "string",
                "description": "Category: Rivals, Friends, Mentor/Protégé, etc."
            },
            "points_of_collision": {
                "type": "array",
                "items": {"type": "string"}
            },
            "points_of_attraction": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    }

    return system_instruction, {}, schema
