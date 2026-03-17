import json

async def get_core_health_schema(count, profile_context):
    type = "core_health"
    system_instruction = f"""
        Ты - генератор физического здоровья.
        Вход: Demographics + Psychology.
        Задача: Сгенерировать здоровье.
        Возвращай ровно {count} объектов внутри поля "{type}".
        
        ВАЖНО:
        - СТРОГО генерируй ВСЕ ТРЕБУЕМЫЕ ПОЛЯ: "weight_kg", "height_cm", "bmi", "bmi_category", "disabilities", "allergies", "chronic_conditions", "healthy_habits", "bad_habits", "chronotype", "sleep_need_hours", "dietary_principles".
        - НЕ ВЫДУМЫВАЙ новые поля (например, blood_pressure, blood_type, sleep_pattern). Возвращай ТОЛЬКО те поля, что есть в примере!
        - Для полей с фиксированным списком значений (Enum) — используй ТОЛЬКО разрешенные значения.
        - **Никогда не используй null внутри списков (массивов)**. Если данных нет, возвращай пустой список [].
        ОЧЕНЬ ВАЖНО: Возвращай ровно {count} объектов внутри поля "{type}". НЕ ОБОРАЧИВАЙ внутренние объекты в дополнительные ключи (например, "health"). Твои объекты должны напрямую содержать поля "weight_kg", "bmi" и т.д.
    """

    schema = {
        "type": "object",
        "required": [
            "weight_kg", "bmi", "bmi_category", "disabilities",
            "allergies", "chronic_conditions", "healthy_habits", "bad_habits",
            "chronotype", "sleep_need_hours", "dietary_principles"
        ],
        "additionalProperties": True,
        "properties": {
            "weight_kg": {"type": "number", "minimum": 30, "maximum": 200},
            "height_cm": {"type": "number", "minimum": 100, "maximum": 250},
            "energy_cycle": {"type": "array", "items": {"type": "number"}},
            "psychology_alignment": {"type": "string"},
            "bmi": {"type": "number"},
            "bmi_category": {"type": "string"},
            "chronotype": {"type": "string", "enum": ["lark", "owl", "hummingbird", "Neutral"], "description": "Strictly choose from list."},
            "sleep_need_hours": {"type": "number"},
            "dietary_principles": {"type": "array", "items": {"type": "string"}},
            "disabilities": {"type": "array", "items": {"type": "string"}},
            "allergies": {"type": "array", "items": {"type": "string"}},
            "chronic_conditions": {"type": "array", "items": {"type": "string"}},
            "healthy_habits": {"type": "array", "items": {"type": "string"}},
            "bad_habits": {"type": "array", "items": {"type": "string"}},
        }
    }

    wrapper_schema = {
        "type": "object",
        "required": [type],
        "properties": {
            type: {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema
            }
        }
    }
    
    example = {
        "core_health": [
            {
                "weight_kg": 78,
                "bmi": 23.5,
                "bmi_category": "Normal weight",
                "chronotype": "owl",
                "sleep_need_hours": 7.5,
                "dietary_principles": ["Intermittent Fasting", "Low Sugar"],
                "disabilities": [],
                "allergies": ["Peanuts", "Dust"],
                "chronic_conditions": [],
                "healthy_habits": ["Running", "Meditation"],
                "bad_habits": ["Late night snacking", "Caffeine addiction"]
            }
        ]
    }

    return system_instruction, example, wrapper_schema
